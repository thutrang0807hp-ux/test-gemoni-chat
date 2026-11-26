export async function runGemini(job) {
  const allowedHosts = new Set(["gemini.google.com", "lh3.google.com", "lh3.googleusercontent.com"]);
  const wait = delay => new Promise(resolve => setTimeout(resolve, delay));
  const visible = element => element.getClientRects().length > 0;
  const editor = () => [...document.querySelectorAll(
    'rich-textarea [contenteditable="true"], .ql-editor[contenteditable="true"], [contenteditable="true"][role="textbox"]'
  )].find(visible);
  const buttons = () => [...document.querySelectorAll("button,[role=menuitem]")].filter(visible);
  const buttonName = button => button.getAttribute("aria-label") || button.title || button.textContent.trim();
  const responseSelector = "model-response, .model-response-text";
  const answers = () => [...document.querySelectorAll(responseSelector)].filter(node => !node.parentElement?.closest(responseSelector));

  async function until(find, ms) {
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      const value = find();
      if (value) return value;
      await wait(350);
    }
  }

  async function uploadPair() {
    const attachments = "attachment-preview, uploader-file-preview, .attachment-preview, .file-preview";
    const previewsBeforeUpload = document.querySelectorAll(attachments).length;
    const findInput = () => [...document.querySelectorAll('input[type=file][multiple]')]
      .find(input => !input.disabled && (!input.accept || /image|\.jpg|\*/i.test(input.accept)));
    let input = findInput();
    if (!input) {
      const attach = buttons().find(button => /add files|upload|attach|thêm tệp|tải tệp|đính kèm/i.test(buttonName(button)));
      attach?.click();
      input = await until(findInput, 8000);
    }
    if (!input) throw new Error("Gemini chưa hiện ô tải hai ảnh. Lượt tạo ảnh chưa được gửi.");
    const data = new DataTransfer();
    for (const ref of job.references) {
      const bytes = Uint8Array.from(atob(ref.data), char => char.charCodeAt(0));
      data.items.add(new File([bytes], ref.name, {type:"image/jpeg"}));
    }
    input.files = data.files;
    input.dispatchEvent(new Event("input", {bubbles:true}));
    input.dispatchEvent(new Event("change", {bubbles:true}));
    const confirmed = await until(() => {
      const shown = [...document.querySelectorAll("[title], [aria-label], img[alt]")].filter(visible).map(item =>
        [item.title, item.getAttribute("aria-label"), item.alt].filter(Boolean).join(" ")
      );
      return job.references.every(ref => shown.some(label => label.includes(ref.name))) ||
        document.querySelectorAll(attachments).length - previewsBeforeUpload >= 2;
    }, 25000);
    if (!confirmed) throw new Error("Gemini chưa xác nhận đủ hai ảnh đính kèm. Lượt tạo ảnh chưa được gửi.");
  }

  function generatedImage(response) {
    return [...response.querySelectorAll("img")].find(img => {
      if (!img.complete || img.naturalWidth < 256 || img.naturalHeight < 256 || !img.currentSrc) return false;
      const container = img.closest("generated-image, generated-image-container, single-image, image-generation");
      const url = new URL(img.currentSrc);
      if (url.protocol === "blob:") return container && url.origin === "https://gemini.google.com";
      if (url.protocol === "data:") return container && /^data:image\/(png|jpeg|webp);base64,/i.test(img.currentSrc);
      return url.protocol === "https:" && !url.port && !url.username && !url.password && allowedHosts.has(url.hostname) &&
        (container || /^\/(?:gg|gg-dl|rd-gg)(?:\/|$)/.test(url.pathname));
    });
  }

  try {
    if (location.origin !== "https://gemini.google.com") throw new Error("Hãy đăng nhập Gemini bằng Chrome thường dùng.");
    const input = await until(editor, 20000);
    if (!input) throw new Error("Không thấy ô chat Gemini. Hãy đăng nhập Gemini bằng Chrome thường dùng.");
    let prompt;
    if (job.action === "image") {
      await uploadPair();
      prompt = "Chỉnh ảnh người mẫu (ảnh 1) bằng trang phục trong ảnh 2. " +
        "Trả ảnh mới. Giữ nguyên gương mặt, tư thế và nền trừ khi yêu cầu khác. Giữ màu và họa tiết bộ đồ.\n\n" + job.prompt;
    } else {
      prompt = "Viết một prompt tiếng Việt để thay đồ trong ảnh. Ảnh 1 là người mẫu, ảnh 2 là bộ đồ. " +
        "Chỉ trả prompt. Không tự đoán màu, phom hoặc logo chưa được cung cấp.\n\n" + job.prompt;
    }
    const previous = new Set(answers());
    const composer = editor();
    if (!composer) throw new Error("Không thấy ô nhập Gemini sau khi tải ảnh.");
    composer.focus();
    if (!document.execCommand("insertText", false, prompt)) {
      composer.textContent = prompt;
      composer.dispatchEvent(new InputEvent("input", {bubbles:true, inputType:"insertText", data:prompt}));
    }
    const send = await until(() => buttons().find(button =>
      !button.disabled && button.getAttribute("aria-disabled") !== "true" &&
      (button.classList.contains("send-button") || /^(send( message| prompt)?|gửi( tin nhắn| lời nhắc)?)$/i.test(buttonName(button)))
    ), 12000);
    if (!send) throw new Error("Không tìm thấy nút gửi đang hoạt động trong Gemini.");
    send.click();
    const latest = () => answers().filter(node => !previous.has(node)).at(-1);
    if (job.action === "image") {
      const image = await until(() => {
        const answer = latest();
        return answer && generatedImage(answer);
      }, 150000);
      if (!image) throw new Error("Gemini chưa trả ảnh mới cho lượt này.");
      const url = image.currentSrc;
      if (url.startsWith("data:")) {
        if (url.length > 32_000_080) throw new Error("Ảnh vượt quá 24 MB.");
        return {image:url.split(",", 2)[1]};
      }
      if (!url.startsWith("blob:")) return {url};
      const response = await fetch(url, {signal:AbortSignal.timeout(15000)});
      const blob = await response.blob();
      if (blob.size > 24_000_000) throw new Error("Ảnh vượt quá 24 MB.");
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",",2)[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      return {image:data};
    }
    let prior = "";
    let changed = Date.now();
    const text = await until(() => {
      const node = latest();
      const value = (node?.querySelector("message-content, .markdown")?.innerText || node?.innerText || "").trim();
      if (prior !== value) { prior = value; changed = Date.now(); }
      const responding = buttons().some(button => /^(stop|dừng|ngừng)(\b|\s)/i.test(buttonName(button)));
      return value && !responding && Date.now() - changed >= 2800 ? value : null;
    }, 100000);
    if (!text) throw new Error("Gemini chưa trả prompt.");
    return {text};
  } catch (error) {
    return {error:error.message || "Gemini chưa hoàn tất yêu cầu."};
  }
}
