# Gemini Studio

Ứng dụng web tiếng Việt để chỉnh prompt bằng Gemini, tạo ảnh từ prompt đã chỉnh và tải ảnh xuống. Nút **Tạo lại ảnh** dùng nội dung hiện có trong ô prompt kết quả.

## Kết nối extension Chrome

1. [Tải Studio Ảnh Gemini 0.2.1](https://github.com/thutrang0807hp-ux/test-gemoni-chat/releases/download/extension-v0.2.1/studio-anh-gemini-0.2.1.zip) và giải nén.
2. Mở `chrome://extensions` trên Chrome máy tính. Bật **Developer mode**, chọn **Load unpacked**, rồi chọn thư mục `studio-anh-gemini-0.2.1` vừa giải nén.
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
