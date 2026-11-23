import { generateInGemini } from "./gemini.js";

const studio = "https://thutrang0807hp-ux.github.io/test-gemoni-chat/";
let busy = false;

chrome.runtime.onMessageExternal.addListener((message, sender, respond) => {
  const source = new URL(sender.url || "about:blank");
  if (source.origin + source.pathname !== studio || sender.frameId !== 0) return;
  if (message?.type === "studio-ping") {
    respond({ok: true});
    return;
  }
  if (message?.type !== "studio-generate") return;
  if (busy) {
    respond({error: "Gemini đang xử lý yêu cầu trước. Hãy đợi rồi thử lại."});
    return;
  }
  const {prompt, ratio, refine} = message;
  if (typeof prompt !== "string" || !prompt.trim() || prompt.length > 12000 ||
      !["1:1", "16:9", "9:16", "4:3", "3:4"].includes(ratio) || typeof refine !== "boolean") {
    respond({error: "Prompt hoặc tỷ lệ ảnh không hợp lệ."});
    return;
  }

  busy = true;
  run(prompt.trim(), ratio, refine, sender.tab?.windowId)
    .then(respond, error => respond({error: error.message}))
    .finally(() => { busy = false; });
  return true;
});

async function run(prompt, ratio, refine, windowId) {
  const tab = await chrome.tabs.create({
    url: "https://gemini.google.com/app",
    active: false,
    ...(windowId === undefined ? {} : {windowId})
  });
  try {
    const deadline = Date.now() + 25000;
    let current;
    do {
      current = await chrome.tabs.get(tab.id);
      if (current.status === "complete" && current.url && !current.url.startsWith("chrome://")) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    } while (Date.now() < deadline);
    if (!current?.url?.startsWith("https://gemini.google.com/")) {
      throw new Error("Hãy đăng nhập Gemini Chat trong Chrome rồi thử lại.");
    }
    const [execution] = await chrome.scripting.executeScript({
      target: {tabId: tab.id},
      func: generateInGemini,
      args: [prompt, ratio, refine]
    });
    const result = execution?.result || {error: "Không đọc được kết quả từ tab Gemini."};
    if (!result.imageUrl) return result;
    try {
      const url = new URL(result.imageUrl);
      if (url.protocol !== "https:" || !url.hostname.endsWith(".googleusercontent.com")) throw new Error();
      const response = await fetch(url, {
        credentials: "include", redirect: "error", signal: AbortSignal.timeout(15000)
      });
      const mime = response.headers.get("content-type")?.split(";")[0];
      if (!response.ok || !["image/png", "image/jpeg", "image/webp"].includes(mime)) throw new Error();
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      try {
        for (;;) {
          const {value, done} = await reader.read();
          if (done) break;
          size += value.length;
          if (size > 8_000_000) throw new Error();
          chunks.push(value);
        }
      } finally {
        await reader.cancel().catch(() => {});
      }
      const bytes = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        bytes.set(chunk, offset);
        offset += chunk.length;
      }
      const binary = [];
      for (let start = 0; start < bytes.length; start += 8192) {
        binary.push(String.fromCharCode(...bytes.subarray(start, start + 8192)));
      }
      return {prompt: result.prompt, mime, image: btoa(binary.join(""))};
    } catch {
      return {prompt: result.prompt, error: "Gemini đã tạo ảnh nhưng extension không tải được ảnh về Studio."};
    }
  } finally {
    await chrome.tabs.remove(tab.id).catch(() => {});
  }
}
