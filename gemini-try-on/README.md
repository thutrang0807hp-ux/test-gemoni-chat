# Gemini Tạo Ảnh

App Windows riêng tạo ảnh trực tiếp từ prompt bằng Gemini Chat. [Tải bộ cài 0.4.12](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/gemini-tao-anh-v0.4.12/Gemini-Tao-Anh-Setup.exe).

1. Nếu chưa kết nối, bấm **Đăng nhập Gemini** và đăng nhập Google trong cửa sổ Chrome vừa mở. Đóng cửa sổ đăng nhập rồi bấm **Kiểm tra kết nối**.
2. Nhập mô tả ảnh. Bạn có thể bấm **Gemini viết lại prompt** để chỉnh mô tả rồi sửa tiếp trong app, hoặc bấm **Tạo ảnh bằng Gemini** ngay.
3. Khi có ảnh, bấm **Lưu ảnh**. Bấm **Tạo ảnh bằng Gemini** lần nữa để tạo ảnh mới bằng prompt hiện tại.

App dùng Chrome ở chế độ không cửa sổ để viết prompt và tạo ảnh. Chỉ bước Đăng nhập Gemini mở cửa sổ Chrome. Bạn có thể đóng Chrome thường dùng. Cần giữ tiến trình Chrome riêng của app chạy trong lúc xử lý. Không cần ảnh tham chiếu, extension, API key hoặc chép cookie. Bản cập nhật dùng lại hồ sơ đăng nhập của Gemini Thử Đồ 0.3.0.

Bấm **Bỏ dấu sao Gemini** sau khi nhận ảnh để xử lý cục bộ bằng [GeminiWatermarkTool v0.3.2](https://github.com/allenk/GeminiWatermarkTool/tree/v0.3.2) (MIT), rồi bấm **Lưu ảnh**. Bản gốc vẫn được giữ trong bộ nhớ đệm của app.

Trong tab **Ảnh tham chiếu**, chọn ảnh PNG, JPG hoặc WebP rồi nhập điều bạn muốn giữ hoặc đổi. Ví dụ “Giữ mặt tiền và bảng hiệu của quán, đưa quán lên sườn núi lúc sáng sớm”. App gửi ảnh đã chọn cùng yêu cầu tới Gemini Chat.

Bản 0.4.12 mở rộng từ luồng 0.4.11: thêm nhiều ảnh theo thứ tự trong tab Ảnh tham chiếu, ảnh gốc trước và ảnh sản phẩm/người/trang phục/bối cảnh sau. Tất cả ảnh được gửi cùng prompt trong một lượt. Có nút xóa danh sách để chọn lại. Đầu vào Python hỗ trợ `references=[...]` và vẫn giữ `reference=...` cho lời gọi một ảnh cũ. Prompt tối đa 160.000 ký tự.
