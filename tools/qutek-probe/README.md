# Thử tạo ảnh bằng qutek khi đã thoát Chrome

Cần Windows và [Node.js 22 trở lên](https://nodejs.org/). Không cần Gemini API key.

1. Giải nén ZIP vào một thư mục riêng rồi mở `Run-Qutek-Test.cmd`.
2. Khi được hỏi, lấy lần lượt hai giá trị `__Secure-1PSID` và `__Secure-1PSIDTS` từ phiên Gemini Chat của bạn. Trong Chrome DevTools, mở **Application → Cookies → https://gemini.google.com**, rồi chép nội dung cột **Value**. Dán vào cửa sổ thử trên PC. Nội dung dán sẽ được ẩn.
3. Khi cửa sổ yêu cầu, thoát hẳn Chrome rồi nhấn **Enter**. Chương trình kiểm tra Chrome đã dừng trước khi gửi yêu cầu.
4. Nếu thấy `THANH CONG`, mở file `qutek-test-...` cạnh script để kiểm tra ảnh. Nếu thấy `CHUA THANH CONG` hoặc `HET THOI GIAN`, bạn có thể chia sẻ đúng dòng trạng thái đó.

Bộ thử gọi SDK qutek trực tiếp, không mở dịch vụ HTTP. Phiên chỉ nằm trong bộ nhớ khi chạy và không ghi vào thư mục thử. Link tải ảnh và mọi chuyển hướng được kiểm tra trước khi gửi cookie. Đây là phép thử một prompt mẫu, chưa tích hợp vào Studio.
