const status = document.getElementById("status");
const input = document.getElementById("code");
const button = document.querySelector("button");
chrome.storage.local.get("code").then(({code}) => {
  if (code) status.textContent = "Đã lưu mã kết nối trên Chrome.";
});
document.querySelector("form").addEventListener("submit", async event => {
  event.preventDefault();
  button.disabled = true;
  try {
    const result = await chrome.runtime.sendMessage({type:"pair", code:input.value.trim()});
    status.textContent = result?.ok ? "Đã kết nối app. Bạn có thể quay lại Gemini Thử Đồ."
      : result?.error || "Không kết nối được app.";
    if (result?.ok) input.value = "";
  } catch {
    status.textContent = "Không kết nối được extension.";
  } finally {
    button.disabled = false;
  }
});
