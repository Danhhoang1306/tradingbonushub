# So sánh thiết kế: Trang chủ

Thiết kế gốc: `design/Trang chu v2.dc.html`. Bản dựng: commit 0540c7b, `templates/public/home.html`, `_header`, `_footer_full`, `_macros`, `static/css/site.css`, `app/content.py`.

So bằng Playwright Chromium trên server tạm (cổng 8021, 8022), DB tạm. Không đụng site thật. Ảnh ghép chứa dữ liệu mock nên để ngoài repo, trong thư mục tạm của phiên; xóa thư mục đó thì mất ảnh, nhưng mọi con số đã ghi ở đây.

Loại: A = lỗi hoặc lệch không lý do. B = do yêu cầu user hoặc brief. C = dev, team leader tự quyết, không được user duyệt. D = chỉ do thiếu dữ liệu.

Về "không được user duyệt": đã đọc tin nhắn của user trong log phiên. Không có tin nào duyệt các mục loại C. User có một câu chung "làm những gì bạn thấy tốt nhất cho dự án này" ở đầu dự án, và "ok. cho phép" chỉ trả lời việc lên cổng 8000.

## 1. Kết luận

- **Khi có đủ ảnh, dữ liệu và chữ gốc, khổ 1440 gần như trùng thiết kế.** Chiều cao 8/9 section bằng nhau đến 0.1px; section Bonus ngắn hơn 35px vì bỏ một câu ghi chú. Footer không có sai lệch nào.
- **Cái user đang thấy khác nhiều vì hai lý do:** DB rỗng (loại D, B) và các quyết định loại C về ảnh, bố cục khi thiếu ảnh, câu chữ. Trang thật hiện cao khoảng 3161px, thiết kế cao 7586px.
- **Khổ 390 khác nhiều** vì dev tự viết toàn bộ responsive. Thiết kế không có media query và tự lỗi ở 390 (tràn ngang, menu rộng 0px, một ảnh rộng 0px), nên phần lớn là sửa lỗi, nhưng cỡ chữ và khoảng cách không ai duyệt.

### Có dữ liệu thiết kế (mục 2, K1 đến K59)

| Loại | Lớn | Vừa | Nhỏ | Tổng |
|---|---|---|---|---|
| A | 0 | 3 | 2 | 5 |
| B | 0 | 1 | 2 | 3 |
| C | 3 | 22 | 25 | 50 |
| D | 0 | 0 | 1 | 1 |
| Tổng | 3 | 26 | 30 | 59 |

### Site thật, DB rỗng (mục 3, R1 đến R16, đếm riêng)

| Loại | Lớn | Vừa | Nhỏ | Tổng |
|---|---|---|---|---|
| A | 0 | 0 | 0 | 0 |
| B | 0 | 1 | 0 | 1 |
| C | 7 | 3 | 0 | 10 |
| D | 4 | 1 | 0 | 5 |
| Tổng | 11 | 5 | 0 | 16 |

## 2. So với đủ dữ liệu thiết kế

DB tạm có 8 bonus, 3 sàn gồm sàn nổi bật, 3 bài, ảnh hero giải mã từ `v2-hero-bg`, ảnh giả cho các ô còn lại ở cả hai bên. Chữ admin sửa được đặt đúng nguyên văn thiết kế để so bố cục. Riêng mục 2.1 dùng chữ mặc định.

Chiều cao section (px, thiết kế / bản dựng):

| Section | 1440 | 390 |
|---|---|---|
| Hero | 820 / 820 | 1142.2 / 840.6 |
| Về chúng tôi | 891.4 / 891.4 | 1791.6 / 1534.8 |
| Bonus | 1555.9 / 1520.9 | 4879.7 / 4555.3 |
| Tại sao chọn | 773.8 / 773.8 | 1502.5 / 1176.1 |
| Loại bonus | 863.1 / 863.1 | 1640.9 / 1275.4 |
| So sánh | 882.4 / 882.4 | 1889.6 / 1649.6 |
| Đăng ký | 582.5 / 582.5 | 1222 / 951 |
| Tin tức | 819.4 / 819.4 | 1854.6 / 1659.6 |
| Footer | 397.1 / 397.1 | 636.5 / 799.5 |
| Toàn trang | 7586 / 7551 | 16559 / 14442 |

### 2.1. Câu chữ (mặc định trong `app/content.py` so với nguyên văn thiết kế)

| # | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa, nguồn gốc | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| K1 | Hero, câu mô tả, vế 1 | 1440, 390 | "...khuyến mãi crypto từ [tên 3 sàn]." | "...khuyến mãi crypto từ các sàn có giấy phép." | Vừa | B | Giữ. Brief mục 5 cấm tên sàn trong nội dung. `app/content.py:107` | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_hero.png` |
| K2 | Hero, câu mô tả, vế 2 | 1440, 390 | "Mỗi ưu đãi ghi rõ khối lượng yêu cầu, thời hạn và giấy phép." | "Mỗi ưu đãi ghi rõ mức nạp tối thiểu, phần rút được và thời hạn." | Vừa | C | Trả lại chữ, hoặc user duyệt chữ mới. `app/content.py:107`. Commit 789490d. QA M3 ghi đây là "Quyết định cần user", không thấy user trả lời | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_hero.png` |
| K3 | Hero card, nhãn | 1440, 390 | "Nổi bật tuần này" | "Nổi bật" | Nhỏ | C | `app/content.py:110`. Commit 2074962, theo QA N5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_hero.png` |
| K4 | Về chúng tôi, đoạn mô tả | 1440, 390 | "...trader cần biết: khối lượng lot phải đạt, phần nào rút được, thời hạn và khu vực áp dụng." | "...trader cần biết: mức nạp tối thiểu, phần nào rút được và thời hạn." | Vừa | C | `app/content.py:193`. Commit 789490d, theo QA M3 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_about.png` |
| K5 | Về chúng tôi, dòng cạnh nút | 1440, 390 | "Cập nhật ưu đãi hằng ngày" | Không có (mặc định rỗng) | Vừa | C | `app/content.py:195`. Commit 789490d | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_about.png` |
| K6 | Tại sao chọn, đoạn mô tả | 1440, 390 | "...phần nào rút được, cần giao dịch bao nhiêu lot và bonus có bị trừ khi rút tiền hay không." | "...phần nào rút được, mức nạp tối thiểu và thời hạn của ưu đãi." | Vừa | C | `app/content.py:203`. Commit 789490d, theo QA M3 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_why.png` |
| K7 | Tại sao chọn, thẻ số | 1440, 390 | Thẻ trắng "100%" + "Ưu đãi có tóm tắt điều kiện rút tiền" | Không có (mặc định rỗng); cột phải chỉ còn ảnh | Lớn | C | `app/content.py:204-205`. Commit 789490d. QA M2 ghi "Quyết định cần user: bỏ, hoặc tính từ DB", không thấy user trả lời | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_why.png` |
| K8 | Tại sao chọn, lý do 01 | 1440, 390 | "Khối lượng yêu cầu, phần rút được và thời hạn hiển thị ngay trên mỗi ưu đãi." | "Mức nạp tối thiểu, phần rút được và thời hạn hiển thị ngay trên mỗi ưu đãi." | Nhỏ | C | `app/content.py:207`. Commit 789490d, theo QA M3 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_why.png` |
| K9 | So sánh, nhãn sàn nổi bật | 1440, 390 | "Phổ biến" | "Nổi bật" | Nhỏ | C | `app/content.py:214`. Commit 2074962, theo QA N5 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_compare.png` |
| K10 | Đăng ký, câu mô tả | 1440, 390 | "Chọn loại ưu đãi bạn quan tâm. Tối đa một email mỗi tuần." | "Chọn loại ưu đãi bạn quan tâm." | Vừa | C | `app/content.py:218`. Commit 789490d. Lý do trong QA: code không giới hạn tần suất gửi | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_signup.png` |
| K11 | Footer, cột Liên kết | 1440, 390 | 4 link | 6 link: thêm "Điều khoản", "Bảo mật"; footer 397 lên 428px ở 1440 | Nhỏ | C | Cần trang pháp lý nhưng thiết kế không có link. `app/content.py:147-148`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\defaults_1440_footer.png` |
| K12 | Bonus, ghi chú cuối section | 1440, 390 | "Số liệu là dữ liệu minh hoạ, cần đối chiếu với trang chính thức của sàn trước khi đăng." (12px, #6B7A84) | Không có; section ngắn hơn 35px (1556 xuống 1521) | Nhỏ | B | Giữ. Câu mô tả dữ liệu mock, cùng loại nhãn "minh hoạ" brief mục 5 yêu cầu xóa | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_bonus.png` |

### 2.2. Bố cục và dữ liệu

| # | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa, nguồn gốc | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| K13 | So sánh, thứ tự thẻ | 1440, 390 | Sàn nổi bật (thẻ navy) ở GIỮA, x=555 | Sàn nổi bật luôn ở ĐẦU, x=130 | Vừa | A | Đặt thẻ nổi bật vào giữa. `app/routes/public.py:148-149` (`order_by(featured.desc(), name)`). Commit 79c9f2b | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_compare.png` |
| K14 | Tại sao chọn, cột ảnh | 1440 | Cột hiển thị 158px + 420px (nguồn ghi 1fr 1fr, `image-slot` đẩy lệch khi render). Thẻ số y=187, cao 130, nhãn 1 dòng | Cột 289px + 289px. Thẻ số y=168, cao 149, nhãn 2 dòng | Vừa | A | Dev chép CSS nguồn, không so với bản render. Nếu muốn khớp hình: `minmax(0,158fr) minmax(0,420fr)` ở `static/css/site.css:383`. User nên chọn, vì tỉ lệ thiết kế có thể là tác dụng phụ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_why.png` |
| K15 | Đăng ký, chip mặc định | 1440, 390 | Chip "Deposit bonus" chọn sẵn (nền navy, chữ trắng) | Không chip nào được chọn | Vừa | A | `templates/public/home.html:264` thêm `checked` cho deposit | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_signup.png` |
| K16 | Hero card, nguồn dữ liệu | 1440, 390 | Sàn trong thẻ độc lập với sàn gắn nhãn ở So sánh | Luôn là bonus giá trị cao nhất của sàn nổi bật; không chọn được bonus khác; không có sàn nổi bật thì mất thẻ | Vừa | C | `app/routes/public.py:130-131`. Cần ô chọn bonus ở admin nếu muốn như thiết kế | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_hero.png` |
| K17 | Thẻ bonus, dòng Hạn | 1440, 390 | Dạng dd/mm | Dạng dd/mm/yyyy, ô giá trị rộng 38 lên 83px | Nhỏ | A | `templates/public/home.html:126` dùng `short_date` khi có ngày | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_bonus.png` |
| K18 | So sánh, dòng Bonus nổi bật | 1440, 390 | Chữ tự do: loại ngắn, có khi không số tiền | Luôn ghép nhãn loại + số tiền, dài hơn 45px | Nhỏ | C | `templates/public/home.html:232` | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_compare.png` |
| K19 | Thẻ bonus, giấy phép | 1440, 390 | Giấy phép ở thẻ bonus khác giấy phép ở thẻ So sánh của cùng sàn | Một trường `license` duy nhất cho cả hai | Nhỏ | D | Không cần sửa: dữ liệu mock của thiết kế tự mâu thuẫn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_bonus.png` |
| K20 | Đăng ký, id section | mọi khổ | `#lien-he` | `#dang-ky` | Nhỏ | C | Không có link nào trỏ tới. `templates/public/home.html:242` | (không có ảnh, đo bằng code) |
| K21 | Input, màu placeholder | 1440, 390 | #757575 (mặc định trình duyệt) | #5F6E78 | Nhỏ | C | Có lợi cho tương phản. `static/css/site.css:465` | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_1440_signup.png` |
| K22 | Input, màu chữ đang gõ | 1440, 390 | #000000 | #021623 | Nhỏ | A | `static/css/site.css:463` | (không có ảnh, đo bằng code) |
| K23 | Banner ngang Quảng cáo #1, #2 | 1440 | Trang chủ v2 không có. Admin.dc.html chỉ có vị trí + ô ảnh | Khối navy tự thiết kế 1252x170px khi banner không có ảnh; mỗi section cao 301px, dài trang thêm 602px. Chỉ hiện khi có banner | Vừa | C | Thiết kế lại hoặc chỉ cho dùng ảnh. `templates/public/_macros.html:63-89`, `static/css/site.css:334-349`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\ads_1440_full.png` |
| K24 | Rail trái (khổ từ 1572px) | 1920 | Số tiền, chữ phụ dưới số, tiêu đề, 3 dòng tự do; không có tag | Thêm tag loại; không có chữ phụ; dòng ghép tự động; số 44px hoặc 30px khi dài | Vừa | C | Vị trí và ngưỡng khớp; nội dung do `top_bonus` sinh. `templates/public/_macros.html:92-120` | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\rail_1920.png` |
| K25 | Rail phải (khổ từ 1572px) | 1920 | Số 52px, chữ phụ, đoạn mô tả, 1 dòng hạn, nút theo số tiền | Số 44px, không chữ phụ, không mô tả, 3 dòng, nút cố định "Mở tài khoản" | Vừa | C | `templates/public/_macros.html:102-115`, `static/css/site.css:369` | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\rail_1920.png` |

### 2.3. Link đích

| # | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa, nguồn gốc | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| K26 | Nút header "Xem bonus" | 1440 | `#bonus`, cuộn trong trang | `/bonus`, sang trang khác | Vừa | C | Dùng `#bonus` khi section bonus đang hiện, không thì `/bonus`. `templates/public/_header.html:20`. Commit e9cf9dd | (không có ảnh, đo bằng code) |
| K27 | Hero "Xem tất cả bonus" | 1440, 390 | `#bonus` | `/bonus` | Vừa | C | `templates/public/home.html:19`. Commit e9cf9dd | (không có ảnh, đo bằng code) |
| K28 | Về chúng tôi "Xem tất cả bonus" | 1440, 390 | `#bonus` | `/bonus` | Vừa | C | `templates/public/home.html:72`. Commit e9cf9dd | (không có ảnh, đo bằng code) |
| K29 | Thẻ bonus "Điều kiện" | 1440, 390 | `#` (chưa có đích) | Trang chi tiết sàn `/san/{slug}` | Nhỏ | C | Đích dev tự chọn; hợp lý nhưng cần user xác nhận. `templates/public/home.html:130` | (không có ảnh, đo bằng code) |
| K30 | "Nhận bonus" (thẻ, hero card) | 1440, 390 | `#` (chưa có đích) | `/go/broker/{id}`, tab mới, rel sponsored | Nhỏ | B | Giữ. Link affiliate thật thay link mock | (không có ảnh, đo bằng code) |

### 2.4. Hover, chuyển màu

| # | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa, nguồn gốc | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| K31 | Hover menu | 1440 | Không đổi | Mờ 0.8 | Nhỏ | C | `static/css/site.css:128` | (không có ảnh, đo bằng code) |
| K32 | Hover "Nhận bonus →" ở hero card | 1440 | Không đổi | Chữ #FFFFFF sang #E4E9EE | Nhỏ | C | `static/css/site.css:247` | (không có ảnh, đo bằng code) |
| K33 | Hover "Điều kiện" | 1440 | Không đổi | Chữ sang #1944DF | Nhỏ | C | `static/css/site.css:73` | (không có ảnh, đo bằng code) |
| K34 | Hover tab Loại bonus | 1440 | Không đổi | Viền 0.15 sang 0.4 | Nhỏ | C | `static/css/site.css:411` | (không có ảnh, đo bằng code) |
| K35 | Hover "Xem bonus loại này" | 1440 | Không đổi | Nền sang #1944DF | Nhỏ | C | `static/css/site.css:54` | (không có ảnh, đo bằng code) |
| K36 | Hover CTA So sánh, thẻ thường | 1440 | Không đổi | Nền sang #1944DF | Nhỏ | C | `static/css/site.css:443` | (không có ảnh, đo bằng code) |
| K37 | Hover CTA So sánh, thẻ nổi bật | 1440 | Không đổi | Nền trắng, chữ navy (đọc CSS, không đo) | Nhỏ | C | `static/css/site.css:445` | (không có ảnh, đo bằng code) |
| K38 | Hover nút "Đăng ký nhận thông báo" | 1440 | Không đổi | Nền trắng, chữ navy | Nhỏ | C | `static/css/site.css:52` | (không có ảnh, đo bằng code) |
| K39 | Hover "Xem tất cả tin tức" | 1440 | Không đổi | Nền sang #1944DF | Nhỏ | C | `static/css/site.css:54` | (không có ảnh, đo bằng code) |
| K40 | Hover thẻ tin tức | 1440 | Không đổi | Tiêu đề sang #1944DF | Nhỏ | C | `static/css/site.css:495` | (không có ảnh, đo bằng code) |
| K41 | Hover link footer | 1440 | Không đổi | Chữ #C2CBD1 sang #FFFFFF | Nhỏ | C | `static/css/site.css:187` | (không có ảnh, đo bằng code) |
| K42 | Hiệu ứng chuyển màu nút, tab, chip | 1440 | 0s | 0.15s | Nhỏ | C | `static/css/site.css:45,65,409,475` | (không có ảnh, đo bằng code) |

### 2.5. Điện thoại (390px)

| # | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa, nguồn gốc | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| K43 | Header | 390 | Menu bị bóp còn rộng 0px, nút "Xem bonus" tràn mép phải và bị cắt | Nút 3 gạch 44x44px, ẩn nút "Xem bonus", menu xổ xuống | Vừa | C | `static/css/site.css:144-160`, `templates/public/_header.html:11`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_hero.png` |
| K44 | Tràn ngang toàn trang | 390 | scrollWidth 464px (lỗi của thiết kế: cột min 380px) | scrollWidth 390px | Vừa | C | Đây là bản dựng tốt hơn. `static/css/site.css:262`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_full.png` |
| K45 | Lề trang | 390 | 24px | 16px | Vừa | C | `static/css/site.css:691`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_full.png` |
| K46 | Logo chữ, header | 390 | 19px; header cao 97px | 17px; header cao 89px | Nhỏ | C | `static/css/site.css:159`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_hero.png` |
| K47 | H1 hero | 390 | 64px, cao dòng 70.4px, 5 dòng cao 352px | 38px, cao dòng 41.8px, 3 dòng cao 125px | Lớn | C | `static/css/site.css:232`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_hero.png` |
| K48 | Chiều cao hero | 390 | 1142px, hero card y=875 | 841px, hero card y=601 | Vừa | C | `static/css/site.css:248-253`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_hero.png` |
| K49 | H2 các section | 390 | 48px, cao dòng 55.2px | 32px, cao dòng 36.8px | Lớn | C | `static/css/site.css:269`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_about.png` |
| K50 | Padding dọc section | 390 | 110px | 72px; toàn trang 16559 xuống 14442px | Vừa | C | `static/css/site.css:691`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_full.png` |
| K51 | Về chúng tôi, ảnh trong thẻ | 390 | 180x127px, cạnh chữ xuống dòng | 338x239px, full ngang | Vừa | C | `static/css/site.css:299`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_about.png` |
| K52 | Về chúng tôi, khối ảnh và số | 390 | Ảnh 180x300, ảnh 380x280, số 56px, gap 20px | Ảnh 173x220, ảnh 358x200, số 40px, gap 12px | Vừa | C | `static/css/site.css:301-305`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_about.png` |
| K53 | Thẻ bonus, số tiền | 390 | 44px | 38px | Nhỏ | C | `static/css/site.css:696`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_bonus.png` |
| K54 | Tại sao chọn, khối ảnh | 390 | Ảnh 1 rộng 0px (lỗi thiết kế), ảnh 2 rộng 420px tràn; số 40px | Ảnh 173x320 và 173x180; số 30px | Vừa | C | `static/css/site.css:396-402`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_why.png` |
| K55 | Tab Loại bonus | 390 | Cao 64px, padding 20/24, chữ 17px | Cao 54px, padding 16/20, chữ 16px | Nhỏ | C | `static/css/site.css:424`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_types.png` |
| K56 | Thẻ Loại bonus | 390 | Tiêu đề 28px, ảnh cao 280px | Tiêu đề 24px, ảnh cao 200px | Nhỏ | C | `static/css/site.css:425-427`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_types.png` |
| K57 | Thẻ So sánh, padding | 390 | 36px | 24px | Nhỏ | C | `static/css/site.css:446`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_compare.png` |
| K58 | Đăng ký | 390 | Tiêu đề 40px; padding 40/36; ô tên và email 2 cột; ảnh 340x420 | Tiêu đề 30px; padding 28/14; ô 1 cột; ảnh 338x229 | Vừa | C | `static/css/site.css:486-490`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_signup.png` |
| K59 | Footer | 390 | Padding trên 90px; 2 cột link; cao 637px | Padding trên 64px; 1 cột; cao 800px | Vừa | C | `static/css/site.css:208-211`. Commit e9cf9dd | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\full_390_footer.png` |

## 3. Site thật đang thấy: DB rỗng

Giả lập bằng DB tạm rỗng, chưa có ảnh, section Đăng ký tắt, theo `docs/PROGRESS.md`. Không mở cổng 8000 và không đọc `data/app.db`, nên trạng thái thật chưa được kiểm chứng trực tiếp. Bên thiết kế để nguyên, chỉ có ảnh hero.

Chiều cao toàn trang: thiết kế 7586px, bản dựng 3161px ở 1440; thiết kế 16559px, bản dựng 4813px ở 390 (số 390 là khi Đăng ký còn bật). Thứ tự còn lại: Hero, Về chúng tôi, Tại sao chọn, Loại bonus, Footer. Các câu đổi ở mục 2.1 cũng hiện ở đây.

| # | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa, nguồn gốc | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| R1 | Hero, ảnh nền | 1440, 390 | Ảnh tòa nhà kính + lớp phủ | Nền navy phẳng | Lớn | C | Trả `image_path` và file, hoặc user đưa ảnh mới. `app/content.py:109`, `templates/public/home.html:8`. Commit 789490d xóa ảnh mà brief mục 5 ghi GIỮ. Lý do QA M1: ảnh có logo một hãng công nghệ, đã kiểm chứng trên ảnh ghép. QA ghi "Quyết định cần user", không thấy user trả lời | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_hero.png` |
| R2 | Hero, chiều cao | 1440, 390 | 820px (390: 1142px) | 702px (390: 617px) | Lớn | C | Bỏ `.hero--plain`. `static/css/site.css:219,250`. Commit 789490d | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_hero.png` |
| R3 | Hero card | 1440, 390 | Có | Không có: chưa có sàn nổi bật và bonus | Lớn | D | Hết khi nhập dữ liệu | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_hero.png` |
| R4 | Về chúng tôi, 2 ô ảnh và ô số bên phải | 1440, 390 | Cột phải: ô ảnh, ô số, ô ảnh rộng; section 891px | Cả cột biến mất; section 712px | Lớn | C | Trả ô nền trung tính. `templates/public/_macros.html:5`, `templates/public/home.html:76`. Commit 2074962. Brief mục 4 yêu cầu "thiếu ảnh thì khối nền trung tính"; QA_REPORT dòng 288 cũng ghi 7 khối xám là đúng brief | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_about.png` |
| R5 | Về chúng tôi, chữ giãn hết ngang | 1440 | Cột trái 598px, H2 3 dòng | Cột đơn 1252px, H2 1 dòng | Lớn | C | Bố cục dev tự nghĩ, hết khi trả ô ảnh. `static/css/site.css:265`. Commit 2074962 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_about.png` |
| R6 | Về chúng tôi, ảnh trong thẻ | 1440, 390 | Ảnh 237x167 + chữ | Chỉ còn chữ | Vừa | C | `templates/public/_macros.html:5`. Commit 2074962 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_about.png` |
| R7 | Về chúng tôi, ô số "N+" | 1440, 390 | Có | Không có: 0 bonus | Vừa | B | Giữ. Brief mục 5: số đếm 0 thì ẩn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_about.png` |
| R8 | Section Bonus | 1440, 390 | Có, 1556px | Ẩn hẳn | Lớn | D | Hết khi có bonus. Brief mục 5 quy định ẩn | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_full.png` |
| R9 | Tại sao chọn, khối ảnh và thẻ số | 1440, 390 | Cột trái ảnh và thẻ số; section 774px | Cả cột biến mất; section 553px | Lớn | C | `templates/public/home.html:149`. Commit 2074962 (ảnh) và 789490d (thẻ số) | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_why.png` |
| R10 | Tại sao chọn, 3 lý do | 1440 | Xếp dọc, cột phải | Xếp ngang 3 cột, full ngang | Lớn | C | Bố cục thiết kế không có. `static/css/site.css:266`. Commit 2074962 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_why.png` |
| R11 | Loại bonus, thẻ phải | 1440, 390 | Ảnh cao 280px, thẻ kéo cao bằng hàng; section 863px | Không ảnh, thẻ ngắn bám trên (`align-self:start`); section 766px | Vừa | C | `static/css/site.css:414`, `templates/public/home.html:194`. Commit 2074962 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_types.png` |
| R12 | Section So sánh | 1440, 390 | Có, 882px | Ẩn hẳn | Lớn | D | Hết khi có sàn bật so sánh | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_full.png` |
| R13 | Section Đăng ký | 1440, 390 | Có, 583px | Ẩn hẳn theo `docs/PROGRESS.md` và README (section tắt vì chưa có SMTP). Không kiểm chứng trên DB thật | Lớn | C | Team leader tự tắt, chỉ báo user sau. Bật lại ở Trang chủ › Section khi có SMTP | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_full.png` |
| R14 | Section Đăng ký, nếu bật | 1440 | Ảnh + form 2 cột; 583px | Form 1 cột căn giữa, rộng tối đa 760px; 693px | Vừa | C | `static/css/site.css:458`. Commit 2074962 | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\empty_1440_signup.png` |
| R15 | Section Tin tức | 1440, 390 | Có, 819px | Ẩn hẳn | Lớn | D | Hết khi có bài bật hiện trang chủ | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_full.png` |
| R16 | Rail hai bên | 1920 | Có | Không có | Vừa | D | Hết khi có banner rail | (không có ảnh, đo bằng code) |

Ảnh tổng: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\nosignup_1440_full.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\empty_390_full.png`.

## 4. Phần đã khớp

Đo ở 1440, sai lệch dưới 2px và cùng màu khi có đủ dữ liệu:

- Header: logo, menu, nút, đường kẻ. Hero: lớp phủ, nhãn, H1, mô tả, nút, kiểu thẻ.
- Về chúng tôi, Bonus (lưới 4 cột, 8 thẻ, thẻ, hàng, nút), Loại bonus, Đăng ký (trừ chip mặc định), Tin tức, Footer.
- Thứ tự section. Token màu, font Be Vietnam Pro, cỡ chữ, line-height, letter-spacing, padding, gap, bo góc của mọi phần tử chữ.
- 5 mô tả loại bonus: 25/25 chuỗi TYPES trùng nguyên văn. Lý do 02, 03; tiêu đề, nhãn các section; footer; cảnh báo rủi ro; copyright.
- Bộ lọc: cùng 6 nút, số thẻ mỗi loại bằng nhau (8, 1, 2, 2, 2, 1), màu pill bằng nhau.
- Tab Loại bonus: 5 tab đổi đúng nội dung, cùng màu. "Xem bonus loại này" lọc và cuộn tới y=1711 ở cả hai bên.
- Chip: bấm đổi nền navy, chữ trắng ở cả hai bên.
- Hover có trong thiết kế: nút header, hero, Về chúng tôi, "Nhận bonus". Màu đổi đúng.
- Rail: vị trí, độ rộng, ngưỡng 1572px bằng nhau ở 1572, 1600, 1920.
- Menu và link có đích tương ứng: 6 mục menu, footer, thẻ tin tức, "Xem đánh giá", "Xem tất cả tin tức".

## 5. Việc chưa so được

- Site thật và DB thật: không được phép đụng. Mục 3 là giả lập.
- Khổ 768, 1024: ngoài phạm vi. CSS cho thấy menu chuyển sang nút 3 gạch từ 1080px trở xuống.
- Firefox, Safari, điện thoại thật.
- Hover rail, hover CTA thẻ nổi bật: chỉ đọc CSS. Menu xổ ở 390: chưa bấm thử.
- Luồng gửi form đăng ký thật: không gửi. Chữ "Đã đăng ký" lấy từ `app/content.py:220-221`, trùng thiết kế.
- Ô ảnh dùng ảnh giả, nên chỉ so khung, không so nội dung ảnh. Ảnh thật cho các ô này chưa có.


## Vòng 2: đo lại trên commit 272be90

Đo lại từ đầu bằng cùng công cụ, không dựa báo cáo dev. Chuẩn: `docs/TEAM_BRIEF.md` mục 13. Server tạm cổng 8021, 8022, DB tạm; không đụng cổng 8000 và `data/app.db`.

Trạng thái đã đo, ở 1440 và 390: đủ ảnh + chữ gốc; đủ ảnh + chữ mặc định; có dữ liệu thiếu ảnh; DB rỗng. Thêm rail ở 1920 và banner ngang ở 1440.

### Kết luận vòng 2

**Có, trang chủ khớp thiết kế về bố cục, kiểu chữ, câu chữ, link và hover.** Còn 6 lệch, không lệch nào mức Lớn, đều ở nơi dữ liệu không có trường tương ứng hoặc ở 390.

| Mức còn lệch | Số lượng | Mục |
|---|---|---|
| Lớn | 0 | |
| Vừa | 3 | K16, K24, K25 |
| Nhỏ | 3 | K18, K59, N1 |

| Nhóm | ĐÃ KHÔI PHỤC | CÒN | Được phép theo mục 13 | Tổng |
|---|---|---|---|---|
| K (có dữ liệu) | 43 | 5 | 11 | 59 |
| R (DB rỗng) | 10 | 0 | 6 | 16 |

K24, K25 chỉ thấy ở màn từ 1572px và khi có banner rail. Việc còn K16, K18, K24, K25 cần trường dữ liệu mới, user chưa quyết. K59, N1 sửa được bằng CSS. ISSUES ghi K59 là chống tràn, nhưng footer thiết kế ở 390 không tràn.

Chiều cao section (px, thiết kế / bản dựng):

| Section | 1440 đủ dữ liệu | 390 đủ dữ liệu | 1440 DB rỗng | 390 DB rỗng |
|---|---|---|---|---|
| Hero | 820 / 820 | 1142.2 / 1143.2 | 820 / 820 | 1142.2 / 891.2 |
| Về chúng tôi | 891.4 / 891.4 | 1791.6 / 1791.6 | 891.4 / 891.4 | 1791.6 / 1791.6 |
| Bonus | 1555.9 / 1520.9 | 4879.7 / 4829.7 | ẩn | ẩn |
| Tại sao chọn | 773.8 / 773.8 | 1502.5 / 1502.5 | 773.8 / 773.8 | 1502.5 / 1502.5 |
| Loại bonus | 863.1 / 863.1 | 1640.9 / 1640.9 | 863.1 / 863.1 | 1640.9 / 1640.9 |
| So sánh | 882.4 / 882.4 | 1889.6 / 1889.6 | ẩn | ẩn |
| Đăng ký | 582.5 / 582.5 | 1222 / 1268 | 582.5 / 692.5 | 1222 / 1378 |
| Tin tức | 819.4 / 819.4 | 1854.6 / 1854.6 | ẩn | ẩn |
| Footer | 397.1 / 397.1 | 636.5 / 636.5 | 397.1 / 397.1 | 636.5 / 636.5 |
| Toàn trang | 7586 / 7551 | 16559 / 16556 | 7586 / 4438 | 16559 / 7841 |

Có dữ liệu thiếu ảnh: mọi section cao bằng dòng đủ dữ liệu. 10 ô ảnh in đủ khung nền `rgba(127,127,127,.12)`, không chữ, đúng kích thước thiết kế ở 1440, kể cả 3 ảnh bài viết khi không có ảnh bìa.

### Khác biệt mới

| Mục | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|
| N1 | Nút "Đăng ký nhận thông báo" | 390 | 1 dòng, rộng 263.8px, H2 2 dòng | Chữ nút xuống 2 dòng, rộng 250px, H2 3 dòng | Nhỏ | Hệ quả của khung 322px. Cho `.btn-arrow--submit` không xuống dòng và xem lại padding `.signup__content` | `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2full_390_signup.png` |

Không có section, khối hay chữ tự thêm nào khác. Hai khoảng trống ở K7, R7 là hệ quả của quyết định ẩn, không tính là lệch.

### Trạng thái từng mục K

| Mục | Trạng thái | Đo được ở 272be90 |
|---|---|---|
| K1 | Được phép theo mục 13 | Không tên sàn: dữ liệu mock thay bằng chữ chung |
| K2 | ĐÃ KHÔI PHỤC | Câu "khối lượng yêu cầu, thời hạn và giấy phép" đã về |
| K3 | ĐÃ KHÔI PHỤC | "Nổi bật tuần này" |
| K4 | ĐÃ KHÔI PHỤC | Nguyên văn |
| K5 | ĐÃ KHÔI PHỤC | "Cập nhật ưu đãi hằng ngày" |
| K6 | ĐÃ KHÔI PHỤC | Nguyên văn |
| K7 | Được phép theo mục 13 | User quyết bỏ số 100%: thẻ ẩn khi chưa nhập, khi nhập thì đúng vị trí. Khi ẩn còn khoảng trống 420x130px trên ảnh |
| K8 | ĐÃ KHÔI PHỤC | Nguyên văn |
| K9 | ĐÃ KHÔI PHỤC | "Phổ biến" |
| K10 | ĐÃ KHÔI PHỤC | "Tối đa một email mỗi tuần." |
| K11 | ĐÃ KHÔI PHỤC | 4 link, footer 397.1px |
| K12 | Được phép theo mục 13 | Câu nói về dữ liệu mock; Bonus ngắn hơn 35px (1440), 50px (390) |
| K13 | ĐÃ KHÔI PHỤC | Thẻ nổi bật ở giữa, x=555 |
| K14 | ĐÃ KHÔI PHỤC | Cột 158 + 420px, thẻ số y=187 |
| K15 | ĐÃ KHÔI PHỤC | Deposit bonus chọn sẵn |
| K16 | CÒN | Vẫn lấy bonus cao nhất của sàn nổi bật; không có sàn nổi bật thì mất thẻ. Đã ghi ISSUES. Cần ô chọn bonus ở admin |
| K17 | ĐÃ KHÔI PHỤC | dd/mm |
| K18 | CÒN | Vẫn ghép nhãn + số tiền, ô rộng hơn 45-49px. Đã ghi ISSUES. Cần trường dữ liệu mới |
| K19 | Được phép theo mục 13 | Dữ liệu DB, một trường license; dữ liệu mock thiết kế tự mâu thuẫn |
| K20 | ĐÃ KHÔI PHỤC | `#lien-he` |
| K21 | ĐÃ KHÔI PHỤC | #757575 |
| K22 | ĐÃ KHÔI PHỤC | #000000 |
| K23 | Được phép theo mục 13 | Đã bỏ khối navy tự thiết kế, còn khung ảnh 970x250px của Admin.dc.html. Vị trí trên trang chủ không có nguồn: mỗi section cao 381px, trang thêm 762px khi có đủ 2 banner |
| K24 | CÒN | Đúng dạng navy, không tag, 3 dòng. Thiếu chữ phụ dưới số; số 30px thay vì 44px khi chuỗi tiền dài hơn 4 ký tự. Đã ghi ISSUES |
| K25 | CÒN | Đúng nền xanh, tag, số 52px, 1 dòng hạn, nút "Nhận {số tiền}". Thiếu chữ phụ và đoạn mô tả riêng (in tiêu đề bonus). Đã ghi ISSUES |
| K26 | ĐÃ KHÔI PHỤC | `#bonus`; section Bonus ẩn thì `/bonus` |
| K27 | ĐÃ KHÔI PHỤC | Như trên |
| K28 | ĐÃ KHÔI PHỤC | Như trên |
| K29 | Được phép theo mục 13 | Thiết kế để `#`, buộc phải có đích. Đã ghi ISSUES |
| K30 | Được phép theo mục 13 | Link affiliate thật thay link mock |
| K31 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K32 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K33 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K34 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K35 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K36 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K37 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K38 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K39 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K40 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K41 | ĐÃ KHÔI PHỤC | Đo lại: không đổi khi hover |
| K42 | ĐÃ KHÔI PHỤC | Đo lại: 0s |
| K43 | Được phép theo mục 13 | Hamburger trong danh sách GIỮ. Menu mở đủ 6 mục và nút, không tràn. Header cao 89px thay vì 97px nên nội dung hero lệch lên 8px |
| K44 | Được phép theo mục 13 | Chống tràn trong danh sách GIỮ: scrollWidth 390px |
| K45 | ĐÃ KHÔI PHỤC | 24px |
| K46 | ĐÃ KHÔI PHỤC | 19px |
| K47 | ĐÃ KHÔI PHỤC | 64px, 5 dòng, cao 352px |
| K48 | ĐÃ KHÔI PHỤC | 1143.2px so với 1142.2px, phần lệch do chữ bonus dài hơn |
| K49 | ĐÃ KHÔI PHỤC | 48px |
| K50 | ĐÃ KHÔI PHỤC | 110px; toàn trang 16556 so với 16559px |
| K51 | ĐÃ KHÔI PHỤC | 180x127px |
| K52 | ĐÃ KHÔI PHỤC | Chiều cao, cỡ số 56px đã về; ô rộng 161px thay vì 180px do chống tràn |
| K53 | ĐÃ KHÔI PHỤC | 44px |
| K54 | Được phép theo mục 13 | Chống tràn: ảnh 88x460 và 234x280 (thiết kế 0px và 420px tràn). Số 40px đã về |
| K55 | ĐÃ KHÔI PHỤC | Không còn sai lệch |
| K56 | ĐÃ KHÔI PHỤC | Không còn sai lệch |
| K57 | ĐÃ KHÔI PHỤC | 36px |
| K58 | Được phép theo mục 13 | Chữ, padding, 2 cột ô, ảnh cao 420px đã về. Khung 322px thay vì 340px bị tràn nên cao hơn 46px; xem N1 |
| K59 | CÒN | Cao 636.5px, padding 90px đã về. 2 cột link chia đều 151/151px, thiết kế 215/87px, cột 2 lệch trái 64px dù thiết kế không tràn. Thử `repeat(2, auto)` ở `static/css/site.css:201` |

### Trạng thái từng mục R

| Mục | Trạng thái | Đo được ở 272be90 |
|---|---|---|
| R1 | ĐÃ KHÔI PHỤC | Ảnh trùng từng byte với `v2-hero-bg` |
| R2 | ĐÃ KHÔI PHỤC | 820px ở 1440. Ở 390 cao 891px vì không có hero card (R3) |
| R3 | Được phép theo mục 13 | Thiếu dữ liệu |
| R4 | ĐÃ KHÔI PHỤC | Đủ ô nền trung tính đúng kích thước, không chữ |
| R5 | ĐÃ KHÔI PHỤC | Cột 598px, H2 3 dòng |
| R6 | ĐÃ KHÔI PHỤC | Ô 237x167px |
| R7 | Được phép theo mục 13 | Brief mục 5: số đếm 0 thì ẩn. Để lại khoảng trống 289x300px cạnh ảnh |
| R8 | Được phép theo mục 13 | Thiếu dữ liệu, brief mục 5 |
| R9 | ĐÃ KHÔI PHỤC | Đủ 2 ô ảnh; thẻ số ẩn theo quyết định của user |
| R10 | ĐÃ KHÔI PHỤC | Xếp dọc |
| R11 | ĐÃ KHÔI PHỤC | Có ô ảnh, section 863.1px |
| R12 | Được phép theo mục 13 | Thiếu dữ liệu |
| R13 | ĐÃ KHÔI PHỤC | Mặc định bật trong code. Chưa kiểm chứng DB thật, nơi có thể đã lưu trạng thái tắt |
| R14 | ĐÃ KHÔI PHỤC | Ảnh và form 2 cột, 582.5px khi có section So sánh. DB rỗng cao 692.5px vì thêm 110px trên khi So sánh ẩn |
| R15 | Được phép theo mục 13 | Thiếu dữ liệu |
| R16 | Được phép theo mục 13 | Thiếu dữ liệu |

### Ảnh ghép vòng 2

- Đủ dữ liệu: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2full_1440_full.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2full_390_full.png`
- Chữ mặc định: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2def_1440_full.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2def_390_full.png`
- Có dữ liệu thiếu ảnh: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2noimg_1440_full.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2noimg_390_full.png`
- DB rỗng: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2empty_1440_full.png`, `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2empty_390_full.png`
- Rail: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2rail_1920.png`. Banner ngang: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2ads_1440_full.png`. Menu mở ở 390: `C:\Users\danhh\AppData\Local\Temp\claude\17ec8c0066fedc03\0e1ca350-6c2d-4075-8d81-f49e661aa4cb\scratchpad\design-home\pairs\r2_menu_390.png`

### Chưa so ở vòng 2

- Site thật và DB thật. Setting đã lưu trong DB thật có thể đè mặc định mới, gồm section Đăng ký và chữ. Cần xem trực tiếp sau khi triển khai.
- Đăng ký ở production khi chưa có SMTP: chỉ đọc code `can_deliver` (`app/mailer.py:18`), chưa chạy. Không gửi email.
- Khổ 768, 1024; Firefox, Safari, điện thoại thật.
- Nội dung ảnh thật ngoài ảnh hero: ô ảnh dùng ảnh giả hoặc để trống.
