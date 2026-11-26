import { runGemini } from "./gemini.js";

const base = "http://127.0.0.1:48947";
const hosts = new Set(["gemini.google.com", "lh3.google.com", "lh3.googleusercontent.com"]);
let busy = false;

async function bridge(path, code, body) {
  const response = await fetch(base + path, {
    method:"POST", headers:{"Authorization":"Bearer " + code,"Content-Type":"application/json"},
    body:body ? JSON.stringify(body) : undefined,
    signal:AbortSignal.timeout(9000),
  });
  if (!response.ok) throw new Error(response.status === 403 ? "Mã kết nối không đúng." : "App không nhận yêu cầu.");
  return response.json();
}

async function downloadMedia(value) {
  const url = new URL(value);
  if (url.protocol !== "https:" || !hosts.has(url.hostname) || url.port || url.username || url.password) {
    throw new Error("Địa chỉ ảnh Gemini không hợp lệ.");
  }
  const result = await fetch(url, {
    credentials:"include", redirect:"error", signal:AbortSignal.timeout(20000),
  });
  const mime = result.headers.get("content-type")?.split(";")[0];
  if (!result.ok || !result.body || !["image/png","image/jpeg","image/webp"].includes(mime)) {
    throw new Error("Gemini có ảnh nhưng extension không tải được.");
  }
  const buffer = [];
  const reader = result.body.getReader();
  let size = 0;
  try {
    for (;;) {
      const {value:bytes, done} = await reader.read();
      if (done) break;
      size += bytes.length;
      if (size > 24_000_000) throw new Error("Ảnh vượt quá 24 MB.");
      for (let start = 0; start < bytes.length; start += 8192) {
        buffer.push(String.fromCharCode(...bytes.subarray(start, start + 8192)));
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
  return btoa(buffer.join(""));
}

async function getResult(job) {
  const tab = await chrome.tabs.create({url:"https://gemini.google.com/app",active:false});
  try {
    const end = Date.now() + 22000;
    while (Date.now() < end) {
      const current = await chrome.tabs.get(tab.id);
      if (current.status === "complete" && current.url && !current.url.startsWith("chrome://")) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    let execution;
    try {
      [execution] = await chrome.scripting.executeScript({target:{tabId:tab.id},func:runGemini,args:[job]});
    } catch {
      throw new Error("Không mở được Gemini. Hãy đăng nhập Gemini trong Chrome thường dùng rồi thử lại.");
    }
    const result = execution?.result;
    if (!result) throw new Error("Gemini chưa phản hồi.");
    if (result.url) return {image:await downloadMedia(result.url)};
    return result;
  } finally {
    await chrome.tabs.remove(tab.id).catch(() => {});
  }
}

async function poll() {
  if (busy) return;
  busy = true;
  let pulse;
  try {
    const {code} = await chrome.storage.local.get("code");
    if (!code) return;
    const {job} = await bridge("/poll", code);
    if (!job) return;
    pulse = setInterval(() => bridge("/ping",code).catch(() => {}),15000);
    let result;
    try { result = await getResult(job); }
    catch (error) { result = {error:error.message}; }
    await bridge("/result", code, {...result,id:job.id});
  } catch {
    // On the next alarm, the extension checks whether the app is open again.
  } finally {
    clearInterval(pulse);
    busy = false;
  }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || message?.type !== "pair") return;
  if (!/^[0-9a-f]{24}$/.test(message.code)) {
    respond({error:"Hãy dán mã từ app Gemini Thử Đồ."});
    return;
  }
  bridge("/ping",message.code).then(async () => {
    await chrome.storage.local.set({code:message.code});
    await chrome.alarms.create("studio-jobs",{periodInMinutes:.5});
    respond({ok:true});
    void poll();
  }).catch(error => respond({error:error.name === "TimeoutError" || error instanceof TypeError
    ? "Mở app và bấm Kết nối Gemini trước." : error.message}));
  return true;
});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === "studio-jobs") void poll(); });
chrome.runtime.onStartup.addListener(() => { void chrome.alarms.create("studio-jobs",{periodInMinutes:.5}); void poll(); });
chrome.runtime.onInstalled.addListener(() => { void chrome.alarms.create("studio-jobs",{periodInMinutes:.5}); void poll(); });
