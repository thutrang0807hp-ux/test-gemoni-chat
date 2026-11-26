import { readFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

const gemini = "https://gemini.google.com";
const responses = "model-response";
const mediaHosts = new Set(["gemini.google.com", "lh3.google.com", "lh3.googleusercontent.com"]);
const formats = ["image/png", "image/jpeg", "image/webp"];

export function imageSource(value, identified, width, height) {
  if (width < 256 || height < 256) return false;
  let url;
  try { url = new URL(value); } catch { return false; }
  if (url.protocol === "blob:") return identified && url.origin === gemini;
  if (url.protocol === "data:") return identified && /^data:image\/(png|jpeg|webp);base64,/i.test(value);
  return url.protocol === "https:" && !url.port && !url.username && !url.password &&
    mediaHosts.has(url.hostname) && (identified || /^\/(?:gg|gg-dl|rd-gg)(?:\/|$)/.test(url.pathname));
}

export function editInstruction(prompt) {
  return "Chỉnh trực tiếp ảnh tham chiếu 1 (người mẫu) bằng trang phục trong ảnh tham chiếu 2 (bộ đồ). " +
    "Trả về ảnh mới. Giữ nguyên nhận diện gương mặt, tư thế và nền của ảnh 1 trừ khi mô tả yêu cầu khác. " +
    "Giữ đúng màu, phom và họa tiết trang phục từ ảnh 2.\n\n" + prompt;
}

async function editorFor(page) {
  const editor = page.locator('rich-textarea [contenteditable="true"]:visible, .ql-editor[contenteditable="true"]:visible, [contenteditable="true"][role="textbox"]:visible').first();
  try { await editor.waitFor({state:"visible", timeout: 22000}); }
  catch { throw new Error("Không thấy ô chat. Bấm Kết nối Gemini và đăng nhập trong cửa sổ của app."); }
  return editor;
}

async function submit(page, editor, prompt) {
  const count = await page.locator(responses).count();
  await editor.fill(prompt);
  const send = page.getByRole("button", {name:/^(send( message| prompt)?|gửi( tin nhắn| lời nhắc)?)$/i})
    .or(page.locator("button.send-button")).first();
  await send.click({timeout:12000});
  return page.locator(responses).nth(count);
}

async function waitForText(page, answer) {
  await answer.waitFor({state:"visible", timeout:75000});
  const stop = page.getByRole("button", {name:/^(stop|dừng|ngừng)(\b|\s)/i}).first();
  const end = Date.now()+45000;
  let last = "", changed = Date.now();
  while (Date.now() < end) {
    const message = answer.locator("message-content, .markdown").first();
    const text = (await (await message.count() ? message : answer).innerText({timeout:4000})).trim();
    if (text !== last) { last = text; changed = Date.now(); }
    if (text && !(await stop.isVisible()) && Date.now() - changed >= 2500) return text;
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  throw new Error("Gemini chưa viết xong prompt.");
}

async function uploadPair(page, paths) {
  // Standards-based file inputs or the same upload dialog available to the user.
  const direct = page.locator('input[type="file"][multiple]').first();
  if (await direct.count()) {
    await direct.setInputFiles(paths, {timeout:10000});
  } else {
    const attachments = page.getByRole("button", {name:/add files|upload|attach|thêm tệp|tải tệp|đính kèm/i}).first();
    await attachments.click({timeout:10000});
    const upload = page.getByRole("menuitem", {name:/upload|tải (tệp|lên)/i})
      .or(page.getByRole("button", {name:/^upload files$|^tải tệp lên$/i})).first();
    const [chooser] = await Promise.all([
      page.waitForEvent("filechooser", {timeout:12000}),
      upload.click({timeout:12000}),
    ]);
    if (!chooser.isMultiple()) throw new Error("Gemini không cho tải hai ảnh cùng lúc trong giao diện này.");
    await chooser.setFiles(paths);
  }
  for (const name of paths.map(path => path.split(/[\\/]/).at(-1))) {
    const attachment = page.getByText(name, {exact:true})
      .or(page.getByRole("img", {name, exact:true}))
      .or(page.getByRole("button", {name:new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i")})).first();
    try { await attachment.waitFor({state:"visible",timeout:22000}); }
    catch { throw new Error("Gemini chưa xác nhận đủ hai ảnh đính kèm. Studio chưa gửi lệnh tạo."); }
  }
}

async function waitForImage(response) {
  await response.waitFor({state:"visible",timeout:90000});
  const end = Date.now() + 120000;
  while (Date.now() < end) {
    const images = await response.locator("img").evaluateAll(nodes => nodes.map(image => ({
      url: image.currentSrc,
      identified: Boolean(image.closest("generated-image, generated-image-container, single-image, image-generation")),
      width: image.naturalWidth, height: image.naturalHeight,
    })));
    const image = images.find(item => imageSource(item.url, item.identified, item.width, item.height));
    if (image) return image;
    await new Promise(resolve => setTimeout(resolve, 600));
  }
  throw new Error("Gemini chưa trả ảnh mới cho lượt này. Có thể yêu cầu chỉ nhận phản hồi văn bản.");
}

async function saveResult(context, page, image, output) {
  let bytes, type;
  if (image.url.startsWith("blob:") || image.url.startsWith("data:")) {
    const result = await page.evaluate(async url => {
      const response = await fetch(url, {signal: AbortSignal.timeout(15000)});
      const type = response.headers.get("content-type")?.split(";")[0];
      const blob = await response.blob();
      if (blob.size > 24_000_000) throw Error("Ảnh quá lớn.");
      return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve({type, data: reader.result.split(",")[1]});
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    }, image.url);
    bytes = Buffer.from(result.data, "base64");
    type = result.type;
  } else {
    const request = await context.request.get(image.url, {
      maxRedirects:0, timeout:20000, headers:{referer:gemini+"/"},
    });
    try {
      if (!request.ok()) throw new Error("Gemini hiện ảnh nhưng Studio chưa tải được file.");
      type = request.headers()["content-type"]?.split(";")[0];
      bytes = await request.body();
    } finally {
      await request.dispose();
    }
  }
  if (!formats.includes(type) || !bytes.length || bytes.length > 24_000_000) {
    throw new Error("File ảnh không hợp lệ hoặc vượt quá 24 MB.");
  }
  await writeFile(output, bytes, {flag:"wx"});
}

async function run(port, request) {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:" + port, {timeout:12000});
  try {
    if (request.action === "shutdown") {
      const session = await browser.newBrowserCDPSession();
      await session.send("Browser.close").catch(() => {});
      return {};
    }
    const context = browser.contexts()[0];
    if (!context) throw new Error("Không tìm thấy hồ sơ Chrome của app.");
    const page = await context.newPage();
    try {
      await page.goto(gemini + "/app", {waitUntil:"domcontentloaded", timeout:30000});
      if (new URL(page.url()).origin !== gemini) throw new Error("Hãy hoàn tất đăng nhập bằng nút Kết nối Gemini.");
      const editor = await editorFor(page);
      if (request.action === "prompt") {
        const instruction = "Soạn một prompt tiếng Việt để chỉnh ảnh. Ảnh thứ nhất là người mẫu, ảnh thứ hai là bộ đồ. " +
          "Chỉ trả prompt. Đừng đoán màu sắc, logo hoặc chi tiết chưa cung cấp.\n\n" + request.prompt;
        return {text: await waitForText(page, await submit(page, editor, instruction))};
      }
      if (request.action !== "image" || request.paths?.length !== 2) throw new Error("Cần đúng hai ảnh tham chiếu.");
      await uploadPair(page, request.paths);
      const answer = await submit(page, editor, editInstruction(request.prompt));
      const image = await waitForImage(answer);
      await saveResult(context, page, image, request.output);
      return {saved:true};
    } finally {
      await page.close().catch(() => {});
    }
  } finally {
    await browser.close().catch(() => {});
  }
}

async function main() {
  try {
    const {port, request} = JSON.parse(readFileSync(0, "utf8"));
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Chrome chưa sẵn sàng.");
    process.stdout.write(JSON.stringify({result:await run(port, request)}));
  } catch (error) {
    const message = error.name === "TimeoutError" ? "Hết thời gian chờ Gemini." : error.message;
    process.stdout.write(JSON.stringify({error:message.split("\n")[0].slice(0,300)}));
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
