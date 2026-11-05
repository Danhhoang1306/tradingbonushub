# QA Report

## Kiểm thử chức năng

Người kiểm: qa-func, ngày 05/11/2026, trên commit 9c29ee1. Chromium (Playwright) + HTTP thật, server `python run.py` cổng 8014,
dev và production, DB + upload ở thư mục tạm. Không đụng cổng 8000, `data/app.db`, không gửi email thật.
Chạy lại: `.venv\Scripts\python qa\run_all.py --full` (kết quả ở `qa/results/*.json`). Mã trong ngoặc là mã kiểm tra trong script.

**Kết quả: 537 kiểm tra, 445 đạt, 92 không đạt. 89 dòng không đạt quy về 3 lỗi Cao, 10 Trung bình, 23 Thấp; 3 dòng còn lại không tính là lỗi (C8.p2, C9.3 ở mục Nghi ngờ; C18.1 chỉ là hai POST HTTP giống nhau, bấm đúp thật trên trình duyệt ra 1 tin). Không có lỗi Nghiêm trọng.**
Không tìm thấy XSS, SQL injection, path traversal, open redirect, bỏ qua CSRF hay leo quyền từ giao diện web.

### Nghiêm trọng

Không có.

### Cao

**C-1. Chạy production theo README: email và SEO hỏng mà không có cảnh báo** (F5.1, F5.2, F5.3)
- Bước: `APP_ENV=production`, `SECRET_KEY=...`, không đặt `BASE_URL`, `SMTP_BACKEND` (đúng mục "Chạy" của README). Đăng ký email ở trang chủ, xem `/` và log.
- Mong đợi: server từ chối chạy hoặc cảnh báo rõ khi thiếu cấu hình bắt buộc của production.
- Thực tế: link xác nhận là `http://127.0.0.1:8000/xac-nhan/...`, canonical/sitemap/og trỏ `127.0.0.1:8000`. Email không được gửi (chỉ vào log, kèm token) nhưng khách vẫn thấy "Kiểm tra hộp thư". Không có dòng cảnh báo nào.
- Vị trí: `app/config.py:19,21` (giá trị mặc định), `Config.require_secret` chỉ kiểm SECRET_KEY; README mục Chạy. Cần xử lý trước Phase 5. `FROM_EMAIL` trống cũng rơi về `no-reply@localhost`.

**C-2. Người lạ dùng form đăng ký để site gửi nội dung tùy ý tới bất kỳ email nào** (P12.1, P12.2)
- Bước: `POST /api/subscribe` với `email=nannhan@...`, `name=TRÚNG THƯỞNG 500 USD, nhận tại http://evil.example/x`, lặp 5 lần.
- Mong đợi: email xác nhận gửi tới địa chỉ chưa xác minh không chứa chữ do người gửi đặt; giới hạn số email theo địa chỉ.
- Thực tế: 5 email trong vài giây tới cùng địa chỉ, mở đầu "Chào TRÚNG THƯỞNG 500 USD, nhận tại http://evil.example/x,". Giới hạn chỉ theo IP (5 lần/10 phút), đổi IP là không giới hạn. Người đã hủy đăng ký vẫn bị gửi lại khi ai đó nhập địa chỉ của họ. Hậu quả: phishing từ domain thật, hỏng uy tín gửi mail.
- Vị trí: `app/routes/public.py:_send_confirm` (dòng "Chào {sub.name}"), `subscribe` (`elif sub.status != "confirmed"` luôn gửi lại).

**C-3. SMTP hỏng vẫn báo thành công, chiến dịch mất luôn** (P14.1, P14.2, P14.3)
- Bước: giả lập gửi thất bại (`qa/mailfail_run.py`: `send_many` trả 0). Admin gửi chiến dịch tới người đã xác nhận; khách đăng ký email.
- Mong đợi: admin thấy lỗi, chiến dịch còn gửi lại được; khách không bị bảo đi kiểm tra hộp thư.
- Thực tế: flash "Đã gửi email", campaign `status=sent, sent_count=0`, không mở lại được (chỉ bản nháp mở được, phải soạn lại). Gửi thiếu giữa chừng cũng báo như vậy. Khách vẫn nhận `sub_ok`.
- Vị trí: `app/routes/admin_people.py:subs_mail` (không xét `sent`), `app/routes/public.py:subscribe` (bỏ qua kết quả `send_email`).

### Trung bình

**T-1. Banner chết vẫn chạy trên trang chủ** (C3.3, C3.4, P4.1)
- Bước: banner gắn sàn, để trống Link đích. (a) Xóa sàn, hoặc (b) xóa link affiliate ở Sàn › Link affiliate. Mở `/`, bấm banner.
- Mong đợi: banner không có đích thì không hiện, admin thấy trạng thái khác "Đang chạy".
- Thực tế: banner vẫn hiện, bấm ra 404, vẫn cộng view, admin vẫn báo "Đang chạy".
- Vị trí: `app/queries.py:live_banner`, `banner_state` không xét đích; `go_ad` thì có xét.

**T-2. Tắt section quảng cáo nhưng vẫn cộng lượt hiển thị** (C13.2)
- Bước: Trang chủ › Section tắt "Quảng cáo #1". Tải `/` 3 lần.
- Mong đợi: `views` không đổi vì banner không hiển thị. Thực tế: `views` từ 1 lên 4, CTR báo cho đối tác sai.
- Vị trí: `app/routes/public.py:home`, hàm `banner()` cộng view trước khi xét `sections`.

**T-3. Gửi form đăng ký hai lần làm link trong email đầu chết** (B7.15, C17.2)
- Bước: gửi cùng email hai lần, mở link trong email thứ nhất.
- Mong đợi: xác nhận được. Thực tế: 404 "Liên kết không hợp lệ", vì mỗi lần gửi lại đổi token.
- Vị trí: `app/routes/public.py:subscribe` (`sub.token = new_token()` khi đang pending).

**T-4. Trùng SEO** (C12.1, C12.2, C12.4, P1.3, P1.4, P1.5)
- Bước: Trang › Sàn và Tin tức điền Meta title/description. Xem `<title>` của `/san/<slug>`, description của `/tin-tuc/<slug>`. Thêm: so sánh `/san` với `/san/so-sanh`, ba trang Giới thiệu.
- Mong đợi: mỗi sàn, bài viết, trang có title và description riêng.
- Thực tế: mọi trang sàn có title "SEO chung mục Sàn"; mọi bài có cùng description. Ở giá trị mặc định: `/san/so-sanh` trùng `/san`, ba trang Giới thiệu trùng title và description.
- Vị trí: `app/routes/public.py:page_ctx` (`page.get("meta_title")` thắng cả tham số `title`), `broker_detail`, `post_detail`, `broker_compare`, `_about`.

**T-5. Slug `so-sanh` tạo được nhưng trang sàn không bao giờ mở được** (C5.3)
- Bước: thêm sàn tên "So sánh". Mở `/san/so-sanh`.
- Mong đợi: báo slug không dùng được. Thực tế: lưu thành công, URL ra trang so sánh, trang sàn không truy cập được.
- Vị trí: `app/routes/admin_data.py:_broker_save` thiếu danh sách slug cấm, `public.py` route tĩnh đứng trước `/san/{slug}`.

**T-6. Request rác gây 500, không cần đăng nhập** (C11.g, C11.b, C11.a, D2.2, D2.3, D2.4, D4.3, P9)
- Bước và thực tế (đều mong đợi 4xx):
  - `/go/broker/99999999999999999999999`, `/go/ad/...`, `POST /api/ad-view/...`, cùng các route admin có id: `OverflowError`.
  - `POST /admin/login` với `csrf_token=é` và cookie CSRF bất kỳ: `TypeError` từ `hmac.compare_digest`. Đã đăng nhập: tương tự, cả khi `csrf_token` gửi dạng file.
  - `/static/a%3Fb`, `/media/` + 5000 ký tự, `/static/` + 400 ký tự: `OSError WinError 123`.
- Vị trí: path `int` không giới hạn; `app/security.py:csrf_ok`; `StaticFiles` trên Windows (`app/main.py`).

**T-7. Trang 500 không có header bảo mật** (D13.500)
- Bước: production, mở `/go/broker/99999999999999999999999`.
- Mong đợi: có CSP, nosniff, X-Frame-Options, HSTS như mọi trang. Thực tế: thiếu cả bốn, vì handler `Exception` chạy ngoài middleware.
- Vị trí: `app/main.py` (`security_headers` so với `server_error`).

**T-8. `APP_ENV` gõ khác `production` thì âm thầm chạy chế độ dev; README ghi sai mặc định** (D14.1, F0.3)
- Bước: `APP_ENV=prod`. Mở `/docs`.
- Mong đợi: từ chối giá trị lạ. Thực tế: `/docs` 200, cookie không Secure, không HSTS, SECRET_KEY trống được thay bằng ngẫu nhiên.
- README ghi mặc định `development` và "SECRET_KEY ngẫu nhiên (dev)". Thực tế mặc định là `production`, chạy không đặt gì thì lỗi `RuntimeError` kèm traceback.
- Vị trí: `app/config.py:13-14`, README bảng biến môi trường.

**T-9. Đặt lại mật khẩu bằng CLI âm thầm nâng editor thành admin** (P2.1)
- Bước: tạo editor, chạy `create-admin --email <editor>` (đúng hướng dẫn "chạy lại lệnh = đặt lại mật khẩu").
- Mong đợi: vai trò giữ nguyên. Thực tế: `role=admin`, vì `--role` mặc định `admin` luôn ghi đè.
- Vị trí: `app/cli.py:create_admin`, `main` (`default="admin"`).

**T-10. Nội dung bị cắt thầm, báo "Đã lưu"** (P3.1, P3.2, P3.3, C6.2, C6.3)
- Bước: khối Giới thiệu 1.500 ký tự, lý do/điểm nổi bật trang chủ, tiêu đề bonus 400 ký tự, bài viết 112.000 ký tự. Form không có `maxlength`.
- Mong đợi: báo lỗi hoặc lưu đủ. Thực tế: cắt còn 1.000 / 255 / 100.000 và báo thành công. Giới hạn cũng lệch model: tên sàn cắt ở 255 trong khi cột `String(120)`, `founded` lưu 100 ký tự trong khi cột `String(20)` (SQLite không chặn).
- Vị trí: `app/routes/admin_base.py:Admin.text/many/long_text`, `app/routes/admin_data.py:_broker_save`.

### Thấp

Mỗi dòng: bước → thực tế (mong đợi hiển nhiên ghi khi cần) · vị trí.

1. **Thêm sàn/bài đồng thời cùng slug → 500** (C10.1): 6 POST song song trả `[400, 303, 400, 400, 400, 500]`, dữ liệu vẫn đúng 1 bản ghi. `_broker_save`, `_posts_save` không bắt `IntegrityError`.
2. **Slug tự sinh lỗi với tiêu đề dài** (C5.5): tiêu đề mà ký tự thứ 120 rơi vào dấu gạch → "Slug chỉ gồm chữ thường...", người nhập không hiểu vì để trống ô slug. `app/utils.py:slugify` cắt sau `strip`.
3. **`/tin-tuc?page=abc`, `?page=`, `?page=1.5`, `/go/broker/abc` trả JSON 422 cho khách** (C11.p, C11.g). Mong đợi: trang 1 hoặc 404. Tham số kiểu `int` của FastAPI, không có handler `RequestValidationError`.
4. **HEAD trả 405 ở mọi trang** (C11.h): `/`, `/bonus`, `/health`, `/sitemap.xml`. Uptime monitor mặc định dùng HEAD sẽ báo sập. Route chỉ khai báo GET.
5. **Sàn đã ẩn vẫn chiếm suất so sánh** (C4.3): 3 sàn bật so sánh, ẩn 1, bật sàn khác → "tối đa 3" trong khi site chỉ hiện 2. `_compare_full`.
6. **`value_num` nhận vô cực** (C7.x): `inf`, `1e999` lưu được và đứng đầu sort "Giá trị cao". `app/utils.py:parse_float`.
7. **Markdown mất định dạng** (C9.2, C9.5, C9.4): `# Tiêu đề` và `##### x` thành chữ thường (h1, h5, h6 không có trong `ALLOWED_TAGS`); khối ``` thành một dòng code vì không bật `fenced_code`. `app/utils.py`.
8. **Lastmod sitemap đổi mỗi lượt xem/click** (C14.1, C14.2): `update(...views+1)` kích hoạt `onupdate` của `updated_at`. `app/models.py`, `public.py`.
9. **Sàn mới thừa hưởng click 30 ngày của sàn đã xóa** (C15.1): SQLite dùng lại id cao nhất, `click_logs` không bị xóa theo. `broker_delete`, `ads_delete`.
10. **Chủ đề liên hệ không kiểm tra** (C18.2): POST lưu nguyên chuỗi tùy ý ngoài danh sách (đã escape khi hiển thị). `contact_submit`.
11. **Lỗi form liên hệ: canonical là `/api/contact`, không noindex** (C18.3). `contact_submit` render tại URL API.
12. **EXIF không bị bỏ** (D5.e): ảnh upload phục vụ nguyên byte, gồm GPS/thiết bị. `app/uploads.py:save_image`.
13. **Phiên hết hạn khi bấm công tắc/Xóa: đăng nhập lại ra trang "Method Not Allowed"** (D8.3): `next` trỏ route chỉ có POST. `_admin_session`.
14. **Mật khẩu đặt ở Cài đặt bị xử lý khác lúc đăng nhập** (D8.7, D8.8): khoảng trắng đầu/cuối bị bỏ, quá 200 ký tự bị cắt, sau đó đăng nhập đúng chuỗi vừa đặt thì 401. `a.text` trong `user_create`, `user_edit`.
15. **URL có `/` cuối chuyển về `http://`** (F4.8): `/bonus/` qua https → 307 `http://localhost:8016/bonus`. Không bật proxy headers.
16. **Esc không đóng menu mobile** (E4.m3): Esc đóng được drawer, hộp xác nhận nhưng menu thì không. `static/js/site.js`.
17. **Tương phản dưới AA** (E7.1): nhãn "Tài trợ" 10px `#8E9AA3` tỉ lệ 2,64; `status-ok` 4,38; `field-hint` 4,43.
18. **Chuỗi liền dài bị cắt mất, không cuộn được** (E1.stress, E2.stress, E1.normal, P10.4): `body { overflow-x: hidden }` che phần tràn. Từ liền ≥ 40 ký tự ở ô thẻ bonus trang chủ (360px, lệch 42px); tên sàn 118 ký tự ở pill so sánh; các ô `dd`, `.broker-row`, `.proscons`, `.broker-aside`, thẻ Tổng quan admin, `/admin/ads`. Dữ liệu thực tế (có dấu cách) đạt ở cả 5 khổ.
19. **Avatar trống với tên không Latin** (P7.1): "日本証券" có slug nhập tay → `mono` rỗng. `mono_from_name`.
20. **Ô ảnh nhận mọi chuỗi bắt đầu `/static/img/`** (P6.2): `/static/img/../../admin/logout...` lưu được. HTML vẫn escape nên không chèn được (P6.1). `Admin._image`.
21. **`SECRET_KEY=x` được chấp nhận ở production** (D14.3). `require_secret`.
22. **`/docs` ở dev trắng trang** (P13.1): CSP chặn CDN của Swagger. Chỉ ảnh hưởng dev.
23. **README sao lưu chỉ một dòng** (F3.1): không có cách phục hồi, không nói nên dừng server. Xem nghi ngờ số 1.

### Đã kiểm và đạt

**Cài đặt sạch (F0)**: `git archive` + venv mới + `pip install -r requirements.txt` + `run.py` + `create-admin` (có/không `ADMIN_PASSWORD`, không treo) + đăng nhập Chromium qua `127.0.0.1` và `localhost`, kể cả cookie Secure; chạy từ thư mục khác; `requirements-dev.txt`; pytest 217 test xanh trên bản sạch.

**Vai A**: nhập trọn sàn (logo, ưu/nhược, tài khoản, nạp rút, so sánh, nổi bật), bonus, bài (ảnh bìa, Markdown), 4 vị trí banner qua UI. Lưu nguyên trạng cả 19 tab Trang chủ/Trang/Cài đặt: HTML public không đổi một byte. 186 ô và mọi ảnh trong các tab đó: sửa xong đều hiện ở public (riêng `ads_note` chỉ in ở rail không ảnh). Sửa, ẩn, chuyển nháp, xóa: biến khỏi danh sách, trang chủ, sitemap, `/go`. Chặn xóa ảnh đang dùng. Chọn ảnh từ thư viện. Bấm đúp Lưu và bấm đúp xác nhận gửi email: 1 bản ghi.

**Vai B**: lọc, sort, giữ tham số khi đổi tab; lọc tại chỗ trang chủ; so sánh 0–3 sàn, khóa pill khi đủ 3; 4 tab sàn; phân trang và chuyên mục; đăng ký (chuẩn hóa email, sở thích, xác nhận, xác nhận lại, hủy, token sai, đăng ký lại sau hủy, link cũ không kích hoạt lại, honeypot, giới hạn tần suất); liên hệ (lỗi tại ô, giữ chữ, giới hạn, bấm đúp 1 tin); click affiliate và quảng cáo đếm đúng từng lượt, beacon rail chỉ ở ≥ 1572px, ClickLog khớp.

**Vai C**: ranh giới ngày theo giờ VN bằng đồng hồ giả (23:59 và 00:30 khi UTC còn ngày cũ) cho bonus, banner, `/go/ad`; sàn inactive ẩn khắp nơi; bonus xóa theo sàn; giới hạn 3 so sánh, 1 nổi bật; slug trùng; tiếng Việt, emoji; ngày biên 0001 và 9999; phân trang vượt quá kẹp về trang cuối; 0 kết quả có câu trống, không in số 0; email lạ (14 dạng) không gây 500, không làm hỏng chiến dịch; link affiliate 1000 ký tự, có dấu.

**Vai D**: XSS với payload ở mọi ô Trang chủ/Trang/Cài đặt, sàn, bonus, bài, banner, alt, tên file, form public, query: 65 trang public + admin (24 + 41) không có HTML lọt ra khi đã bỏ CSP (`bypass_csp`). Markdown không còn thẻ, thuộc tính, URL nguy hiểm. Không có JSON-LD trong v2. CSRF thiếu/sai/của phiên khác: 403. 56 route admin chưa đăng nhập đều bị chặn. Editor 403 ở mọi route Cài đặt, không có mục Cài đặt ở sidebar. Phiên hết hạn, đăng xuất dùng lại cookie, khóa và xóa tài khoản đang mở phiên, Back sau đăng xuất. Open redirect 15 payload qua `next`, `back`, subscribe. `/go/ad` không nhận URL từ query. URL `javascript:`, `data:`, `//` bị từ chối. Traversal 19 dạng, không liệt kê thư mục, tên thiết bị Windows không treo. Upload từ chối SVG, HTML, GIF, BMP, TIFF, ICO, polyglot; polyglot PNG+HTML phục vụ `image/png` + nosniff, tên ngẫu nhiên. SQLi qua query, slug, ids. CSP thật: không lỗi console ở 43 trang, 5 khổ. Cookie HttpOnly/Secure/Lax, Max-Age 7 ngày, DB chỉ lưu hash. `/docs`, `/redoc`, `/openapi.json` 404 ở production. Server không nghe IP LAN. `X-Forwarded-For` không lách giới hạn. `CF-Connecting-IP` chỉ tin từ loopback; đổi header từ loopback tạo ngăn mới, qua proxy (ghi đè như Cloudflare) thì không lách được. Host giả không vào canonical. Có analytics: chỉ public nới CSP, admin vẫn chặt.

**Vai E**: 21 trang public + 22 trang admin ở 360/390/768/1440/1920 với dữ liệu thực tế đạt, trừ pill tên sàn quá dài. Focus nhìn thấy ở mọi phần tử; skip link; phím mũi tên ở tab Loại bonus; Enter mở menu mobile; drawer nhận focus, Esc đóng, có đổi thì hỏi trước; hộp xác nhận. Mọi ảnh có alt, 1 `<h1>`, `lang=vi`. So thiết kế 5 trang (trang chủ, bonus, sàn, so sánh, liên hệ) ở 1440 và 390: khớp bố cục, màu, chữ; khác có chủ ý là hết ảnh mẫu. Menu ghi "Sàn" (theo Trang chu v2), trang con của thiết kế ghi "Sàn uy tín".

**Vai F**: alembic upgrade trên DB trống, `alembic check` không lệch, 13 bảng, downgrade rồi upgrade lại. WAL thật, có file `-wal`. Restart giữ dữ liệu, ảnh, phiên. Tắt nóng giữ dữ liệu đã commit, `integrity_check` ok. Sao lưu lạnh rồi phục hồi được. Qua proxy https: đăng nhập, cookie Secure, POST, không lỗi mixed content/CSP, canonical/sitemap/email dùng `BASE_URL` https (cả khi có `/` cuối). Sitemap XML hợp lệ, robots đúng. 300 request 60 luồng: không 5xx, không `database is locked`, click và lượt xem đúng tuyệt đối.

### Nghi ngờ, chưa tái hiện được hoặc cần quyết định

1. **Sao lưu nóng**: README bảo copy `data/app.db*`. Copy khi site đang ghi không an toàn về lý thuyết, nhưng 40 lần thử dưới tải đều `integrity_check` ok (F3.2). Nên dùng `sqlite3 .backup` hoặc dừng server.
2. **Máy quét link trong email**: mail xác nhận chứa cả link xác nhận và link hủy, cả hai chạy bằng GET. Bộ quét mở mọi link có thể hủy ngay người vừa xác nhận. Thiếu `List-Unsubscribe-Post`, Gmail/Yahoo yêu cầu với người gửi số lượng lớn. Chưa thử với dịch vụ thật.
3. **Đăng nhập theo IP+email**: đúng brief, nhưng đổi email mỗi lần thì không bị chặn, mỗi lần tốn một Argon2. Chưa đo tải CPU.
4. **Bài đặt ngày tương lai hiện ngay** (C8.p2) và đứng đầu danh sách. Brief không yêu cầu hẹn giờ nên chưa tính là lỗi. Cần user quyết định.
5. **Click và view không lọc bot**: `curl` vào `/go/*` hay tải lại trang chủ đều cộng. Brief không yêu cầu.
6. **Rail có ảnh không in `ads_note`**: VIEW_CONTEXT ghi dưới nút, rail ảnh không có nút. Cần xem có bắt buộc cảnh báo rủi ro không.
7. **Editor gửi được chiến dịch và xem danh sách email**; editor không có chỗ tự đổi mật khẩu. Brief không nói rõ.
8. **Xuống dòng đơn trong Markdown bị gộp** (C9.3): đúng chuẩn Markdown, nhưng người nhập có thể bất ngờ.
9. **POST thân rất lớn** tới form public: 3MB không lỗi; cỡ 50MB+ chưa thử, `Form` không có trần riêng.

### Chưa kiểm được

- Gửi SMTP thật, độ trễ khi SMTP chậm: cấm gửi thật, chỉ giả lập thất bại.
- Cloudflare Tunnel thật: dùng proxy TLS tự viết (`qa/https_proxy.py`) mô phỏng; cổng 8000 bị cấm.
- Firefox, Safari, thiết bị thật, trình đọc màn hình: chỉ có Chromium.
- Google Analytics thật: chỉ thử đoạn inline, không tải script ngoài.
- Hết hạn phiên 7 ngày thực tế và ngày hết hạn thực tế: mô phỏng bằng sửa DB và đồng hồ giả.
- Admin so với `Admin.dc.html`: chỉ xem ảnh chụp của bản thật, không ghép đôi. Quét mock data thuộc qa-mock.
- Chạy dài ngày, DB lớn, ảnh rất lớn gần ngưỡng bomb của Pillow.

## Audit mock

Người kiểm: qa-mock, 05/11/2026, trên commit 9c29ee1 (cây làm việc chưa đổi code sản phẩm). Chạy lại: `.venv/Scripts/python.exe qa/mock/run_audit.py` (khoảng 10 phút, tự bật và tắt server ở cổng 8013, DB tạm), rồi `qa/mock/hardcoded.py`, `qa/mock/shots.py`. Kết quả ở `qa/mock/out/` (gitignore vì chứa chuỗi mock trích từ `design/`).

### Kết luận

**Dữ liệu mock dạng chữ (sàn, bonus, bài viết, số đếm, link `xxxx`, người đăng ký, email demo): KHÔNG còn trên web.** Quét 305 chuỗi và số trích tự động từ `design/`, không có hit nào ở public ngoài `100%` nêu dưới.

**Nhưng trang chủ DB rỗng vẫn còn 2 thứ đến từ thiết kế mà không phải giao diện thuần:** ảnh nền hero có logo Microsoft (M1) và số `100%` không có nguồn (M2). Cả hai nằm trong phần brief cho GIỮ hoặc coi là mặc định, nên không phải dev bỏ sót, nhưng user cần quyết định. Ngoài ra có 45 chuỗi là tuyên bố về sự thật cần duyệt, vài câu trong đó hiện không đúng với hệ thống.

### Phát hiện

| # | Mức | Ở đâu | Bằng chứng | Tái hiện |
|---|---|---|---|---|
| M1 | Cao | `/` (1440, 390), `static/img/hero-bg.webp`, `app/content.py:33` | Ảnh nền hero có bảng hiệu **Microsoft** đọc rõ, góc phải dưới ảnh gốc có dấu sao 4 cánh trông như watermark ảnh AI (chưa xác minh nguồn gốc). Trùng byte với khóa `v2-hero-bg` của thiết kế (sha1 1f0fd634e7). Dùng nhãn hiệu bên thứ ba, không liên quan, trên site tài chính: có thể bị hiểu là liên kết với Microsoft. Quét text không thể thấy, chỉ phát hiện bằng mắt | Mở `/`, xem `qa/mock/out/shots/home_1440.png`, `home_390.png`. Admin đổi được ở Trang chủ › Hero, nhưng DB mới vẫn dùng ảnh này làm mặc định |
| M2 | Cao | `/` section Tại sao chọn, `app/content.py:119-120` | `100%` + "Ưu đãi có tóm tắt điều kiện rút tiền" hiện khi có **0 ưu đãi**. Số cứng, không tính từ DB. Khi có dữ liệu cũng có thể sai: `withdrawable` không bắt buộc, bonus trống hiện "—" | DB rỗng, mở `/`. Trùng token `100%` trong markup `Trang chu v2.dc.html`. Sửa/ẩn được ở Trang chủ › Tại sao chọn |
| M3 | Trung bình | `/`, `app/content.py:31,122` | Câu khẳng định sai với hệ thống: "Mỗi ưu đãi ghi rõ khối lượng yêu cầu" và "Khối lượng yêu cầu ... hiển thị ngay trên mỗi ưu đãi". Model `Bonus` và form admin không có trường khối lượng | Xem `app/models.py` lớp Bonus, `templates/admin/bonus.html` |
| M4 | Trung bình | Header mọi trang con, `/lien-he` | Nút "Nhận tư vấn" (`system_text.header_cta_page`) mâu thuẫn "Chúng tôi không tư vấn đầu tư cá nhân" (`contact_page.response_note`) | Mở `/lien-he`, đọc nút góc phải và ghi chú |
| M5 | Trung bình | `/san`, `/san/*`, `app/routes/public.py:200,235,250` | Breadcrumb "Sàn uy tín" viết cứng, không sửa được từ admin (vi phạm mục 12), lệch khi đổi tiêu đề trang, và là một tuyên bố "uy tín". Pha sentinel: còn trên 19 trang sau khi đổi mọi Setting | Sửa Trang › Sàn, breadcrumb không đổi |
| M6 | Trung bình | `/admin/subscribers?tab=mail` | Không xóa được bản nháp chiến dịch: không có route xóa campaign. Sau khi xóa hết, "QAFIC nháp" vẫn còn, bảng `campaigns` còn 1 dòng. Chỉ thấy ở admin | Lưu nháp ở Gửi email, tìm nút xóa: không có |
| M7 | Thấp | `/admin`, `/admin/ads?tab=stats` | `click_logs` không bị xóa theo sàn/banner: xóa hết dữ liệu, biểu đồ vẫn "4 click" thay vì "Chưa có click nào trong 30 ngày qua". Là số thật của sàn đã xóa, không phải mock | Click `/go/broker/1`, xóa sàn, mở `/admin` |
| M8 | Thấp | `templates/admin/bonus.html:53,55` | Placeholder lấy từ mock: `50%, $30, $4/lot…`, `Ví dụ: Thưởng nạp tiền lần đầu`. Chỉ ở admin, placeholder thuộc nhóm GIỮ; `$4/lot` khớp BONUSES | Mở `/admin/bonus/new` |
| M9 | Thấp | `/admin`, `/admin/subscribers?tab=mail` | In số 0: `0/0`, `Banner đang chạy 0`, 3 ô 0 khác, `Gửi tới 0 người`. Brief "Con số đếm bằng 0 thì ẩn" viết cho public; cần chốt có áp dụng cho bảng thống kê admin không. **Public không in số 0 nào** | DB rỗng, mở `/admin` |
| M10 | Thấp | Chân trang mọi trang, `app/content.py:76` | `Copyright © 2026` là năm cứng; context đã có `site.year` nhưng không template nào dùng | Sang 2027 vẫn in 2026 nếu không sửa tay |
| M11 | Thấp | `/dieu-khoan`, `/bao-mat` | Mặc định chỉ có "Nội dung đang được cập nhật." (viết cứng ở `legal.html:4`). Site có form thu email và link affiliate nên cần nội dung thật trước khi lên public | DB rỗng, mở hai trang |

### Đã kiểm và đạt

- **Không có seed:** khởi động DB mới, cả 12 bảng 0 dòng, kể cả `settings`. `alembic/` không chèn dữ liệu.
- **DB rỗng, public + admin, 1440 và 390:** 0 biến Jinja chưa render, 0 `None`/`undefined`/`NaN`, 0 link `#` hay `javascript:`, 0 ảnh hỏng, 0 request lỗi, 0 nhãn trống, 0 ảnh thiếu alt, 0 tràn ngang, 0 lỗi JS.
- **Chữ placeholder:** "demo" chỉ ở mô tả cuộc thi (chữ thật), "minh họa", "ảnh nền" chỉ là nhãn trường admin. Không có "lorem", "mẫu", "test" lộ ra.
- **Ngày cứng:** chỉ `2026` trong copyright (M10). Số cứng public: chỉ `100%` (M2) và `1–2 ngày` (xem bảng tuyên bố).
- **Domain ngoài:** chỉ `fonts.googleapis.com`, `fonts.gstatic.com`, brief cho phép.
- **Runtime thiết kế:** 0 request tới unpkg, `support.js`, `image-slot.js`, babel, `.dc.html`. Trong 28 URL thăm dò, mọi đường dẫn tới `design/`, file zip, `.env`, `mail to/` đều 404 (kể cả `/static/../design/*`, `/media/%2e%2e/*`). `/docs`, `/openapi.json` trả 200 ở development; đã chạy `APP_ENV=production` xác nhận 404.
- **Mã nguồn (60 file trong `templates/`, `static/`, `app/`, `alembic/`):** chỉ còn `100%` (M2), placeholder (M8), và 3 comment CSS nhắc đường dẫn `design/`. Hit `BY` là chữ "by" trong comment alembic, không phải mock.
- **Trạng thái:** lỗi và thành công của form đăng ký/liên hệ, xác nhận, hủy, link sai, 404, 500 thật (status 500, dùng lỗi DB) đều không có mock.
- **Dữ liệu chỉ đến từ DB (pha B):** nhập "Sàn A", "Sàn B", 5 bonus, 3 bài, 4 banner, người đăng ký, tin nhắn, email/telegram/mạng xã hội, ảnh qua form admin và public. Chữ đánh dấu xuất hiện ở 128 URL. Sau khi xóa hết qua admin: **public trùng từng dòng với pha A (0 khác biệt, 0 dấu vết)**, file upload còn 0. Khác biệt chỉ ở admin: M6, M7 và tài khoản QA.
- **Kiểm chứng máy quét:** thêm "Sàn A" vào danh sách token thì máy quét bắt được, nên 0 hit là 0 thật. Lần đầu máy quét báo "Sàn B" ở admin là nhầm do sidebar "Sàn" liền "Bài viết", đã sửa thành khớp nguyên từ. Cảnh báo 4 ảnh hỏng ở pha B là ảnh lazy trong rail/hộp chọn đang ẩn, request thật trả 200/304.
- **Mục 12 (pha C):** đổi 175 chuỗi Setting thành sentinel. 161 chuỗi nội dung đều hiện ở public, và đều có ô sửa ở admin. 14 chuỗi còn lại không phải chữ public (`sections[].label` chỉ dùng trong admin, `pages.system` là tên tab).

### Chữ viết cứng ở public, không sửa được từ admin

Đo bằng pha C (`out/sentinel_report.json`, 121 mục) và đọc tĩnh (`out/hardcoded_static.json`).

- **Khung giao diện, hợp lệ:** nhãn cột và thẻ (Nạp tối thiểu, Giấy phép, Đòn bẩy tối đa, Hết hạn...), nút (Nhận bonus, Về sàn, Mở tài khoản, Xem tất cả bonus, Đăng ký nhận thông báo, Gửi tin nhắn), tab (Tổng quan, Tất cả sàn, Giá trị cao...), `aria-label`, placeholder form.
- **Nên xem lại, không hẳn là khung:** "Sàn uy tín" (M5); badge "Phổ biến" gắn cho sàn nổi bật (`home.html:215`) là nhận định; "Đánh giá {tên}", "Thành lập {năm}" (`public.py:248-249`); "Nội dung đang được cập nhật." (M11); nhãn "Hợp tác với sàn"; hai nhãn khác nhau cho cùng trường: "Rút lợi nhuận" (trang chủ), "Rút được" (`/bonus`).
- **Empty state (brief cho phép):** "Chưa có ưu đãi trong mục này.", "Chưa có sàn nào.", "Chưa có bài viết nào.", ...
- **Ngoài site nhưng người dùng đọc được:** tiêu đề và thân email xác nhận, dòng hủy nhận (`public.py:388-389`, `mailer.py:22`) không sửa được từ admin.

### Tuyên bố trong `app/content.py` cần user xác nhận

154 chuỗi: 86 chữ giao diện, 23 kiến thức và cảnh báo (`bonus_types`, cảnh báo rủi ro, công bố affiliate), 45 tuyên bố. Không phải lỗi, trừ dòng ghi rõ. Tất cả sửa được ở admin. Danh sách đủ theo khóa: `qa/mock/out/content_strings.json`.

| Nội dung | Khóa | Nhận xét khi đối chiếu code |
|---|---|---|
| Chỉ liệt kê sàn có giấy phép / từ các sàn có giấy phép / "ít nhất một giấy phép ... công bố công khai" | `meta_desc`, `hero.sub`, `pages.gioithieu.desc`, `home_about.points`, `home_why.reasons[1]`, `about_blocks.method[0]` | Trường `license` không bắt buộc, sàn không giấy phép vẫn lưu được. Là cam kết biên tập |
| Mỗi ưu đãi ghi rõ khối lượng yêu cầu; quy đổi sang số lot | `hero.sub`, `home_why.reasons[0]`, `about_blocks.method[2]`, `home_about.text` | **Hiện sai** (M3): không có trường này |
| 100% ưu đãi có tóm tắt điều kiện rút tiền | `home_why.stat_*` | **Không có nguồn** (M2) |
| Tối đa một email mỗi tuần | `home_contact.text` | Code không giới hạn, admin gửi bao nhiêu cũng được |
| Bạn sẽ nhận thông báo khi có bonus mới | `system_text.sub_confirmed_text` | Không gửi tự động, chiến dịch soạn tay |
| Phản hồi trong 1–2 ngày làm việc; không tư vấn đầu tư cá nhân | `contact_page.response_note` | Cam kết vận hành; mâu thuẫn nút "Nhận tư vấn" (M4) |
| Cập nhật ưu đãi hằng ngày | `home_about.badge` | Cam kết vận hành, site không tự cập nhật |
| Thay đổi điều khoản được ghi lại trong mục Tin sàn | `about_blocks.about[2]` | Cam kết biên tập |
| Ưu đãi hết hạn được gỡ khỏi danh sách | `home_why.reasons[2]`, `about_blocks.about[2]` | Đúng: code tự ẩn bonus hết hạn |
| Ưu đãi từ các sàn **đối tác** | `home_bonus.title` | Cần có quan hệ đối tác thật |
| Sàn giao dịch **uy tín** | `pages.san.title` | Nhận định, cộng breadcrumb cứng (M5) |
| Hoa hồng không làm thay đổi điều kiện bạn nhận được | `footer.about_text`, `about_blocks.affiliate[1]` | Cần đúng với từng sàn |
| Nội dung tài trợ luôn có nhãn "Tài trợ" hoặc "Quảng cáo" | `about_blocks.affiliate[2]` | Đúng: banner luôn in "Tài trợ" |
| Đọc điều khoản từng chương trình, tóm tắt; không chỉ là con số quảng cáo | `home_about.text`, `home_why.*`, `about_blocks.about[0]` | Cam kết biên tập |

### Quyết định cần user

1. Thay ảnh hero (M1) bằng ảnh không có nhãn hiệu, dùng làm mặc định. Khuyến nghị làm trước khi lên public.
2. `100%` (M2): bỏ, hoặc thay bằng con số tính từ DB.
3. Chọn: thêm trường "khối lượng yêu cầu" vào Bonus, hay sửa câu chữ (M3).
4. Đổi nút "Nhận tư vấn" (M4) và duyệt bảng tuyên bố trên.
5. Viết Điều khoản, Bảo mật (M11).

### Quy mô

Lượt mở trang: 1.043 (DB rỗng 282, có dữ liệu 325, sau xóa 266, sentinel 170). DB rỗng: 56 URL public và 78 URL admin khác nhau, mỗi URL ở cả 1440 và 390, gồm mọi `?tab=`, form `/new`, trạng thái form, 404, 500. Không có trang nào lỗi khi crawl.

### Chưa kiểm được

- Nội dung chữ bên trong ảnh chỉ soát bằng mắt ở `static/img/` (2 file) và 2 ảnh chụp trang chủ, không OCR. 16 ảnh chụp còn lại đã tạo nhưng chưa xem.
- Rail chỉ crawl ở 1440 và 390 nên ở trạng thái ẩn (rail hiện từ 1572px): đã quét trong DOM, chưa nhìn bằng mắt.
- Sentinel chạy ở 1440, không chạy 390.
- Hộp chọn ảnh, chép link và các trạng thái chỉ sinh ra bằng JS trong admin không được bấm hết; chỉ quét DOM ban đầu.
- Lịch sử git không quét. `design/` đã gitignore, nhưng chưa xác minh các commit cũ có từng chứa mock hay không.
- Tính đúng sự thật của 45 tuyên bố: chỉ đối chiếu với code, không đối chiếu thực tế vận hành.
