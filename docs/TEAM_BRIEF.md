# TradingBonusHub v2 — Team Brief (đọc toàn bộ trước khi làm)

## 1. Mục tiêu
Dựng lại TradingBonusHub từ đầu: site public so sánh bonus sàn forex/crypto + trang quản trị.
Backend cũ đã bị xóa hoàn toàn, KHÔNG tham chiếu nó. Giao diện lấy 100% từ `design/`.
Dữ liệu mock trong thiết kế bị loại bỏ: site chạy với database rỗng, mọi dữ liệu do admin nhập.

## 2. Luật an toàn (vi phạm là lỗi nghiêm trọng)
- KHÔNG chạy server ở cổng 8000: cloudflared đang bật, cổng 8000 lên thẳng tradingbonushub.com.
  Dùng cổng: backend 8010, public FE 8011, admin FE 8012, QA 8013 / 8014.
- KHÔNG đụng SQL Server hay database cũ. KHÔNG đụng cloudflared, `cloudflared.yml`.
- KHÔNG đọc/in/commit giá trị trong `.env`. KHÔNG sửa `.env`.
- KHÔNG đụng `mail to/`, thư mục `.git`, thư mục `F:\Tradingbonushub_old_2026-11-04`.
- KHÔNG gửi email thật. Test dùng `SMTP_BACKEND=console` (chỉ log), không gọi mạng ngoài.
- KHÔNG git commit/push: team leader làm việc đó. Repo là PUBLIC, không đưa secret vào code.
- Chỉ sửa file thuộc phần mình sở hữu (mục 9). Cần sửa phần người khác: ghi vào docs/ISSUES.md.
- Dùng database test riêng qua `DATABASE_URL`, không làm bẩn `data/app.db`.
- Tất cả UI bằng tiếng Việt. Không có i18n.

## 3. Stack (đã chốt, không đổi)
Python 3.12, FastAPI, Jinja2, SQLAlchemy 2 (sync), Alembic, SQLite (WAL) tại `data/app.db`
(user đã xác nhận: chỉ dùng SQLite, không dùng SQL Server), argon2-cffi, nh3 + markdown (bài viết),
Pillow (kiểm tra ảnh), pytest + httpx, Playwright cho QA.
Không React, không bước build, không Tailwind. CSS thuần + JS vanilla tối thiểu.
Server render toàn bộ (cần cho SEO). Không dùng runtime `support.js`, `image-slot.js`, Babel, unpkg.
Chạy: `python run.py` (host 127.0.0.1, PORT từ env, mặc định 8000).
Biến môi trường: SECRET_KEY, APP_ENV, DATABASE_URL, PORT, BASE_URL, SMTP_BACKEND (smtp|console),
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL.

## 4. Nguồn thiết kế (`design/`, không được serve)
- `Trang chu v2.dc.html`  → trang chủ. (`Trang chu.dc.html` là bản cũ: BỎ QUA.)
- `Cac trang.dc.html`     → bonus, sàn, so sánh, chi tiết sàn, tin tức, bài viết, giới thiệu, liên hệ.
- `Admin.dc.html`         → quản trị.
- `assets/logo.png`, `.image-slots.state.json` (khóa `v2-hero-bg` = ảnh nền hero, data URI webp).
Định dạng: `<sc-for>`, `<sc-if>`, `{{ }}` và style inline; logic ở class Component cuối file.
Chuyển sang Jinja + class CSS, giữ nguyên pixel: màu, cỡ chữ, khoảng cách, bo góc, hover
(`style-hover`), bố cục, responsive. Token: nền #F5F5F5, navy #021623, xanh #1944DF, chữ phụ #4B5B66,
#A9B6C1, #C2CBD1; font Be Vietnam Pro 400–700; max-width 1300px.
`<image-slot>` → `<img>` thật lấy từ dữ liệu; thiếu ảnh thì khối nền trung tính, không có chữ placeholder.

## 5. Mock hay giao diện? (quy tắc quan trọng nhất)
GIỮ (là giao diện/nội dung tĩnh của site): nav, tiêu đề, mô tả trang, nhãn cột, nút, tab, placeholder
input, lý do "Tại sao chọn", mô tả 5 loại bonus (TYPES), các khối giới thiệu/phương pháp/affiliate
(ABOUT), câu cảnh báo rủi ro, ảnh nền hero, logo.
XÓA (phải đến từ DB, DB rỗng thì không hiện gì):
BONUSES, BROKERS, POSTS, PAY, banners, subs, linkStats, mọi tên sàn (Exness, Vantage, VT Markets,
Bybit, OKX) trong nội dung, số liệu (views, clicks, đếm, CTR, số tổng ở hero), link `xxxx`,
người đăng ký mẫu, nhãn "Bài viết minh hoạ", quảng cáo rail, số đếm cứng, email demo
`admin@tradingbonushub.com`. Email/telegram liên hệ đến từ Settings; rỗng thì ẩn dòng đó.
Khối mock hardcode trong HTML hoặc JS đều phải xóa, không chỉ ẩn.
Không tạo seed/fixture dữ liệu mẫu trong code chạy thật. Fixture chỉ nằm trong `tests/`.

Trạng thái rỗng: mỗi danh sách có empty state câu trung tính ("Chưa có bonus nào.", ...).
Trang chủ: section cần dữ liệu mà rỗng thì ẩn hẳn section (bonus, so sánh, tin tức, quảng cáo).
Con số đếm bằng 0 thì ẩn. Không in "0 bonus".

## 6. Mô hình dữ liệu (`app/models.py`)
Mọi bảng: id, created_at, updated_at.
- AdminUser: email unique, password_hash, role(admin|editor), is_active, last_login_at
- AdminSession: token_hash, user_id, expires_at, csrf_token
- Broker: slug unique, name, mono(2 ký tự), kind(forex|crypto), tagline, summary, license, min_deposit,
  leverage, platforms, spread, withdrawal, founded (đều text), affiliate_url, logo_path,
  pros(JSON list[str]), cons(JSON list[str]), accounts(JSON list{name,min_deposit,spread,commission}),
  payment_methods(JSON list{method,deposit,withdraw,time}), in_compare(bool, tối đa 3),
  featured(bool, tối đa 1), is_active, clicks(int)
- Bonus: broker_id FK, type(nodep|deposit|cashback|contest|crypto), amount(text), value_num(float, để sort),
  title, min_deposit, withdrawable(text), expiry_date(date|null; null = "Liên tục"), is_active
- Post: slug unique, title, category(Hướng dẫn|Kiến thức|So sánh|Tin sàn), excerpt, body_md, cover_path,
  read_minutes(tự tính), status(draft|published), published_at, show_home(bool), views(int)
- Banner: broker_id FK null, name, image_path, placement(after-bonus|before-blog|rail-left|rail-right),
  target_url, start_date, end_date, is_active, views, clicks
- Subscriber: name, email unique, interests(JSON list type), status(pending|confirmed|unsubscribed),
  token unique, confirmed_at
- ContactMessage: topic, name, email, body, is_read
- Campaign: subject, body, audience(JSON list type), status(draft|sent), sent_count, sent_at
- Setting: key unique, value(JSON). Khóa: site_name, contact_email, partner_email, telegram, meta_title,
  meta_desc, hero{eyebrow,headline,sub,cta,image_path}, sections[{id,label,on}], menu[{label,url}], footer_note.
  Giá trị mặc định của hero/sections/menu/footer_note/meta là chữ trong thiết kế (không phải mock);
  site_name mặc định TradingBonusHub; contact_email, partner_email, telegram mặc định rỗng.

Quy tắc nghiệp vụ: bonus hết hạn tự rời trang public. Tối đa 3 sàn in_compare, 1 sàn featured (chặn ở
server). Banner chỉ hiện khi active và trong khoảng ngày. Sàn inactive ẩn cả bonus của nó.

## 7. URL
Public: `/`, `/bonus?type=&sort=new|value|expiry`, `/san?kind=forex|crypto`, `/san/so-sanh?ids=1,2,3`,
`/san/{slug}?tab=overview|bonus|accounts|pay`, `/tin-tuc?cat=`, `/tin-tuc/{slug}`, `/gioi-thieu`,
`/gioi-thieu/cach-danh-gia`, `/gioi-thieu/affiliate`, `/lien-he`, `/dieu-khoan`, `/bao-mat`,
`/go/broker/{id}` (đếm click, 302; không có link thì 404), `/go/ad/{id}`, `POST /api/subscribe`,
`/xac-nhan/{token}`, `/huy-dang-ky/{token}`, `POST /api/contact`, `/sitemap.xml`, `/robots.txt`, `/health`,
`/media/*` (ảnh upload ở `data/uploads`), `/static/*`. 404/500 có trang riêng theo thiết kế.
Admin (`/admin`, form POST server-side, redirect về danh sách): `/admin/login`, `/admin/logout` (POST),
`/admin`, `/admin/bonus`, `/admin/brokers`, `/admin/ads`, `/admin/home`, `/admin/posts`, `/admin/subscribers`,
`/admin/messages`, `/admin/settings`; mỗi nhóm có `/new`, `/{id}/edit`, `/{id}/delete` (POST),
`/{id}/toggle` (POST) khi có công tắc. Tab con dùng `?tab=` theo SUBS trong `Admin.dc.html`.
Thêm tab "Tin nhắn" và màn đăng nhập, cùng phong cách, dù thiết kế chưa có.

## 8. Bảo mật tối thiểu
Argon2id; cookie HttpOnly + SameSite=Lax + Secure khi production; session trong DB (hash token), hạn 7 ngày;
CSRF cho mọi POST admin; giới hạn 5 lần đăng nhập sai/15 phút theo IP+email; honeypot + rate limit cho
subscribe/contact; double opt-in; link hủy trong mọi email; nội dung Markdown qua nh3; upload chỉ
PNG/JPEG/WEBP, xác minh bằng Pillow, tên file ngẫu nhiên, tối đa 5MB; security headers (CSP cho phép Google Fonts);
`affiliate_url`/`target_url` chỉ http(s); `/go/ad` không phải open redirect; không có admin mặc định: tạo qua
`python -m app.cli create-admin --email X` (nhập mật khẩu bằng prompt). `/admin` có `noindex`.
Không có /docs của FastAPI ở production.

## 9. Sở hữu file
- Backend: `app/`, `alembic/`, `alembic.ini`, `tests/`, `requirements.txt`, `run.py`, `.env.example`, `README.md`,
  `docs/VIEW_CONTEXT.md` (hợp đồng dữ liệu cho FE).
- Public FE: `templates/public/`, `templates/base_public.html`, `static/css/tokens.css`, `static/css/site.css`,
  `static/js/site.js`, `static/img/`.
- Admin FE: `templates/admin/`, `static/css/admin.css`, `static/js/admin.js`. Dùng lại tokens.css.
- QA: `qa/` và `docs/QA_REPORT.md`.
- Mọi người: thêm mục vào `docs/ISSUES.md`.

## 10. Định nghĩa hoàn thành
`pytest` xanh; chạy được với DB rỗng không lỗi; site trông giống thiết kế; admin thêm dữ liệu → hiện ở public;
quét toàn bộ HTML + JS + CSS không còn dữ liệu mock. Báo cáo cuối của agent: làm gì, kiểm tra gì và kết quả
thực tế, cái gì chưa xong. Không báo "xong" nếu chưa tự chạy thử.

## 12. Admin quản lý được TOÀN BỘ nội dung public (yêu cầu của user, ưu tiên trên mục 5)
Thiết kế Admin.dc.html chưa phủ hết. Mọi chữ, ảnh, link nhìn thấy trên site public phải sửa được từ admin,
trừ khung giao diện (nhãn cột, nút, tab). Mục 5 "GIỮ" nghĩa là: dùng chữ thiết kế làm GIÁ TRỊ MẶC ĐỊNH
lưu trong Setting, không hardcode trong template. Bổ sung khóa Setting:
- pages: {bonus|san|tin|gioithieu|lienhe: {title, desc, meta_title, meta_desc}}
- home_about {eyebrow, title, text, images[3]}, home_why {title, reasons[{title,text}], images[2]},
  home_types {title, image}, home_contact {title, text, image}, home_blog {title}, home_compare {title}
- bonus_types: [{id, label, desc, points[]}] (5 loại cố định id, sửa chữ được)
- about_blocks: {about|method|affiliate: [{title,text}], image theo từng tab}
- contact_page {intro, topics[], response_note}
- footer {about_text, columns[{title, links[{label,url}]}], risk_note, copyright}
- legal: {terms_md, privacy_md}; social links; favicon/logo; og_image; analytics_head (script GA, chỉ admin role)
Thêm bảng MediaFile (path, alt, width, height, size) + màn "Thư viện ảnh": upload một lần, chọn ảnh ở mọi form.

Màn admin mới (Admin FE thiết kế theo đúng phong cách Admin.dc.html: sidebar navy, pill xanh, bảng trắng,
drawer phải 480px cho form, công tắc tròn):
- "Nội dung trang chủ" mở rộng tab: Section | Hero | Về chúng tôi | Tại sao chọn | Loại bonus | Liên hệ | Menu & chân trang
- "Trang" (mới): tab Bonus | Sàn | Tin tức | Giới thiệu | Liên hệ | Điều khoản | Bảo mật — sửa tiêu đề, mô tả, SEO, khối nội dung
- "Thư viện ảnh" (mới): lưới ảnh, upload, alt, copy link, xóa (chặn xóa khi đang dùng)
- "Tin nhắn" (mới), "Cài đặt" thêm tab Mạng xã hội, Tracking
Bố cục: mỗi form có cột trái là trường nhập, cột phải là xem trước nhỏ khi màn đủ rộng; nút "Xem trên site ↗"
mở đúng trang public; lưu bằng một nút cố định đáy form; báo "Đã lưu" ngắn. Nhóm sidebar thành
Dữ liệu (Bonus, Sàn, Bài viết, Quảng cáo) | Nội dung (Trang chủ, Trang, Thư viện ảnh) | Khách (Người đăng ký, Tin nhắn) | Hệ thống (Cài đặt).

## 11. Cách làm việc (vibe coding có kỷ luật)
- Trước khi code: đọc đúng phần cần, nêu kế hoạch ngắn trong đầu; không đoán, xem file thật.
- Chia nhỏ theo lát dọc: làm một việc, chạy thử, rồi mới sang việc tiếp theo. Không viết nhiều rồi mới test.
- Ưu tiên đơn giản: không thêm tính năng, lớp trừu tượng hay thư viện ngoài brief.
- Gặp lỗi: tìm nguyên nhân gốc, không che lỗi, không xóa test cho qua, không retry mù.
- Hết phần việc: dùng Skill `simplify` để dọn code đã đổi, rồi Skill `code-review` mức `medium` cho phần đã làm
  và sửa các lỗi được xác nhận. Backend chạy thêm Skill `security-review`. FE dùng Skill `run` để mở và nhìn trang thật.
- Thiếu thông tin hoặc brief mâu thuẫn: chọn phương án an toàn nhất, ghi vào docs/ISSUES.md, làm tiếp.
