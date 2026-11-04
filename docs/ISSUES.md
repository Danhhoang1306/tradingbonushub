# ISSUES

## [Backend → Public FE] Ảnh mặc định cần có trong `static/img/`
Setting mặc định trỏ tới `/static/img/logo.png` (logo + favicon) và `/static/img/hero-bg.webp` (ảnh nền hero,
lấy từ khóa `v2-hero-bg` trong `design/.image-slots.state.json`, là data URI webp). Public FE tạo hai file này.
Admin đổi được qua Cài đặt › Chung và Trang chủ › Hero.

## [Backend → FE] Chạy server local phải đặt `APP_ENV=development`
Mặc định là `production` (an toàn khi lên tunnel): bắt buộc `SECRET_KEY`, cookie Secure (không đăng nhập được qua
http://127.0.0.1). Khi thử ở 8011/8012: `APP_ENV=development`, `DATABASE_URL`/`UPLOAD_DIR` trỏ thư mục tạm. Xem
cuối `docs/VIEW_CONTEXT.md`.

## [Backend → Admin FE] Mục "Cài đặt" chỉ dành cho role admin
Editor mở `/admin/settings` nhận 403. Ẩn mục này trong sidebar khi `not user.is_admin`.

## [Backend] Lệch nhỏ so với brief (đã chọn phương án an toàn/đơn giản)
- Thêm bảng `ClickLog` (đếm click theo ngày) để Tổng quan có biểu đồ 30 ngày và "click 30 ngày" từ DB thật.
- Thêm biến môi trường `UPLOAD_DIR` (mặc định `data/uploads`) để test/QA dùng thư mục tạm.
- Khóa Setting `footer_note` (mục 6) được thay bằng `footer.risk_note` (mục 12) để không trùng hai nơi sửa.
- Setting bổ sung ngoài danh sách mục 12 (đều là chữ thiết kế): `meta_keywords`, `branding{logo_path,favicon_path,og_image}`,
  `home_bonus{eyebrow,title}`, các trường `eyebrow`/`points`/`badge`/`count_label`/`stat_value`/`stat_label`/`success_*`,
  `bonus_types[].short` (nhãn ngắn cho tab/chip vì thiết kế dùng hai bộ nhãn), `pages.terms/privacy`, `contact_page.success_text`.
- `Campaign.status` có thêm giá trị `sending` (ghi lại trước khi gửi, đổi thành `sent` khi xong).
- Bonus "Sắp hết hạn" = đang hiển thị và hết hạn trong ≤ 14 ngày.
- Mô tả trang Liên hệ mặc định ("Gửi câu hỏi, báo lỗi thông tin bonus hoặc đề nghị hợp tác.") do backend đặt vì
  thiết kế không có header riêng cho trang này; admin sửa được ở Trang › Liên hệ.
- Gửi email chiến dịch chạy đồng bộ trong request (một kết nối SMTP cho cả lô). Đủ cho danh sách nhỏ; danh sách lớn
  (hàng nghìn) cần hàng đợi nền – chưa làm.
