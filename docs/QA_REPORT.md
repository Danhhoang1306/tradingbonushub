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

## Audit mock vòng 2

Người kiểm: qa-mock, 05/11/2026, trên commit 2e4229e. Chạy lại: `qa/mock/run_audit.py` (10 phút), `qa/mock/shots.py`, `qa/mock/claims_check.py`, `qa/mock/secret_scan.py`. Script đã cập nhật theo hành vi mới: xác nhận và hủy đăng ký qua POST, xóa bản nháp chiến dịch, đo sentinel cả các trạng thái form. Hai script vòng này mới thêm: `claims_check.py`, `secret_scan.py`.

### Kết luận

**KHÔNG còn dữ liệu mock trên web.** DB rỗng: 0 hit trong 305 token mock ở public và admin, kể cả `100%`. Ảnh Microsoft đã gỡ, xem ảnh chụp 1440 và 390 xác nhận hero nền navy, không còn ảnh bên thứ ba. Dữ liệu hư cấu xóa xong thì public và admin trùng từng dòng với DB rỗng.

**Lịch sử git: không tìm thấy secret thật** trong phạm vi quét (xem mục Secret). 11 phát hiện vòng 1 đều đã sửa. Còn 2 phát hiện mức trung bình mới (N1, N2), không phải mock.

### M1–M11

| # | Trạng thái | Bằng chứng thực tế |
|---|---|---|
| M1 ảnh Microsoft | ĐÃ SỬA | `static/img/hero-bg.webp` không còn ở HEAD, `hero.image_path` mặc định rỗng, hero `hero--plain`. Đã nhìn `home_1440.png`, `home_390.png`. File cũ vẫn tải được từ lịch sử repo public (N7) |
| M2 `100%` | ĐÃ SỬA | `stat_value` rỗng, khối số ẩn. Quét DB rỗng: 0 số cứng dạng `%`, `$`, `+` |
| M3 câu "khối lượng yêu cầu" | ĐÃ SỬA | Câu đã đổi thành mức nạp, phần rút được, thời hạn. Câu mới vẫn chưa được đảm bảo (N2) |
| M4 "Nhận tư vấn" | ĐÃ SỬA | Nút trang con là "Xem bonus", trỏ `/bonus` |
| M5 breadcrumb "Sàn uy tín" | ĐÃ SỬA | Không còn "uy tín" trong template và route; breadcrumb lấy `pages.san.label`, pha sentinel không còn thấy chữ cứng. Tiêu đề trang vẫn có chữ "uy tín" (mục duyệt) |
| M6 không xóa được nháp | ĐÃ SỬA | Xóa qua nút trên `/admin/subscribers?tab=mail`, `campaigns` còn 0 dòng |
| M7 click sót | ĐÃ SỬA | Xóa sàn và banner, `click_logs` còn 0 dòng, biểu đồ về "Chưa có click nào" |
| M8 placeholder mock | ĐÃ SỬA | `/admin/bonus/new`: 0 hit `$4/lot`, `$30`, `50%` |
| M9 số 0 ở admin | ĐÃ SỬA | DB rỗng: số 0 đứng riêng chỉ còn trong câu hướng dẫn "bằng 0 thì ẩn" ở `/admin/home?tab=about` |
| M10 năm cứng | ĐÃ SỬA | `footer.copyright` dùng `{year}`, render 2026 từ `today_vn()`. Không giả lập năm 2027 |
| M11 Điều khoản, Bảo mật | ĐÃ SỬA, cần duyệt | Có bản nháp, hiện đúng định dạng (`privacy_1440.png`, `terms_1440.png`). Đối chiếu ở dưới |

### Phát hiện còn lại

| # | Mức | Ở đâu | Bằng chứng | Tái hiện |
|---|---|---|---|---|
| N1 | Trung bình | `/` màn ≥1572px, rail phải có ảnh; `static/css/site.css:374-375` | Câu cảnh báo rủi ro dưới banner ảnh gần như không đọc được: chữ xanh nhạt 10px trên nền sáng. `.rail--right .rail__note` mạnh hơn `.rail__note--plain` nên ghi đè màu. Rail trái (nền navy) đọc được | Banner ảnh ở `rail-right`, mở `/` ở 1700px, xem `qa/mock/out/shots/rail_1700_scroll.png` |
| N2 | Trung bình | `/`, `/bonus`, `app/content.py:107,178,207`; `app/routes/admin_data.py:104-125` | "Mỗi ưu đãi ghi rõ mức nạp tối thiểu, phần rút được và thời hạn" không được đảm bảo: bonus chỉ có tiêu đề vẫn đăng, thẻ hiện `Nạp tối thiểu — Rút được —` | Đã thử thật trong `claims_check.py`. Cách xử lý: bắt buộc hai trường, hoặc user tự đảm bảo khi nhập |
| N3 | Thấp | `app/routes/admin_data.py:255` | Giấy phép chỉ kiểm khác rỗng: thiếu thì 400 (đúng), nhưng `-` vẫn lưu được. "Chỉ sàn có giấy phép" vẫn phụ thuộc người nhập | `claims_check.py` |
| N4 | Thấp | `/admin/pages?tab=terms`, `?tab=privacy` | Ô "Nhãn breadcrumb" của hai tab này lưu được nhưng public không dùng; breadcrumb hiện tiêu đề trang | Pha sentinel: `pages.terms.label`, `pages.privacy.label` không xuất hiện ở public |
| N5 | Thấp | `templates/public/home.html`, `_macros.html` | Chữ cứng mang tính nhận định, không sửa được từ admin: badge "Phổ biến". Mặc định "Nổi bật tuần này" thực chất là sàn nổi bật, không đổi theo tuần | Mở `/` với sàn featured |
| N6 | Thấp | `app/content.py:69` | Bảo mật hứa nhận yêu cầu "sửa" dữ liệu, admin không có màn sửa người đăng ký, chỉ xóa. Người dùng vẫn đăng ký lại được | Xem `/admin/subscribers` |
| N7 | Thấp | Lịch sử repo public | `qa/results/s4_security.json`, `s6_ops.json` chứa giá trị cookie phiên của server test tạm (vô giá trị, DB đã bỏ), và ảnh Microsoft ở commit e9cf9dd đến trước 789490d. Nên thêm `qa/results/` vào gitignore | Xem mục Secret |

Không phải lỗi: trang chủ khi chưa có ảnh có 7 khối xám trống (đúng brief, nhưng trông như chưa xong). Cần tải ảnh trước khi lên public.

### Đã kiểm và đạt

- **DB rỗng, 1440 và 390:** 12 bảng 0 dòng khi khởi động. 0 biến Jinja chưa render, 0 link chết, 0 ảnh hỏng, 0 request lỗi, 0 nhãn trống, 0 tràn ngang, 0 lỗi JS. Domain ngoài chỉ Google Fonts.
- **Runtime thiết kế:** 0 request tới unpkg, `support.js`, `image-slot.js`. 28 URL thăm dò: chỉ `/sitemap.xml`, `/robots.txt`, `/health` trả 200; `/docs`, `/openapi.json` nay 404 cả ở development.
- **Vòng đời dữ liệu:** "Sàn A" hiện ở 128 URL. Xóa hết: mọi bảng dữ liệu về 0, file upload 0, 0 dấu vết. Khác biệt duy nhất là tài khoản editor do QA tạo ở pha A.
- **Máy quét:** thêm "Sàn A" thì bắt được, nên 0 hit là 0 thật. 4 cảnh báo ảnh hỏng ở pha có dữ liệu vẫn là ảnh lazy đang ẩn như vòng 1.
- **Trạng thái:** trang hỏi xác nhận, hỏi hủy, đã xác nhận, đã hủy, 404, 500 thật (status 500), editor 403: không có mock.
- **Rail ≥1572px:** hiện đủ hai bên ở 1700px, có nhãn "Tài trợ", gọi beacon `/api/ad-view/3` và `/4`. Bản native rail trái đúng, bản ảnh rail phải lỗi chữ cảnh báo (N1).
- **Mục 12:** 200 sentinel, 184 hiện ở public. 14 không phải chữ public, 2 là N4. Mọi chuỗi public đều có ô sửa ở admin.

### Đối chiếu Điều khoản, Bảo mật với hành vi thật

| Câu | Kết quả | Bằng chứng |
|---|---|---|
| Chỉ nhận email sau khi xác nhận | Đúng, trừ chính email xác nhận | Chiến dịch chỉ tới người đã xác nhận, người pending không nhận |
| Mỗi email có liên kết hủy | Đúng | Cả email xác nhận và chiến dịch đều có. Email "Gửi thử" chỉ tới admin |
| Nội dung tài trợ có nhãn "Tài trợ" | Đúng | Thấy ở banner và rail |
| Dữ liệu đăng ký, liên hệ thu thập | Đúng, còn thiếu chi tiết kỹ thuật | Thêm token, thời điểm và số lần gửi email xác nhận, không đáng kể |
| Thống kê click không gắn danh tính, IP | Đúng | `click_logs` chỉ có loại, id, ngày, số đếm; bảng không có cột IP |
| IP chỉ trong bộ nhớ, không vào DB | Đúng | Gửi đăng ký với IP giả: không có trong DB, không có trong log. Access log ghi 127.0.0.1 |
| Cookie kỹ thuật ngắn hạn, không cookie quảng cáo | Đúng | Xem trang: 0 cookie. Cookie flash 60 giây (đọc code). Cookie admin chỉ ở khu quản trị |
| Bên thứ ba: Google Fonts, email, hạ tầng mạng, link ngoài, công cụ đo lường | Đúng | Request ngoài chỉ có Google Fonts |
| Yêu cầu xem, sửa, xóa qua Liên hệ | Một phần | Xóa có, sửa không có màn admin (N6) |
| Dữ liệu giữ đến khi yêu cầu xóa | Đúng | Người hủy đăng ký vẫn còn dòng, trạng thái `unsubscribed` |
| Không bán dữ liệu, tự chịu rủi ro, thay đổi điều khoản | Không kiểm bằng code | User tự xác nhận |

Không có câu nào nói sai hành vi thật, trừ chữ "sửa" (N6). Tuyên bố trang chủ sai duy nhất về mặt bảo đảm là N2.

### Danh sách user phải tự xác nhận

175 chuỗi: 109 giao diện, 23 kiến thức và cảnh báo, 43 tuyên bố. Những câu chỉ user biết đúng hay sai:

1. **Chỉ sàn có giấy phép**, "ít nhất một giấy phép từ cơ quan quản lý được công bố công khai": phải đúng với từng sàn nhập vào.
2. **Từ các sàn đối tác**: có quan hệ đối tác thật với các sàn không.
3. **Sàn giao dịch uy tín** (tiêu đề `/san`): có muốn khẳng định vậy không.
4. **Hoa hồng không làm thay đổi điều kiện bonus bạn nhận được**: đúng với từng sàn không. Link affiliate có thể có điều kiện riêng.
5. **Chúng tôi đọc điều khoản của từng chương trình và tóm tắt**: có làm vậy cho mọi ưu đãi không.
6. **Thay đổi điều khoản được ghi lại trong mục Tin sàn**: có duy trì được không. Không có cơ chế tự động.
7. **Chúng tôi sẽ trả lời qua email**: có người trả lời không. Khi chưa nhập email liên hệ, trang vẫn nhận tin.
8. **Không bán dữ liệu**, Điều khoản và Bảo mật nói chung: nên đọc lại toàn bộ, cân nhắc nhờ người có chuyên môn pháp lý. Vòng này chỉ đối chiếu với code, không đánh giá pháp lý.
9. **Mô tả 5 loại bonus** ("Thường rút được ngay", "Tính theo lot đã đóng"...): kiến thức chung, nên đọc lại cho khớp cách tính thật.

### Secret trong lịch sử git

Quét 51 commit trên mọi ref, 43 commit của tag `old-project-final`, 615 blob text, cộng commit message. Giá trị không ghi vào báo cáo. Chi tiết đã che ở `qa/mock/out/secret_scan.json`.

- **File nhạy cảm:** chưa từng commit `.env`, `cloudflared.yml`, `*.db`, `*.pem`, `*.key`. Chỉ có `.env.example`.
- **Định dạng đặc trưng:** 0 khớp (private key, AWS, GitHub, Google, Slack, SendGrid, Stripe, Telegram bot, sk-, JWT, Cloudflare tunnel).
- **34 dòng gán giá trị nghi vấn, đã phân loại hết:** mật khẩu giả trong `tests/` và `qa/` cho DB tạm (28); `FERNET_KEY` trong `.github/workflows/ci.yml` cũ, giải mã ra chuỗi ASCII có chữ "test", là khóa CI; `DEMO_PASSWORD` trong `scripts/seed_demo_commission.py` cũ, giá trị dạng demo; 2 dòng `setup-cloudflare.ps1` là code sinh hoặc nhập khóa lúc chạy; 2 dòng `token_uri` là URL công khai của Google.
- **Chuỗi dài ngẫu nhiên (54):** mã hash commit, tên hàm test, slug bài cũ, và 3 cookie phiên test (N7).
- **Việc nên làm:** nếu DB cũ từng có tài khoản dùng `DEMO_PASSWORD`, đổi mật khẩu đó vì script đã public.

Giới hạn: không so với giá trị trong `.env` thật (brief cấm đọc), nên không phát hiện được secret thật bị dán vào file mà không có tên khóa hay định dạng đặc trưng. 163 khớp yếu dạng code không xem từng dòng. Giá trị dưới 6 ký tự không quét. Không kiểm phía GitHub: fork, log Actions, secret của PR.

### Quy mô

1.068 lượt mở trang: DB rỗng 292, có dữ liệu 331, sau xóa 270, sentinel 175. DB rỗng có 56 URL public và 81 URL admin khác nhau, mỗi URL ở cả 1440 và 390. Không trang nào lỗi khi crawl.

### Chưa kiểm được

- Ảnh chụp đã xem: trang chủ 1440, 390, trang chủ đầy đủ, rail 1700, Bảo mật 1440. Các trang con còn lại đã chụp nhưng chưa xem.
- `claims_check.py`: POST liên hệ trực tiếp trả 400 nên phép thử IP chỉ qua form đăng ký; form liên hệ được đối chiếu bằng cấu trúc bảng (không có cột IP). Luồng liên hệ qua giao diện đã chạy đúng trong crawl.
- Log server ở production thật, log của Cloudflare và nhà cung cấp email: nằm ngoài code.
- Sentinel chỉ ở 1440. Không giả lập năm 2027.
- Rail chỉ xem ở 1700px, chưa thử sát ngưỡng 1572px.

### Ghi chú thời điểm

Trong lúc audit, commit 896b241 (start.bat, stop.bat) được thêm và site lên cổng 8000 lúc 13:12:57 (Phase 5). Đó không phải do qa-mock: audit chỉ chạy ở 8013 với DB tạm, không đụng `data/app.db` và server thật. Kết quả crawl ở trên đo trên 2e4229e với cấu hình mặc định, chưa đo site đang chạy thật (nơi section đăng ký đã tắt). Quét secret đã chạy lại sau commit này. N1, N2 và danh sách user xác nhận vẫn còn áp dụng cho site đang chạy.

Quét lại trên 52 commit (gồm 896b241): `start.bat`, `stop.bat` không có secret. 2 khớp định dạng là chính regex trong `qa/mock/secret_scan.py`. 10 dòng nghi vấn mới đều ở script `qa/`, chưa xem từng dòng; cookie phiên test trong `qa/results/s4_security.json` tăng lên 4 (N7).

## Kiểm thử chức năng – Vòng 2

Người kiểm: qa-func, 05/11/2026, trên commit 2e4229e. HEAD chuyển sang 896b241 trong lúc chạy, nhưng commit đó không đổi `app/`, `templates/`, `static/`, chỉ thêm `start.bat`, `stop.bat` và 7 dòng README.
Chạy lại: `.venv\Scripts\python qa\run_all.py --full`. Hai bộ mới: `qa/s9_round2.py` (hồi quy), `qa/s10_upgrade_prod.py` (nâng cấp từ DB tạo bằng code 9c29ee1, quy trình production theo README).

**Kết quả: 666 kiểm tra, 647 đạt, 19 không đạt. Toàn bộ 3 lỗi Cao và 10 lỗi Trung bình của vòng 1 đã sửa thật. 22/23 lỗi Thấp đã sửa, 1 lỗi sửa một phần. Phát hiện mới: 2 Trung bình, 9 Thấp. Không có lỗi Nghiêm trọng hay Cao.**
Dòng không đạt còn lại: 18 dòng quy về các lỗi dưới đây, 1 dòng (C9.3, xuống dòng đơn trong Markdown) không tính là lỗi.

### Lỗi CÒN từ vòng 1

**Thấp 18 (sửa một phần). Chuỗi liền rất dài tràn ở admin** (E2.stress.*)
- Bước: tên sàn/tiêu đề 170+ ký tự không có dấu cách, mở `/admin` và `/admin/ads`.
- Mong đợi: không tràn. Thực tế: lệch 664px và 720px ở 360px; còn lệch ở 1920px (192px, 220px). Thẻ tổng quan `.row-link-inline` và dòng banner.
- Public đã đạt cả 5 khổ. Dữ liệu thực tế ở admin đạt.

### Lỗi MỚI

#### Trung bình

**N-1. Giới hạn 3 email/24 giờ bị vượt khi gửi đồng thời** (R1.4)
- Bước: 20 POST `/api/subscribe` song song cùng địa chỉ, khác IP.
- Mong đợi: tối đa 3 email. Thực tế: 4 đến 6 email qua các lần chạy; `confirm_count` chỉ ghi 3. Với SMTP thật, thời gian gửi dài hơn nên khe hở rộng hơn.
- Vị trí: `app/routes/public.py:subscribe`, kiểm `_may_send_confirm` rồi gửi, sau đó mới `_note_confirm_sent`. Nội dung email đã cố định nên không còn là kênh phishing.

**N-2. Người đã hủy nhận tới 3 email, tài liệu ghi tối đa 1/24 giờ** (R1.5)
- Bước: địa chỉ đã hủy, lần gửi xác nhận cuối quá 24 giờ. Người khác nhập địa chỉ đó 6 lần.
- Mong đợi: tối đa 1 email (VIEW_CONTEXT). Thực tế: 3 email, trạng thái bị đổi từ `unsubscribed` thành `pending` dù chủ địa chỉ không làm gì.
- Vị trí: `subscribe`, nhánh `unsubscribed` đặt lại `confirm_sent_at`, `confirm_count` rồi rơi vào giới hạn của `pending`.

#### Thấp

| Mã | Lỗi | Bước → thực tế (mong đợi) | Vị trí |
|---|---|---|---|
| N-3 | Hủy rồi tự đăng ký lại trong 24 giờ không có email (R1.6) | Hủy, gửi lại form → báo "Kiểm tra hộp thư", không email, vẫn `unsubscribed` (cần báo thử lại sau) | `subscribe` |
| N-4 | Gửi trùng địa chỉ có dấu phẩy khi gửi tiếp (R5.8) | Chiến dịch partial có `a,b@x.co` → `sent_to` lưu `a, b@x.co`, gửi tiếp nhận lần 2 (mỗi người 1 email) | `admin_people.py:subs_mail`, dùng `m["To"]` thay vì email gốc |
| N-5 | Người lạ ghi đè tên, sở thích của địa chỉ đang chờ | Gửi form với cùng email, khác tên → tên `Chủ thật` thành `Kẻ lạ`, sở thích đổi (giữ dữ liệu đến khi xác nhận) | `subscribe` |
| N-6 | Slug bỏ mất chữ Ð (R8) | "Ðồng Eth" (U+00D0, hay gặp khi gõ/dán) → `ong-eth` (mong `dong-eth`) | `app/utils.py:slugify` |
| N-7 | `PORT=abc`, `SMTP_PORT=abc` in traceback (R9.10, R9.11) | Thoát mã 1 kèm traceback (mong mã 2, báo rõ như lỗi cấu hình khác) | `app/config.py:27,33` |
| N-8 | `SECRET_KEY` 40 dấu cách được chấp nhận (R9.12) | Server chạy (mong từ chối) | `Config.problems` |
| N-9 | Ô Nhãn của Trang › Điều khoản, Bảo mật không có tác dụng (A6.1) | Sửa nhãn → breadcrumb vẫn dùng tiêu đề (mong nhãn mới) | `public.py:_legal` |
| N-10 | README: bước phục hồi ảnh sai khi thư mục còn (P16) | `Copy-Item -Recurse backup-uploads data\uploads` lồng thành `data\uploads\backup-uploads`, ảnh vẫn 404 (cần lệnh có `\*` hoặc xóa trước) | README mục Phục hồi |
| N-11 | README: chạy khối Production trong cửa sổ vừa chạy dev (P17) | `APP_ENV=development` còn sót, server chạy dev: không HSTS, cookie không Secure, không cảnh báo (cần đặt `APP_ENV` trong khối Production) | README mục Chạy |

Ghi chú U12: DB từng lưu tab Hero với `/static/img/hero-bg.webp` sẽ gãy ảnh vì file đã bị xóa khỏi repo. Tôi tái hiện được trên DB tạo bằng code cũ; cần kiểm nếu có DB thật nào lưu tab Hero trước khi nâng cấp.

### Đã sửa (đã tự xác minh)

**Cao:** C-1 (thiếu BASE_URL, SMTP_BACKEND: thoát 2, liệt kê đủ; console có cảnh báo). C-2 (tên không vào email; 6 lần tuần tự chỉ 3 email; xem N-1, N-2). C-3 (0 email: flash `send_failed`, về nháp; `sub_failed` cho khách).

**Trung bình:** T-1 banner chết. T-2 view khi tắt section. T-3 token giữ nguyên khi đang chờ. T-4 SEO riêng từng trang. T-5 cấm `so-sanh` mọi dạng viết. T-6 id khổng lồ, CSRF không ASCII, đường dẫn Windows đều 4xx. T-7 trang 500 đủ header (gây 500 thật bằng thiếu bảng). T-8 `APP_ENV` lạ bị từ chối, README đúng. T-9 CLI giữ vai trò. T-10 quá dài báo 400, không cắt.

**Thấp (22):** 1 đua slug, 2 slug dài, 3 JSON 422, 4 HEAD, 5 suất so sánh, 6 `inf`, 7 Markdown h1/h5/fence, 8 lastmod, 9 ClickLog, 10 chủ đề liên hệ, 11 canonical lỗi liên hệ, 12 EXIF, 13 trang 405 sau đăng nhập lại, 14 mật khẩu, 15 redirect http, 16 Esc menu, 17 tương phản, 19 avatar trống, 20 đường dẫn ảnh, 21 SECRET_KEY ngắn, 22 `/docs`, 23 README phục hồi có rồi (xem N-10).

### Mục Nghi ngờ vòng 1

| # | Mục | Kết quả |
|---|---|---|
| 1 | Sao lưu nóng | Đã sửa: README dùng `sqlite3 backup`; 40 lần dưới tải toàn vẹn, lệnh README chạy được |
| 2 | Máy quét link | Đã sửa: GET, HEAD không đổi trạng thái; có `List-Unsubscribe-Post`, POST one-click hủy được |
| 3 | Đăng nhập đổi email | Còn, đúng brief: 12 lần sai từ 1 IP, đổi email, không bị chặn (R10.2). Chưa đo CPU |
| 4 | Bài ngày tương lai | Đã sửa, xem Hồi quy |
| 5 | Click không lọc bot | Còn, cần quyết định: `curl /go/*` vẫn đếm; HEAD không đếm |
| 6 | Rail ảnh thiếu `ads_note` | Đã sửa |
| 7 | Editor | Còn, cần quyết định: gửi được chiến dịch, không tự đổi được mật khẩu |
| 8 | Xuống dòng đơn Markdown | Không phải lỗi, đúng chuẩn |
| 9 | POST thân lớn | Đã sửa: BodyLimit đạt |

### Hồi quy phần mới: đạt

- **Khóa theo email:** tuần tự đúng 3 lần/24 giờ, cùng token, quá 24 giờ gửi tiếp được. Lỗi ở N-1, N-2, N-3.
- **Chiến dịch gửi dở:** lô đầu đi, lô sau hỏng thành `partial` (20/45); gửi tiếp đúng 25 người còn lại, không ai nhận 2 lần, thành `sent`. Gửi lại chiến dịch đã xong 404. 5 POST đồng thời cùng nháp: mỗi người 1 email.
- **Kẹt sending:** chưa quá 15 phút không gỡ nhầm; quá 15 phút và sau restart về `draft`/`partial` đúng.
- **BodyLimit:** Content-Length và chunked đều chặn đúng 1MB/8MB/64MB; 413 có header bảo mật; form nhỏ, chunked nhỏ qua được và phát lại đúng thân; upload 8 ảnh 40MB được.
- **Trang xác nhận POST:** GET, HEAD không đổi trạng thái; nút chạy thật trên Chromium và qua https; `form-action` không chặn; noindex; token sai 404; link xác nhận cũ sau khi hủy không kích hoạt lại. POST không có CSRF theo thiết kế, cần biết token 43 ký tự.
- **Hẹn giờ:** dùng đồng hồ giả, 23:59 VN không xuất hiện ở danh sách, trang chủ, sitemap, trang bài, số đếm chuyên mục; 00:01 VN (ngày UTC cũ) hiện đủ; admin có nhãn Hẹn giờ; xóa ngày rồi lưu thì đăng ngay.
- **Slug tiếng Việt:** Đ, Ư, Ơ, Ỷ, dấu tổ hợp, ký tự đặc biệt đúng; tiêu đề dài lưu được. Lỗi ở N-6.
- **Chặn production:** `APP_ENV` rỗng/lạ, SECRET_KEY 31 ký tự, BASE_URL rác, SMTP_BACKEND lạ, smtp thiếu host/from đều thoát 2, không traceback, chưa tạo DB. `APP_ENV=Production` chạy được.
- **Migration 0002:** DB tạo bằng code 9c29ee1 có dữ liệu thật qua form: số dòng mọi bảng không đổi, token, trạng thái giữ nguyên, phiên cũ còn, link trong email cũ dùng được, chiến dịch kẹt về nháp, UNIQUE và FK cascade còn, `alembic check` sạch, downgrade rồi upgrade đều được.

### Quy trình production trong README (cổng 8014)

Bản `git archive`, venv mới, `SMTP_BACKEND=console`, `BASE_URL=https://localhost:8016`, proxy TLS tự viết. Đạt: thiếu cấu hình báo đủ, cảnh báo console, create-admin, đăng nhập https, cookie Secure/HttpOnly/Lax, thêm sàn cần license, khách đăng ký và bấm xác nhận, email/canonical/sitemap dùng https, HSTS, `/docs` 404, không lỗi CSP, sao lưu nguyên văn lệnh README khi đang chạy, phục hồi database. Lỗi ở N-10, N-11.

### Chưa kiểm được

- `start.bat`, `stop.bat`, site thật ở cổng 8000: cấm chạy cổng 8000, cấm đọc `.env`. Lúc 13:12 có `python run.py` nghe 127.0.0.1:8000 kèm `data/app.db`, không do QA bật, QA không đụng vào.
- SMTP thật, Cloudflare Tunnel thật; lô SMTP bị từ chối từng địa chỉ chỉ giả lập.
- Firefox, Safari, thiết bị thật, trình đọc màn hình.
- CPU khi spam đăng nhập; chạy dài ngày, DB lớn.

## Kiểm thử chức năng – Vòng 3

Người kiểm: qa-func, 06/11/2026, trên commit 272be90. Giao diện khác trước theo brief mục 13 không tính là lỗi.
Chạy lại: `.venv\Scripts\python qa\run_all.py --full`. Bộ mới: `qa/s11_round3.py` (bulk save, đối chiếu chức năng với 2e4229e, bảo mật route mới, nâng cấp DB, production + SMTP qua bộ nhận local `qa/fake_smtp.py`). Danh sách đối chiếu: `qa/results/s11_parity.json`.

**Kết quả: 775 kiểm tra, 769 đạt, 6 không đạt. 2 lỗi Trung bình, 2 lỗi Thấp. Không có lỗi Nghiêm trọng hay Cao.** 6 dòng gồm 4 lỗi dưới đây (B1.1, E20, B10.1, C19.1) và 2 dòng không tính là lỗi: C9.3 (Markdown đúng chuẩn), E7.1 (màu lấy từ thiết kế).
Số liệu gộp kết quả mới nhất của từng bộ: một lượt `--full`, sau đó chạy lại s2, s9, s10, s11 vì script còn kỳ vọng cũ hoặc lỗi script. Không có lượt liền mạch nào sau lần sửa script cuối.

**Đính chính vòng 2:** kiểm tra D1.1 ("route admin chưa đăng nhập bị chặn") ở vòng 2 đạt mà không thử route nào, vì `admin_routes()` của QA trả danh sách rỗng với FastAPI hiện tại. Dòng "đã đạt" đó không có giá trị. Vòng 3 đã sửa script, có kiểm số lượng, và thử thật 59 đường dẫn, đều đạt.

### Trung bình

**V3-1. "Xuất bản thay đổi" ở Quảng cáo âm thầm đổi ngày kết thúc của banner chạy trên một năm** (B1.1)
- Bước: banner chạy từ 01/01/2025 đến 30/11/2026. Mở `/admin/ads`, ô ngày hiện `01/01/2025 – 30/11`. Không sửa gì, bấm "Xuất bản thay đổi".
- Mong đợi: mọi dòng giữ nguyên.
- Thực tế: báo "Đã lưu", `end_date` thành 2025-11-30. Theo `banner_state`, banner thành "Đã kết thúc", ngừng hiện và `/go/ad` trả 404. Admin không sửa gì ở dòng đó.
- Vị trí: `app/utils.py`. `date_range_label` bỏ năm của ngày đến khi đó là năm nay, còn `parse_date_range` hiểu ngày đến thiếu năm theo năm của ngày bắt đầu.
- Cũng xảy ra khi năm bắt đầu khác năm nay và ngày đến nằm trong năm nay, với ngày/tháng đến không nhỏ hơn ngày/tháng bắt đầu. 9 dạng khoảng ngày còn lại giữ nguyên.

**V3-2. Trang Bảo mật và Điều khoản không còn link nào trên site public** (E20)
- Bước: DB mới, xem `/` và `/bonus`, tìm `/bao-mat`, `/dieu-khoan`.
- Mong đợi: người để lại email vào được chính sách bảo mật.
- Thực tế: hai trang vẫn 200 nhưng chỉ vào được bằng URL. Mặc định `footer.columns` đã bỏ hai link trong commit này; thiết kế không có hai link đó.
- Vị trí: `app/content.py`, `DEFAULTS["footer"]`. Theo chữ của brief 13 đây có thể là chủ đích, nhưng brief không nhắc tới, nên cần user quyết định. Admin thêm lại được ở Trang chủ › Menu & chân trang.

### Thấp

**V3-3. Một banner mất link chặn lưu cả trang Quảng cáo, thông báo không chỉ banner nào** (B10.1)
- Bước: banner gắn sàn, để trống link. Xóa link affiliate của sàn đó. Sửa một banner khác trên `/admin/ads`, bấm Xuất bản.
- Mong đợi: lưu được, hoặc lỗi chỉ rõ thẻ nào.
- Thực tế: flash chung "Link phải bắt đầu bằng http:// hoặc https://", không thẻ nào được lưu, chữ vừa sửa mất vì redirect. Thẻ lỗi có nhãn "no_link" nhưng thông báo không dẫn tới đó.
- Vị trí: `app/routes/admin_data.py:ads_bulk`.

**V3-4. Banner không ảnh là link rỗng, không có tên cho trình đọc màn hình** (C19.1)
- Bước: banner không ảnh ở vị trí after-bonus. Xem `/`.
- Mong đợi: khối nền theo brief, nhưng link có `aria-label`.
- Thực tế: `<a href="/go/ad/1" class="ad__image" ...></a>`.
- Vị trí: `templates/public/_macros.html:66`.

### Chức năng bị mất so với 2e4229e

Crawl mọi form và link của 41 màn admin + 10 trang public ở cả hai bản rồi so.

- **Chưa có quyết định:** link footer tới `/dieu-khoan`, `/bao-mat` (V3-2).
- **Thay thế, không mất:** lưu link từng dòng thành `/admin/brokers/links` (route cũ còn, không còn nút). Logo, favicon, email hợp tác dời từ tab Chung sang tab Thương hiệu, lưu và hiện đúng. Công tắc ẩn sàn, khóa/xóa tài khoản dời vào drawer, đã thao tác thật.
- **Bỏ theo brief 13:** biểu đồ, top sàn, thẻ click affiliate, dòng tin chưa đọc ở Tổng quan (số chưa đọc còn ở sidebar). Bài liên quan, phân trang tin tức. Ô Nhãn của Trang › Liên hệ (dùng header mục Giới thiệu). Rail ảnh không in `ads_note`, đã ghi ở `docs/ISSUES.md`.
- Không có route POST nào mất nút ngoài mục trên.

### Đã kiểm và đạt

- **Bulk save:** lưu nguyên trạng đúng (trừ V3-1); sửa một dòng chỉ đổi dòng đó, không mất views, clicks, ảnh, sàn; Enter trong ô lưu đúng; công tắc không nộp nhầm form lớn. Một dòng sai (javascript:, ngày sai, quá dài) thì không lưu dòng nào; dòng không gửi lên giữ nguyên; id lạ bỏ qua; xóa trống link được. Dạng ngày `30/11`, `– 30/11`, `01/12 – 31/01` đúng.
- **Bảo mật:** 43 đường dẫn POST thiếu hoặc sai CSRF đều 403, chưa đăng nhập về login, gồm route mới. Editor 403 toàn bộ Cài đặt, gồm tab Thương hiệu. Editor sửa được link và banner, như quyền cũ. Redirect qua `back`, `tab`, `q`, `next`, Referer không ra ngoài host; `/admin/bonus/../..//evil.com` trong `back` vẫn cùng host; CRLF trong `q` không chèn header. XSS: payload trong URL, tên, giấy phép, nhãn mới, tham số drawer, `cat`, tìm trực tiếp không lọt ra trên 23 trang khi bỏ CSP; `s4` đạt 157/157.
- **Production + console:** đăng ký báo lỗi, không lưu, không ghi token vào log; chiến dịch về nháp, không mất chữ; gửi thử 502; liên hệ và hủy đăng ký vẫn chạy.
- **Production + SMTP (bộ nhận local, có STARTTLS và kiểm chứng chỉ):** đăng ký nhận đúng email, link https, có `List-Unsubscribe-Post`, không có tên; địa chỉ bị từ chối không chặn người khác, báo `send_partial`; SMTP tắt báo `sub_failed`.
- **Nâng cấp, restart:** DB từ 2e4229e lên 0003, từ 9c29ee1 lên 0003: đủ dòng, phiên, link email cũ, chiến dịch partial gửi tiếp không trùng; `alembic check` sạch; downgrade rồi upgrade được. Restart và tắt nóng giữ dữ liệu, ảnh.
- **README production:** cài sạch, lệnh sao lưu và phục hồi chạy nguyên văn, ảnh trở lại.
- **Lỗi vòng 2 đã sửa:** thấp 18 và N-1 đến N-11, đã chạy lại. 20 POST đồng thời còn đúng 3 email; đã hủy nhận 1 email, giữ `unsubscribed`, báo `sub_wait`; `Ð` thành `dong`; `PORT=abc` thoát mã 2.
- **Nghi ngờ vòng 1:** số 3 đã sửa (đổi email bị chặn sau 20 lần sai theo IP). Số 5 (`curl /go/*` vẫn đếm) và số 7 (editor gửi được chiến dịch, không tự đổi được mật khẩu) vẫn chờ quyết định.

Tương phản: nhãn "Tài trợ" 2,64 và `nav-count` 3,46 dưới AA, nhưng hai màu này có trong thiết kế nên không tính là lỗi theo brief 13.

### Chưa kiểm được

- Site thật ở cổng 8000, `start.bat`, tunnel, `data/app.db`, `.env`: cấm đụng.
- Nhà cung cấp SMTP thật, độ trễ khi gửi lô lớn: chỉ có bộ nhận local.
- Firefox, Safari, thiết bị thật, trình đọc màn hình. Điện thoại chỉ giả lập Chromium.
- So từng màn với thiết kế: `s8` chạy và tạo ảnh ghép, nhưng tôi không xem lại vòng này. Báo cáo so thiết kế ở `docs/design-diff/` là của người khác.
- Chạy dài ngày, DB lớn.


## Vòng 4: chạy lại sau Phase 7 (06/11)
**Kết quả: pytest 519 đạt (không tính tests/test_hub_sync.py, của việc khác). QA: 755/774 đạt. Audit mock: không còn dữ liệu mock; 18 khóa không sửa được từ admin đều là nhãn nội bộ, không có khóa mới.**

Script `s1`, `s7`, `s11` đã lỗi từ Phase 6 (ô nằm trong khối thu gọn, công tắc đổi tại chỗ), nên kết quả cũ của chúng là từ trước đó. Đã sửa script để chạy hết.

Dòng không đạt, không dòng nào là lỗi mới:
- Kỳ vọng cũ, trái quyết định sau đó, chưa sửa script: B6.*, B7.* (190fa19: lưu dòng hợp lệ, nêu tên dòng lỗi, có test ở `tests/test_phase6_design.py`); C11.1, C11.3 (13.1: in số 0); B4.0 (Phase 6.1: bỏ chọn hết hiện bảng nhãn); A1, D10.s (tab Section không còn form; route `/admin/home/sections`, `/admin/brokers/{id}/link`, `/admin/media/{id}/edit` còn nhưng UI không dùng).
- Đã biết từ trước: C9.3 (Markdown đúng chuẩn), E7.1 (màu lấy từ thiết kế).

So thiết kế: `s8` tạo ảnh ghép 10 màn. Chỉ xem 3 ảnh (home 1440, bonus 1440, sàn 390): bố cục khớp, khác biệt là dữ liệu mẫu và menu mobile đã chốt. 7 ảnh còn lại và màn admin chưa so bằng mắt vòng này. Rail, thẻ hero, thẻ so sánh, chân trang xem riêng bằng dữ liệu tạm ở 1920 và 390: không tràn, không lỗi JS.
