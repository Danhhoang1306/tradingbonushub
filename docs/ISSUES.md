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
- Phase 4: thêm cột `Subscriber.confirm_sent_at`, `confirm_count`, `Campaign.sent_to` (migration 0002); `Campaign.status` thêm `partial`; bỏ `/docs` ở mọi môi trường; người đã hủy đăng ký chỉ nhận lại tối đa 1 email xác nhận mỗi 24 giờ.
- Mô tả trang Liên hệ mặc định ("Gửi câu hỏi, báo lỗi thông tin bonus hoặc đề nghị hợp tác.") do backend đặt vì
  thiết kế không có header riêng cho trang này; admin sửa được ở Trang › Liên hệ.
- Gửi email chiến dịch chạy đồng bộ trong request (một kết nối SMTP cho cả lô). Đủ cho danh sách nhỏ; danh sách lớn
  (hàng nghìn) cần hàng đợi nền – chưa làm.

## [Backend → Admin FE] Việc cần làm trong template/JS sau khi backend xử lý các mục dưới (05/11)
Chi tiết trong `docs/VIEW_CONTEXT.md` (mục 0.5, 4.2 và từng màn).
1. `templates/admin/home.html`: editor dòng lấy từ `form.data` khi có (`points`, `reasons`, `menu`, `columns`); macro `v()` hiện
   tại đọc `fd[name]` vẫn đúng với trường đơn, nhưng không dùng nó cho trường lặp vì giá trị là `list[str]`.
2. `templates/admin/pages.html`, `settings.html`: đọc `form.data` khi 400 (`about_blocks`, `social` đã ghép sẵn).
3. `settings.html` tab users: hiện `edit_role`/`edit_password` ở dòng có `u.id == form.errors_user_id`; ô form thêm dùng
   `form.data.email`, `form.data.role`.
4. `messages.html` + macro `delete_form`: gửi hidden `back` khi xóa (macro `toggle` đã có), và ở nút đánh dấu trong drawer.
5. `subscribers.html`: nút `formaction="{{ mail_form.test_action }}"` "Gửi thử cho tôi"; hidden `draft_id`; link `c.edit_url` ở Lịch sử gửi.
6. `static/js/admin.js`: đếm người nhận bằng `audience_count_url` (JSON `{count}`, cần gắn URL vào `data-*` từ template), thay cho việc tải cả trang.
7. Không còn phụ thuộc `media_library` ở tab không có ô ảnh (nút chọn đã tự ẩn khi rỗng).

## [Backend → Public FE] Việc cần làm trong template/JS (05/11)
**[ĐÃ LÀM 05/11, Public FE: cả 6 mục. `templates/public/_bare.html` đã xóa.]**
Chi tiết trong `docs/VIEW_CONTEXT.md` (mục 2.1, 2.2, mục 3).
1. **Ưu tiên, công bố affiliate:** in `site.footer.affiliate_note` cạnh copyright ở footer trang con (`base_public.html`), và
   `site.cta_note` dưới mọi nút "Mở tài khoản" (`broker_detail.html`, `broker_compare.html`, thay cho `site.footer.risk_note`). Rỗng thì ẩn.
2. Rail: `<... data-view-url="{{ b.view_url }}">` và trong `site.js` gọi `navigator.sendBeacon` một lần mỗi lượt tải khi
   `matchMedia('(min-width: 1572px)').matches`. Chưa làm thì `views` của rail đứng ở 0. In `site.ads_note` dưới nút rail.
3. Thay chữ viết cứng: `home.html` "Nổi bật tuần này" → `site.hero.card_label`; `contact.html` "Đã gửi" → `site.contact_page.success_title`;
   `_header.html` → `site.system_text.header_cta_home` / `header_cta_page`; `404.html`, `500.html` → `not_found_text` / `error_text`;
   `subscription.html` → `sub_confirmed_text` / `sub_unsubscribed_text` / `sub_invalid_text`.
4. `home.html`: link "Xem bonus loại này" dùng `t.url`.
5. `500.html`: bỏ được nhánh `_bare.html` vì `site` luôn có, kể cả khi DB hỏng (giữ lại cũng không sao).
6. `broker_compare.html`: kiểm tra empty state khi `?ids=` rỗng (đang render được, chỉ cần xem câu chữ).

## [Backend → Admin FE] Việc thêm trong template (05/11, sau đợt trên)
Chi tiết trong `docs/VIEW_CONTEXT.md` (mục 4, 5).
1. `overview.html`: thêm thẻ Banner quảng cáo từ `banners` (name, `placement|placement_label`, clicks, `ctr(clicks, views)`, `state|banner_state_label`, `edit_url`); rỗng thì ẩn.
2. `_base.html`: logo sidebar dùng `branding.logo_path`.
3. `home.html` tab hero: ô `card_label`. Tab menu: ô `affiliate_note`, `cta_note`, `ads_note`.
4. `pages.html` tab lienhe: ô `success_title`. Tab mới `system` (“Chữ hệ thống”): ẩn 4 trường chung, hiện 12 ô theo `settings.system_text` với nhãn tiếng Việt.
5. `subtabs` của Trang đã có sẵn tab `system`; từ giờ tới khi làm mục 4, tab này hiện form chung và nút Lưu không đổi gì.
6. Sàn › Link affiliate: giữ cột "30 ngày", bỏ cột "Đăng ký" khỏi kế hoạch.

## [Admin FE → Backend] Cần bổ sung để form admin không mất dữ liệu / đúng thiết kế
1. **[ĐÃ XỬ LÝ 05/11]** **Trang chủ – lỗi validate làm mất các dòng lặp**: `form.data` dựng từ `form.multi_items()` nên trường lặp
   (`menu_label`, `point_title`, `reason_*`, `footer_col_*`, `*_points`) chỉ còn giá trị cuối. Khi 400 (vd. link menu sai),
   FE hiện lại danh sách đã lưu thay vì danh sách vừa nhập. Đề nghị: `form.data` giữ list cho khóa lặp (hoặc trả sẵn
   `menu`/`points`/`reasons`/`columns` đã parse). Ảnh vừa upload khi form lỗi cũng không hiện lại trong ô (đã vào thư viện).
2. **[ĐÃ XỬ LÝ 05/11]** **Trang / Cài đặt – lỗi validate mất chữ vừa nhập**: `form` chỉ có `errors`, không có `data`; FE phải hiện lại giá trị đã
   lưu. Đề nghị thêm `form.data` như màn Trang chủ.
3. **[ĐÃ XỬ LÝ 05/11]** **Cài đặt › Tài khoản**: lỗi của form "sửa tài khoản" và "thêm tài khoản" dùng chung khóa (`email/password/role`) nên FE
   không biết lỗi thuộc dòng nào; hiện tạm ở hộp lỗi đầu tab. Đề nghị thêm `form.errors_user_id` (id dòng bị lỗi) hoặc khóa riêng.
4. **[ĐÃ XỬ LÝ 05/11]** **Tin nhắn**: `POST toggle_url`/`delete_url` luôn về `/admin/messages` (mất `tab=unread`). Đề nghị nhận trường `back` như Bonus.
5. **[ĐÃ XỬ LÝ 05/11]** **Người đăng ký › Gửi email**: thiết kế có nút "Gửi thử cho tôi" – chưa có route, FE thay bằng "Lưu nháp".
   Bản nháp chưa mở lại/sửa được (chỉ hiện trong Lịch sử gửi).
6. **[ĐÃ XỬ LÝ 05/11: context `banners`]** **Tổng quan**: thiết kế có thẻ "Banner quảng cáo" (click · CTR từng banner) – context không có; FE thay bằng "Sàn nhiều
   click nhất" (`top_brokers`). Nếu muốn giống thiết kế: thêm `banners` (name, placement, clicks, views).
7. **[BỎ theo quyết định team leader 05/11: giữ cột "30 ngày"]** **Sàn › Link affiliate**: cột "Đăng ký" trong thiết kế không có dữ liệu – FE hiện "30 ngày" (`clicks_30d`).
8. **[ĐÃ XỬ LÝ 05/11: context `branding` ở mọi trang admin trừ login]** **Sidebar admin dùng logo cố định `/static/img/logo.png`** vì context admin không có `site.branding`. Nếu cần logo theo
   Cài đặt, thêm `branding` vào `render_admin`.
9. **[ĐÃ XỬ LÝ 05/11: biến `ADMIN_PASSWORD`, không cần `PYTHONIOENCODING`]** **CLI**: `create-admin` chỉ nhận mật khẩu qua `getpass` (không chạy được không tương tác trên Windows); QA/FE phải gọi
   `app.cli.create_admin(email, role, password)` trực tiếp, và cần `PYTHONIOENCODING=utf-8` (in tiếng Việt lỗi cp1252 khi
   không qua `main()`).

## [Admin FE] Ghi chú
- `admin.css` dùng biến của `static/css/tokens.css` (đã có, không khai báo lại). Màu riêng của thiết kế admin khác site
  public (đỏ `#B4232A`, xanh lá `#1F8A4C`, công tắc tắt `#C9D1D8`) khai báo trong `admin.css` với tiền tố `--a-*`.
- Nút trong thiết kế Admin.dc.html không kế thừa font (trình duyệt dùng font hệ thống); bản thật dùng Be Vietnam Pro cho
  mọi nút để đồng nhất – chữ menu/pill trông đậm hơn thiết kế một chút.

## [Public FE] Ghi chú và đề nghị bổ sung (04/11)
- **Đã tạo** `static/img/logo.png` (thu nhỏ từ `design/assets/logo.png` 1254px/1,1MB xuống 128px/9KB, cùng hình; hiển thị 42px) và
  `static/img/hero-bg.webp` (giải mã khóa `v2-hero-bg`).
- **[ĐÃ XỬ LÝ 05/11]** **[→ Backend] Link Điều khoản / Bảo mật**: mặc định `footer.columns` không có `/dieu-khoan`, `/bao-mat`, nên hai trang này
  không có link nào trên site. Đề nghị thêm vào cột "Liên kết" mặc định (FE đã render mọi link trong `footer.columns`).
- **[ĐÃ XỬ LÝ 05/11: `site.ads_note`]** **[→ Backend] Câu cảnh báo trong quảng cáo dọc (rail)**: thiết kế có dòng "CFD có rủi ro mất vốn cao." dưới nút. Không có khóa
  Setting nên FE bỏ dòng này (không hardcode). Nếu cần: thêm khóa ví dụ `ads_note` (str) – FE sẽ in nếu khác rỗng.
  Trang chi tiết sàn dùng `site.footer.risk_note` cho dòng cảnh báo dưới nút "Mở tài khoản".
- **[ĐÃ XỬ LÝ 05/11: `site.hero.card_label`, `site.contact_page.success_title`, `site.system_text`]** **[→ Backend, tùy chọn] Chữ hệ thống đang viết cứng trong template** (coi là nhãn giao diện, giống empty state):
  nhãn thẻ hero "Nổi bật tuần này"; tiêu đề khối thành công "Đã gửi" (trang Liên hệ); câu mô tả trang
  `subscription.html` (đã xác nhận / đã hủy / liên kết không hợp lệ), 404, 500; nút header "Xem bonus" (trang chủ) và
  "Nhận tư vấn" (trang con, trỏ `/lien-he`; thiết kế trỏ sang Bonus nhưng nhãn là tư vấn). Muốn admin sửa được thì cần khóa Setting.
- **Thẻ "So sánh 3 sàn" ở trang chủ**: theo thiết kế, nút là "Xem đánh giá {tên}" → `k.url` (VIEW_CONTEXT ghi "Mở tài khoản" → `go_url`).
  FE giữ theo thiết kế. Nút "Mở tài khoản" có ở bảng `/san/so-sanh` và trang chi tiết sàn.
- **Thẻ bonus trang chủ** dùng nhãn dài `bonus_types[].label` (giống thiết kế: "Cashback / rebate"); trang `/bonus` dùng `type_label` (nhãn ngắn).
- Lọc "Bonus mới nhất" ở trang chủ và tab "Loại bonus" chạy bằng `static/js/site.js`; khi tắt JS, hàng nút lọc bị ẩn và
  hiện đủ 8 bonus, tab hiển thị loại đầu tiên. Chip chọn loại khi đăng ký và chủ đề Liên hệ là checkbox/radio thật (không cần JS).

## [Public FE → Backend] Phát hiện khi code-review, cần sửa ở `app/`
- **[ĐÃ XỬ LÝ 05/11]** **Bỏ chọn hết sàn ở `/san/so-sanh` không được** (đã tái hiện): pill cuối link tới `?ids=`, nhưng `broker_compare` coi `ids` rỗng là
  "dùng mặc định" (`if ids.strip()`), nên trang hiện lại 3 sàn `in_compare`. Cần phân biệt "không có tham số" với "tham số rỗng".
- **[ĐÃ XỬ LÝ 05/11: giữ `type`, `kind`, `tab`, `cat`, `page`; bỏ `sort`, `ids`]** **Canonical bỏ query** (đã tái hiện): `/tin-tuc?page=2` có canonical là `/tin-tuc`; tương tự `?cat=`, `/bonus?type=`, `/san?kind=`,
  `/san/{slug}?tab=`. Trang phân trang và trang lọc bị báo cho công cụ tìm kiếm là bản trùng. Cần quyết định tham số nào giữ trong
  `meta.canonical`. FE đã bỏ canonical/og:url ở trang noindex.
- **[ĐÃ XỬ LÝ 05/11 phía backend, chờ beacon của Public FE]** **`Banner.views` của rail bị đếm thừa**: `home()` cộng view mọi request, nhưng rail chỉ hiện ở màn ≥ 1572px (như thiết kế). Lượt mở trên
  điện thoại/laptop vẫn tính view nên CTR rail thấp hơn thực tế.
- **[ĐÃ XỬ LÝ 05/11: `page_ctx` dùng nội dung mặc định nên render đủ `base_public.html`]** **Trang 500 khi DB hỏng không dùng `_bare.html`**: `_error_page` gọi `page_ctx()` trước `render()`, DB hỏng thì văng trước và rơi về
  `<h1>` trần. Template 500 đã chịu được thiếu `site` theo VIEW_CONTEXT; cần render `public/500.html` với context tối thiểu khi `page_ctx` lỗi.
- **[ĐÃ XỬ LÝ 05/11: `bonus_types[].url`]** **Link "Xem bonus loại này" ở trang chủ** FE tự ghép `/bonus?type=<id>` (lệch quy tắc 0.3, id cố định, giống link footer mặc định) vì context
  trang chủ không có URL này. Nếu muốn đúng quy tắc: thêm `url` vào phần tử `bonus_types`.

## [Admin FE → Backend] Thêm từ code review
10. **[ĐÃ XỬ LÝ 05/11]** **Cài đặt › SEO không có nút "Chọn từ thư viện"** cho `og_image`: `_settings_page` chỉ truyền `media_library` khi `tab == "general"`
    (`app/routes/admin_content.py`). Đề nghị thêm tab `seo`; FE không cần sửa gì (nút tự hiện khi có `media_library`).
11. **[ĐÃ XỬ LÝ 05/11: `GET /admin/subscribers/audience-count`]** **Đếm người nhận**: JS phải tải cả trang `/admin/subscribers?tab=mail&aud=...` rồi đọc một con số. Đề nghị route nhẹ trả JSON `{count}`.
    Khi tắt JS không xem lại được số theo lựa chọn (GET dùng `aud`, form POST dùng `audience`), nên nút hiện "Gửi email" và số của từng nhóm nằm trên pill.
12. **[ĐÃ XỬ LÝ 05/11 phần truyền theo tab và giới hạn 200 dòng; CHƯA làm ảnh thu nhỏ]** **Trang chủ / Trang**: `media_library` được truyền cho mọi tab kể cả tab không có ô ảnh (Section, Menu, Bonus...), không giới hạn số dòng,
    và ảnh trong hộp chọn là file gốc. Thư viện lớn sẽ nặng; đề nghị chỉ truyền cho tab cần và sinh ảnh thu nhỏ.
- **Câu công bố affiliate ở footer trang con**: thiết kế có "Một số liên kết là liên kết affiliate." sau copyright, và dưới nút "Mở tài khoản" có
  "Liên kết affiliate. CFD có rủi ro mất vốn cao do đòn bẩy.". Mặc định `footer.copyright` không có câu đầu, không có khóa nào cho câu sau (FE dùng
  `footer.risk_note`). Đề nghị thêm câu affiliate vào giá trị mặc định hoặc thêm khóa riêng, vì đây là thông tin công bố cần có trên trang có link affiliate.

## [Admin FE → Backend] Từ code review đợt 3 (05/11)
13. **[ĐÃ XỬ LÝ 05/11]** **Cài đặt › Tài khoản, lỗi 400 ở dòng sửa**: `user_edit` không trả lại vai trò vừa chọn, ô vai trò quay về giá trị đã lưu. Sửa mật khẩu rồi
    lưu lại thì đổi vai trò bị mất dù báo "Đã lưu". Đề nghị trả `form.data.edit_role`; FE sẽ đọc khi `form.errors_user_id == u.id`.
14. **[ĐÃ XỬ LÝ 05/11]** **`back` khi xóa**: FE đã gửi ở mọi form xóa, nhưng chỉ `messages_delete` dùng. `subs_delete`, `media_delete`, xóa bonus/sàn/banner/bài viết vẫn về
    URL cố định, mất lọc và tìm kiếm. Đề nghị đổi sang `a.back(...)`.
15. **[ĐÃ XỬ LÝ 05/11]** **Gửi 0 người**: FE đã khóa nút khi có JS. Khi tắt JS nhánh `no_recipients` vẫn redirect và mất nội dung đang soạn; đề nghị render lại form.
16. **[ĐÃ XỬ LÝ 05/11: `system_fields`]** **[FE: khóa chưa có nhãn tự hiện ở khối "Chữ khác", không còn bị bỏ sót]** **Chữ hệ thống**: danh sách 12 khóa và nhãn đang viết trong `pages.html`, trùng `DEFAULTS["system_text"]`. Thêm khóa mới phải sửa cả template.


## [Backend → FE] Phase 4: đã xong phía backend, việc còn lại của FE (05/11)
Chi tiết trong `docs/VIEW_CONTEXT.md`.

**Public FE**
1. `subscription.html`: khi `action_url` có giá trị, render `<form method="post" action="{{ action_url }}">` với nút
   `site.system_text["sub_" ~ status ~ "_button"]`. **Bắt buộc: chưa làm thì khách không xác nhận/hủy được**, vì GET không còn đổi trạng thái.
2. Form đăng ký: `flash.code == "sub_failed"` hiện cạnh form như `sub_invalid`, không hiện khối "đã đăng ký".
3. Ẩn khối khi rỗng: `site.hero.image_path` (nền navy, xóa `static/img/hero-bg.webp`), `site.home_why.stat_value`/`stat_label`, `site.home_about.badge`.
4. `_header.html`: nút trang con trỏ `/bonus`, chữ `site.system_text.header_cta_page`.
5. Rail có ảnh cũng in `site.ads_note` (Nghi ngờ 6).
6. `legal.html`: `body_html` giờ có nội dung mặc định, không còn cần câu "đang được cập nhật" (giữ cho trường hợp admin xóa hết).
7. Lỗi Thấp của FE trong QA_REPORT: 16 (Esc menu mobile), 17 (tương phản), 18 (chuỗi dài). `site.footer.copyright` đã thay `{year}` sẵn, thay lần nữa ở template cũng vô hại.

**Admin FE**
1. Hiện `form_errors` cho mọi khóa không gắn ô: lỗi độ dài có thể ở `menu_label`, `reason_text`, `about_block_text`...
2. `ads.html`, `overview.html`: `state` thêm `no_link`, `broker_hidden` (đã có trong `|banner_state_label`), không được tô như "Đang chạy".
3. `subscribers.html`: `campaigns[].status` thêm `partial` ("Gửi dở"), `delete_url` có form xóa kèm csrf, `sent_count` hiện cả khi `partial`.
4. `posts.html`: nhãn "Hẹn giờ" khi `p.scheduled`.
5. `pages.html`: tab mới `compare`, `method`, `affiliate` (chỉ trường chung); ô `label` ở mọi tab trừ `system`; tab `system` lặp `system_fields`, bỏ danh sách khóa viết tay.
6. `brokers.html`: `license` là ô bắt buộc (`required`), hiện lỗi `license`; thêm `maxlength` theo VIEW_CONTEXT nếu muốn báo sớm.
7. `settings.html` tab users: đọc `form.data.edit_role` khi `form.errors_user_id == u.id`.
8. `home.html` tab menu: gợi ý ô copyright: viết `{year}` để tự cập nhật năm.

**QA**
- Production giờ cần đủ `SECRET_KEY` (≥ 32 ký tự), `BASE_URL`, `SMTP_BACKEND`, nếu không `run.py` thoát mã 2. `/xac-nhan`, `/huy-dang-ky` phải POST. Broker cần `license`. Script `qa/` cần cập nhật.

## [Admin FE → Backend] Phát hiện khi chạy đầu cuối Phase 4 (05/11)
17. **[ĐÃ XỬ LÝ 05/11]** **Ô `label` ở Trang › Cách đánh giá và Công bố affiliate lưu được nhưng không hiện trên site**: `_about()` trong `app/routes/public.py` luôn tạo
    breadcrumb bằng `_crumb(ctx, "gioithieu", "/gioi-thieu")`, nên nhãn của `pages.method`, `pages.affiliate` không được dùng. Đề nghị thêm crumb theo `tab`, hoặc bỏ ô này khỏi hai tab đó.

## [Backend → FE] Vòng 2: thay đổi hợp đồng (05/11)
**Public FE**
1. `home.html` dòng badge sàn nổi bật: thay chữ cứng "Phổ biến" bằng `site.home_compare.featured_label` (mặc định "Nổi bật", rỗng → ẩn badge).
2. Form đăng ký: thêm `sub_wait` vào danh sách flash lỗi (`sub_invalid`, `sub_rate`, `sub_failed`), hiện `flash.text` cạnh form, không hiện khối "đã đăng ký".
3. `site.hero.card_label` mặc định đổi thành "Nổi bật" (template không cần sửa).

**Admin FE**
1. Trang chủ › tab Section: thêm ô `compare_featured_label` (giá trị `settings.home_compare.featured_label`, nhãn "Nhãn sàn nổi bật"). Form không gửi trường này thì giữ giá trị cũ.
2. Bonus: `min_deposit`, `withdrawable` bắt buộc, không nhận giá trị chỉ có dấu như "-", "—" (lỗi ở `drawer.errors`). Thêm `required`.
3. Sàn: `license` không nhận "-", "—", "N/A", "không có".
4. Người đăng ký: người đã hủy giữ trạng thái `unsubscribed` cho tới khi chính chủ bấm link xác nhận; không còn đổi sang `pending` khi ai đó nhập lại địa chỉ.

**Vận hành**
- Migration mới `0003` (cột `subscribers.reconfirm_token`), tự chạy khi khởi động lại `run.py`.
- Site đang chạy có thể đã lưu `hero.card_label` cũ trong Setting: đổi mặc định không ghi đè giá trị đã lưu, phải sửa ở admin nếu muốn đổi.


## [Phase 6 Backend → FE] Trả về đúng thiết kế: thay đổi context/route (05/11)
Chi tiết cuối cùng nằm trong `docs/VIEW_CONTEXT.md`. Phần "bỏ biến" an toàn cho template đang dùng `{% if %}`/`{% for %}`, trừ `pagination.pages` (mục P6).

**Public FE (revert-public)**
- P1. `page.title`, `page.desc`, `page.label` của `/san/so-sanh` lấy từ mục Sàn; của `/gioi-thieu/cach-danh-gia`, `/gioi-thieu/affiliate`, `/lien-he` lấy từ mục Giới thiệu. Template không đổi. Meta SEO vẫn riêng.
- P2. `crumbs`: So sánh = Trang chủ / Sàn uy tín. Cách đánh giá, Affiliate, Liên hệ = Trang chủ / Giới thiệu. Mục cuối có `url` thật: dùng để làm link (dòng A số 5 pages.md, `base_public.html:44`).
- P3. `site.menu`: trang chủ giữ "Sàn" (đúng `Trang chu v2`, `Admin`), mọi trang khác mục `/san` lấy `site.pages.san.label` = "Sàn uy tín" (đúng `Cac trang`). Template không đổi.
- P4. Biến mới `nav_path`: dùng thay `current_path` để tô menu trong `_header.html`. Ở `/lien-he`, `nav_path` = `/gioi-thieu`, nên sáng "Giới thiệu" như thiết kế (dòng C số 3). `current_path` giữ nguyên cho `next` của form.
- P5. `x|expiry_label` trả `31/12` (dd/mm), `Liên tục` khi None. `home.html:32` "Hạn đến" giữ `date_vn` vì thiết kế ghi `31/12/2026` ở thẻ hero. Ngày ở meta bài viết dùng `short_date`.
- P6. **Bỏ `pagination`** (thiết kế hiện hết bài, dòng C số 57): `/tin-tuc` trả toàn bộ, tham số `page` bị bỏ qua. Phải xóa khối `pagination` trong `post_list.html`, nếu không template lỗi. Bỏ `related_posts`: xóa khối ở `post_detail.html`.
- P7. `/tin-tuc/{slug}`: biến mới `back_url` cho nút "← Về danh sách" (giữ chuyên mục đang lọc). `page.desc` = "{chuyên mục} · {n} phút đọc". `posts[].url` ở trang lọc có thêm `?cat=`.
- P8. `compare_pick[].url` luôn là chuỗi: khi đủ 3 sàn, pill chưa chọn trỏ về đúng URL hiện tại (bấm không có tác dụng như thiết kế). Bỏ nhánh `is-disabled`.
- P9. `compare_brokers` trang chủ: theo thứ tự nhập, đủ 3 sàn thì sàn `featured` đứng giữa. Cột `/san/so-sanh` luôn theo thứ tự danh sách.
- P10. `POST /api/subscribe` redirect về `next#lien-he` (id thiết kế, K20): đổi `id="dang-ky"` trong `home.html` thành `id="lien-he"`. Production + `SMTP_BACKEND=console` → flash `sub_failed`, không lưu gì.
- P11. `site.hero.image_path` mặc định `/static/img/hero-bg.webp`: cần file này trong `static/img/`.
- P12. `site.hero.card_label`, `site.home_compare.featured_label`, `site.home_about.badge`, `site.home_why.stat_label`, `site.system_text.header_cta_page`... đã về chữ thiết kế. `stat_value` rỗng → ẩn thẻ số (`home.html:154` đã đúng), `stat_label` có sẵn chữ nhưng chỉ in khi có `stat_value`.
- P13. Footer cột Liên kết về 4 link như thiết kế, `/dieu-khoan`, `/bao-mat` không còn link mặc định.

**Admin FE (revert-admin)**
- A1. `nav`: một nhóm duy nhất (`label` None), phẳng: Tổng quan, Bonus, Sàn, Quảng cáo, Nội dung trang chủ, Bài viết, Người đăng ký, Cài đặt, rồi Trang, Thư viện ảnh, Tin nhắn. Vòng lặp hiện tại vẫn chạy. Mục Người đăng ký đếm mọi người đăng ký.
- A2. `/admin`: `stats` đúng 4 thẻ, `value` đã có dấu chấm nghìn. Bỏ `click_days`, `click_total`, `top_brokers`, `unread_messages`. `banners`: mọi banner theo thứ tự danh sách, thêm `broker` (tên sàn, None nếu banner không gắn sàn, khi đó dùng `name`). `expiring`: tối đa 4, theo thứ tự danh sách, ngưỡng 60 ngày. Câu rỗng "14 ngày" phải đổi.
- A3. `ctr()` trả `1.7%` (dấu chấm như thiết kế).
- A4. Bonus: bỏ `required` ở `min_deposit`, `withdrawable`; nhận "—" và ô trống. `license` của sàn vẫn bắt buộc.
- A5. `subtabs` của Bonus giữ `type`, `q`; của Bài viết giữ `q`.
- A6. `drawer.close_url` có ở mọi drawer: dùng thay biến `close_url` viết cứng. `edit_url`, `add_url`, `drawer.action` đã giữ tab và lọc.
- A7. Thứ tự: Sàn theo thứ tự nhập; Bài viết nháp xuống cuối.
- A8. Gửi email: soạn mới chọn sẵn nhóm `deposit` (`audience_options[].selected`, `audience_count`).
- A9. Route lưu nhiều dòng cho nút "Xuất bản thay đổi", thay nút "Lưu" từng dòng:
  `POST links_action` (`/admin/brokers/links`): `url_<id>` cho mỗi sàn.
  `POST ads_action` (`/admin/ads/bulk`): `placement_<id>`, `target_url_<id>`, `dates_<id>` cho mỗi banner. `dates_<id>` là một ô chữ như thiết kế, giá trị hiện tại `b.dates` (`01/11 – 30/11`), trống = không giới hạn.
  Lỗi → redirect kèm flash `invalid_url`, `too_long`, `invalid_dates`, không lưu dòng nào. Route `link_url`, `edit_url` cũ vẫn còn.
- A10. Filter mới `x|login_day`: `Hôm nay` hoặc `01/11/2026` cho cột Đăng nhập.
- A11. `pages.compare|method|affiliate|lienhe`: `title`, `desc` giờ chỉ là nguồn cho thẻ `<title>`, meta description; `label` không còn hiện ở đâu.
- A12. Trả lời 10 câu của revert-admin (05/11):
  1. Làm, nhưng backend tự gắn query: `edit_url`, `add_url`, `drawer.action`, `drawer.close_url` đã có `tab`, `type`, `q`. FE không gắn thêm, không cần `back` khi lưu drawer. Lưu xong và lỗi 400 đều giữ đúng danh sách.
  2. Làm: tab `brand` ("Thương hiệu"): `partner_email`, `logo_path`, `favicon_path`, `POST /admin/settings/brand`. Tab `general` chỉ còn 3 trường, không đụng tới ba trường kia. Thứ tự: general, seo, users, brand, social, tracking. `media_library` có ở `brand`, `seo`.
  3. Làm: giữ `{label, links}`, một nhóm (A1).
  4. Làm: A2, khóa là `banners[].broker`.
  5. Làm hết.
  6. Không thêm `AdminUser.name`: báo cáo xếp cột Tên loại B (brief mục 6), thêm phải có migration và ô nhập. Không cần `today`: dùng `|login_day` (A10).
  7. Không có nguồn dữ liệu: sàn không báo số đăng ký về site. FE hiện "—", ghi vào báo cáo là không khôi phục được.
  8. Làm chọn sẵn `deposit`. Nháp thiếu tiêu đề hoặc nội dung không lưu được: trả 400 như gửi thường.
  9. Làm.
  10. Có: A9.

## [Phase 6 Backend] Dòng báo cáo chưa khôi phục được hoặc cần user xem lại (05/11)
**Không khôi phục được, cần user quyết**
- K16 (thẻ hero độc lập với sàn nổi bật): thiết kế là chữ cứng, không nói bonus nào được chọn. Muốn đúng phải thêm ô chọn bonus ở admin. Giữ logic cũ: bonus giá trị cao nhất của sàn nổi bật; không có sàn nổi bật thì không có thẻ.
- K18 (dòng "Bonus nổi bật" là chữ tự do như "Deposit 50%"): không có trường dữ liệu tương ứng, vẫn ghép nhãn loại + số tiền.
- K24, K25 (rail có chữ phụ "mỗi lot", đoạn mô tả, dòng tự do): `bonus.amount` là một chuỗi, không tách được; không có trường mô tả rail. Backend không thêm trường.
- Sàn › Link affiliate, cột "Đăng ký": sàn không báo số đăng ký về site, không có nguồn dữ liệu. FE hiện "—".
- Cài đặt › Tài khoản, cột Tên: báo cáo xếp loại B, không thêm `AdminUser.name`.

**Giữ khác thiết kế, có lý do**
- Dòng số 25 pages.md (sort "Sắp hết hạn" theo ngày tăng dần): thiết kế chỉ đẩy "Liên tục" xuống cuối vì ngày trong mock là chuỗi, nên 31/12 đứng trước 30/11 dưới nhãn "Sắp hết hạn". Giữ sort thật. Muốn y thiết kế: sửa một dòng ở `app/queries.py`.
- "Click quảng cáo (tháng)": nhãn đúng thiết kế, số vẫn là 30 ngày gần nhất, vì báo cáo chỉ yêu cầu đổi nhãn.

**Hệ quả của việc trả về đúng thiết kế, user nên biết**
- `/dieu-khoan`, `/bao-mat` không còn link mặc định trên site (K11); trang vẫn chạy, có trong sitemap. Chính sách bảo mật thường cần có link công khai. Thêm lại ở Trang chủ › Menu & chân trang nếu cần.
- `/tin-tuc` hiện hết bài, không phân trang (dòng số 57); danh sách dài sẽ nặng dần.
- Thẻ "Bonus sắp hết hạn" lấy 4 bonus theo thứ tự danh sách (mới nhất trước), nên bonus sắp hết hạn nhất có thể không nằm trong 4 dòng. Tab Sắp hết hạn vẫn đủ.
- Thẻ "Người đăng ký" và số ở sidebar đếm mọi người đăng ký (cả chờ xác nhận, đã hủy) như thiết kế, không còn là số đã xác nhận.
- Hai trang đều dùng "Về TradingBonusHub" làm H1 (Giới thiệu, Liên hệ...): theo thiết kế, thẻ `<title>` vẫn riêng.

**Vận hành: site thật dùng dữ liệu đã lưu trong `data/app.db`, backend không được đụng**
- Mặc định mới chỉ có tác dụng với khóa chưa từng lưu. Khóa đã lưu qua admin giữ nguyên. Sau khi restart, team leader cần kiểm tra ở admin: `sections` (bật lại Form đăng ký), `hero` (ảnh, nhãn thẻ, câu mô tả), `home_about`, `home_why`, `home_compare`, `home_contact`, `pages`, `about_blocks`, `contact_page`, `system_text`, `menu`, `footer`.
- Khi production còn `SMTP_BACKEND=console`, form đăng ký hiện nhưng luôn báo `sub_failed`.

**Ngoài phạm vi, chưa xử lý**
- **[ĐÃ XỬ LÝ 05/11, FE không cần sửa]** Gửi chiến dịch, gửi thử ở production với console: `send_failed` (lưu thành nháp, redirect về form nháp, giữ chữ), `test_failed` (502). Lưu nháp vẫn chạy.
- `bonus_filters` trang chủ ẩn loại chưa có bonus; thiết kế luôn có 6 nút. Không có dòng trong báo cáo.

## [Phase 6 Public FE] Dòng chưa khôi phục được hoặc giữ khác thiết kế (05/11)
**Không khôi phục được từ template, cần user quyết** (cùng các mục backend đã ghi ở trên)
- K16: thẻ hero vẫn lấy bonus cao nhất của sàn nổi bật, không có sàn nổi bật thì ẩn thẻ. Thiết kế là chữ cứng. Muốn chọn tự do cần ô chọn bonus ở admin.
- K18: dòng "Bonus nổi bật" vẫn ghép nhãn loại + số tiền ("Cashback $4/lot"), thiết kế là chữ tự do ("Cashback", "Deposit 50%"). Cần trường dữ liệu mới.
- K24, K25: rail đã về đúng hai dạng (trái navy số 44px, không tag, 3 dòng; phải xanh có tag, số 52px, đoạn chữ, 1 dòng hạn, nút "Nhận {số tiền}"), nhưng thiếu chữ phụ dưới số ("mỗi lot", "không cần nạp tiền"), đoạn mô tả riêng (đang in tiêu đề bonus), dòng "Rút trong ngày" (đang in "Hạn đến dd/mm"). Không có trường dữ liệu. Số dài hơn 4 ký tự dùng 30px để không tràn rail 160px.
- K23: banner ngang thiết kế trang chủ không có. Đã bỏ khối navy tự thiết kế, chỉ còn dạng ảnh theo khung 970×250 của `Admin.dc.html`, căn giữa rộng 970px, cùng nhãn "Tài trợ". Vị trí và khoảng cách trên trang chủ không có nguồn trong thiết kế, giữ padding 56px sẵn có. Banner không có ảnh hiện khối nền trung tính (theo quyết định thiếu ảnh), trang chủ vẫn đếm view cho nó.

**Giữ khác thiết kế, có lý do**
- K29: "Điều kiện" giữ link `/san/{slug}`: thiết kế là `#`, chưa có đích.
- Dòng 14 pages.md: giữ skip link và viền focus, chỉ thấy khi dùng bàn phím.
- Dòng 42 pages.md: giữ câu "Chưa chọn sàn nào..." (thiết kế vỡ bảng khi bỏ chọn hết).
- Dòng 48 pages.md: dòng ưu đãi tab Bonus ở ≤640px giữ xếp dọc: ba cột của thiết kế làm nút đè lên chữ. Padding đã về 24.
- K12: bỏ câu "Số liệu là dữ liệu minh hoạ", Bonus ngắn hơn thiết kế 35px ở 1440, 50px ở 390 (loại B).

**Chống tràn ở điện thoại (brief mục 13), sai số so với thiết kế**
- H1 "Về TradingBonusHub": 40,4px ở 390, 36,8px ở 360 (thiết kế 52px tràn 71px). H1 khác giữ 52px; cỡ chữ tính theo từ dài nhất qua biến `--w`.
- Email ở Liên hệ: 17,2px và 15,4px ở 390 (thiết kế 18px, khung tràn). Ô số "N+" tự giảm dưới 56px khi không vừa.
- Tại sao chọn: giữ tỉ lệ 158:420 ở mọi khổ, ở 390 ảnh trái còn 88×460px (thiết kế 0px, ảnh phải tràn).
- Hàng sàn ở 390: cột hai lệch 11px so với thiết kế để nút không lấn padding và không tràn ở 360. Đăng ký ở 390 cao hơn 46px vì khung 322px thay vì 340px bị tràn.
- Footer đầy đủ ở ≤520px: 2 cột link bằng `repeat(2, ...)`, cao bằng thiết kế (636,5px).
- Hamburger: nút "Xem bonus"/"Nhận tư vấn" ở ≤600px nằm trong menu mở ra, không đủ chỗ trên thanh header.

**Tự thêm đã gỡ, ảnh hưởng nội dung**
- Rail dạng ảnh không còn in `site.ads_note`: thiết kế không có dòng này ở dạng ảnh. Dạng dựng từ dữ liệu vẫn in. Khác yêu cầu Phase 4 mục 5.
- Trang Liên hệ: email, Telegram là chữ thường như thiết kế, không còn link.


## [Phase 6 Admin FE] Trả về đúng thiết kế: phần còn khác và việc cần user chọn (05/11)
**[Lỗi thời: câu "đã xử lý mọi dòng" đo lại vòng 2 không đúng. Xem `docs/design-diff/admin.md` mục Vòng 2 và mục Phase 6.1 Admin FE cuối file.]**

**Không khôi phục được (thiếu dữ liệu)**
- Sàn › Link affiliate, cột "Đăng ký": giữ tên cột đúng thiết kế, ô hiện "—". Sàn không báo số đăng ký về site. Số click 30 ngày chuyển vào tooltip ô Click.
- Cài đặt › Tài khoản, cột "Tên": giữ cột, ô hiện "—". `AdminUser` không có tên (backend không thêm, xem A12 mục 6). Muốn có tên thật cần cột DB và ô nhập.
- Trạng thái mới không có trong thiết kế: "Không có link", "Sàn đang ẩn" của banner vẫn tô đỏ ở Quảng cáo; bài hẹn giờ hiện "Hẹn giờ" thay cho "Đã đăng".

**Giữ khác thiết kế, user quyết**
- Font mọi nút: giữ Be Vietnam Pro. File thiết kế không cho nút kế thừa font nên ra Arial, có vẻ là sơ suất. Chiều cao đã ép về đúng thiết kế (menu 38px bước 42, nút 40 và 42px), riêng chiều rộng nút, pill, tab con rộng hơn chút do font. Muốn về Arial: bỏ `button` khỏi rule `input, select, textarea, button { font: inherit }` và đổi menu, pill, tab sang font hệ thống ở `static/css/admin.css`.
- Hộp xác nhận trước khi Xóa và trước khi Gửi email (`admin.md` dòng "Xóa", "Trước khi gửi"): thiết kế làm ngay. Giữ hộp xác nhận vì gửi email và xóa không hoàn tác được, không đổi giao diện lúc thường. Muốn bỏ: gỡ `data-confirm` ở `_base.html`, `settings.html`, `subscribers.html`.
- Phím Esc đóng drawer, hỏi trước khi bỏ thay đổi chưa lưu: thiết kế không có. Giữ vì không đổi giao diện và QA đã kiểm phím tắt này. Focus ô đầu tiên (viền đậm) đã bỏ: drawer nhận focus, chỉ nhảy vào ô khi có lỗi.
- "Xem trên site ↗" ở đầu trang: thiết kế không có, brief mục 12 yêu cầu. Giữ một nút, bỏ hai link trùng. Đích trang chủ cũng có ở sidebar, nên các tab gốc của thiết kế có thể bỏ nếu user muốn.
- "Xuất bản thay đổi": site không có nháp/xuất bản. Màn có form: lưu form (Tab Section: chỉ lưu tiêu đề section). Sàn › Link affiliate, Quảng cáo › Banner: lưu mọi dòng một lần qua `links_action`, `ads_action`. Gửi email: lưu nháp (thay nút "Lưu nháp"), chưa soạn gì thì chỉ báo "Đã lưu"; thiếu một trong hai ô thì báo lỗi như backend. Màn còn lại lưu ngay từng thao tác nên nút chỉ báo "Đã lưu" 1,8 giây, không ghi gì.
- Đổi công tắc trên thẻ banner khi đang sửa ô chưa bấm Xuất bản: trang tải lại, chữ đang sửa mất (như thiết kế không có cảnh báo; bản trước cũng mất vì nút Lưu riêng từng thẻ).

**Chức năng tự thêm đã chuyển chỗ, khung bảng giữ nguyên**
- Bài viết, Người đăng ký: nút nhỏ "Lọc" cuối hàng tab con, mở drawer (tìm kiếm, lọc trạng thái). Sàn ẩn/hiện: công tắc trong drawer Sửa sàn. Xem bài trên site: nút trong drawer Sửa bài. Trạng thái người đăng ký, tài khoản bị khóa, lượt xem bài: tooltip.
- Sửa bài, Xóa người đăng ký, Sửa tài khoản: nút nhỏ hiện khi rê chuột vào dòng (màn cảm ứng luôn hiện). Bài viết còn bấm được vào tiêu đề.
- Tài khoản: thêm, đổi vai trò, đổi mật khẩu, khóa, xóa nằm trong drawer. "+ Thêm tài khoản" cuối hàng tab con.
- Gửi email: "Lịch sử gửi" là link nhỏ cạnh hai nút, mở drawer tại chỗ, không mất chữ đang soạn.
- Thẻ banner: link "Sửa" cuối dòng số liệu; bấm ảnh cũng mở drawer.
- Menu chính: nút ↑ ↓ ✕ nổi lên khi rê chuột hoặc focus vào dòng; "+ Thêm mục menu" dưới danh sách. Cảnh báo rủi ro về lại thẻ Menu chính như thiết kế.
- Tổng quan: bỏ dải tin nhắn chưa đọc (số chưa đọc vẫn ở sidebar). Thẻ có tiêu đề luôn hiện; số 0 để trống; hết dữ liệu hiện "Không có bonus nào sắp hết hạn.", "Chưa có banner nào.".
- Câu rỗng ở các danh sách: thiết kế không có, giữ theo brief mục 5, bỏ nút "+ Thêm" trùng đầu trang.
- Trang › So sánh, Cách đánh giá, Công bố affiliate, Liên hệ: bỏ ô nhãn breadcrumb (A11), tiêu đề và mô tả có ghi chú chỉ dùng cho thẻ title, meta.


## [Phase 6.1 Backend → FE] Đợt sửa cuối theo brief 13.1 (06/11)
Chi tiết trong `docs/VIEW_CONTEXT.md`. Chưa sửa template thì trang vẫn chạy, các tab mới hiện form trống.

**Admin FE**
- B1. Bulk lưu từng dòng: `POST links_action`, `ads_action` không còn redirect khi có lỗi. Dòng hợp lệ được lưu; dòng lỗi không lưu, trả **HTTP 400**, render lại đúng tab, hàng đó giữ chữ vừa nhập (`k.affiliate_url`; `b.placement`, `b.target_url`, `b.dates`). Mỗi hàng có `errors` (dict, rỗng nếu không lỗi): `k.errors.affiliate_url`; `b.errors.target_url`, `b.errors.dates`, `b.errors.placement`. Nên in dưới ô bằng `ui.err`. Flash `bulk_errors` đã nêu tên dòng ("Chưa lưu: ..."), hiện ở alert sẵn có. Dòng không đổi thì không bị kiểm tra, nên banner "Thiếu link đích" không còn chặn banner khác. Bỏ flash `invalid_dates`.
- B2. Thư viện ảnh: `media_action` (`POST`, đã giữ `q`), trường `alt_<id>`. Đặt `page_form` trỏ form này, ô mô tả dùng `form="page-form"`, bỏ form và nút Lưu từng thẻ để không lồng form. Lỗi cùng kiểu B1: `m.errors.alt`, `m.alt` giữ chữ vừa nhập. Không gõ gì thì vẫn POST, báo "Đã lưu" đúng thực tế.
- B3. Gửi email: **xóa đoạn chặn trong `initPublish` của `static/js/admin.js`** (nút Xuất bản khi chưa soạn). Để form POST `action=draft`: server trả 400, lỗi ở `subject`, `body`, giữ nguyên nhóm đã chọn. Backend không lưu riêng nhóm, vì nháp cần tiêu đề và nội dung.
- B4. `/admin/home`, thứ tự tab mới: `sections`, `hero`, `menu`, rồi `hero_extra` (Hero nâng cao), `headings` (Tiêu đề section), `footer` (Chân trang), `about`, `why`, `types`, `contact`.
  - `sections`: bỏ form tiêu đề; nút Xuất bản dùng `data-publish`. Các ô `bonus_*`, `compare_*`, `blog_*`, `compare_featured_label` chuyển sang tab `headings`, cùng tên trường.
  - `hero`: bỏ ô `card_label`, chuyển sang tab `hero_extra`, cùng tên trường.
  - `menu`: chỉ còn dòng menu và `risk_note`. `about_text`, `copyright`, `affiliate_note`, `cta_note`, `ads_note`, cột footer chuyển sang tab `footer`, cùng tên trường.
  - Form gốc không gửi các ô đó thì giá trị giữ nguyên. Tab `footer` không gửi dòng cột nào = xóa hết cột.
- B5. Không cần tab SEO nâng cao: tab `seo` gốc chỉ có 4 ô đúng thiết kế, SEO từng trang nằm ở Trang. Việc còn lại là bỏ cột xem trước. Drawer: khối "Thông tin chi tiết" chỉ là việc của template, tên trường không đổi.
- B6. Số 0 ở `nav`: `count` là 0 cho mục có đếm, None cho mục không đếm. Đổi `{% if i.count %}` theo quyết định 13.1 nếu áp dụng cho sidebar (thiết kế dùng `count ?? ''`, nên in 0).

**Public FE**
- C1. Backend đã truyền số 0 (int), None chỉ dành cho tab không có số (So sánh, tab Giới thiệu, tab chi tiết sàn trừ Bonus). Sửa template:
  - `base_public.html:52`: `{% if t.count is not none %}`.
  - `bonus_list.html:6`: luôn in `{{ bonus_count }} ưu đãi`.
  - `broker_list.html:17`: `{{ k.bonus_count }}`, bỏ `or "—"`.
  - Bảng so sánh: `cells` có số 0, kiểm tra template không đổi thành "—".

## [Phase 6.1 Public FE] Cập nhật so với mục "[Phase 6 Public FE]" (06/11)
- Dòng 42 pages.md không còn giữ câu "Chưa chọn sàn nào...": bỏ chọn hết hiện bảng nhãn như thiết kế. DB chưa có sàn nào vẫn là "Chưa có sàn nào." (dòng 90).
- Đã chốt theo thiết kế: tab danh sách (Bonus, Sàn, Tin, Giới thiệu) về đầu trang; sort, chọn sàn, tab chi tiết sàn giữ vị trí cuộn; dải tab luôn giữ vị trí.
- Đã chốt: in "0 ưu đãi đang hoạt động" ở khung chi tiết sàn và ô "0+" ở trang chủ như thiết kế.


## [Phase 6.1 Admin FE] Dòng còn lệch thiết kế sau đợt 13.1 (06/11)
Số dòng theo `docs/design-diff/admin.md` mục Vòng 2. Các dòng không nêu ở đây và thuộc bảng CÒN của vòng 2 đã sửa; chưa có đo độc lập lại sau đợt này.

**Thuộc danh sách GIỮ (13, 13.1), không sửa:** 5 font nút; 10 Đăng xuất; 86 "Tin sàn" (brief mục 6); 97, 120 hộp xác nhận; 119 Esc; câu báo rỗng.

**Còn lệch, cần user quyết:**
- 15 "Xuất bản thay đổi" không có nháp/xuất bản thật: lưu form, lưu nhiều dòng, hoặc chỉ báo "Đã lưu" ở màn lưu ngay. Ở Gửi email là lưu nháp.
- 44 công tắc: đã đổi tại chỗ, không tải lại, không báo gì. Bản chất vẫn là POST + đọc trang trả về; dưới tab con có lọc (vd. Đang hiển thị) số dòng đổi thì tải lại trang.
- Mũi tên Section vẫn tải lại trang, giữ vị trí cuộn. Thiết kế không tải lại.
- 57 banner: link "Sửa" chỉ hiện khi rê hoặc focus; 80, 88 nút "Lọc"; 93 link "Lịch sử gửi"; 108, 109 nút Sửa khi rê và "+ Thêm tài khoản"; 77 "+ Thêm mục menu" và ↑ ↓ ✕ nằm ngoài thẻ, trên nền trang. Không có trong thiết kế, giữ vì 13.1 cấm bỏ chức năng và các nút này không làm đổi khung.
- 107 cột Tên hiện "—", cột Đăng ký (Link affiliate) hiện "—": không có dữ liệu.
- 114 ô Sàn là select, ô Hết hạn là ô ngày: dữ liệu là khóa ngoại và kiểu ngày; ô cao đúng 45px. Muốn ô chữ như thiết kế ("Liên tục", "31/12") cần backend nhận chữ.
- 118 drawer Sửa, Thêm mở bằng tải trang (form server-side), nhìn không khác.
- Khối "Thông tin chi tiết" đóng sẵn cuối drawer Sửa bonus, Sửa sàn: 13.1 yêu cầu, thiết kế không có.
- Vùng ảnh Hero, SEO: thêm link nhỏ "Chọn từ thư viện", "Bỏ ảnh" trên hàng nhãn, không đổi bố cục.
- Trang chủ có 10 tab, ở 1440 tab cuối "Liên hệ" bị khuất, cuộn ngang trong hàng tab (hàng tab của thiết kế cũng `overflow-x: auto`).
- Ô Chung, SEO là textarea như thiết kế, Enter gửi form thay vì xuống dòng; ô Email không còn kiểm tra phía trình duyệt, server vẫn kiểm tra.
- Sidebar: Thư viện ảnh, Tin nhắn in 0 theo 13.1 (mục mới, thiết kế không có).

**Không đổi nghĩa:** công tắc trong drawer Tài khoản, Sửa sàn vẫn POST và tải lại. Mọi màn chạy được khi tắt JS, trừ "Bỏ ảnh" (xóa ô đường dẫn thay thế).
