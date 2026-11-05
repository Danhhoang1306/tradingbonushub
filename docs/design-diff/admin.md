# So sánh thiết kế: Trang quản trị

Kiểm toán độc lập ngày 05/11/2026. So `design/Admin.dc.html` với `templates/admin/*`, `static/css/admin.css`. Rộng 1440, cao 900. Dữ liệu tạm nạp đúng state của thiết kế, không vào repo. Không dựa vào `docs/QA_REPORT.md`.

Loại: **A** lỗi hoặc lệch không lý do. **B** do yêu cầu user/brief. **C** dev hoặc team leader tự quyết, không tìm thấy user duyệt. **D** chỉ khác do dữ liệu.

Giới hạn của loại C: tôi chỉ đọc được brief, `docs/ISSUES.md`, `docs/VIEW_CONTEXT.md` và git log, không đọc được hội thoại với user. C nghĩa là không có ghi nhận user duyệt trong các nguồn đó. Loại B dựa vào brief, mà brief do team leader viết.

Ảnh ghép nằm trong thư mục tạm (có dữ liệu mẫu nên không đưa vào repo public). Trái là thiết kế, phải là bản dựng. Riêng ảnh ghép toàn trang của màn dài: thanh "Lưu thay đổi" dính đáy hiện giữa ảnh là do cách chụp.

## Tổng hợp (có dữ liệu)

| Loại | Lớn | Vừa | Nhỏ | Tổng |
|---|---|---|---|---|
| A | 0 | 7 | 8 | 15 |
| B | 4 | 17 | 9 | 30 |
| C | 12 | 28 | 37 | 77 |
| D | 0 | 0 | 4 | 4 |
| Tổng | 16 | 52 | 58 | 126 |

## Tổng hợp (DB rỗng)

| Loại | Lớn | Vừa | Nhỏ | Tổng |
|---|---|---|---|---|
| A | 0 | 0 | 0 | 0 |
| B | 0 | 0 | 5 | 5 |
| C | 0 | 1 | 4 | 5 |
| D | 0 | 0 | 0 | 0 |
| Tổng | 0 | 1 | 9 | 10 |

## Khác biệt khi có dữ liệu

| Màn | Vị trí | Thiết kế gốc | Bản dựng | Mức độ | Loại | Cách sửa (file:dòng) | Ảnh ghép |
|---|---|---|---|---|---|---|---|
| Sidebar | Nhóm menu | 8 mục phẳng, không nhóm | Thêm 4 nhãn nhóm Dữ liệu / Nội dung / Khách / Hệ thống (11px/600, in hoa, #A9B6C1, opacity .8) | Lớn | B | Theo brief mục 12; muốn bỏ thì sửa app/routes/admin_base.py:196-209 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Thứ tự mục | Tổng quan, Bonus, Sàn, Quảng cáo, Nội dung trang chủ, Bài viết, Người đăng ký, Cài đặt | Bài viết lên trước Quảng cáo; Nội dung trang chủ xuống nhóm thứ hai | Vừa | B | Theo brief mục 12; app/routes/admin_base.py:197-205 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Số mục | 8 | 11: thêm Trang, Thư viện ảnh, Tin nhắn | Vừa | B | Theo brief mục 7, 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Nhãn mục | "Nội dung trang chủ" | "Trang chủ" (h1 vẫn là "Nội dung trang chủ", nên nhãn menu và tiêu đề lệch nhau) | Nhỏ | B | Brief mục 12 ghi "Trang chủ"; app/routes/admin_base.py:203 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Toàn admin | Font của mọi nút: menu, tab con, pill, Thêm, Sửa, Lưu | Arial (thiết kế không cho button kế thừa font, có vẻ là sơ suất của file thiết kế) | Be Vietnam Pro; kéo theo rộng và cao: "Tổng quan" 67→73.3px, pill "No-deposit" 97→109px, tab "Tất cả" 76→82px | Vừa | C | Admin FE tự quyết, ghi ở docs/ISSUES.md:90-91. Giữ nguyên hay về Arial là việc user chọn; static/css/admin.css:23 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Sidebar | Chiều cao dòng menu | 38px, bước 42px | 40px, bước 44px (hệ quả của font) | Nhỏ | C | Theo dòng font; static/css/admin.css:53 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Số đếm trên mục đang chọn | #A9B6C1 | #DCE3FB | Nhỏ | C | static/css/admin.css:59 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Sidebar | Hover mục menu | Không đổi nền | Nền rgba(255,255,255,.06) | Nhỏ | C | static/css/admin.css:56 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Khối logo | Không phải link; logo không có nền; dòng chữ cao 19 và 15px | Là link về /admin; nền logo rgba(255,255,255,.12); chữ cao 20.3 và 16.2px | Nhỏ | C | templates/admin/_base.html:13; static/css/admin.css:42-44 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Cuối sidebar | Chỉ có dòng email, rộng 200px | Thêm link "Đăng xuất" cùng hàng (x163, 12px gạch chân); email thu còn 106.5px. Vị trí email khớp x24 y861 | Vừa | B | Cần cho /admin/logout ở brief mục 7; templates/admin/_base.html:34-37 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Giá trị email | Email demo cố định | Email của tài khoản đang đăng nhập | Nhỏ | B | Brief mục 5 cấm email demo | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | "Xem trang chủ ↗" | Mở cùng tab | target=_blank. Hộp và màu khớp (24,806, 200x45) | Nhỏ | C | templates/admin/_base.html:33 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Sidebar | Số đếm Người đăng ký | Đếm mọi người đăng ký | Chỉ đếm đã xác nhận | Nhỏ | C | app/routes/admin_base.py:207 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_list_1440.png` |
| Đầu trang | Nút "Xuất bản thay đổi" trên Tổng quan, Bonus, Sàn, Quảng cáo, Bài viết, Người đăng ký, Tài khoản | Có ở MỌI màn (1237,52, 163x42) | KHÔNG có. Chỉ còn ở Trang chủ, Trang, Cài đặt (trừ Tài khoản). Không có dòng nào trong docs ghi lại việc bỏ nút này | Lớn | C | templates/admin/_base.html:51; đặt page_form ở overview, bonus, brokers, ads, posts, subscribers. Cần user quyết vì các màn này lưu ngay từng thao tác, nút sẽ không có gì để xuất bản | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Đầu trang | Ý nghĩa "Xuất bản thay đổi" | Một nút chung, báo "Đã lưu" 1.8s | Chỉ là submit page-form, trùng hẳn nút "Lưu thay đổi" đáy form (cùng form id). Không có nháp/xuất bản. Ở tab Section nó chỉ lưu tiêu đề section, không liên quan công tắc và mũi tên | Vừa | C | templates/admin/_base.html:51; templates/admin/home.html:3,34,45; templates/admin/settings.html:3,112 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Đầu trang | Hộp nút "+ Thêm" | y53, cao 40px, không viền | y48, cao 44px, viền 1px; rộng 139→142px | Nhỏ | A | static/css/admin.css:98 bỏ viền của .btn-primary | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Đầu trang | Cao h1 | 40px (line-height normal) | 38.4px (line-height 1.2), mọi nội dung bên dưới dịch lên 2px | Nhỏ | A | static/css/admin.css:77 bỏ line-height: 1.2 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Đầu trang | "+ Thêm banner" | Quảng cáo không có nút thêm | Có | Vừa | B | Dữ liệu phải do admin nhập (brief mục 1) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Đầu trang | "Xem trên site ↗" | Không có | Có ở đầu trang; thêm lần nữa ở đáy form và "Mở trang ↗" ở khối xem trước: 3 link cùng đích trên một màn. Brief chỉ yêu cầu một nút | Nhỏ | C | Giữ một: templates/admin/_base.html:50; bỏ templates/admin/home.html:187,192 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Toàn admin | Màu xanh trạng thái ("Đã lưu", "Đã đăng") | #1F8A4C | #1A7A42 (đổi vì tương phản, commit 2e4229e) | Nhỏ | C | static/css/admin.css:6 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Toàn admin | Rê chuột dòng bảng | Chỉ bảng Bonus | Mọi bảng | Nhỏ | C | static/css/admin.css:191 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_list_1440.png` |
| Tổng quan | Số thẻ thống kê | 4 thẻ, mỗi thẻ 277px | 5 thẻ, mỗi thẻ 222px: thêm "Click affiliate (30 ngày)" | Lớn | C | app/routes/admin.py:103 (bỏ dòng), docs/VIEW_CONTEXT.md:412 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Thẻ "Sàn nhiều click nhất" | Không có | Thêm cả thẻ. Ban đầu là thẻ THAY cho Banner quảng cáo (docs/ISSUES.md:78); Banner được trả lại nhưng thẻ này vẫn giữ | Lớn | C | Xóa templates/admin/overview.html:43-53 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Biểu đồ "Click theo ngày" | Không có ở Tổng quan, chỉ ở Quảng cáo > Thống kê | Thêm thẻ biểu đồ, trang cao 514→752px | Lớn | C | Xóa templates/admin/overview.html:54-58; ClickLog thêm ở docs/ISSUES.md:17 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Thẻ "Bonus sắp hết hạn" | 4 dòng, gồm cả bonus hết hạn sau 25 và 56 ngày | Rỗng, câu "Không có bonus nào hết hạn trong 14 ngày tới." vì tự đặt ngưỡng 14 ngày | Lớn | C | app/queries.py:12; thiết kế không nêu ngưỡng, cần user chốt số ngày | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Số dòng và thứ tự bonus sắp hết hạn | Tối đa 4, theo thứ tự danh sách | Không giới hạn (5 dòng khi thử ngày gần), sắp theo ngày | Nhỏ | C | app/routes/admin.py:91-93 thêm .limit(4) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_exp14_1440.png` |
| Tổng quan | Nhãn thẻ 3 | "Click quảng cáo (tháng)" | "Click quảng cáo (30 ngày)" | Nhỏ | C | app/routes/admin.py:102 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Định dạng số thẻ thống kê | Có dấu chấm nghìn (hàm fmt vi-VN) | Không: 4215 (cùng trang có chỗ ghi "4.624 click") | Vừa | A | app/routes/admin.py:102-104 dùng filter num; hoặc templates/admin/overview.html:9 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Dòng banner | Sàn · vị trí; cao 43px | Tên banner · vị trí, thêm dòng trạng thái; cao 63px; tên là link | Vừa | C | templates/admin/overview.html:37 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Link ở tiêu đề thẻ | Không có | "Xem tất cả", "Thống kê", "Link affiliate" | Nhỏ | C | templates/admin/overview.html:22,34,44 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Ngày hết hạn | 31/12 | 31/12/2026 | Nhỏ | C | templates/admin/overview.html:26 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_exp14_1440.png` |
| Tổng quan, Quảng cáo | Dấu thập phân CTR | 1.7% | 1,7% | Nhỏ | C | app/templating.py:84. Bản dựng đúng tiếng Việt hơn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Tổng quan | Dải thông báo tin nhắn chưa đọc | Không có | Hiện khi có tin chưa đọc (đọc từ code, chưa chụp) | Nhỏ | B | Hệ quả màn Tin nhắn; templates/admin/overview.html:14-18 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_1440.png` |
| Bonus | Tab "Sắp hết hạn" | 5 dòng | 0 dòng với cùng dữ liệu, cùng lý do ngưỡng 14 ngày | Lớn | C | app/routes/admin_data.py:64-65; app/queries.py:12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_exp_1440.png` |
| Bonus | Lọc và tìm khi đổi tab con | Giữ lọc (Cashback + Đang hiển thị = 1 dòng) | Mất lọc: link tab chỉ có ?tab=, ra 7 dòng, pill về Tất cả | Vừa | A | app/routes/admin_base.py:219 cho phép giữ tham số; templates/admin/_base.html:61 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Ô tìm kiếm | Lọc ngay khi gõ | Phải nhấn Enter, tải lại trang (gõ xong vẫn 8 dòng) | Vừa | C | Thêm JS debounce ở static/js/admin.js; brief mục 3 yêu cầu JS tối thiểu nên cần user chọn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Hộp ô tìm kiếm | 226x42px, chữ 16px, #000 | 220x40px, chữ 14px, #021623 | Nhỏ | A | static/css/admin.css:168-170 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Cột bảng | 7 cột 120, 376, 130, 90, 90, 90, 80 | Vẫn 7 cột, đúng tên; Tiêu đề 366, Hết hạn 100 | Nhỏ | C | templates/admin/bonus.html:5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Ngày ở cột Hết hạn | 31/12, 30/11 | 31/12/2026, 30/11/2026 | Vừa | C | app/templating.py:72-73 (đang dùng date_vn) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Nút Sửa | Rộng 80px, chữ #000, là button | Rộng 54px, căn phải, chữ #021623; dòng nào cũng thế | Vừa | C | static/css/admin.css:106-109,202 thêm width 100% cho nút Sửa trong bảng | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Dòng đang ẩn | Bình thường, chỉ công tắc tắt | Chữ mờ opacity .55 | Vừa | C | static/css/admin.css:193; templates/admin/bonus.html:27 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Cảnh báo trong ô Tiêu đề, ngày đỏ | Không có, ngày luôn #4B5B66 | Thêm chữ "Sắp hết hạn", "Đã hết hạn", "Sàn đang ẩn"; ngày đỏ khi sắp hết hạn | Vừa | C | templates/admin/bonus.html:31,35 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_exp_exp14_1440.png` |
| Bonus | Tiêu đề bonus | Chữ thường | Là link mở drawer, rê chuột thành xanh | Nhỏ | C | templates/admin/bonus.html:30 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Bonus | Công tắc | Đổi tại chỗ, không tải lại, không báo gì | POST rồi tải lại trang, báo "Đã cập nhật"; giữ tab và lọc | Vừa | B | Brief mục 7 yêu cầu form POST server-side | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_1440.png` |
| Sàn > Danh sách | Cột bảng | 7 cột; So sánh, Nổi bật rộng 90 | 8 cột: thêm "Hiển thị"; So sánh, Nổi bật còn 80; Giấy phép 346→240 | Lớn | C | templates/admin/brokers.html:31,36,49 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_list_1440.png` |
| Sàn > Danh sách | Ô tên sàn | Chỉ tên, dòng cao 58px | Thêm huy hiệu 2 chữ, dòng phụ "Forex · n bonus", cột 140→170, dòng cao 67px | Vừa | C | templates/admin/brokers.html:39-43 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_list_1440.png` |
| Sàn > Danh sách | Thứ tự sàn | Theo danh sách | Nổi bật lên đầu, rồi theo tên | Vừa | C | app/routes/admin_data.py:206 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_list_1440.png` |
| Sàn > Danh sách | Câu ghi chú | Không có số đếm | Thêm "(3/3 đang bật)" | Nhỏ | C | templates/admin/brokers.html:33 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_list_1440.png` |
| Sàn > Link affiliate | Cột thứ 4 | "Đăng ký" (số người đăng ký qua link) | "30 ngày" (click 30 ngày). Team leader quyết, không thấy user duyệt: docs/ISSUES.md:64,80 | Lớn | C | templates/admin/brokers.html:12,22. Muốn có cột Đăng ký phải có nguồn dữ liệu từ sàn, cần user chọn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_links_1440.png` |
| Sàn > Link affiliate | Câu ghi chú trên bảng | Không có, bảng ở y182 | Thêm câu về /go/broker/…, bảng ở y218 | Vừa | C | Xóa templates/admin/brokers.html:9 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_links_1440.png` |
| Sàn > Link affiliate | Lưu link | Sửa thẳng trong ô, lưu bằng nút Xuất bản | Mỗi dòng thêm nút "Lưu"; ô nhập 684→625px; dòng 65→69px | Vừa | C | templates/admin/brokers.html:16-20 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_links_1440.png` |
| Sàn > Link affiliate | Độ rộng cột | 140, 684, 100, 100 | 160, 684, 90, 90 | Nhỏ | C | templates/admin/brokers.html:7 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_links_1440.png` |
| Sàn > Danh sách | Bật So sánh sàn thứ 4 | Không phản hồi gì | Báo lỗi "Chỉ được chọn tối đa 3 sàn để so sánh." | Nhỏ | B | Brief mục 6 chặn ở server | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_list_1440.png` |
| Quảng cáo > Banner | Ô chạy từ – đến | 1 ô chữ, thẻ cao 175px | 2 ô ngày xếp chồng, thẻ cao 231px | Lớn | C | templates/admin/ads.html:56-59; static/css/admin.css:402-403 cho 2 ô cùng hàng (ô 167px không đủ, cần đổi bố cục) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Banner | Tiêu đề thẻ | Sàn · vị trí | Sàn · tên banner | Vừa | C | templates/admin/ads.html:39 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Banner | Nhãn ô link | "Link affiliate" | "Link đích", kèm placeholder | Vừa | C | templates/admin/ads.html:52-53 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Banner | Chân thẻ | Chỉ dòng số liệu | Thêm nút "Lưu" và "Sửa" bên phải | Vừa | C | templates/admin/ads.html:62-68 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Banner | Ô ảnh khi chưa có ảnh | Viền đứt, icon, chữ "Banner 970×250" | Nền xám, chữ "Banner dạng thẻ (không có ảnh)". Brief mục 4 ghi không có chữ placeholder | Vừa | C | templates/admin/ads.html:36 bỏ chữ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Banner | Khoảng cách giữa các thẻ | 20px | 24px | Nhỏ | A | templates/admin/ads.html:33 đang là stack-lg (24px); thêm rule gap 20px riêng, vì .stack là 16px | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Banner | Vị trí banner | 2 lựa chọn | 4 lựa chọn: thêm hai cột hero | Nhỏ | B | Brief mục 6 (placement rail-left, rail-right) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |
| Quảng cáo > Thống kê | Ô Banner | 1 dòng "sàn · vị trí", dòng cao 47px | 2 dòng: tên, rồi sàn · vị trí; dòng cao 67px | Vừa | C | templates/admin/ads.html:14 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_stats_1440.png` |
| Quảng cáo > Thống kê | Hàng "Tổng" | Không có | Thêm hàng tổng nền #FAFAFA | Vừa | C | Xóa templates/admin/ads.html:21-23 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_stats_1440.png` |
| Quảng cáo > Thống kê | Cột Trạng thái | Rộng 100px, xám, 400 | Rộng 120px, xanh lá, 500 | Nhỏ | C | templates/admin/ads.html:7,16 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_stats_1440.png` |
| Quảng cáo > Thống kê | Trục biểu đồ | Không có nhãn | Thêm nhãn ngày đầu và "Hôm nay" | Nhỏ | C | templates/admin/_macros.html:217 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_stats_1440.png` |
| Nội dung trang chủ | Số tab con | 3 | 7: thêm Về chúng tôi, Tại sao chọn, Loại bonus, Liên hệ | Lớn | B | Brief mục 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Nội dung trang chủ > Section | Khối "Tiêu đề các section có dữ liệu" | Không có, trang cao 630px | Thêm khối cao 505px dưới danh sách section, có nút Lưu riêng | Vừa | B | Brief mục 12 yêu cầu sửa được chữ; vị trí do dev chọn. templates/admin/home.html:34-46 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Nội dung trang chủ > Section | Mũi tên dòng đầu, dòng cuối | Luôn đủ 20 nút, bấm không tác dụng | Ẩn nút, còn 18, để chỗ trống | Nhỏ | C | templates/admin/home.html:25 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Nội dung trang chủ > Section | Câu mô tả | "Dùng mũi tên để đổi thứ tự." | Thêm câu về section tự ẩn | Nhỏ | C | templates/admin/home.html:19 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Nội dung trang chủ > Section | Sau khi bấm mũi tên (công tắc cùng cơ chế, chưa đo riêng) | Giữ nguyên vị trí cuộn | Tải lại, cuộn về đầu: scrollY 457→0 (đo ở cửa sổ cao 500px) | Vừa | A | Khôi phục cuộn hoặc đổi sang fetch; templates/admin/home.html:26 và static/js/admin.js | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Nội dung trang chủ > Section | Section đang tắt | Chỉ công tắc tắt | Chữ xám, gạch ngang | Nhỏ | C | static/css/admin.css:362 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_sections_1440.png` |
| Nội dung trang chủ > Hero | Bố cục | 1 cột 760px | Form 700px + cột "Xem trước" 380px | Vừa | B | Brief mục 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Nội dung trang chủ > Hero | Ô Nhãn nhỏ, Chữ trên nút | Textarea 1 dòng, kéo giãn được | Input thường | Nhỏ | C | templates/admin/home.html:59,62 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Nội dung trang chủ > Hero | Cao textarea | 58 và 76px (line-height normal) | 64 và 85px (line-height 1.5) | Nhỏ | A | static/css/admin.css:270 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Nội dung trang chủ > Hero | Ô "Nhãn thẻ bonus nổi bật" | Không có | Thêm | Nhỏ | B | Brief mục 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Nội dung trang chủ > Hero | Ảnh nền | Trong cùng thẻ; vùng kéo thả viền đứt cao 160px, rộng hết form | Thẻ riêng; ảnh nhỏ 160x90, ô đường dẫn, nút Chọn từ thư viện, Tải ảnh mới, Bỏ ảnh; nhãn đổi thành "Ảnh nền" | Vừa | B | Brief mục 12 (Thư viện ảnh); templates/admin/_macros.html:107-127 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Trang chủ, Cài đặt | Nút lưu đáy form | Không có | Thanh dính đáy màn hình, che một phần nội dung khi cuộn | Vừa | B | Brief mục 12; static/css/admin.css:329-332 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_hero_1440.png` |
| Nội dung trang chủ > Menu | Dòng menu chính | Số thứ tự 01–06 + 2 ô 330px | Bỏ số; thêm tiêu đề cột, nút ↑ ↓ ✕, "+ Thêm mục menu"; ô 266px | Vừa | C | templates/admin/home.html:159 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_menu_1440.png` |
| Nội dung trang chủ > Menu | Màu chữ ô đường dẫn | #4B5B66 | #021623 | Nhỏ | A | static/css/admin.css:291 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_menu_1440.png` |
| Nội dung trang chủ > Menu | Nội dung tab | 1 thẻ: menu + cảnh báo rủi ro, cao 511px | 4 thẻ, tổng 2178px: Menu, Chân trang, Ghi chú dưới nút, Cột link chân trang; cảnh báo rủi ro chuyển sang thẻ Chân trang | Lớn | B | Brief mục 12 (footer); templates/admin/home.html:157-182 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\home_menu_1440.png` |
| Bài viết | Ô tìm kiếm | Không có, bảng ở y182 | Thêm hàng tìm kiếm, bảng ở y236 | Vừa | C | Xóa templates/admin/posts.html:8-13 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Cột thao tác và nút Sửa, nút Thêm | 5 cột, không có sửa, không có thêm | 6 cột: thêm cột Sửa và "+ Thêm bài viết" | Vừa | B | Dữ liệu do admin nhập (brief mục 1, 7) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Nút ↗ từng dòng | Không có | Thêm cho bài đã đăng | Nhỏ | C | templates/admin/posts.html:26 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Tiêu đề dài | Hiện đủ, cột 578px | Bị cắt "…" ở 1440, cột 452px | Vừa | A | templates/admin/posts.html:5,19 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Cao dòng | 51px | 59–60px (do nút) | Nhỏ | C | Hệ quả cột thao tác; static/css/admin.css:188 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Thứ tự | Nháp ở cuối | Nháp lên đầu | Nhỏ | C | app/routes/admin_data.py:493 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Chuyên mục thứ 4 | "Tin tức" | "Tin sàn" | Nhỏ | B | Brief mục 6 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Bài viết | Số lượt xem dưới tiêu đề | Không có | Hiện khi views > 0 (đọc từ code, dữ liệu so sánh bằng 0) | Nhỏ | C | templates/admin/posts.html:20 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\posts_all_1440.png` |
| Người đăng ký > Danh sách | Hàng lọc và tìm | Không có, bảng ở y182 | Thêm 4 pill trạng thái + ô tìm, bảng ở y236 | Vừa | C | Xóa templates/admin/subscribers.html:68-77 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_list_1440.png` |
| Người đăng ký > Danh sách | Cột bảng | 4: Họ tên, Email, Quan tâm, Ngày | 6: thêm Trạng thái và cột nút Xóa; dòng 47→59px; Email, Quan tâm 367→256px | Vừa | C | templates/admin/subscribers.html:66,80,86,88 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_list_1440.png` |
| Gửi email | Nhóm chọn sẵn | 1 nhóm chọn sẵn | Không chọn; không chọn nghĩa là tất cả; thêm chữ giải thích và số đếm trong pill | Vừa | C | templates/admin/subscribers.html:14,17 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Ô Tiêu đề | 45px, 15px, padding 12/14 | 40px, 14px, padding 10/12. Lỗi CSS: .field .input-lg yếu hơn .field input[type=text] nên không có hiệu lực; ô Nội dung vẫn đúng 15px | Vừa | A | static/css/admin.css:313 đổi thành .field input.input-lg | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Nút "Lưu nháp" | Không có | Thêm thứ 3. Ban đầu thay cho "Gửi thử cho tôi" (docs/ISSUES.md:76), Gửi thử trả lại nhưng Lưu nháp vẫn giữ | Vừa | C | templates/admin/subscribers.html:32 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Bảng "Lịch sử gửi" | Không có | Thêm bảng 6 cột dưới form | Vừa | C | templates/admin/subscribers.html:39-62 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Câu hướng dẫn dưới Nội dung | Không có | Thêm; nút tụt xuống | Nhỏ | C | templates/admin/subscribers.html:27 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Nút "Gửi thử cho tôi" | 140x44, 500, padding 13/22, #000 | 155x46, 600, padding 13/26, #021623 | Nhỏ | A | templates/admin/subscribers.html:33; static/css/admin.css:134 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Nút "Gửi tới N người" | 172x42, không viền | 155x46, viền 1px | Nhỏ | A | static/css/admin.css:98,134 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Gửi email | Trước khi gửi | Gửi ngay | Hộp xác nhận (đọc từ code, không bấm vì không được gửi email) | Nhỏ | C | templates/admin/subscribers.html:35 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Cài đặt | Số tab con | 3 | 5: thêm Mạng xã hội, Tracking | Vừa | B | Brief mục 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_general_1440.png` |
| Cài đặt > Chung | Bố cục | 1 thẻ không tiêu đề, padding 28, cao 286px | 3 thẻ có tiêu đề, padding 24, tổng 883px; Email liên hệ chia 2 cột | Lớn | C | templates/admin/settings.html:65-82 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_general_1440.png` |
| Cài đặt > Chung | Trường thêm | 3 trường | Thêm Email hợp tác, Logo, Favicon | Vừa | B | Brief mục 6, 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_general_1440.png` |
| Cài đặt > Chung, SEO | Ô nhập | Textarea 45px, 15px, padding 12/14 | Input 40px, 14px, padding 10/12 | Vừa | A | Thêm rule riêng cho form Cài đặt như .drawer ở static/css/admin.css:280-281 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_general_1440.png` |
| Cài đặt > Chung | Dấu * bắt buộc ở Tên website | Không có | Có | Nhỏ | C | templates/admin/settings.html:67 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_general_1440.png` |
| Cài đặt > SEO | Bố cục | 1 cột 760px | Form 700px + cột xem trước kết quả Google | Vừa | B | Brief mục 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_seo_1440.png` |
| Cài đặt > SEO | Ảnh chia sẻ | Vùng kéo thả 380x200 trong cùng thẻ | Thẻ riêng; ảnh nhỏ 160x84 + ô đường dẫn + nút | Vừa | B | Brief mục 12 (Thư viện ảnh) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_seo_1440.png` |
| Cài đặt > SEO | Gợi ý dưới ô | Không có | "Nên dưới 60 ký tự"… | Nhỏ | C | templates/admin/settings.html:87-89 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_seo_1440.png` |
| Cài đặt > Tài khoản | Cột bảng | 4: Tên, Email, Vai trò, Đăng nhập | 6: Email, Vai trò / mật khẩu mới, Trạng thái, Đăng nhập, Hoạt động, cột Xóa | Lớn | C | templates/admin/settings.html:11,15 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_users_1440.png` |
| Cài đặt > Tài khoản | Cột Tên | Có | Bỏ vì AdminUser không có tên | Vừa | B | Brief mục 6; muốn có phải thêm cột DB | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_users_1440.png` |
| Cài đặt > Tài khoản | Sửa trong dòng | Chỉ xem | Select vai trò, ô mật khẩu mới, nút Lưu, công tắc, nút Xóa | Lớn | C | templates/admin/settings.html:21-37 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_users_1440.png` |
| Cài đặt > Tài khoản | Dưới bảng | Không có | Thêm câu ghi chú và form "Thêm tài khoản quản trị" | Vừa | C | templates/admin/settings.html:45-56 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_users_1440.png` |
| Cài đặt > Tài khoản | Định dạng Đăng nhập | "Hôm nay", 01/11/2026 | 05/11/2026 13:49 | Nhỏ | C | templates/admin/settings.html:34 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\set_users_1440.png` |
| Drawer Sửa bonus | Thứ tự trường | Sàn, Tiêu đề, Mức, Nạp, Hết hạn, Loại bonus (cuối) | Sàn, Loại bonus (lên thứ 2), Tiêu đề… | Vừa | C | templates/admin/bonus.html:52 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer Sửa bonus | Bố cục ô | Mọi ô 1 cột 424px | Có hàng 2 cột 204px | Vừa | C | templates/admin/bonus.html:54-61 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer Sửa bonus | Trường thêm | 5 ô + loại | Thêm Giá trị để sắp xếp, Phần rút được, công tắc Hiển thị | Vừa | B | Brief mục 6 (value_num, withdrawable, is_active) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer Sửa bonus | Ô Sàn, ô Hết hạn | Ô chữ tự do | Select sàn; ô ngày (trống = Liên tục) | Vừa | B | Brief mục 6 (broker_id, expiry_date) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer | Chân drawer | Không viền; Lưu 340x47; chữ "Xoá" | Có viền trên; Lưu 338x49; chữ "Xóa" | Nhỏ | C | static/css/admin.css:382,98; templates/admin/_base.html:87 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer | Đổ bóng | Không có | box-shadow lớn | Nhỏ | C | static/css/admin.css:377 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer | Đóng drawer | Giữ nguyên tab và lọc | ✕, overlay, Esc đều về /admin/bonus: mất tab=off và type (cùng kiểu ở các drawer khác) | Vừa | A | close_url ở templates/admin/bonus.html:3, brokers.html:3, ads.html:3, posts.html:3 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer | Cách mở | Mở tại chỗ | Tải trang mới /admin/bonus/{id}/edit | Nhỏ | B | Brief mục 7 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer | Esc | Không đóng | Đóng, có hỏi nếu đã đổi; focus vào ô đầu (viền đậm) | Nhỏ | C | static/js/admin.js:111-118 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer | Xóa | Xóa ngay | Có hộp xác nhận | Nhỏ | C | templates/admin/_base.html:90 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_1440.png` |
| Drawer Sửa sàn | Số trường | 6 ô, không phải cuộn | 7 nhóm, form cao hơn 1700px, phải cuộn | Lớn | B | Brief mục 6; templates/admin/brokers.html:61-104 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_broker_edit_1440.png` |
| Drawer Sửa sàn | "Xem trên site ↗" ở đầu drawer | Không có | Có | Nhỏ | B | Brief mục 12 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_broker_edit_1440.png` |
| Gửi email | Số trên nút Gửi | "Gửi tới 260 người" (công thức mock) | "Gửi tới 4 người" (số thật) | Nhỏ | D | Không sửa | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_1440.png` |
| Quảng cáo > Banner | Nội dung ô ảnh | Ô chờ ảnh | Khi có ảnh, ô đúng tỉ lệ 970/250, ảnh cắt cover (thử bằng logo) | Nhỏ | D | Không sửa | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_img_1440.png` |
| Sàn > Danh sách | Link affiliate, số click theo sàn | Số giả | Số trong DB tạm | Nhỏ | D | Không sửa | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\brokers_links_1440.png` |
| Quảng cáo > Banner | Cách hiện ngày trong ô date | — | mm/dd/yyyy do trình duyệt headless tiếng Anh; máy tiếng Việt có thể khác | Nhỏ | D | Không sửa; muốn cố định dd/mm phải dùng ô chữ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_1440.png` |

## Khác biệt khi DB rỗng (tách riêng)

Thiết kế không có trạng thái rỗng nào. Ảnh ghép đặt thiết kế (có dữ liệu mẫu) cạnh bản dựng DB rỗng, chỉ để đối chiếu khung.

| Màn | Vị trí | Thiết kế gốc | Bản dựng | Mức độ | Loại | Cách sửa (file:dòng) | Ảnh ghép |
|---|---|---|---|---|---|---|---|
| Tổng quan | Thẻ thống kê khi bằng 0 | Thiết kế không có trạng thái rỗng; brief mục 5: số 0 thì ẩn | Hiện "—" cỡ 36px ở cả 5 thẻ | Vừa | C | templates/admin/overview.html:9 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_empty_1440.png` |
| Tổng quan | Thẻ Banner quảng cáo | Luôn có thẻ | Ẩn cả thẻ khi chưa có banner; biểu đồ chiếm cả hàng | Nhỏ | C | templates/admin/overview.html:32,55 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_empty_1440.png` |
| Tổng quan | Bonus sắp hết hạn | Không có câu rỗng | "Không có bonus nào hết hạn trong 14 ngày tới." (nêu ngưỡng tự đặt) | Nhỏ | C | templates/admin/overview.html:29 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_empty_1440.png` |
| Sidebar | Số đếm | Không có trạng thái rỗng | Ẩn số 0, đúng brief | Nhỏ | B | Brief mục 5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_empty_1440.png` |
| Bonus | Khi chưa có sàn | Không có | Dải "Chưa có sàn nào. Thêm sàn trước khi thêm bonus." viền xanh; bảng còn tiêu đề + "Chưa có bonus nào." | Nhỏ | B | Brief mục 5; templates/admin/bonus.html:19-21 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_empty_1440.png` |
| Sàn, Quảng cáo, Bài viết | Trạng thái rỗng | Không có | Câu "Chưa có…" + nút "+ Thêm…", trùng nút ở đầu trang | Nhỏ | C | Bỏ nút ở templates/admin/_macros.html:187 hoặc nơi gọi | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_banner_empty_1440.png` |
| Quảng cáo > Thống kê | Rỗng | Không có | Bảng còn tiêu đề + câu rỗng; biểu đồ thay bằng câu rỗng | Nhỏ | B | Brief mục 5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\ads_stats_empty_1440.png` |
| Người đăng ký > Danh sách | Rỗng | Không có | Pill, ô tìm, tiêu đề cột vẫn hiện + câu rỗng | Nhỏ | B | Brief mục 5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_list_empty_1440.png` |
| Gửi email | Nút gửi khi chưa có người nhận | Không có | Nút mờ "Chưa có người nhận", không bấm được | Nhỏ | C | templates/admin/subscribers.html:34-35 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\subs_mail_empty_1440.png` |
| Drawer Thêm bonus | Chưa có sàn | Ô chữ, nhập được | Select rỗng + link "Thêm sàn trước" | Nhỏ | B | Brief mục 6 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_new_empty_1440.png` |

## Phần đã khớp (đo được, lệch dưới 2px hoặc chỉ do font nút)

- Khung: sidebar 248px, nền #021623, padding 24/16, gap 28; main padding 32/40/64; nền #F5F5F5.
- Logo 36px bo 8; tên 15px/700; "Quản trị" 12px #A9B6C1. Menu: padding 11/14, bo 999, 14px/500, mục chọn #1944DF. Nút "Xem trang chủ ↗" đúng hộp 24,806, 200x45; email đúng x24 y861, 12px.
- Breadcrumb 13px #4B5B66; h1 32px/600, -0.02em; hàng tab con cao 44px, viền 0.12, tab 14px 500/600, gạch chân 2px #021623.
- Thẻ thống kê: padding 24, nhãn 13px, số 36px/600, khe 1px. Thẻ danh sách Tổng quan: 2 cột 544px, gap 24, padding 24, tiêu đề 16px/600, dòng 14px, viền 0.08, ngày đỏ #B4232A.
- Bảng: tiêu đề cột 12px in hoa 0.05em, padding 14/20, viền 0.1 và 0.06; tên cột Bonus khớp cả 7. Công tắc 40x22, nút tròn 18, #1944DF và #C9D1D8. Pill padding 8/16, 13px/500, chọn #021623. Nút Sửa padding 6/14, 13px.
- Đúng tên cột: Bonus, Quảng cáo > Thống kê (5 cột). Đúng 4 tab Bonus, 2 tab Sàn, 2 tab Quảng cáo, 3 tab Bài viết, 2 tab Người đăng ký, cùng thứ tự.
- Quảng cáo > Banner: thẻ padding 20, lưới 524+524, gap 24; tiêu đề 17px/600; ô nhập 10/12, 14px; số liệu 13px.
- Thống kê: bảng 5 cột cùng tên; biểu đồ cao 160, 30 cột, gap 4, cột cuối #1944DF; hình dạng trùng khi cùng số liệu.
- Section: thẻ 760px, padding 24, dòng cao 53px, số 01–10, đúng 10 tên section và thứ tự mặc định, nút tròn 32px, đổi thứ tự chạy đúng.
- Gửi email: thẻ 760px, padding 28, placeholder đúng, ô Nội dung 15px. "Gửi thử cho tôi" trong thiết kế là nút chết, bản dựng có route thật.
- Drawer: rộng 480, phủ rgba(2,22,35,.45), padding 28, tiêu đề 22px/600, nút đóng 36px, ô nhập 12/14 15px, nút Lưu xanh và Xóa viền đỏ cùng cỡ chữ.
- Số liệu 7/8, 2, 409, 4 và số dòng các tab Bonus Tất cả, Đang hiển thị, Đã ẩn khớp. Lọc theo loại, tìm, công tắc, giới hạn 3 sàn so sánh chạy đúng ý nghĩa.

## Ghi nhận ở rộng 390 (không tính khác biệt)

Thiết kế không responsive: sidebar 248px cố định, trang tràn ngang 451–648px, có màn nội dung gần như không đọc được. Bản dựng tự làm responsive: menu burger, không tràn ngang (scrollWidth 390 ở cả 24 màn). Đây là phần thêm tốt, đúng brief mục 4.

Ảnh: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\bonus_all_390.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\overview_390.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs\drawer_bonus_edit_390.png`.

## Chưa so được

- Hành vi sau khi gửi email và gửi thử: không bấm vì không được gửi email. Dòng "Đã gửi tới N người" của thiết kế chưa đối chiếu bằng mắt.
- Dải tin nhắn chưa đọc, lượt xem bài viết, trạng thái lỗi form: chỉ đọc code.
- Các màn mới (Trang, Thư viện ảnh, Tin nhắn, Đăng nhập, tab Về chúng tôi, Tại sao chọn, Loại bonus, Liên hệ, Mạng xã hội, Tracking): không có bản gốc, chưa soi phong cách từng màn.
- Kéo thả ảnh của image-slot trong thiết kế: bản dựng không dùng runtime này.
- Màn hình cao khác 900 và Windows khác font hệ thống: Arial ở phía thiết kế có thể đổi.

## Vòng 2 (đo lại trên commit 272be90, theo TEAM_BRIEF mục 13)

Tự đo ngày 06/11/2026 ở 1440x900 và 390, cả DB có dữ liệu và DB rỗng, không dựa vào báo cáo dev. Mục 13: mọi khác biệt ngoài danh sách GIỮ là lỗi. Ảnh ghép vòng 2 nằm ở thư mục tạm `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\`. Các dòng ghi "cần user xác nhận" là tôi suy ra, mục 13 không nêu rõ.

**Dòng cũ (136):** 87 đã khôi phục, 17 được phép, 32 còn lệch. **Khác biệt mới:** 10. **Tổng còn lệch: 42** (Lớn 2, Vừa 17, Nhỏ 23).

Dev ghi ở docs/ISSUES.md "Đã xử lý mọi dòng A, C". Đo thực tế không đúng như vậy: nhiều dòng chỉ chuyển chỗ, và một số được ghi là "user quyết" trong khi chưa nằm trong danh sách GIỮ.

### Trạng thái từng dòng cũ

| # | Màn | Vị trí | Trạng thái | Mức còn lại | Ghi chú | Ảnh ghép |
|---|---|---|---|---|---|---|
| 1 | Sidebar | Nhóm menu | ĐÃ KHÔI PHỤC | | | |
| 2 | Sidebar | Thứ tự mục | ĐÃ KHÔI PHỤC | | | |
| 3 | Sidebar | Số mục | ĐƯỢC PHÉP (mục 13) | | Mục mới đặt sau 8 mục gốc, đúng mục 13 | |
| 4 | Sidebar | Nhãn mục | ĐÃ KHÔI PHỤC | | | |
| 5 | Toàn admin | Font của mọi nút: menu, tab con, pill, Thêm, Sửa, Lưu | CÒN | Nhỏ | Vẫn Be Vietnam Pro. Chiều cao đã đúng (menu 38px, nút 40 và 42px) nhưng rộng hơn: "Xuất bản thay đổi" 163→170px, "Gửi thử" 139.5→146px | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\bonus_all_1440.png` |
| 6 | Sidebar | Chiều cao dòng menu | ĐÃ KHÔI PHỤC | | | |
| 7 | Sidebar | Số đếm trên mục đang chọn | ĐÃ KHÔI PHỤC | | | |
| 8 | Sidebar | Hover mục menu | ĐÃ KHÔI PHỤC | | | |
| 9 | Sidebar | Khối logo | ĐÃ KHÔI PHỤC | | | |
| 10 | Sidebar | Cuối sidebar | CÒN | Nhỏ | Link "Đăng xuất" vẫn cùng hàng email. Không có trong GIỮ nhưng cần để đăng xuất; cần user xác nhận | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_1440.png` |
| 11 | Sidebar | Giá trị email | ĐƯỢC PHÉP (mục 13) | | Không còn email demo | |
| 12 | Sidebar | "Xem trang chủ ↗" | ĐÃ KHÔI PHỤC | | | |
| 13 | Sidebar | Số đếm Người đăng ký | ĐÃ KHÔI PHỤC | | | |
| 14 | Đầu trang | Nút "Xuất bản thay đổi" trên Tổng quan, Bonus, Sàn, Quảng cáo, Bài viết, Người đăng ký, Tài khoản | ĐÃ KHÔI PHỤC | | | |
| 15 | Đầu trang | Ý nghĩa "Xuất bản thay đổi" | CÒN | Vừa | Vẫn không có nháp hay xuất bản. Màn form: trùng hẳn "Lưu thay đổi". Tab Section: chỉ lưu tiêu đề section. Xem mục kiểm tra nút Xuất bản | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_sections_1440.png` |
| 16 | Đầu trang | Hộp nút "+ Thêm" | ĐÃ KHÔI PHỤC | | | |
| 17 | Đầu trang | Cao h1 | ĐÃ KHÔI PHỤC | | | |
| 18 | Đầu trang | "+ Thêm banner" | ĐƯỢC PHÉP (mục 13) | | Suy ra từ "thay bằng dữ liệu DB": phải có chỗ thêm dữ liệu. Áp dụng cả "+ Thêm bài viết". Cần user xác nhận | |
| 19 | Đầu trang | "Xem trên site ↗" | CÒN | Nhỏ | Còn "Xem trên site ↗" ở đầu trang trên tab gốc Section, Hero, Menu | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_hero_1440.png` |
| 20 | Toàn admin | Màu xanh trạng thái ("Đã lưu", "Đã đăng") | ĐÃ KHÔI PHỤC | | | |
| 21 | Toàn admin | Rê chuột dòng bảng | ĐÃ KHÔI PHỤC | | | |
| 22 | Tổng quan | Số thẻ thống kê | ĐÃ KHÔI PHỤC | | | |
| 23 | Tổng quan | Thẻ "Sàn nhiều click nhất" | ĐÃ KHÔI PHỤC | | | |
| 24 | Tổng quan | Biểu đồ "Click theo ngày" | ĐÃ KHÔI PHỤC | | | |
| 25 | Tổng quan | Thẻ "Bonus sắp hết hạn" | ĐÃ KHÔI PHỤC | | | |
| 26 | Tổng quan | Số dòng và thứ tự bonus sắp hết hạn | ĐÃ KHÔI PHỤC | | | |
| 27 | Tổng quan | Nhãn thẻ 3 | ĐÃ KHÔI PHỤC | | | |
| 28 | Tổng quan | Định dạng số thẻ thống kê | ĐÃ KHÔI PHỤC | | | |
| 29 | Tổng quan | Dòng banner | ĐÃ KHÔI PHỤC | | | |
| 30 | Tổng quan | Link ở tiêu đề thẻ | ĐÃ KHÔI PHỤC | | | |
| 31 | Tổng quan | Ngày hết hạn | ĐÃ KHÔI PHỤC | | | |
| 32 | Tổng quan, Quảng cáo | Dấu thập phân CTR | ĐÃ KHÔI PHỤC | | | |
| 33 | Tổng quan | Dải thông báo tin nhắn chưa đọc | ĐÃ KHÔI PHỤC | | | |
| 34 | Bonus | Tab "Sắp hết hạn" | ĐÃ KHÔI PHỤC | | | |
| 35 | Bonus | Lọc và tìm khi đổi tab con | ĐÃ KHÔI PHỤC | | | |
| 36 | Bonus | Ô tìm kiếm | ĐÃ KHÔI PHỤC | | | |
| 37 | Bonus | Hộp ô tìm kiếm | ĐÃ KHÔI PHỤC | | | |
| 38 | Bonus | Cột bảng | ĐÃ KHÔI PHỤC | | | |
| 39 | Bonus | Ngày ở cột Hết hạn | ĐÃ KHÔI PHỤC | | | |
| 40 | Bonus | Nút Sửa | ĐÃ KHÔI PHỤC | | | |
| 41 | Bonus | Dòng đang ẩn | ĐÃ KHÔI PHỤC | | | |
| 42 | Bonus | Cảnh báo trong ô Tiêu đề, ngày đỏ | ĐÃ KHÔI PHỤC | | | |
| 43 | Bonus | Tiêu đề bonus | ĐÃ KHÔI PHỤC | | | |
| 44 | Bonus | Công tắc | CÒN | Nhỏ | Vẫn POST rồi tải lại, báo "Đã cập nhật". Cuộn đã giữ được | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\bonus_all_1440.png` |
| 45 | Sàn > Danh sách | Cột bảng | ĐÃ KHÔI PHỤC | | | |
| 46 | Sàn > Danh sách | Ô tên sàn | ĐÃ KHÔI PHỤC | | | |
| 47 | Sàn > Danh sách | Thứ tự sàn | ĐÃ KHÔI PHỤC | | | |
| 48 | Sàn > Danh sách | Câu ghi chú | ĐÃ KHÔI PHỤC | | | |
| 49 | Sàn > Link affiliate | Cột thứ 4 | ĐƯỢC PHÉP (mục 13) | | Tên cột đã đúng; ô luôn "—" vì sàn không báo số đăng ký | |
| 50 | Sàn > Link affiliate | Câu ghi chú trên bảng | ĐÃ KHÔI PHỤC | | | |
| 51 | Sàn > Link affiliate | Lưu link | ĐÃ KHÔI PHỤC | | | |
| 52 | Sàn > Link affiliate | Độ rộng cột | ĐÃ KHÔI PHỤC | | | |
| 53 | Sàn > Danh sách | Bật So sánh sàn thứ 4 | ĐƯỢC PHÉP (mục 13) | | Logic chặn ở server, chỉ hiện khi vi phạm | |
| 54 | Quảng cáo > Banner | Ô chạy từ – đến | ĐÃ KHÔI PHỤC | | | |
| 55 | Quảng cáo > Banner | Tiêu đề thẻ | ĐÃ KHÔI PHỤC | | | |
| 56 | Quảng cáo > Banner | Nhãn ô link | ĐÃ KHÔI PHỤC | | | |
| 57 | Quảng cáo > Banner | Chân thẻ | CÒN | Nhỏ | Bỏ nút Lưu; còn link "Sửa" xanh cuối dòng số liệu | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\ads_banner_1440.png` |
| 58 | Quảng cáo > Banner | Ô ảnh khi chưa có ảnh | ĐÃ KHÔI PHỤC | | | |
| 59 | Quảng cáo > Banner | Khoảng cách giữa các thẻ | ĐÃ KHÔI PHỤC | | | |
| 60 | Quảng cáo > Banner | Vị trí banner | ĐƯỢC PHÉP (mục 13) | | Suy ra từ placement cột hero của public. Cần user xác nhận | |
| 61 | Quảng cáo > Thống kê | Ô Banner | ĐÃ KHÔI PHỤC | | | |
| 62 | Quảng cáo > Thống kê | Hàng "Tổng" | ĐÃ KHÔI PHỤC | | | |
| 63 | Quảng cáo > Thống kê | Cột Trạng thái | ĐÃ KHÔI PHỤC | | | |
| 64 | Quảng cáo > Thống kê | Trục biểu đồ | ĐÃ KHÔI PHỤC | | | |
| 65 | Nội dung trang chủ | Số tab con | ĐƯỢC PHÉP (mục 13) | | Tab mới mục 12 | |
| 66 | Nội dung trang chủ > Section | Khối "Tiêu đề các section có dữ liệu" | CÒN | Vừa | Khối tiêu đề và nút "Lưu thay đổi" vẫn nằm dưới danh sách section, trang cao 900→1393px | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_sections_1440.png` |
| 67 | Nội dung trang chủ > Section | Mũi tên dòng đầu, dòng cuối | ĐÃ KHÔI PHỤC | | | |
| 68 | Nội dung trang chủ > Section | Câu mô tả | ĐÃ KHÔI PHỤC | | | |
| 69 | Nội dung trang chủ > Section | Sau khi bấm mũi tên (công tắc cùng cơ chế, chưa đo riêng) | ĐÃ KHÔI PHỤC | | | |
| 70 | Nội dung trang chủ > Section | Section đang tắt | ĐÃ KHÔI PHỤC | | | |
| 71 | Nội dung trang chủ > Hero | Bố cục | CÒN | Vừa | Form vẫn 700px (ô 712→652px) + cột Xem trước | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_hero_1440.png` |
| 72 | Nội dung trang chủ > Hero | Ô Nhãn nhỏ, Chữ trên nút | ĐÃ KHÔI PHỤC | | | |
| 73 | Nội dung trang chủ > Hero | Cao textarea | ĐÃ KHÔI PHỤC | | | |
| 74 | Nội dung trang chủ > Hero | Ô "Nhãn thẻ bonus nổi bật" | CÒN | Nhỏ | Ô thêm vẫn có | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_hero_1440.png` |
| 75 | Nội dung trang chủ > Hero | Ảnh nền | CÒN | Vừa | Vẫn thẻ riêng, ảnh nhỏ, ô đường dẫn, 2 nút; không còn vùng 160px trong thẻ gốc | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_hero_1440.png` |
| 76 | Trang chủ, Cài đặt | Nút lưu đáy form | CÒN | Vừa | Thanh "Lưu thay đổi" dính đáy vẫn có ở Hero, Menu, SEO, Chung. Trùng nút Xuất bản | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_menu_1440.png` |
| 77 | Nội dung trang chủ > Menu | Dòng menu chính | CÒN | Vừa | Số 01–06 đã về; ô 330→300px, y+2; thêm ↑ ↓ ✕ hiện khi rê hoặc focus và "+ Thêm mục menu", đẩy cảnh báo rủi ro y593→635 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_menu_1440.png` |
| 78 | Nội dung trang chủ > Menu | Màu chữ ô đường dẫn | ĐÃ KHÔI PHỤC | | | |
| 79 | Nội dung trang chủ > Menu | Nội dung tab | CÒN | Lớn | Cảnh báo rủi ro đã về thẻ Menu, nhưng còn 3 thẻ thêm; trang cao 900→2385px | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\home_menu_1440.png` |
| 80 | Bài viết | Ô tìm kiếm | CÒN | Nhỏ | Hàng tìm đã bỏ, bảng về y182; đổi thành nút "Lọc" cuối hàng tab, không có trong thiết kế | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\posts_all_1440.png` |
| 81 | Bài viết | Cột thao tác và nút Sửa, nút Thêm | ĐƯỢC PHÉP (mục 13) | | Cột đã về 5. Cần chỗ sửa bài; nút Sửa nay hiện khi rê, xem MỚI 1 | |
| 82 | Bài viết | Nút ↗ từng dòng | ĐÃ KHÔI PHỤC | | | |
| 83 | Bài viết | Tiêu đề dài | ĐÃ KHÔI PHỤC | | | |
| 84 | Bài viết | Cao dòng | ĐÃ KHÔI PHỤC | | | |
| 85 | Bài viết | Thứ tự | ĐÃ KHÔI PHỤC | | | |
| 86 | Bài viết | Chuyên mục thứ 4 | CÒN | Nhỏ | Vẫn "Tin sàn" theo brief mục 6, thiết kế là "Tin tức" | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\posts_all_1440.png` |
| 87 | Bài viết | Số lượt xem dưới tiêu đề | ĐÃ KHÔI PHỤC | | | |
| 88 | Người đăng ký > Danh sách | Hàng lọc và tìm | CÒN | Nhỏ | Hàng lọc đã bỏ; đổi thành nút "Lọc" cuối hàng tab | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\subs_list_1440.png` |
| 89 | Người đăng ký > Danh sách | Cột bảng | ĐÃ KHÔI PHỤC | | | |
| 90 | Gửi email | Nhóm chọn sẵn | ĐÃ KHÔI PHỤC | | | |
| 91 | Gửi email | Ô Tiêu đề | ĐÃ KHÔI PHỤC | | | |
| 92 | Gửi email | Nút "Lưu nháp" | ĐÃ KHÔI PHỤC | | | |
| 93 | Gửi email | Bảng "Lịch sử gửi" | CÒN | Nhỏ | Bảng đã bỏ; đổi thành link "Lịch sử gửi" cạnh hai nút, mở drawer | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\subs_mail_1440.png` |
| 94 | Gửi email | Câu hướng dẫn dưới Nội dung | ĐÃ KHÔI PHỤC | | | |
| 95 | Gửi email | Nút "Gửi thử cho tôi" | ĐÃ KHÔI PHỤC | | | |
| 96 | Gửi email | Nút "Gửi tới N người" | ĐÃ KHÔI PHỤC | | | |
| 97 | Gửi email | Trước khi gửi | CÒN | Nhỏ | Vẫn hộp xác nhận (đọc từ code; ghi ở docs/ISSUES.md là chờ user quyết) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\subs_mail_1440.png` |
| 98 | Cài đặt | Số tab con | ĐƯỢC PHÉP (mục 13) | | Tab mới mục 12; tab gốc đứng trước | |
| 99 | Cài đặt > Chung | Bố cục | ĐÃ KHÔI PHỤC | | | |
| 100 | Cài đặt > Chung | Trường thêm | ĐƯỢC PHÉP (mục 13) | | Đã chuyển sang tab mới Thương hiệu; tab Chung còn đúng 3 ô | |
| 101 | Cài đặt > Chung, SEO | Ô nhập | CÒN | Nhỏ | Cỡ đã đúng 45px, 15px; nhưng là input, không phải textarea có tay kéo như thiết kế | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_general_1440.png` |
| 102 | Cài đặt > Chung | Dấu * bắt buộc ở Tên website | ĐÃ KHÔI PHỤC | | | |
| 103 | Cài đặt > SEO | Bố cục | CÒN | Vừa | Form vẫn 700px (ô 704→644px) + cột xem trước Google | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_seo_1440.png` |
| 104 | Cài đặt > SEO | Ảnh chia sẻ | CÒN | Vừa | Đã về cùng thẻ, nhưng vẫn ảnh nhỏ + ô đường dẫn + nút, không phải vùng 380x200 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_seo_1440.png` |
| 105 | Cài đặt > SEO | Gợi ý dưới ô | ĐÃ KHÔI PHỤC | | | |
| 106 | Cài đặt > Tài khoản | Cột bảng | ĐÃ KHÔI PHỤC | | | |
| 107 | Cài đặt > Tài khoản | Cột Tên | CÒN | Vừa | Cột đã về, luôn hiện "—" vì không có trường tên | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_users_1440.png` |
| 108 | Cài đặt > Tài khoản | Sửa trong dòng | CÒN | Nhỏ | Bảng đã chỉ xem; thêm nút "Sửa" hiện khi rê dòng, mở drawer | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_users_1440.png` |
| 109 | Cài đặt > Tài khoản | Dưới bảng | CÒN | Nhỏ | Ghi chú và form đã bỏ khỏi trang; thêm nút "+ Thêm tài khoản" cuối hàng tab | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_users_1440.png` |
| 110 | Cài đặt > Tài khoản | Định dạng Đăng nhập | ĐÃ KHÔI PHỤC | | | |
| 111 | Drawer Sửa bonus | Thứ tự trường | ĐÃ KHÔI PHỤC | | | |
| 112 | Drawer Sửa bonus | Bố cục ô | ĐÃ KHÔI PHỤC | | | |
| 113 | Drawer Sửa bonus | Trường thêm | CÒN | Vừa | Thứ tự 5 ô đầu đã đúng; vẫn thêm Giá trị sắp xếp, Phần rút được, công tắc, dấu * | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_bonus_edit_1440.png` |
| 114 | Drawer Sửa bonus | Ô Sàn, ô Hết hạn | CÒN | Vừa | Vẫn select và ô ngày; ô cao 47px làm các ô dưới lệch 2px | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_bonus_edit_1440.png` |
| 115 | Drawer | Chân drawer | ĐÃ KHÔI PHỤC | | | |
| 116 | Drawer | Đổ bóng | ĐÃ KHÔI PHỤC | | | |
| 117 | Drawer | Đóng drawer | ĐÃ KHÔI PHỤC | | | |
| 118 | Drawer | Cách mở | CÒN | Nhỏ | Vẫn tải trang mới, nhìn giống nhau | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_bonus_edit_1440.png` |
| 119 | Drawer | Esc | CÒN | Nhỏ | Vẫn Esc đóng, có hỏi nếu đã đổi. Focus ô đầu đã bỏ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_bonus_edit_1440.png` |
| 120 | Drawer | Xóa | CÒN | Nhỏ | Vẫn hộp xác nhận | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_bonus_edit_1440.png` |
| 121 | Drawer Sửa sàn | Số trường | CÒN | Lớn | Vẫn 7 nhóm, form rất dài, các ô gốc bị xáo: Giấy phép y162→835 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_broker_edit_1440.png` |
| 122 | Drawer Sửa sàn | "Xem trên site ↗" ở đầu drawer | CÒN | Nhỏ | Vẫn có | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_broker_edit_1440.png` |
| 123 | Gửi email | Số trên nút Gửi | ĐƯỢC PHÉP (mục 13) | | Số thật thay mock | |
| 124 | Quảng cáo > Banner | Nội dung ô ảnh | ĐƯỢC PHÉP (mục 13) | | Ô trống là khối xám, đúng quyết định của user | |
| 125 | Sàn > Danh sách | Link affiliate, số click theo sàn | ĐƯỢC PHÉP (mục 13) | | Số thật thay mock | |
| 126 | Quảng cáo > Banner | Cách hiện ngày trong ô date | ĐÃ KHÔI PHỤC | | | |

### Trạng thái dòng cũ khi DB rỗng

| # | Màn | Vị trí | Trạng thái | Mức còn lại | Ghi chú | Ảnh ghép |
|---|---|---|---|---|---|---|
| R1 | Tổng quan | Thẻ thống kê khi bằng 0 | ĐÃ KHÔI PHỤC |  | Số 0 để trống, giữ khung thẻ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_empty_1440.png` |
| R2 | Tổng quan | Thẻ Banner quảng cáo | ĐÃ KHÔI PHỤC |  | Thẻ luôn hiện, 2 cột như thiết kế | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_empty_1440.png` |
| R3 | Tổng quan | Bonus sắp hết hạn | ĐÃ KHÔI PHỤC |  | Câu không còn nêu ngưỡng | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_empty_1440.png` |
| R4 | Sidebar | Số đếm | ĐƯỢC PHÉP (mục 13) |  | Mục 5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_empty_1440.png` |
| R5 | Bonus | Khi chưa có sàn | ĐƯỢC PHÉP (mục 13) |  | Mục 5: dải nhắc thêm sàn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\bonus_all_empty_1440.png` |
| R6 | Sàn, Quảng cáo, Bài viết | Trạng thái rỗng | ĐÃ KHÔI PHỤC |  | Đã bỏ nút Thêm trùng | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\ads_banner_empty_1440.png` |
| R7 | Quảng cáo > Thống kê | Rỗng | ĐƯỢC PHÉP (mục 13) |  | Mục 5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\ads_stats_empty_1440.png` |
| R8 | Người đăng ký > Danh sách | Rỗng | ĐÃ KHÔI PHỤC |  | Pill và ô tìm đã vào drawer Lọc | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\subs_list_empty_1440.png` |
| R9 | Gửi email | Nút gửi khi chưa có người nhận | CÒN | Nhỏ | Nút mờ "Chưa có người nhận" vẫn có. Mức Nhỏ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\subs_mail_empty_1440.png` |
| R10 | Drawer Thêm bonus | Chưa có sàn | ĐƯỢC PHÉP (mục 13) |  | Hệ quả select sàn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\drawer_bonus_new_empty_1440.png` |

### Khác biệt MỚI (đều là loại A)

| # | Màn | Vị trí | Thiết kế gốc | Bản dựng | Mức độ | Cách sửa (file:dòng) | Ảnh ghép |
|---|---|---|---|---|---|---|---|
| MỚI 1 | Bài viết | Nút "Sửa" hiện khi rê (rê, focus, cảm ứng) | Không có nút | Nút tràn 20px ra ngoài ô, đè 4px chữ đầu cột Chuyên mục ở MỌI dòng ("Hướng dẫn" mất nét đầu); đè tiêu đề dài (26x13px ở 1440). Trên cảm ứng nút hiện thường trực nên đè mọi tiêu đề xuống dòng, tới 20x13px | Vừa | static/css/admin.css:204, chừa chỗ trong ô thay vì right:-20px | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\hover_posts_long_1440.png` |
| MỚI 2 | Người đăng ký | Nút "Xóa" hiện khi rê | Không có nút | Đè 2px chữ ngày ở các ngày rộng (30/10/2026); liền sát chữ ở các dòng khác. Cả 1440 và cảm ứng | Nhỏ | static/css/admin.css:204 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\hover_subs_1440.png` |
| MỚI 3 | Nội dung trang chủ > Menu | Nút ↑ ↓ ✕ khi đang gõ ô đường dẫn | Không có | Nút nổi đè 104x32px lên phần phải ô đang gõ; ô không chừa padding (12px) nên chữ dài bị che ngay lúc nhập | Vừa | static/css/admin.css:296-297 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\menu_focus_long.png` |
| MỚI 4 | Drawer Lọc, Lịch sử gửi, Sửa/Thêm tài khoản | Bàn phím | Drawer gốc không có các màn này | Esc không đóng (drawer dữ liệu thì đóng). Tab đi ra ngoài: sau 3 lần sang sidebar nằm dưới lớp phủ, dù khai aria-modal | Vừa | templates/admin/_macros.html:190; static/js/admin.js:170 chỉ xử lý [data-drawer] | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\set_users_1440.png` |
| MỚI 5 | Thư viện ảnh | Nút Xuất bản | Màn mới | Gõ mô tả ảnh rồi bấm: 0 POST, vẫn báo "Đã lưu"; tải lại thì mất chữ. Báo sai | Vừa | templates/admin/_base.html:52 và static/js/admin.js:79-88; màn có ô chưa lưu không được báo Đã lưu | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_1440.png` |
| MỚI 6 | Gửi email | Nút Xuất bản khi chưa soạn | "Đã lưu" (mock) | Chỉ đổi nhóm rồi bấm: 0 POST, báo "Đã lưu"; tải lại về Deposit bonus. Báo sai | Nhỏ | static/js/admin.js:90-97 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\subs_mail_1440.png` |
| MỚI 7 | Quảng cáo > Banner | Nút Xuất bản khi có banner thiếu link | Lưu được | Một banner "Thiếu link đích" chặn lưu mọi banner, kể cả sửa banner khác. Câu lỗi "Link phải bắt đầu bằng http:// hoặc https://" không nói banner nào. Tái hiện bằng cách xóa link của sàn | Vừa | app/routes/admin_data.py:491 (bỏ qua banner không đổi link, nêu tên banner) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\ads_banner_1440.png` |
| MỚI 8 | Quảng cáo > Banner, Sàn > Link affiliate | Lỗi khi Xuất bản nhiều dòng | Không có | Một ô sai thì mọi ô vừa sửa về giá trị cũ (thử "abc" ở ô ngày; javascript: ở ô link), phải nhập lại từ đầu | Vừa | app/routes/admin_data.py:351-354,491-496 render lại với dữ liệu đã nhập | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\ads_banner_1440.png` |
| MỚI 9 | Trang > Điều khoản, Bảo mật | Xuất bản không đổi gì | Màn mới | Dữ liệu lưu bị đổi \n thành \r\n. Không thấy trên giao diện | Nhỏ | Chuẩn hóa xuống dòng ở app/routes/admin_content.py | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\overview_1440.png` |
| MỚI 10 | Bài viết, Người đăng ký, Tài khoản | Cỡ nút trên cảm ứng | Không có nút | Nút Sửa, Xóa cao 26px, rộng 46–48px; bấm được nhưng nhỏ | Nhỏ | static/css/admin.css:205 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-admin\pairs2\hover_subs_1440.png` |

### Chức năng dời vào hover: bàn phím và cảm ứng

| Chức năng | Bàn phím | Cảm ứng (390 và 1024) | Vấn đề |
|---|---|---|---|
| Xóa người đăng ký | Dùng được: Tab tới (18 lần), nút hiện, có viền focus; Enter mở hộp xác nhận; Esc hủy, focus về nút | Dùng được: nút luôn hiện, chạm mở hộp xác nhận | MỚI 2, MỚI 10 |
| Sửa bài viết | Dùng được: Tab tới (21 lần), Enter mở drawer, Esc về đúng danh sách | Dùng được: chạm mở drawer | MỚI 1, MỚI 10 |
| Sửa tài khoản | Mở được: Tab tới (22 lần), Enter mở drawer. Esc không đóng, Tab thoát ra ngoài | Dùng được: chạm mở drawer | MỚI 4, MỚI 10 |
| ↑ ↓ ✕ Menu chính | Dùng được: focus ô nhập là hiện, Tab tới được | Dùng được: luôn hiện, không tràn ngang | MỚI 3 |

Giới hạn: trình mô phỏng cảm ứng báo hover:none. Chưa thử laptop cảm ứng thật, nơi chuột là con trỏ chính: ở đó nút ẩn cho tới khi rê, và chạm phải kích hoạt trạng thái hover trước.

### Nút Xuất bản từng màn

| Màn | Hành vi đo được | Đúng nhãn? |
|---|---|---|
| Tổng quan, Bonus, Sàn > Danh sách, Quảng cáo > Thống kê, Bài viết, Người đăng ký > Danh sách, Tài khoản, Tin nhắn | 0 POST, hiện "Đã lưu" 1.8s rồi ẩn | Không xuất bản gì. Giống hành vi file thiết kế và quyết định mục 13. Câu "Đã lưu" đúng vì các thao tác trên màn đã lưu ngay |
| Sàn > Link affiliate | Lưu mọi dòng, ở lại tab, báo Đã lưu; URL sai bị chặn | Lưu đúng. Lỗi làm mất chữ đã sửa (MỚI 8) |
| Quảng cáo > Banner | Lưu vị trí, link, ngày. Không đổi gì thì DB y nguyên; khứ hồi đúng với ngày qua năm, năm cũ, chỉ từ, chỉ đến, trống | Lưu đúng. Bị chặn bởi banner thiếu link (MỚI 7), lỗi làm mất chữ (MỚI 8) |
| Trang chủ: Section | Chỉ lưu tiêu đề section; công tắc và mũi tên đã lưu từ trước | Đúng mục 13, nhưng nhãn rộng hơn việc làm (dòng 15) |
| Trang chủ, Trang, Cài đặt: các tab form còn lại | Lưu form, ở lại tab. Bấm khi không đổi gì: giá trị hiệu lực không đổi ở 23 tab, trừ xuống dòng của tab Điều khoản, Bảo mật | Lưu đúng (MỚI 9) |
| Gửi email, đã soạn | Lưu nháp, trạng thái draft, sent_count 0. Enter ở ô Tiêu đề cũng chỉ lưu nháp, không gửi | An toàn, nhưng nhãn "Xuất bản" làm việc "lưu nháp". Chỉ có tiêu đề thì báo lỗi |
| Gửi email, chưa soạn | 0 POST, báo "Đã lưu", không lưu nhóm đã chọn | Báo sai (MỚI 6) |
| Thư viện ảnh | 0 POST, báo "Đã lưu", không lưu ô mô tả đang gõ | Báo sai (MỚI 5) |

### Phần đo khớp ở vòng 2

Khớp dưới 2px, trừ độ rộng do font nút: Tổng quan (4 thẻ, 2 thẻ danh sách, cả khi rỗng); Bonus (mọi tab con, 5 dòng Sắp hết hạn, tìm khi gõ, giữ lọc, ô tìm 226x42); Sàn (7 cột, đúng thứ tự); Link affiliate (cột, dòng); Quảng cáo > Banner (thẻ 175px, gap 20); Thống kê (cột, biểu đồ); Bài viết (5 cột, thứ tự, dòng 51px khi tiêu đề 1 dòng); Người đăng ký (4 cột, dòng 47px); Gửi email (chọn sẵn nhóm, ô 45px và 15px, nút); Section (20 mũi tên, dòng 53px, giữ cuộn: 459→459, ↑ dòng đầu 0 POST); Cài đặt > Chung (1 thẻ, padding 28). Sidebar: 8 mục đầu đúng tên, thứ tự, 38px, bước 42; hover, "Xem trang chủ" cùng tab đã về. Rộng 390: không tràn ngang ở cả 22 màn DB rỗng.

### Kết luận vòng 2

Chưa khớp hoàn toàn theo mục 13. Các màn bảng và Tổng quan đã gần như trùng thiết kế. Còn lệch rõ ở form Trang chủ (Section, Hero, Menu), Cài đặt > SEO và hai drawer Sửa, chủ yếu vì ô nhập của mục 12 và model. Muốn khớp hoàn toàn thì user phải chọn: chuyển các ô đó sang tab hoặc màn mới, hay đưa chúng vào danh sách GIỮ.

### Chưa so được

- Laptop cảm ứng thật. Hành vi sau khi bấm Gửi tới và Gửi thử (không bấm, vì không được gửi email). Phong cách từng màn mới. 390 với DB có dữ liệu ở vòng 2 (chỉ đo DB rỗng và các phép thử cảm ứng).
