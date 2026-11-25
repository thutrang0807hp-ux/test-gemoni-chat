import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright-core";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const flowCli = fileURLToPath(new URL(
  "./node_modules/@park-sang-gwon/google-flow-mcp/dist/cli.js", import.meta.url
));

export function flowProject(value) {
  const url = new URL(value);
  if (!["https://flow.google.com", "https://labs.google"].includes(url.origin) ||
      !/\/project\/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}(?:\/|$)/i.test(url.pathname)) {
    throw new Error("Hãy mở một dự án trong Google Flow trước.");
  }
  return url.origin + url.pathname;
}

export async function useFlow(request, call) {
  return call("flow_generate_image", {
    prompt: request.prompt,
    model: request.model,
    ratio: request.ratio,
    count: 1,
    reference_images: request.references,
    project_url: flowProject(request.project),
    output_dir: request.output,
    auto_confirm: true,
  });
}

async function generation(port, request) {
  const server = new StdioClientTransport({
    command: process.execPath,
    args: [flowCli],
    stderr: "ignore",
    env: {
      ...process.env,
      FLOW_MCP_CHROME_PATH: request.state + "/studio-will-launch-browser",
      FLOW_MCP_CONFIG: request.state + "/studio-flow.json",
      FLOW_MCP_USER_DATA_DIR: request.profile,
      FLOW_MCP_CDP_PORT: String(port),
      FLOW_MCP_STATE_DIR: request.state,
      FLOW_MCP_GENERATION_TIMEOUT_MS: "240000",
      FLOW_MCP_LOG_LEVEL: "warn",
    },
  });
  const client = new Client({name: "studio-anh-gemini", version: "0.3.0"});
  try {
    await client.connect(server);
    return await useFlow(request, async (name, args) => {
      const result = await client.callTool({name, arguments: args}, undefined, {timeout: 300000});
      if (result.isError || !result.structuredContent) {
        const code = result.content?.find(item => item.type === "text")?.text;
        let detail;
        try { detail = JSON.parse(code); } catch {}
        const errorCode = detail?.code || detail?.error?.code;
        const suffix = typeof errorCode === "string" && /^[A-Za-z0-9_]+$/.test(errorCode)
          ? " (" + errorCode + ")" : "";
        throw new Error("Flow chưa trả ảnh. Kiểm tra dự án, phiên đăng nhập và hai ảnh tham chiếu" + suffix + ".");
      }
      return result.structuredContent;
    });
  } finally {
    await client.close();
  }
}

async function browserTask(port, request) {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:" + port, {timeout: 12000});
  try {
    const context = browser.contexts()[0];
    if (!context) throw new Error("Không tìm thấy hồ sơ trình duyệt của Studio.");
    if (request.action === "project") {
      const projectPages = context.pages().map(page => {
        try { return flowProject(page.url()); } catch { return null; }
      }).filter(Boolean);
      return {project: projectPages.at(-1) || ""};
    }
    if (request.action === "shutdown") {
      const session = await browser.newBrowserCDPSession();
      await session.send("Browser.close").catch(() => {});
      return {};
    }
    if (request.action !== "write") throw new Error("Tác vụ không hợp lệ.");
    const page = await context.newPage();
    try {
      await page.goto("https://gemini.google.com/app", {waitUntil: "domcontentloaded", timeout: 30000});
      if (new URL(page.url()).origin !== "https://gemini.google.com") {
        throw new Error("Hãy đăng nhập Google trong cửa sổ kết nối của Studio.");
      }
      const editor = page.locator('rich-textarea [contenteditable="true"]:visible, .ql-editor[contenteditable="true"]:visible, [contenteditable="true"][role="textbox"]:visible').first();
      try { await editor.waitFor({state:"visible",timeout:20000}); }
      catch { throw new Error("Không thấy ô chat Gemini. Hãy kiểm tra đăng nhập từ nút Kết nối Google."); }
      const answers = page.locator("model-response");
      const prior = await answers.count();
      await editor.fill(request.prompt);
      const send = page.getByRole("button", {name:/^(send( message| prompt)?|gửi( tin nhắn| lời nhắc)?)$/i})
        .or(page.locator("button.send-button")).first();
      await send.click({timeout:10000});
      const answer = answers.nth(prior);
      await answer.waitFor({state:"visible",timeout:90000});
      let priorText = "";
      let changed = Date.now();
      const deadline = Date.now() + 95000;
      const stop = page.getByRole("button", {name:/^(stop|dừng|ngừng)(\b|\s)/i}).first();
      while (Date.now() < deadline) {
        if (new URL(page.url()).origin !== "https://gemini.google.com") throw new Error("Phiên Gemini đã thay đổi.");
        const child = answer.locator("message-content, .markdown").first();
        const text = (await (await child.count() ? child : answer).innerText({timeout:5000})).trim();
        if (text !== priorText) { priorText = text; changed = Date.now(); }
        if (text && !(await stop.isVisible()) && Date.now() - changed >= 3500) return {text};
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      throw new Error("Gemini chưa viết xong trong thời gian chờ.");
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
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Phiên trình duyệt chưa sẵn sàng.");
    const result = request.action === "generate" ? await generation(port, request) : await browserTask(port, request);
    process.stdout.write(JSON.stringify({result}));
  } catch (error) {
    const details = error instanceof Error && error.name !== "TimeoutError" ? error.message : "Đã hết thời gian chờ.";
    process.stdout.write(JSON.stringify({error: details.split("\n")[0].slice(0,400)}));
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
