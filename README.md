# Gemini Studio

Ứng dụng web tiếng Việt để chỉnh prompt bằng Gemini, tạo ảnh từ prompt đã chỉnh và tải ảnh xuống. Nút **Tạo lại ảnh** dùng nội dung hiện có trong ô prompt kết quả.

## Chạy trên máy

Cần Python 3.9 trở lên và kết nối Internet.

```bash
python3 app.py
```

Mở http://127.0.0.1:8765.

## Dùng Gemini Chat bằng tài khoản Google

Nhập prompt rồi bấm **Sao chép prompt và mở Gemini Chat**. Dán nội dung vào Gemini Chat. Khi có kết quả, bạn có thể dán prompt đã chỉnh vào ô Kết quả và kéo hoặc chọn ảnh đã tải về để xem trong Studio.

## Dùng Gemini API

Lấy API key ở [Google AI Studio](https://aistudio.google.com/apikey), dán vào mục **Kết nối Gemini**, rồi nhập prompt và bấm **Chỉnh prompt và tạo ảnh**. Dự án Google cần có quyền và hạn mức sử dụng mô hình tạo ảnh Gemini.

App gửi yêu cầu đến Gemini qua máy chủ Python. API key được dùng trong phiên hiện tại và không được lưu vào mã nguồn. GitHub lưu mã nguồn của app. Bạn cần chạy máy chủ Python để sử dụng giao diện và tạo ảnh.
