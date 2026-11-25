# Gemini Studio

Ứng dụng web tiếng Việt để chỉnh prompt bằng Gemini, tạo ảnh từ prompt đã chỉnh và tải ảnh xuống. Nút **Tạo lại ảnh** dùng nội dung hiện có trong ô prompt kết quả.

## Kết nối extension Chrome

1. [Tải Studio Ảnh Gemini 0.2.2](https://thutrang0807hp-ux.github.io/test-gemoni-chat/downloads/studio-anh-gemini-0.2.2.zip) và giải nén.
2. Mở `chrome://extensions` trên Chrome máy tính. Bật **Developer mode**, chọn **Load unpacked**, rồi chọn thư mục `studio-anh-gemini-0.2.2` vừa giải nén.
3. Mở hoặc tải lại [Gemini Studio](https://thutrang0807hp-ux.github.io/test-gemoni-chat/). Mục **Kết nối extension Chrome** sẽ báo phiên bản đã kết nối. Nếu đã cài Gemini Studio Bridge, hãy gỡ bản cũ và chọn thư mục extension mới ở bước 2.
4. [Đăng nhập Gemini Chat](https://gemini.google.com/app) một lần bằng Chrome. Sau đó nhập prompt trong Studio và bấm **Gửi**. Kết quả hiện trong Studio. Nút **Tạo lại ảnh** dùng prompt hiện tại trong ô kết quả.

Extension mở một tab Gemini ở nền cho mỗi yêu cầu. Cách này phụ thuộc vào giao diện Gemini Chat và quyền tạo ảnh của tài khoản Google. Extension chỉ nhận yêu cầu từ trang Studio của repo này. Không cần Gemini API key.

## Chạy trên máy

Cần Python 3.9 trở lên và kết nối Internet.

```bash
python3 app.py
```

Mở http://127.0.0.1:8765.

## Chuyển prompt sang Gemini Chat khi chạy trên máy

Nhập prompt rồi bấm **Sao chép prompt và mở Gemini Chat**. Dán nội dung vào Gemini Chat. Khi có kết quả, bạn có thể dán prompt đã chỉnh vào ô Kết quả và kéo hoặc chọn ảnh đã tải về để xem trong Studio.

## Dùng Gemini API trên máy

Lấy API key ở [Google AI Studio](https://aistudio.google.com/apikey), dán vào mục **Kết nối Gemini**, rồi nhập prompt và bấm **Chỉnh prompt và tạo ảnh**. Dự án Google cần có quyền và hạn mức sử dụng mô hình tạo ảnh Gemini.

App gửi yêu cầu đến Gemini qua máy chủ Python. API key được dùng trong phiên hiện tại và không được lưu vào mã nguồn. Bản GitHub Pages chạy luồng Gemini Chat. Để gọi Gemini API qua Studio, hãy chạy máy chủ Python trên máy.

## Studio chạy trên máy chủ

Bản này dùng một dịch vụ Python chạy liên tục. Người dùng đăng nhập bằng Google, gửi yêu cầu rồi có thể thoát Chrome. Khi quay lại cùng tài khoản, Studio đọc trạng thái và kết quả đã lưu trong SQLite.

1. Tạo OAuth client loại **Web application** trong Google Cloud. Thêm redirect URI dạng `https://studio.example.com/auth/google/callback` cho domain sẽ host Studio. Khi OAuth app đang ở chế độ Testing, thêm tài khoản được phép vào danh sách test users.
2. Trong nơi quản lý biến môi trường của máy chủ, khai báo các biến sau. Giữ thông tin bí mật ở máy chủ.

| Biến | Giá trị |
| --- | --- |
| `STUDIO_ORIGIN` | URL HTTPS của Studio, ví dụ `https://studio.example.com` |
| `STUDIO_SESSION_SECRET` | Chuỗi ngẫu nhiên, tạo bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GOOGLE_CLIENT_ID` | Client ID của OAuth app |
| `GOOGLE_CLIENT_SECRET` | Client secret của OAuth app |
| `GOOGLE_ALLOWED_EMAIL` | Địa chỉ Google được phép đăng nhập và sử dụng hạn mức Gemini |
| `GEMINI_API_KEY` | Khóa Gemini API của máy chủ, có quyền với mô hình tạo ảnh |

3. Chạy **một** instance bằng Dockerfile sau một HTTPS reverse proxy. Dùng volume bền vững gắn tại `/data`, và giữ dịch vụ chạy cả khi không có người mở trang. Cổng HTTP trong container là `8080`. Nếu chạy trực tiếp, cài `requirements.txt`, đặt `STUDIO_DATABASE` trỏ tới SQLite trên ổ lưu trữ bền vững rồi chạy `python studio_server.py`.

Hàng đợi xử lý độc lập với phiên web. Yêu cầu đang chờ và ảnh đã hoàn tất được giữ trong SQLite. Nếu chính máy chủ khởi động lại giữa lúc Gemini đang xử lý, Studio đánh dấu yêu cầu lỗi để bạn gửi lại.

## Bản cài đặt Windows

Tải [Studio Ảnh Gemini 0.3.0](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/windows-v0.3.0/Studio-Anh-Gemini-Setup.exe). Studio dùng Chrome đã cài trên máy để tự mở một hồ sơ Google riêng. Bộ cài đã kèm Node.js và phần kết nối Flow. Bạn có thể thoát cửa sổ Chrome thường dùng trong khi hồ sơ riêng của Studio vẫn chạy.

1. Bấm **Kết nối Google**, đăng nhập trên trang Google trong cửa sổ riêng và mở hoặc tạo một dự án trong tab Flow. Phiên đăng nhập được lưu trong hồ sơ trình duyệt trên PC.
2. Trong tab **Viết lại kịch bản**, dán kịch bản tham khảo và thông tin sản phẩm rồi bấm **Viết lại kịch bản**. Gemini trả bản viết lại trong Studio.
3. Trong tab **Thay đồ trong ảnh**, bấm **Đọc dự án**, chọn ảnh người mẫu và ảnh bộ đồ. Nhập yêu cầu thay đồ rồi bấm **Viết prompt và tạo ảnh**. Có thể dùng **Chỉ viết prompt thay đồ** hoặc chỉnh prompt rồi bấm **Tạo lại ảnh trong Flow**.
4. Studio lưu bản làm việc và ảnh thành công gần nhất trên PC. Bấm **X** để thu Studio xuống khay hệ thống trong khi tác vụ chạy.

Không cần API key hay chép cookie. Phần Flow dùng [google-flow-mcp của ParkSangGwon](https://github.com/ParkSangGwon/google-flow-mcp) phiên bản 0.3.1. Tích hợp điều khiển giao diện web, nên việc tạo thật cần tài khoản có quyền truy cập Gemini và Flow. Khi Google thay đổi giao diện, Studio có thể báo lỗi và cần cập nhật.
