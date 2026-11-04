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
