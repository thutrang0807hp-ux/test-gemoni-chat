# Gemini Thử Đồ

Ứng dụng Windows riêng để viết prompt thay đồ và thử chỉnh ảnh trực tiếp bằng Gemini Chat.

- [Bộ cài Windows 0.2.0](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/gemini-thu-do-v0.2.0/Gemini-Thu-Do-Setup.exe)
- [Extension Chrome 0.2.0](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/gemini-thu-do-v0.2.0/Gemini-Thu-Do-Extension.zip)

1. Cài app và mở **Gemini Thử Đồ** từ Start Menu. Đăng nhập [Gemini Chat](https://gemini.google.com/app) trong Chrome thường dùng.
2. Giải nén ZIP extension. Mở `chrome://extensions`, bật **Developer mode**, chọn **Load unpacked** rồi chọn thư mục `extension` chứa `manifest.json`.
3. Bấm **Kết nối Gemini** trong app để sao chép mã. Mở extension **Gemini Thử Đồ** trong Chrome. Dán mã và bấm **Kết nối**. App và extension ghi nhớ mã trên máy.
4. Trong app, chọn **ảnh người mẫu** và **ảnh bộ đồ**, nhập hoặc nhờ Gemini viết lại prompt. Bấm **Tạo ảnh bằng Gemini** rồi **Lưu ảnh** khi có kết quả. Extension kiểm tra yêu cầu khoảng 30 giây một lần.
5. Để Chrome chạy khi xử lý. Bạn có thể đóng tab Gemini đang xem. Extension sẽ mở tab tác vụ riêng và đóng tab đó khi xong. Bấm X của app để thu xuống khay hệ thống.

Không cần API key hay chép cookie. App chỉ nghe trên loopback và sử dụng mã ghép cặp. Hai ảnh tham chiếu được chuẩn hóa thành JPEG tối đa 1.800 pixel mỗi chiều trước khi gửi. App chỉ lưu ảnh hoàn tất gần nhất vào thư mục riêng `%LOCALAPPDATA%\GeminiThuDo`. Đây là bản thử tích hợp dựa trên giao diện Gemini Chat.
