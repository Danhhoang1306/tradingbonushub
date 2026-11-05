# So sánh thiết kế: các trang con

Nguồn: `design/Cac trang.dc.html`. Bản dựng: `templates/public/*`, `static/css/site.css`, commit 0540c7b. Ngày 05/11/2026.

Cách làm: dữ liệu của thiết kế được nạp vào DB tạm, ảnh giả giống nhau cho hai bên. Hai bên chụp ở rộng 1440 và 390, đo bounding box và computed style của mọi phần tử có chữ. Sai lệch từ 2px hoặc khác màu thì ghi. Các khác biệt cùng một nguyên nhân gộp thành một dòng.

Loại: A = lỗi hoặc lệch không có lý do. B = do brief (mục 5, 7, 8, 12). C = dev hoặc team leader tự quyết, repo không có bằng chứng user duyệt. D = chỉ khác do thiếu dữ liệu.

Về loại C: kiểm toán chỉ đọc được repo, không đọc được hội thoại với user. Nếu user đã duyệt miệng một mục nào đó, team leader cần chuyển mục đó sang B. Một số mục C là sửa lỗi của thiết kế và được ghi "Nên giữ".

Ảnh ghép chứa dữ liệu mẫu nên nằm ngoài repo, trong thư mục tạm của phiên này, có thể bị xóa.

## Tổng hợp (không tính mục DB rỗng)

| Loại | Lớn | Vừa | Nhỏ | Tổng |
|---|---|---|---|---|
| A | 0 | 1 | 19 | 20 |
| B | 0 | 1 | 3 | 4 |
| C | 14 | 31 | 12 | 57 |
| D | 0 | 4 | 0 | 4 |
| Tổng | 14 | 37 | 34 | 85 |

Mục DB rỗng so riêng: 8 dòng (6 B, 1 C trùng mục trên, 1 khớp).

Ở 1440 với đủ dữ liệu và ảnh, bố cục gần như khớp pixel: Bonus, Sàn, chi tiết sàn, Tin tức, Về chúng tôi có chiều cao trang bằng đúng thiết kế. Khác biệt chủ yếu ở chữ, ở phần thêm mới, ở trạng thái thiếu ảnh và ở bản mobile.


## Chung: header, đầu trang, footer (mọi trang con)

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Mọi trang | Menu, mục thứ 3 | 1440, 390 | "Sàn uy tín" | "Sàn"; vì nhãn ngắn hơn 43,7px, các mục menu lệch: Trang chủ/Bonus +24px, 3 mục cuối −19px | Lớn | C | `app/content.py:127`. Commit 79c9f2b. Đổi lại "Sàn uy tín" nếu user muốn | [bonus_all_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_all_1440.png) |
| 2 | Mọi trang | Nút header | 1440 | "Nhận tư vấn", rộng 159,7px, tới Bonus | "Xem bonus", rộng 154,7px, tới `/bonus`. Link khớp thiết kế, nhãn không khớp. Lịch sử: e9cf9dd đặt "Nhận tư vấn" trỏ `/lien-he`, 789490d đổi thành "Xem bonus" (QA M4). QA_REPORT ghi đây là "Quyết định cần user" nhưng repo không có bằng chứng user đã duyệt | Lớn | C | `app/content.py:159` | [bonus_all_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_all_1440.png) |
| 3 | Liên hệ | Menu: mục đang chọn | 1440, 390 | Bấm "Liên hệ" sáng mục "Giới thiệu" | Sáng mục "Liên hệ" | Vừa | C | `templates/public/_header.html:16` | [contact_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_1440.png) |
| 4 | Mọi trang | Đổi tab, sort, chọn sàn | 1440, 390 | Không tải lại. Sort giữ vị trí cuộn (400→400) | Tải lại trang, cuộn về đầu (400→0). Do server render và URL thật theo brief mục 3, 7 | Vừa | B | Không cần sửa, hoặc thêm neo `#main` vào link |  |
| 5 | Bonus, Sàn, Tin, Giới thiệu | Mục cuối breadcrumb | 1440, 390 | Là nút, bấm về tab đầu của mục | Chữ thường, không bấm được. Ở `/bonus?type=crypto` không về được "Tất cả" bằng breadcrumb | Nhỏ | A | `templates/base_public.html:44` |  |
| 6 | Mọi trang | Hover menu chưa chọn | 1440 | Chỉ "Trang chủ" có nền 0,1 khi hover; các nút còn lại không đổi | Mọi mục có nền rgba(255,255,255,.1). Kết luận từ CSS và phép đo trên "Trang chủ" | Nhỏ | A | `static/css/site.css:123` |  |
| 7 | Mọi trang | Hover tab chưa chọn | 1440 | Màu giữ #A9B6C1 | Đổi sang #FFFFFF | Nhỏ | A | `static/css/site.css:178` |  |
| 8 | Mọi trang | Hover breadcrumb | 1440 | Màu giữ #A9B6C1 | Đổi sang #FFFFFF | Nhỏ | A | `static/css/site.css:167` |  |
| 9 | Bonus, So sánh | Hover pill sort/chọn sàn | 1440 | Viền giữ rgba(2,22,35,.15) | Viền #021623 | Nhỏ | A | `static/css/site.css:84` |  |
| 10 | Mọi trang | Chuyển trạng thái nút | 1440 | transition 0s | transition 0,15s | Nhỏ | A | `static/css/site.css:45,65` |  |
| 11 | Bonus, Sàn, Tin, chi tiết | Số đếm ở tab đang chọn | 1440, 390 | font-weight 600 (kế thừa tab) | font-weight 500 | Nhỏ | A | `static/css/site.css:180` | [bonus_all_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_all_1440.png) |
| 12 | Bonus, So sánh, Bài viết, Liên hệ | Chữ nút trắng (Về sàn, Đánh giá, Về danh sách), chữ trong ô nhập | 1440, 390 | rgb(0,0,0) (mặc định nút trình duyệt) | rgb(2,22,35). Gần token hơn, mắt thường khó thấy | Nhỏ | A | `static/css/site.css:14`. Có thể giữ |  |
| 13 | Liên hệ | Màu placeholder | 1440, 390 | Không đặt màu (mặc định trình duyệt) | #5F6E78. Đọc từ CSS, chưa đo pixel | Nhỏ | A | `static/css/site.css:465` |  |
| 14 | Mọi trang | Skip link, viền focus | 1440, 390 | Không có | Có. Không thấy khi chưa dùng bàn phím | Nhỏ | C | `static/css/site.css:16,21`. Nên giữ |  |
| 15 | Mọi trang | Header mobile | 390 | Không có hamburger: logo, 6 mục dọc, nút. Header cao 361px | Hamburger, menu gập, header cao 81px. Áp dụng từ ≤1080px. Mở ra là danh sách rộng 358px, căn trái | Lớn | C | `templates/public/_header.html:11`, `static/css/site.css:144-156`. Commit e9cf9dd | [menu_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_menu_390.png)<br>[bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png) |
| 16 | Mọi trang | Nút header mobile | 390 | Hiện "Nhận tư vấn" 160x46 | Ẩn hẳn ở ≤600px, kể cả trong menu đã mở | Vừa | C | `static/css/site.css:158` | [menu_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_menu_390.png) |
| 17 | Mọi trang | Tên thương hiệu | 390 | 18px | 17px (≤600px), letter-spacing −.34px | Nhỏ | A | `static/css/site.css:159` | [menu_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_menu_390.png) |
| 18 | Mọi trang | H1 | 390 | 52px / lh 57,2 / ls −1,56 | 34px / lh 37,4 / ls −1,02 (`clamp(34px,6vw,52px)`) | Lớn | C | `static/css/site.css:169`. Commit e9cf9dd. Thiết kế có H1 tràn 71px ở Giới thiệu, nên cần một mức nhỏ hơn 52px nhưng con số 34px là tự chọn | [bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png)<br>[about_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_about_390.png) |
| 19 | Mọi trang | Lề hai bên | 390 | 24px | 16px (≤520px) | Vừa | C | `static/css/site.css:691` | [bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png) |
| 20 | Mọi trang | Đầu trang | 390 | padding-top 56, tabs margin-top 40, tab padding 16/22 | padding-top 40, tabs margin-top 28, tab padding 14/16 | Vừa | C | `static/css/site.css:693-695` | [bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png) |
| 21 | Mọi trang | Khung main | 390 | padding 48 / 110 | padding 32 / 72 | Vừa | C | `static/css/site.css:692` | [bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png) |
| 22 | Giới thiệu, Liên hệ | Tràn ngang | 390 | Trang rộng 461px (lỗi của `minmax(340px,1fr)`) | Rộng 390px, không tràn | Nhỏ | C | `static/css/site.css:653,663`. Nên giữ: sửa lỗi thiết kế | [about_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_about_390.png)<br>[contact_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_390.png) |

## Bonus

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 23 | Bonus | Thẻ: Hết hạn | 1440, 390 | "30/11" | "30/11/2026" | Vừa | C | `app/templating.py:72-73` dùng `short_date`. Commit 79c9f2b | [bonus_all_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_all_1440.png) |
| 24 | Bonus | Thẻ: lưới 3 cột điều kiện | 1440, 390 | 3 cột bằng nhau (77/77/77 ở 1440; 92,7 x3 ở 390). "Nạp tối thiểu" luôn 2 dòng ở 1440 | `1fr 1fr max-content`. Thẻ có "Liên tục" thành cột rộng hơn, "Nạp tối thiểu" 1 dòng, cả hàng tụt 16px, cột lệch +12/+25px; 390: 108,5/108,5/76,9. Thẻ cạnh nhau không còn thẳng hàng | Vừa | A | `static/css/site.css:525,530`. Trả lại 3 cột sau khi sửa định dạng ngày | [bonus_all_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_all_1440.png)<br>[bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png) |
| 25 | Bonus | Sort "Sắp hết hạn" | 1440 | Có ngày trước, "Liên tục" sau, giữ thứ tự nhập | Theo ngày tăng dần. 8/10 vị trí khác thiết kế. Hợp lý hơn nhưng tự quyết | Nhỏ | C | `app/queries.py:31`. Nên giữ |  |
| 26 | Bonus | Thanh sort | 390 | Pill căn trái, x=24 | Pill căn phải, x=40,8 | Nhỏ | A | `static/css/site.css:516` | [bonus_nodep_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_nodep_390.png) |
| 27 | Bonus | Padding ngang nút "Nhận bonus" | 1440, 390 | 13px | 20px. Kích thước nút vẫn bằng nhau do `flex:1` | Nhỏ | A | `static/css/site.css:532` |  |
| 28 | Bonus | Link "Nhận bonus" | 1440, 390 | `#`, cùng tab | `/go/broker/{id}`, tab mới, `rel=sponsored` | Nhỏ | B | Theo brief mục 7. Không cần sửa |  |
| 29 | Bonus | Thẻ: giấy phép cạnh tên sàn | 1440, 390 | Giấy phép riêng từng bonus (ngắn hơn) | Giấy phép đầy đủ của sàn, vì brief mục 6 chỉ có `license` ở Broker | Nhỏ | B | Không cần sửa | [bonus_all_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_bonus_all_1440.png) |

## Sàn: danh sách

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 30 | Sàn | Thứ tự sàn | 1440, 390 | Thứ tự nhập | Nổi bật trước, rồi tên theo byte: chữ hoa đứng trước chữ thường, nên "VT..." đứng trước "Va...". Admin không chỉnh được thứ tự | Vừa | C | `app/routes/public.py:212`. Commit 79c9f2b | [san_all_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_all_390.png) |
| 31 | Sàn | Breadcrumb | 1440, 390 | "Trang chủ / Sàn uy tín" | "Trang chủ / Sàn". H1 vẫn "Sàn giao dịch uy tín", thành ra không đồng nhất | Vừa | C | `app/content.py:179`. Commit 789490d (QA M5) | [san_all_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_all_390.png) |
| 32 | Sàn | Tên sàn trong hàng | 1440, 390 | Chữ thường | Link tới trang sàn, thêm một đích bấm | Nhỏ | C | `templates/public/broker_list.html:11` |  |
| 33 | Sàn | Hàng sàn | 390 | Padding 24; cột 150/135; "Xem đánh giá" 135x42 cạnh "Bonus đang có"; hàng cao 225px | Padding 20; cột 149/149; nút riêng một hàng, 318x42; hàng cao 272px | Vừa | C | `static/css/site.css:549-554` | [san_all_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_all_390.png) |

## So sánh

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 34 | So sánh | H1 | 1440, 390 | "Sàn giao dịch uy tín" | "So sánh sàn giao dịch" | Lớn | C | `app/content.py:183`. Commit 789490d | [san_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_1440.png) |
| 35 | So sánh | Mô tả | 1440, 390 | "Thông tin giấy phép, tài khoản, phí và phương thức nạp rút của từng sàn." | "So sánh giấy phép, mức nạp, đòn bẩy, phí và bonus của tối đa 3 sàn." | Vừa | C | `app/content.py:183` | [san_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_1440.png) |
| 36 | So sánh | Breadcrumb | 1440, 390 | "Trang chủ / Sàn uy tín" | "Trang chủ / Sàn / So sánh" (thêm một cấp) | Vừa | C | `app/routes/public.py:257` | [san_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_1440.png) |
| 37 | So sánh | Pill khi đã đủ 3 sàn | 1440, 390 | Pill bình thường, opacity 1, con trỏ pointer; bấm không có tác dụng | Pill mờ opacity .45, không bấm được, con trỏ not-allowed | Vừa | C | `templates/public/broker_compare.html:10`, `static/css/site.css:86`. Commit e9cf9dd | [san_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_1440.png) |
| 38 | So sánh | Thứ tự pill và cột | 1440, 390 | Thứ tự nhập | Theo tên; cột 2 và 3 đổi chỗ, dx ±357px | Vừa | C | `app/routes/public.py:212` | [san_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_1440.png) |
| 39 | So sánh | Thứ tự cột sau khi chọn lại | 1440 | Luôn theo thứ tự danh sách | Theo thứ tự bấm: bỏ cột đầu rồi chọn lại thì cột đó xuống cuối | Nhỏ | C | `app/routes/public.py:253` |  |
| 40 | So sánh | Dưới bảng | 1440, 390 | Không có | Thêm "Liên kết affiliate. CFD có rủi ro mất vốn cao do đòn bẩy." Trang dài thêm 39px. Câu lấy từ khung trang chi tiết sàn | Vừa | C | `templates/public/broker_compare.html:43`. Commit 9c29ee1, `docs/ISSUES.md:46-47` | [san_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_1440.png) |
| 41 | So sánh | Tên sàn ở đầu cột | 1440, 390 | Chữ thường | Link tới trang sàn | Nhỏ | C | `templates/public/broker_compare.html:21` |  |
| 42 | So sánh | Bỏ chọn hết | 1440 | Bảng chỉ còn nhãn, xếp vỡ | "Chưa chọn sàn nào. Chọn sàn ở trên để so sánh." Tốt hơn thiết kế | Nhỏ | C | `templates/public/broker_compare.html:45`. Nên giữ | [compare_none_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_compare_none_1440.png) |
| 43 | So sánh | Hover "Đánh giá" | 1440 | Không đổi | Viền #021623 | Nhỏ | A | `static/css/site.css:75` |  |
| 44 | So sánh | Bảng | 390 | Cột 180/200, padding 20, bảng rộng 780px, thấy 1 cột sàn | Cột 120/170, padding 14, bảng rộng 630px, thấy 1,3 cột sàn | Vừa | C | `static/css/site.css:569-572` | [san_compare_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_san_compare_390.png) |

## Chi tiết sàn (4 tab)

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 45 | Chi tiết sàn | Breadcrumb | 1440, 390 | "Trang chủ / Sàn uy tín / {sàn}" | "Trang chủ / Sàn / {sàn}", tên sàn lệch −40px | Vừa | C | `app/content.py:179`. Commit 789490d (QA M5) | [detail_overview_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_overview_1440.png) |
| 46 | Tab Bonus | Dòng ưu đãi: ngày | 1440, 390 | "... · hết hạn 31/12" | "... · hết hạn 31/12/2026" | Vừa | C | `templates/public/broker_detail.html:13` | [detail_bonus_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_bonus_390.png) |
| 47 | Tab Bonus | Thứ tự ưu đãi | 1440, 390 | Thứ tự nhập | Giá trị giảm dần | Nhỏ | C | `app/routes/public.py:275` | [detail_bonus_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_bonus_390.png) |
| 48 | Tab Bonus | Dòng ưu đãi | 390 | 3 cột 120/1fr/auto: chữ vỡ từng từ, nút đè lên chữ, hàng cao ~280-325px | Xếp dọc, nút căn trái, hàng cao ~190-210px. Sửa lỗi thiết kế | Lớn | C | `static/css/site.css:614-615`. Nên giữ | [detail_bonus_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_bonus_390.png) |
| 49 | Tab Tài khoản, Nạp & rút | Ô bảng khi hàng 2 dòng | 1440 | Căn đỉnh (grid) | Căn giữa (table), chữ tụt +10px. Các vị trí chữ khác lệch dưới 2px | Nhỏ | A | `static/css/site.css:596` thêm `vertical-align:top` | [detail_pay_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_pay_1440.png) |
| 50 | Tab Tổng quan | Viền Ưu điểm/Lưu ý | 1440, 390 | rgba(2,22,35,.08) | rgba(2,22,35,.06) | Nhỏ | A | `static/css/site.css:585` |  |
| 51 | Tab Tổng quan | Khối nội dung | 390 | Padding 32 | Padding 20 | Vừa | C | `static/css/site.css:612` | [detail_bonus_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_bonus_390.png) |
| 52 | Tab Tổng quan | Ưu điểm/Lưu ý | 390 | 2 cột 127px, mỗi mục 2-3 dòng | 1 cột 318px | Vừa | C | `static/css/site.css:613` |  |
| 53 | Chi tiết sàn | Khung sàn | 390 | sticky, top 24 | static | Nhỏ | C | `static/css/site.css:616` | [detail_bonus_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_detail_bonus_390.png) |

## Tin tức

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 54 | Tin tức | Ảnh thẻ khi bài chưa có ảnh | 1440, 390 | Khối ảnh cao 220px có viền chấm và chữ "Ảnh bài viết" | Không có khối. Thẻ cao ~147px thay vì ~365px (đo trên ảnh ghép). Brief mục 4 yêu cầu "khối nền trung tính, không có chữ placeholder"; commit 2074962 đổi thành không in gì. Việc bỏ chữ placeholder là B, việc bỏ cả khối là C | Lớn | C | `templates/public/_macros.html:3-6`. Trả lại `<div class="media">` luôn in | [noimg_tin_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_tin_1440.png) |
| 55 | Tin tức | Xuống dòng tiêu đề thẻ | 1440, 390 | Xuống dòng thường, có từ mồ côi | `text-wrap:pretty`, chỗ ngắt khác (rộng dòng −60px ở ca đo được) | Nhỏ | A | `static/css/site.css:509` | [noimg_tin_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_tin_1440.png) |
| 56 | Tin tức | Hover thẻ | 1440 | Không đổi | Tiêu đề đổi #1944DF, có transition | Nhỏ | A | `static/css/site.css:495` |  |
| 57 | Tin tức | Phân trang | 1440, 390 | Không có, hiện hết | 12 bài/trang, có "Trang trước/sau". Đọc từ code, 8 bài mẫu không kích hoạt nên chưa chụp | Nhỏ | C | `app/routes/public.py:26`, `templates/public/post_list.html:8` |  |

## Bài viết

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 58 | Bài viết | Dòng dưới H1 | 1440, 390 | "{chuyên mục} · {n} phút đọc" | Tóm tắt bài (`excerpt`), rỗng thì không có dòng. Đầu trang thấp đi 42px, toàn bộ nội dung nhích lên | Lớn | C | `app/routes/public.py:327`. Commit 79c9f2b | [article_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_article_1440.png) |
| 59 | Bài viết | Khối "Bài viết liên quan" | 1440, 390 | Không có | Thêm tiêu đề 28px và tối đa 3 thẻ. Trang dài thêm 455px (1440, 1 bài liên quan) | Lớn | C | `templates/public/post_detail.html:12-19`, `app/routes/public.py:326`. Commit 79c9f2b, e9cf9dd | [article_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_article_1440.png)<br>[article_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_article_390.png) |
| 60 | Bài viết | Ảnh bìa khi chưa có ảnh | 1440, 390 | Khối ảnh cao 400px | Không có khối, nội dung nhảy lên đầu. Cùng nguyên nhân với thẻ Tin tức | Lớn | C | `templates/public/post_detail.html:7`, `templates/public/_macros.html:3-6` | [noimg_article_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_article_1440.png) |
| 61 | Bài viết | Ngày trong dòng meta | 1440, 390 | "28/10" | "28/10/2026" | Vừa | C | `templates/public/post_detail.html:8` dùng `date_vn`. Commit e9cf9dd | [article_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_article_1440.png) |
| 62 | Bài viết | Nút "Về danh sách" | 1440 | Giữ chuyên mục đang lọc (về 2 bài) | Luôn về `/tin-tuc` (8 bài), mất bộ lọc | Nhỏ | A | `templates/public/post_detail.html:10` |  |
| 63 | Bài viết | Hover "Về danh sách" | 1440 | Không đổi | Viền #021623 | Nhỏ | A | `static/css/site.css:625` |  |
| 64 | Bài viết | Ảnh bìa | 390 | Cao 400px | Cao 220px | Vừa | C | `static/css/site.css:628` | [article_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_article_390.png) |
| 65 | Bài viết | Thân bài | 390 | 17px / lh 30,6 | 16px / lh 28,8 | Nhỏ | C | `static/css/site.css:650` | [article_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_article_390.png) |

## Giới thiệu

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 66 | Về chúng tôi, Cách đánh giá, Affiliate | Khi tab chưa có ảnh | 1440 | 2 cột: 3 khối dọc bên trái, khối ảnh 602x520 bên phải | Không có khối ảnh, 3 khối xếp thành 3 cột ngang, trang thấp đi 191px. Commit 2074962 thêm rule riêng cho ca này | Lớn | C | `static/css/site.css:655`, `templates/public/_macros.html:3-6` | [noimg_about_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_about_1440.png) |
| 67 | Cách đánh giá | H1 | 1440, 390 | "Về TradingBonusHub" | "Cách chúng tôi đánh giá" | Lớn | C | `app/content.py:184`. Commit 789490d | [method_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_method_1440.png) |
| 68 | Cách đánh giá | Mô tả | 1440, 390 | "Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt." | "Các tiêu chí chúng tôi dùng khi tóm tắt bonus và thông tin sàn giao dịch." Một dòng thay vì hai, đầu trang thấp đi 28px | Vừa | C | `app/content.py:184` | [method_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_method_1440.png) |
| 69 | Cách đánh giá | Khối 03: tiêu đề | 1440, 390 | "Khối lượng yêu cầu" | "Mức nạp và thời hạn" | Vừa | C | `app/content.py:250`. Commit 789490d (QA M3: mô hình không có trường khối lượng). QA_REPORT ghi là "Quyết định cần user" | [method_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_method_1440.png) |
| 70 | Cách đánh giá | Khối 03: nội dung | 1440, 390 | "Quy đổi yêu cầu khối lượng sang số lot cụ thể để dễ so sánh giữa các sàn." | "Ghi rõ mức nạp tối thiểu và thời hạn của từng ưu đãi để dễ so sánh giữa các sàn." | Vừa | C | `app/content.py:250` | [method_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_method_1440.png) |
| 71 | Công bố affiliate | H1 | 1440, 390 | "Về TradingBonusHub" | "Công bố affiliate" | Lớn | C | `app/content.py:185`. Commit 789490d | [affiliate_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_affiliate_1440.png) |
| 72 | Công bố affiliate | Mô tả | 1440, 390 | "Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt." | "Cách trang này có thu nhập và điều đó ảnh hưởng đến bạn thế nào." Đầu trang thấp đi 28px | Vừa | C | `app/content.py:185` | [affiliate_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_affiliate_1440.png) |
| 73 | Cách đánh giá, Affiliate | Breadcrumb | 1440, 390 | "Trang chủ / Giới thiệu" | "Trang chủ / Giới thiệu / {tên tab}" | Vừa | C | `app/routes/public.py:348`. Commit 2e4229e | [method_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_method_1440.png)<br>[affiliate_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_affiliate_1440.png) |
| 74 | Giới thiệu | Bố cục | 390 | Khối padding 28, ảnh cao 520 sticky, gap 48 | Khối padding 22, ảnh cao 300 static, gap 24 | Vừa | C | `static/css/site.css:661` | [about_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_about_390.png) |

## Liên hệ

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 75 | Liên hệ | H1 | 1440, 390 | "Về TradingBonusHub" | "Liên hệ". `docs/ISSUES.md:26-27` nói thiết kế "không có header riêng" nên tự đặt; thực tế thiết kế dùng header chung của Giới thiệu | Lớn | C | `app/content.py:182`. Commit 79c9f2b | [contact_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_1440.png) |
| 76 | Liên hệ | Mô tả | 1440, 390 | "Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt." | "Gửi câu hỏi, báo lỗi thông tin bonus hoặc đề nghị hợp tác." Đầu trang thấp đi 28px | Vừa | C | `app/content.py:182` | [contact_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_1440.png) |
| 77 | Liên hệ | Breadcrumb | 1440, 390 | "Trang chủ / Giới thiệu" | "Trang chủ / Liên hệ" | Vừa | C | `app/routes/public.py` hàm `_contact_ctx` | [contact_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_1440.png) |
| 78 | Liên hệ | Câu trong khung navy | 1440, 390 | "Chúng tôi phản hồi trong 1–2 ngày làm việc. Chúng tôi không tư vấn đầu tư cá nhân." (2 dòng) | "Chúng tôi sẽ trả lời qua email. Chúng tôi không tư vấn đầu tư cá nhân." (1 dòng) | Vừa | C | `app/content.py:261`. Commit 789490d | [contact_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_1440.png) |
| 79 | Liên hệ | Email trong khung navy | 1440, 390 | Chữ thường | Link `mailto:`, hover đổi #E4E9EE | Nhỏ | C | `templates/public/contact.html:8-9` |  |
| 80 | Liên hệ | Gửi form rỗng | 1440 | Hiện "Đã gửi" ngay (mô phỏng) | Báo lỗi dưới ô, ở URL `/api/contact` | Nhỏ | B | Brief mục 7, 8. Không cần sửa |  |
| 81 | Liên hệ | Bố cục | 390 | Padding 36; Họ tên và Email 2 cột 128px | Padding 24/16; 1 cột 306px | Vừa | C | `static/css/site.css:679-680` | [contact_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_contact_390.png) |

## Chỉ khác do thiếu dữ liệu

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 82 | Bonus | Nút "Nhận bonus" | 1440 | Luôn có | Sàn chưa có link affiliate thì ẩn, "Về sàn" giãn hết hàng | Vừa | D | `templates/public/_macros.html`, thẻ bonus. Nhập link ở admin | [noimg_bonus_noaff_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_bonus_noaff_1440.png) |
| 83 | So sánh | Nút "Mở tài khoản", câu affiliate | 1440 | Luôn có | Không có link thì ẩn cả hai | Vừa | D | Nhập link ở admin | [noimg_compare_noaff_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_compare_noaff_1440.png) |
| 84 | Chi tiết sàn | Nút và câu trong khung sàn | 1440 | Luôn có | Không có link thì khung chỉ còn tên và một câu, cao giảm từ ~251px xuống ~150px (đo trên ảnh ghép) | Vừa | D | Nhập link ở admin | [noimg_detail_noaff_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_noimg_detail_noaff_1440.png) |
| 85 | Liên hệ | Email, Hợp tác, Telegram | 1440, 390 | Luôn có (dữ liệu demo) | Rỗng thì ẩn từng dòng, khung navy còn lại trống | Vừa | D | Nhập ở Cài đặt | [empty_contact_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_contact_1440.png) |

## Trạng thái DB rỗng (so riêng)

Phía thiết kế: thay BONUSES, BROKERS, POSTS bằng mảng rỗng lúc tải trang, để thấy đúng hành vi thiết kế khi không có dữ liệu.

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Loại | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|---|
| 86 | Bonus, Sàn, Tin | Số đếm ở tab | 1440, 390 | "0" | Ẩn | Vừa | B | Brief mục 5. Không cần sửa | [empty_bonus_nodep_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_bonus_nodep_1440.png) |
| 87 | Bonus | "0 ưu đãi" | 1440, 390 | Hiện | Ẩn. Khối báo rỗng nằm cao hơn ~24px vì thiết kế có thêm một khoảng gap của lưới rỗng | Nhỏ | B | Brief mục 5 | [empty_bonus_nodep_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_bonus_nodep_1440.png) |
| 88 | Bonus | Câu báo rỗng | 1440, 390 | "Chưa có ưu đãi trong mục này.", nền trắng, padding 48 | Giống hệt | Nhỏ | Khớp | Không | [empty_bonus_nodep_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_bonus_nodep_1440.png) |
| 89 | Sàn | Danh sách rỗng | 1440, 390 | Trống trơn | "Chưa có sàn nào." | Vừa | B | Brief mục 5 | [empty_san_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_san_1440.png) |
| 90 | So sánh | Không có sàn | 1440, 390 | "Chọn tối đa 3 sàn:" và bảng nhãn xếp vỡ | Bỏ cả hai, chỉ còn "Chưa có sàn nào." | Vừa | B | Brief mục 5 | [empty_compare_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_compare_1440.png) |
| 91 | Tin tức | Danh sách rỗng | 1440, 390 | Trống trơn | "Chưa có bài viết nào." | Vừa | B | Brief mục 5 | [empty_tin_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_tin_1440.png) |
| 92 | Sàn, So sánh | "Bonus đang có" = 0 | 1440, 390 | "0" | "—". Đọc từ code, chưa chụp | Nhỏ | B | `templates/public/broker_list.html:17` |  |
| 93 | Giới thiệu | Thiếu ảnh | 1440, 390 | Khối ảnh placeholder | Không có khối, 3 cột. Trùng dòng ở mục Giới thiệu, là C, không phải do DB rỗng | Lớn | C | Xem mục Giới thiệu | [empty_about_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots/pair_empty_about_1440.png) |

## Câu chữ đổi so với thiết kế (nguyên văn)

Đối chiếu mọi chữ hiển thị trên 18 màn. Ngoài danh sách này, chữ tĩnh trùng khớp nguyên văn, kể cả các khối ABOUT của tab Về chúng tôi và Affiliate, nhãn cột, nhãn tab, nút, placeholder, cảnh báo rủi ro, copyright.

| Vị trí | Thiết kế gốc | Bản dựng |
|---|---|---|
| Menu | Sàn uy tín | Sàn |
| Nút header | Nhận tư vấn | Xem bonus |
| Breadcrumb mục Sàn | Sàn uy tín | Sàn |
| H1 So sánh | Sàn giao dịch uy tín | So sánh sàn giao dịch |
| Mô tả So sánh | Thông tin giấy phép, tài khoản, phí và phương thức nạp rút của từng sàn. | So sánh giấy phép, mức nạp, đòn bẩy, phí và bonus của tối đa 3 sàn. |
| H1 Cách đánh giá | Về TradingBonusHub | Cách chúng tôi đánh giá |
| Mô tả Cách đánh giá | Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt. | Các tiêu chí chúng tôi dùng khi tóm tắt bonus và thông tin sàn giao dịch. |
| Khối 03 Cách đánh giá, tiêu đề | Khối lượng yêu cầu | Mức nạp và thời hạn |
| Khối 03 Cách đánh giá, nội dung | Quy đổi yêu cầu khối lượng sang số lot cụ thể để dễ so sánh giữa các sàn. | Ghi rõ mức nạp tối thiểu và thời hạn của từng ưu đãi để dễ so sánh giữa các sàn. |
| H1 Affiliate | Về TradingBonusHub | Công bố affiliate |
| Mô tả Affiliate | Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt. | Cách trang này có thu nhập và điều đó ảnh hưởng đến bạn thế nào. |
| H1 Liên hệ | Về TradingBonusHub | Liên hệ |
| Mô tả Liên hệ | Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt. | Gửi câu hỏi, báo lỗi thông tin bonus hoặc đề nghị hợp tác. |
| Ghi chú Liên hệ | Chúng tôi phản hồi trong 1–2 ngày làm việc. Chúng tôi không tư vấn đầu tư cá nhân. | Chúng tôi sẽ trả lời qua email. Chúng tôi không tư vấn đầu tư cá nhân. |
| Dòng dưới H1 bài viết | {chuyên mục} · {n} phút đọc | Tóm tắt bài, hoặc không có |
| Ngày (thẻ bonus, tab Bonus, meta bài viết) | 31/12 | 31/12/2026 |

Chữ mới không có trong thiết kế: "Bài viết liên quan"; câu affiliate dưới bảng so sánh (câu có sẵn, vị trí mới); "Chưa chọn sàn nào. Chọn sàn ở trên để so sánh."; "Trang trước", "Trang sau"; các câu báo rỗng; lỗi form.

## Trang không có trong thiết kế (thêm mới)

| Trang | Cùng phong cách? | Ghi chú |
|---|---|---|
| `/dieu-khoan`, `/bao-mat` | Có: cùng header, đầu trang navy, footer; nội dung trên thẻ trắng rộng tối đa 860px | Nội dung do dev viết (`app/content.py:17` ghi là bản nháp, chủ site cần đọc lại) |
| 404 | Có: thẻ trắng, số 404 xanh, 2 nút | |
| `/xac-nhan`, `/huy-dang-ky` (token sai) | Có: cùng thẻ với 404 | Chỉ chụp trạng thái token sai |
| 500 | Chưa chụp được | Chỉ đọc template, cùng khung với 404 |

## Đã khớp (đo được)

- 1440: header cao 83px, logo 40x40, cỡ chữ và màu menu, nút header (padding, icon 36px, hover), nền đầu trang, breadcrumb, H1 52px/57,2/−1,56, mô tả 17px, tab (padding, viền, màu), số đếm, main 48/110, footer và 2 câu trong footer.
- Bonus 1440: lưới 4 cột, thẻ 295px, nền, số tiền 40px, tag, nút và hover, sort "Mới nhất" và "Giá trị cao" đúng thứ tự, sort giữ khi đổi tab, số đếm tab.
- Sàn 1440: hàng, avatar 56px, cột, nút và hover. Chiều cao trang bằng nhau.
- Chi tiết sàn 1440: 4 tab, ô thông tin, Ưu điểm/Lưu ý, khung sàn sticky, vị trí chữ trong bảng lệch dưới 2px.
- Tin tức 1440 (có ảnh): lưới, thẻ, ảnh 220px, meta, ngày ngắn ở thẻ. Chiều cao trang bằng nhau.
- Bài viết 1440: cột 780px, ảnh 400px, 17px/30,6, khoảng cách đoạn 24px, nút quay lại.
- Về chúng tôi 1440 (có ảnh): bố cục, ảnh 602x520 sticky. Chiều cao trang bằng nhau.
- Liên hệ 1440: toàn bộ kích thước khung và form bằng nhau, chỉ lệch dọc 28px do mô tả ngắn hơn. Trạng thái "Đã gửi": khối 539x99, nền #F5F5F5, chữ giống hệt.
- Link: logo, menu, nút header, "Về sàn", "Xem đánh giá", "Đánh giá", breadcrumb bài viết về chuyên mục.
- Bảng so sánh: 8 hàng đúng nhãn, đúng thứ tự, dòng xen kẽ.

## Chưa so được

- Trang 500; trang xác nhận và hủy đăng ký với token đúng.
- Khổ giữa 1440 và 390 (768, 1080), trong đó hamburger xuất hiện từ ≤1080px.
- Dữ liệu thật ở cổng 8000: theo yêu cầu không đụng tới. Những gì user đang thấy có thể khác vì phụ thuộc dữ liệu thật, đặc biệt là việc có ảnh hay không.
- Hover menu chưa chọn: kết luận từ CSS, không đo trực tiếp.
- Sticky: chỉ kiểm tra thuộc tính `position`, không cuộn thử.

## Vòng 2 (commit 272be90, đối chiếu docs/TEAM_BRIEF.md mục 13)

Đo lại từ đầu, không dùng báo cáo dev. DB tạm mới với dữ liệu của thiết kế; 18 màn ở 1440 và 390; thêm thiếu ảnh và thiếu link (`noimg`), DB rỗng (`empty`), hover, link, sort, chọn sàn, form. Ảnh giả và cách đo như vòng 1. Ảnh ghép vòng 2 nằm ở `C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots2/`. Hai server đã tắt, cổng 8000 không bị đụng.

Quy ước: mọi khác biệt ngoài danh sách GIỮ của mục 13 là CÒN, kể cả khi `docs/ISSUES.md` ghi "giữ có lý do" nhưng vẫn khôi phục được. Tiêu chuẩn "Được phép" là suy luận của kiểm toán từ mục 13; dòng 48 và 89-91 nên được user hoặc team leader xác nhận.

### Kết quả

| | Lớn | Vừa | Nhỏ | Tổng |
|---|---|---|---|---|
| Còn lệch (6 dòng cũ, 4 mới) | 0 | 2 | 8 | 10 |

Dòng cũ: 71 đã khôi phục, 16 được phép, 6 còn (tổng 93, gồm 85 dòng chính và 8 dòng DB rỗng).

Đo được ở 1440, có dữ liệu và thiếu ảnh: chiều cao cả 18 màn bằng đúng thiết kế, không còn chữ hay kiểu chữ nào khác, trừ giấy phép trên thẻ bonus (dữ liệu DB). Ở 390: mọi màn nhích đều −280px do hamburger; ngoài ra chỉ khác ở Giới thiệu, Liên hệ (chống tràn), hàng sàn −11px, tab Bonus của chi tiết sàn và M2, M4.

### Từng dòng cũ

| # | Trang | Vị trí | Trạng thái | Ghi chú đo được |
|---|---|---|---|---|
| 1 | Mọi trang | Menu, mục thứ 3 | ĐÃ KHÔI PHỤC | "Sàn uy tín" ở mọi trang con |
| 2 | Mọi trang | Nút header | ĐÃ KHÔI PHỤC | "Nhận tư vấn", tới `/bonus` |
| 3 | Liên hệ | Menu: mục đang chọn | ĐÃ KHÔI PHỤC | Mục "Giới thiệu" sáng |
| 4 | Mọi trang | Đổi tab, sort, chọn sàn | CÒN | Sort: cuộn 400→0, thiết kế giữ 400. Do server render (mục 3), mục 13 không liệt kê, chưa ghi ISSUES. Vừa |
| 5 | Bonus, Sàn, Tin, Giới thiệu | Mục cuối breadcrumb | ĐÃ KHÔI PHỤC | Mục cuối là link |
| 6 | Mọi trang | Hover menu chưa chọn | ĐÃ KHÔI PHỤC | Hover đo trực tiếp, không đổi |
| 7 | Mọi trang | Hover tab chưa chọn | ĐÃ KHÔI PHỤC |  |
| 8 | Mọi trang | Hover breadcrumb | ĐÃ KHÔI PHỤC |  |
| 9 | Bonus, So sánh | Hover pill sort/chọn sàn | ĐÃ KHÔI PHỤC |  |
| 10 | Mọi trang | Chuyển trạng thái nút | ĐÃ KHÔI PHỤC | Duration 0s; không còn transition trên nút |
| 11 | Bonus, Sàn, Tin, chi tiết | Số đếm ở tab đang chọn | ĐÃ KHÔI PHỤC |  |
| 12 | Bonus, So sánh, Bài viết, Liên hệ | Chữ nút trắng (Về sàn, Đánh giá, Về danh sách), chữ trong ô nhập | ĐÃ KHÔI PHỤC | Về sàn, Đánh giá #000; hết sai màu chữ khi đo |
| 13 | Liên hệ | Màu placeholder | ĐÃ KHÔI PHỤC | Đã bỏ rule màu placeholder (đọc CSS) |
| 14 | Mọi trang | Skip link, viền focus | Được phép | Sửa của QA, không thấy khi không dùng bàn phím |
| 15 | Mọi trang | Header mobile | Được phép | Hamburger, header 81px, mọi nội dung dưới header nhích đúng −280px |
| 16 | Mọi trang | Nút header mobile | Được phép | Nút nằm trong menu mở ra, đúng nhãn, đúng kích thước. Đi kèm hamburger |
| 17 | Mọi trang | Tên thương hiệu | ĐÃ KHÔI PHỤC |  |
| 18 | Mọi trang | H1 | ĐÃ KHÔI PHỤC | 52px; riêng "Về TradingBonusHub" xem dòng 22 |
| 19 | Mọi trang | Lề hai bên | ĐÃ KHÔI PHỤC |  |
| 20 | Mọi trang | Đầu trang | ĐÃ KHÔI PHỤC |  |
| 21 | Mọi trang | Khung main | ĐÃ KHÔI PHỤC |  |
| 22 | Giới thiệu, Liên hệ | Tràn ngang | Được phép | Không tràn. H1 40,35px rộng 339/342px, cỡ tối đa vừa màn là ~40,7px: đạt "cỡ lớn nhất vừa màn" |
| 23 | Bonus | Thẻ: Hết hạn | ĐÃ KHÔI PHỤC |  |
| 24 | Bonus | Thẻ: lưới 3 cột điều kiện | ĐÃ KHÔI PHỤC |  |
| 25 | Bonus | Sort "Sắp hết hạn" | CÒN | Vẫn theo ngày tăng dần, 8/10 vị trí khác. ISSUES ghi "giữ có lý do", dev tự giữ. Nhỏ |
| 26 | Bonus | Thanh sort | ĐÃ KHÔI PHỤC |  |
| 27 | Bonus | Padding ngang nút "Nhận bonus" | ĐÃ KHÔI PHỤC |  |
| 28 | Bonus | Link "Nhận bonus" | Được phép | Link thật thay `#`, cùng hình dạng nút |
| 29 | Bonus | Thẻ: giấy phép cạnh tên sàn | Được phép | Dữ liệu DB: giấy phép của sàn thay mock của bonus |
| 30 | Sàn | Thứ tự sàn | ĐÃ KHÔI PHỤC |  |
| 31 | Sàn | Breadcrumb | ĐÃ KHÔI PHỤC |  |
| 32 | Sàn | Tên sàn trong hàng | ĐÃ KHÔI PHỤC |  |
| 33 | Sàn | Hàng sàn | Được phép | Padding và nút đúng thiết kế; cột 2 lệch −11px để nút không lấn padding. Đã ghi ISSUES |
| 34 | So sánh | H1 | ĐÃ KHÔI PHỤC |  |
| 35 | So sánh | Mô tả | ĐÃ KHÔI PHỤC |  |
| 36 | So sánh | Breadcrumb | ĐÃ KHÔI PHỤC |  |
| 37 | So sánh | Pill khi đã đủ 3 sàn | ĐÃ KHÔI PHỤC |  |
| 38 | So sánh | Thứ tự pill và cột | ĐÃ KHÔI PHỤC |  |
| 39 | So sánh | Thứ tự cột sau khi chọn lại | ĐÃ KHÔI PHỤC |  |
| 40 | So sánh | Dưới bảng | ĐÃ KHÔI PHỤC |  |
| 41 | So sánh | Tên sàn ở đầu cột | ĐÃ KHÔI PHỤC |  |
| 42 | So sánh | Bỏ chọn hết | CÒN | Vẫn câu "Chưa chọn sàn nào..." thay bảng nhãn. ISSUES ghi giữ, dev tự giữ. Nhỏ |
| 43 | So sánh | Hover "Đánh giá" | ĐÃ KHÔI PHỤC |  |
| 44 | So sánh | Bảng | ĐÃ KHÔI PHỤC |  |
| 45 | Chi tiết sàn | Breadcrumb | ĐÃ KHÔI PHỤC |  |
| 46 | Tab Bonus | Dòng ưu đãi: ngày | ĐÃ KHÔI PHỤC |  |
| 47 | Tab Bonus | Thứ tự ưu đãi | ĐÃ KHÔI PHỤC |  |
| 48 | Tab Bonus | Dòng ưu đãi | Được phép | Giữ xếp dọc vì thiết kế tự lỗi ở 390 (nút đè chữ). Cao hàng 216 so với 324px. Đã ghi ISSUES; đây là khác biệt mobile lớn nhất còn lại, nên user xác nhận |
| 49 | Tab Tài khoản, Nạp & rút | Ô bảng khi hàng 2 dòng | ĐÃ KHÔI PHỤC | 1440 hết lệch. Ở 390 xem M2 |
| 50 | Tab Tổng quan | Viền Ưu điểm/Lưu ý | ĐÃ KHÔI PHỤC |  |
| 51 | Tab Tổng quan | Khối nội dung | ĐÃ KHÔI PHỤC |  |
| 52 | Tab Tổng quan | Ưu điểm/Lưu ý | ĐÃ KHÔI PHỤC |  |
| 53 | Chi tiết sàn | Khung sàn | ĐÃ KHÔI PHỤC |  |
| 54 | Tin tức | Ảnh thẻ khi bài chưa có ảnh | ĐÃ KHÔI PHỤC | Khối 220px, chiều cao trang = thiết kế. Không chữ và không viền chấm. Màu nền xem M1 |
| 55 | Tin tức | Xuống dòng tiêu đề thẻ | ĐÃ KHÔI PHỤC |  |
| 56 | Tin tức | Hover thẻ | ĐÃ KHÔI PHỤC |  |
| 57 | Tin tức | Phân trang | ĐÃ KHÔI PHỤC | Đã bỏ phân trang (đọc code) |
| 58 | Bài viết | Dòng dưới H1 | ĐÃ KHÔI PHỤC | "{chuyên mục} · {n} phút đọc" |
| 59 | Bài viết | Khối "Bài viết liên quan" | ĐÃ KHÔI PHỤC |  |
| 60 | Bài viết | Ảnh bìa khi chưa có ảnh | ĐÃ KHÔI PHỤC | Khối 400px |
| 61 | Bài viết | Ngày trong dòng meta | ĐÃ KHÔI PHỤC |  |
| 62 | Bài viết | Nút "Về danh sách" | ĐÃ KHÔI PHỤC |  |
| 63 | Bài viết | Hover "Về danh sách" | ĐÃ KHÔI PHỤC |  |
| 64 | Bài viết | Ảnh bìa | ĐÃ KHÔI PHỤC |  |
| 65 | Bài viết | Thân bài | ĐÃ KHÔI PHỤC |  |
| 66 | Về chúng tôi, Cách đánh giá, Affiliate | Khi tab chưa có ảnh | ĐÃ KHÔI PHỤC | 2 cột, khối 602x520, trang 1229=1229 |
| 67 | Cách đánh giá | H1 | ĐÃ KHÔI PHỤC |  |
| 68 | Cách đánh giá | Mô tả | ĐÃ KHÔI PHỤC |  |
| 69 | Cách đánh giá | Khối 03: tiêu đề | ĐÃ KHÔI PHỤC |  |
| 70 | Cách đánh giá | Khối 03: nội dung | ĐÃ KHÔI PHỤC |  |
| 71 | Công bố affiliate | H1 | ĐÃ KHÔI PHỤC |  |
| 72 | Công bố affiliate | Mô tả | ĐÃ KHÔI PHỤC |  |
| 73 | Cách đánh giá, Affiliate | Breadcrumb | ĐÃ KHÔI PHỤC |  |
| 74 | Giới thiệu | Bố cục | ĐÃ KHÔI PHỤC |  |
| 75 | Liên hệ | H1 | ĐÃ KHÔI PHỤC |  |
| 76 | Liên hệ | Mô tả | ĐÃ KHÔI PHỤC |  |
| 77 | Liên hệ | Breadcrumb | ĐÃ KHÔI PHỤC |  |
| 78 | Liên hệ | Câu trong khung navy | ĐÃ KHÔI PHỤC |  |
| 79 | Liên hệ | Email trong khung navy | ĐÃ KHÔI PHỤC |  |
| 80 | Liên hệ | Gửi form rỗng | Được phép | Kiểm tra form thật: logic, không đổi giao diện khi chưa lỗi |
| 81 | Liên hệ | Bố cục | ĐÃ KHÔI PHỤC | Padding 36, 2 cột. Khung 322 thay 340px và ô nhập 119 thay 128px: được phép vì chống tràn |
| 82 | Bonus | Nút "Nhận bonus" | Được phép | Không có link trong DB thì ẩn nút |
| 83 | So sánh | Nút "Mở tài khoản", câu affiliate | Được phép | Không có link trong DB thì ẩn. Câu affiliate đã bỏ |
| 84 | Chi tiết sàn | Nút và câu trong khung sàn | Được phép | Không có link trong DB thì ẩn |
| 85 | Liên hệ | Email, Hợp tác, Telegram | Được phép | Rỗng thì ẩn dòng. Có dữ liệu ở 390: email 17,2 và 15,4px để vừa khung, đạt quy tắc cỡ chữ |
| 86 | Bonus, Sàn, Tin | Số đếm ở tab | CÒN | Tab 0 vẫn ẩn; thiết kế in "0", và trạng thái này xảy ra cả khi có dữ liệu. Mục 13 đè mục 5. Vừa |
| 87 | Bonus | "0 ưu đãi" | CÒN | "0 ưu đãi" vẫn ẩn; thiết kế có màn này. Nhỏ |
| 88 | Bonus | Câu báo rỗng | ĐÃ KHÔI PHỤC | Chữ và kiểu khớp. Vị trí xem M3 |
| 89 | Sàn | Danh sách rỗng | Được phép | Thiết kế không có màn rỗng cho Sàn; để trắng là do tôi xóa mock |
| 90 | So sánh | Không có sàn | Được phép | Như dòng 89 |
| 91 | Tin tức | Danh sách rỗng | Được phép | Như dòng 89 |
| 92 | Sàn, So sánh | "Bonus đang có" = 0 | CÒN | `/san` vẫn "—", thiết kế in "0" (đọc code, chưa chụp). Bảng so sánh cũng vậy. Nhỏ |
| 93 | Giới thiệu | Thiếu ảnh | ĐÃ KHÔI PHỤC | Khối ảnh giữ nguyên, 2 cột |

### Khác biệt mới hoặc vòng 1 chưa ghi

| # | Trang | Vị trí | Viewport | Thiết kế gốc | Bản dựng | Mức | Cách sửa | Ảnh ghép |
|---|---|---|---|---|---|---|---|---|
| M1 | Tin tức, Bài viết, Giới thiệu | Màu khối ảnh trống | 1440, 390 | rgba(127,127,127,.08): pixel 245 trên thẻ trắng, 235 trên nền xám | rgba(127,127,127,.12): pixel 239 và 230 | Nhỏ | `static/css/tokens.css:24` | [noimg_about_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots2/pair_noimg_about_1440.png) |
| M2 | Chi tiết sàn, tab Tài khoản và Nạp & rút | Cột cuối bảng | 390 | Chữ cột cuối ở vị trí chuẩn | Lệch +3px do `<table>` với cột 32/24% | Nhỏ | `static/css/site.css:525-526` | [detail_pay_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots2/pair_detail_pay_390.png) |
| M3 | Bonus, DB rỗng hoặc tab 0 mục | Vị trí khối báo rỗng | 1440 | y=500 (thêm một gap của lưới rỗng) | y=476, cao hơn 24px | Nhỏ | `templates/public/bonus_list.html:11` | [empty_bonus_nodep_1440](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots2/pair_empty_bonus_nodep_1440.png) |
| M4 | Chi tiết sàn | Dải tab | 390 | Giữ vị trí cuộn sau khi bấm tab | Tải lại trang nên dải về đầu: tab đang chọn lệch +43 đến +157px, có thể bị khuất. Cùng nguyên nhân dòng 4 | Nhỏ | `templates/base_public.html:52`, hoặc cuộn tab đang chọn vào vùng nhìn | [detail_pay_390](file:///C:/Users/danhh/AppData/Local/Temp/claude/17ec8c0066fedc03/0e1ca350-6c2d-4075-8d81-f49e661aa4cb/scratchpad/design-pages/shots2/pair_detail_pay_390.png) |

### Không tính là lệch giao diện, nhưng nên biết

- Chuỗi "Sàn uy tín" và "Nhận tư vấn" trong file thiết kế dùng dạng Unicode không chuẩn NFC, bản dựng dùng NFC. Mắt thường không thấy; vị trí menu lệch 1px.
- `/dieu-khoan`, `/bao-mat` không còn link nào trên site (đúng thiết kế, đã ghi ISSUES). Chính sách bảo mật thường cần link công khai: user nên quyết.
- Mặc định mới chỉ có tác dụng với khóa Setting chưa từng lưu. Nếu `data/app.db` đã lưu các khóa cũ qua admin thì site thật có thể vẫn hiện chữ cũ. Vòng này đo trên DB tạm nên chưa xác nhận điều đó.

### Chưa so được

Trang 500; xác nhận và hủy đăng ký với token đúng; khổ 768 và 1080; dữ liệu thật ở cổng 8000; sticky chỉ kiểm tra thuộc tính; `bonus_count` = 0 có dữ liệu chỉ đọc code.
