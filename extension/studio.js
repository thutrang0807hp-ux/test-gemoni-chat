(() => {
  if (location.pathname !== "/test-gemoni-chat/") return;

  window.addEventListener("message", async event => {
    if (event.source !== window || event.origin !== location.origin) return;
    const {bridge, id, message} = event.data ?? {};
    if (bridge !== "gemini-studio-request" || typeof id !== "string" ||
        !["studio-ping", "studio-generate"].includes(message?.type)) return;

    let result;
    try {
      result = await chrome.runtime.sendMessage(message);
    } catch {
      result = {error: "Extension chưa sẵn sàng. Hãy tải lại trang sau khi cập nhật."};
    }
    window.postMessage({
      bridge: "gemini-studio-response",
      id,
      result: result || {error: "Không nhận được phản hồi từ extension."}
    }, location.origin);
  });
})();
