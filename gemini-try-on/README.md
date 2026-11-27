# 0.4.6 — xác định lỗi hết thời gian chờ

Bản này bổ sung chẩn đoán, chưa khẳng định đã sửa nguyên nhân tạo ảnh trên tài khoản thực.

- Lỗi hiển thị bước cụ thể: mở Gemini, tìm ô nhập, tải ảnh tham chiếu, gửi prompt, chờ ảnh hoặc tải kết quả.
- Khi lỗi xảy ra, app chụp trang Gemini trước khi dọn tab. Bấm **Xem lỗi Gemini** để mở ảnh trên máy.
- Trạng thái cuối được lưu tại `%LOCALAPPDATA%\GeminiReferencesTest\diagnostics\status.json`; ảnh lỗi tại `last-error.png` cùng thư mục. Không gửi các tệp này lên mạng tự động.
- Nếu cả tiến trình vượt thời gian chờ, thông báo vẫn giữ bước cuối thay vì chỉ ghi timeout.
- Các hàm gửi, nhận và tải ảnh giữ nguyên. Không tự gửi lại lượt tạo ảnh.

# Bản thử 0.4.5 — ảnh tham chiếu

Bản thử độc lập trên nhánh `reference-attachments`. Không sửa SceneForge và không thay release 0.4.4. Cài vào thư mục riêng, dùng hồ sơ riêng; cần đăng nhập một lần trong bản thử.

1. Đăng nhập như bản 0.4.4 rồi kiểm tra kết nối.
2. Thêm ảnh: ảnh gốc trước, ảnh sản phẩm/người/trang phục/bối cảnh sau. Danh sách hiển thị đúng thứ tự gửi.
3. Trong prompt ghi rõ vai trò ảnh 1, ảnh 2… rồi bấm Tạo ảnh bằng Gemini.
4. Đợi kết quả; lưu ảnh hoặc dùng Bỏ dấu sao Gemini như trước.

Nút viết lại prompt vẫn chỉ xử lý văn bản như bản gốc. Tạo ảnh mới đính kèm danh sách ảnh đang chọn. Khi không chọn ảnh, đường gửi cũ được giữ nguyên. Mỗi ảnh PNG/JPEG/WebP tối đa 20 MB; prompt tối đa 160.000 ký tự.

Đã kiểm tra cú pháp, đối chiếu 10 hàm gửi/nhận nguyên bản và upload nhị phân theo thứ tự qua Chromium. Những kiểm tra này không thay thế kiểm thử bằng tài khoản Gemini thật. Chưa xác nhận lượt tạo ảnh thực với tài khoản của người dùng.

Chạy từ mã nguồn trên Windows: cài Python và Node, `pip install -r gemini-try-on/requirements.txt`, `npm ci --prefix gemini-try-on/runtime`, rồi `python gemini-try-on/main.py`.

---

# Gemini Tạo Ảnh

App Windows riêng tạo ảnh trực tiếp từ prompt bằng Gemini Chat. [Tải bộ cài 0.4.4](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/gemini-tao-anh-v0.4.4/Gemini-Tao-Anh-Setup.exe).

1. Nếu chưa kết nối, bấm **Đăng nhập Gemini** và đăng nhập Google trong cửa sổ Chrome vừa mở. Đóng cửa sổ đăng nhập rồi bấm **Kiểm tra kết nối**.
2. Nhập mô tả ảnh. Bạn có thể bấm **Gemini viết lại prompt** để chỉnh mô tả rồi sửa tiếp trong app, hoặc bấm **Tạo ảnh bằng Gemini** ngay.
3. Khi có ảnh, bấm **Lưu ảnh**. Bấm **Tạo ảnh bằng Gemini** lần nữa để tạo ảnh mới bằng prompt hiện tại.

App dùng Chrome ở chế độ không cửa sổ để viết prompt và tạo ảnh. Chỉ bước Đăng nhập Gemini mở cửa sổ Chrome. Bạn có thể đóng Chrome thường dùng. Cần giữ tiến trình Chrome riêng của app chạy trong lúc xử lý. Không cần ảnh tham chiếu, extension, API key hoặc chép cookie. Bản cập nhật dùng lại hồ sơ đăng nhập của Gemini Thử Đồ 0.3.0.

Bấm **Bỏ dấu sao Gemini** sau khi nhận ảnh để xử lý cục bộ bằng [GeminiWatermarkTool v0.3.2](https://github.com/allenk/GeminiWatermarkTool/tree/v0.3.2) (MIT), rồi bấm **Lưu ảnh**. Bản gốc vẫn được giữ trong bộ nhớ đệm của app.
