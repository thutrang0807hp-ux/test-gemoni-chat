import { execFileSync } from "node:child_process";
import { Writable } from "node:stream";
import { createInterface } from "node:readline/promises";
import { writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";
import { GeminiClient, MemoryStorageAdapter } from "gemini-web-api";

const imageHosts = new Set(["lh3.googleusercontent.com", "lh3.google.com", "gemini.google.com"]);
const limit = 24 * 1024 * 1024;

function validateUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.port || url.username || url.password || !imageHosts.has(url.hostname)) {
    throw new Error("Gemini tra link anh ngoai danh sach may chu anh da xac dinh.");
  }
  return url;
}

export async function downloadImage(value, cookie, request = fetch) {
  let url = validateUrl(value);
  const signal = AbortSignal.timeout(45_000);
  for (let hop = 0; hop <= 3; hop++) {
    const response = await request(url, {
      headers: {Cookie: cookie, Referer: "https://gemini.google.com/"},
      redirect: "manual",
      signal,
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const next = response.headers.get("location");
      await response.body?.cancel();
      if (!next || hop === 3) throw new Error("Khong the theo link tai anh.");
      url = validateUrl(new URL(next, url));
      continue;
    }
    const type = (response.headers.get("content-type") || "").split(";")[0];
    if (!response.ok || !response.body || !["image/png", "image/jpeg", "image/webp"].includes(type)) {
      await response.body?.cancel();
      throw new Error("Gemini co tra link, nhung may chu anh khong tra file anh.");
    }
    const chunks = [];
    let size = 0;
    const reader = response.body.getReader();
    try {
      for (;;) {
        const {done, value: chunk} = await reader.read();
        if (done) break;
        size += chunk.length;
        if (size > limit) throw new Error("Anh lon hon 24 MB.");
        chunks.push(chunk);
      }
    } finally {
      await reader.cancel().catch(() => {});
      reader.releaseLock();
    }
    const data = Buffer.concat(chunks, size);
    if (type === "image/png" && data.subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex"))) return {data, extension: "png"};
    if (type === "image/jpeg" && data.subarray(0, 3).equals(Buffer.from("ffd8ff", "hex"))) return {data, extension: "jpg"};
    if (type === "image/webp" && data.toString("ascii", 0, 4) === "RIFF" && data.toString("ascii", 8, 12) === "WEBP") return {data, extension: "webp"};
    throw new Error("File tai ve khong co dinh dang anh hop le.");
  }
}

export function generatedImage(output) {
  return output.candidates?.[output.chosen ?? 0]?.generatedImages?.[0];
}

async function inputSession() {
  if (!process.stdin.isTTY || process.platform !== "win32") {
    throw new Error("Mo Run-Qutek-Test.cmd trong cua so Terminal tren Windows.");
  }
  const silentOutput = new Writable({write(chunk, encoding, callback) { callback(); }});
  const input = createInterface({input: process.stdin, output: silentOutput, terminal: true});
  input.on("SIGINT", () => process.exit(130));
  async function ask(label) {
    process.stdout.write(label);
    const answer = await input.question("");
    process.stdout.write("\n");
    return answer.trim();
  }
  try {
    const psid = await ask("Dan Value cua __Secure-1PSID, sau do Enter: ");
    const psidts = await ask("Dan Value cua __Secure-1PSIDTS, sau do Enter: ");
    for (;;) {
      await ask("Thoat han Chrome, sau do nhan Enter de bat dau: ");
      const listing = execFileSync("tasklist.exe", ["/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"], {encoding: "utf8"});
      if (!/^"chrome\.exe"/im.test(listing)) break;
      console.log("Chrome van dang chay.");
    }
    return {psid, psidts};
  } finally {
    input.close();
  }
}

async function main() {
  let stage = "Doc phien Gemini";
  let deadline;
  try {
    const {psid, psidts} = await inputSession();
    deadline = setTimeout(() => {
      console.error(`HET THOI GIAN: ${stage}. Chua xac nhan duoc anh.`);
      process.exit(1);
    }, 240_000);
    if (![psid, psidts].every(value => typeof value === "string" && /^[\x21-\x7e]+$/.test(value) && !/[;,]/.test(value))) {
      throw new Error("Ban can nhap ca hai gia tri phien, khong kem ten cookie.");
    }
    stage = "Ket noi Gemini Chat";
    console.log(stage + "…");
    const client = new GeminiClient({
      cookies: {"__Secure-1PSID": psid, "__Secure-1PSIDTS": psidts},
      storage: new MemoryStorageAdapter(),
      verbose: false,
    });
    try {
      await client.init(false);
    } catch {
      throw new Error("qutek khong khoi tao duoc phien Gemini. Chua the kiem tra tao anh.");
    }
    stage = "Cho Gemini tao anh";
    console.log(stage + "…");
    let output;
    try {
      output = await client.generateContent(
        "Generate one original square image of a small cafe on a sunny beach. Return the generated image.",
        [], "gemini-3-flash", undefined, true,
      );
    } catch {
      throw new Error("qutek khong nhan duoc phan hoi tu yeu cau tao anh.");
    }
    const image = generatedImage(output);
    if (!image?.url) {
      throw new Error(output.text?.trim()
        ? "Gemini tra van ban, khong co anh tao moi."
        : "Gemini khong tra anh tao moi.");
    }
    stage = "Tai anh";
    console.log(stage + "…");
    const {data, extension} = await downloadImage(image.url, client.getCookieString());
    const filename = `qutek-test-${randomUUID().slice(0, 8)}.${extension}`;
    await writeFile(filename, data, {flag: "wx"});
    console.log(`THANH CONG: ${filename}`);
  } catch (error) {
    console.error(`CHUA THANH CONG: ${error instanceof Error ? error.message : stage}`);
    process.exitCode = 1;
  } finally {
    clearTimeout(deadline);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
