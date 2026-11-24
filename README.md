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

Tải [Studio-Anh-Gemini-Setup.exe](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/windows-v0.2.1/Studio-Anh-Gemini-Setup.exe). Mở **Studio Ảnh Gemini** từ Start Menu. Bản này dùng phiên Gemini Chat của bạn và không cần Gemini API key.

1. Đăng nhập tài khoản của bạn tại [Gemini Chat](https://gemini.google.com/app).
2. Trong tab Gemini, mở DevTools bằng `F12`, vào **Application → Storage → Cookies**, rồi chọn mục Gemini. Tìm `__Secure-1PSID` và `__Secure-1PSIDTS` của cùng phiên.
3. Trong Studio, bấm **Kết nối Gemini Chat** và dán hai giá trị lần lượt vào hộp thoại. Đây là thông tin đăng nhập. Chỉ nhập vào bản Studio trên PC của bạn. Studio lưu hai giá trị trong Windows Credential Manager.
4. Bấm **Chỉnh prompt và tạo ảnh**. Bấm **X** để đưa app xuống khay cạnh đồng hồ. Bạn có thể thoát Chrome, miễn PC vẫn bật và Studio vẫn chạy. Bấm biểu tượng Studio để xem hoặc lưu ảnh khi hoàn tất.

Bản này dùng thư viện [Gemini-API](https://github.com/HanaokaYuzu/Gemini-API) để gọi Gemini Web từ PC. Đây là tích hợp không chính thức. Khi Google hết hạn phiên hoặc yêu cầu xác thực lại, hãy kết nối lại trong Studio.
