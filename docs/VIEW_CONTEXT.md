# VIEW_CONTEXT – hợp đồng dữ liệu Backend ↔ Template

Tài liệu này là nguồn duy nhất FE cần để viết template. Backend do `app/` sở hữu; mọi tên ở đây khớp code
(kiểm bằng `pytest`). Thấy sai hoặc thiếu: ghi `docs/ISSUES.md`, đừng đoán.

Quy ước kiểu: `str`, `int`, `float`, `bool`, `date` (ngày, không giờ), `datetime` (UTC trong DB; luôn đưa qua
filter `date_vn`/`datetime_vn` để ra giờ VN), `X|None` (có thể None), `list[...]`.

---

## 0. Quy tắc chung (đọc trước)

1. **Template là Jinja2, autoescape bật.** Chỉ dùng `|safe` cho các biến ghi rõ “HTML đã lọc” (`body_html`,
   filter `markdown`) và `site.analytics_head` (do admin role `admin` nhập, đặt trong `<head>`).
2. **Mọi biến ngữ cảnh là dict/list thường** (không phải object ORM). Truy cập `x.key` hoặc `x["key"]`.
   Backend đã tránh các khóa trùng tên method của dict (`values`, `items`, `keys`, `get`...), nên `x.key` luôn an toàn.
   Ngoại lệ duy nhất: vòng lặp dict lỗi `errors` dùng `errors.items()`.
3. **Link/URL tính sẵn ở backend** (`url`, `go_url`, `edit_url`...). FE không tự ghép URL có tham số.
4. **Ảnh**: mọi trường ảnh là đường dẫn công khai dạng `/media/<hex>.<ext>` (upload) hoặc `/static/img/...`
   (mặc định FE cung cấp) hoặc chuỗi rỗng. Rỗng → khối nền trung tính, không chữ placeholder.
5. **Danh sách rỗng** → empty state câu trung tính (ví dụ “Chưa có bonus nào.”). Số đếm `0`/`None` → ẩn.
6. **Không dữ liệu mẫu trong template.** Chữ tĩnh của trang (tiêu đề, mô tả, lý do, footer...) lấy từ `site.*`
   (bảng Setting, mặc định = chữ thiết kế). Chỉ nhãn khung (nút, nhãn cột, tab) được viết cứng trong template.
7. **Tên file template cố định** (bảng ở mục 2 và 4). Partial/base tùy FE đặt (`templates/base_public.html`,
   `templates/public/_*.html`, `templates/admin/_*.html`).
8. File stub hiện tại có `data-stub="BACKEND STUB"`: FE ghi đè toàn bộ.

### 0.1 Flash (thông báo ngắn sau redirect)

Có ở **mọi** template (public và admin): biến `flash`:

```
flash: None | {"kind": "success"|"error", "text": str, "code": str}
```

Hiện một lần rồi tự mất (cookie đã bị xóa khi render). Gợi ý: admin hiện “Đã lưu” dạng toast 1,8s;
public hiện trong khối form tương ứng dựa vào `flash.code`.

| code | kind | text | Xuất hiện ở |
|---|---|---|---|
| `saved` | success | Đã lưu | admin |
| `created` | success | Đã thêm | admin |
| `deleted` | success | Đã xóa | admin |
| `toggled` | success | Đã cập nhật | admin |
| `sent` | success | Đã gửi email | admin Người đăng ký |
| `uploaded` | success | Đã tải ảnh lên | admin Thư viện ảnh |
| `logged_out` | success | Đã đăng xuất | trang đăng nhập |
| `compare_limit` | error | Chỉ được chọn tối đa 3 sàn để so sánh. | admin Sàn |
| `media_in_use` | error | Ảnh đang được dùng, không thể xóa. | admin Thư viện ảnh |
| `self_delete` | error | Không thể xóa hoặc khóa chính tài khoản đang đăng nhập. | admin Cài đặt › Tài khoản |
| `no_recipients` | error | Không có người nhận phù hợp. | admin Người đăng ký › Gửi email |
| `invalid_url` | error | Link phải bắt đầu bằng http:// hoặc https:// | admin Sàn › Link affiliate |
| `sub_ok` | success | Kiểm tra hộp thư để xác nhận email. | trang có form đăng ký (sau POST /api/subscribe) |
| `sub_invalid` | error | Vui lòng nhập email hợp lệ. | như trên |
| `sub_rate` | error | Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút. | như trên |
| `contact_ok` | success | Cảm ơn bạn. Chúng tôi sẽ trả lời qua email. | `/lien-he` |

Trang chủ: nếu `flash.code == "sub_ok"` thì hiện khối “đã đăng ký” (`site.home_contact.success_title` /
`success_text`) thay cho form; `sub_invalid`/`sub_rate` hiện `flash.text` cạnh form.

### 0.2 Lỗi validate

- Admin form drawer: `drawer.errors` – dict `{tên_trường: thông_báo}`; khi có lỗi, server trả **HTTP 400**,
  render lại cùng trang với drawer mở và `drawer.data` = giá trị vừa nhập.
- Admin form tab (Trang chủ, Trang, Cài đặt): `form.errors` (dict như trên), HTTP 400.
- Form liên hệ public: `form.errors` (khóa `email`, `body`, hoặc `form` = lỗi chung như rate limit), HTTP 400/429.
- Lỗi gắn với trường: hiện ngay dưới input có `name` tương ứng. Khóa không khớp input nào: hiện đầu form.

### 0.3 CSRF

- **Admin (đã đăng nhập)**: mọi `<form method="post">` phải có
  `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`. Thiếu/sai → HTTP 403.
  Kể cả nút bật/tắt, xóa, đăng xuất.
- **Trang đăng nhập**: cùng cú pháp, biến `csrf_token` có sẵn trong context login.
- **Form public** (`/api/subscribe`, `/api/contact`): không cần CSRF, nhưng **bắt buộc** có ô honeypot ẩn:
  `<input type="text" name="website" value="" tabindex="-1" autocomplete="off" hidden>` (có giá trị → bị coi là bot).

### 0.4 Upload ảnh trong form admin

Form có ảnh phải `enctype="multipart/form-data"`. Mỗi trường ảnh `<name>` gồm hai input:
- `<name>` (text/hidden): đường dẫn ảnh đang chọn. Chọn từ thư viện (`media_library`) thì đặt `path` vào đây.
  Gửi rỗng = bỏ ảnh. Chỉ chấp nhận đường dẫn có trong thư viện, `/static/img/...` hoặc giá trị hiện tại.
- `<name>_file` (`type=file`, `accept="image/png,image/jpeg,image/webp"`): nếu có file thì ưu tiên file.
  File được kiểm tra (PNG/JPEG/WEBP thật, ≤ 5MB), lưu vào thư viện ngay cả khi phần còn lại của form lỗi.
Lỗi ảnh nằm ở `errors["<name>"]`.

`media_library: list[{"id": int, "path": str, "alt": str, "width": int, "height": int}]` (mới nhất trước) – có
ở các trang admin có trường ảnh (xem từng trang).

---

## 1. Helper Jinja (filter / global)

| Tên | Dùng | Kết quả |
|---|---|---|
| `x\|date_vn` | `date` hoặc `datetime` | `31/12/2026` (datetime đổi sang giờ VN); None → `""` |
| `x\|short_date` | như trên | `31/12` |
| `x\|datetime_vn` | `datetime` | `31/12/2026 08:30` |
| `x\|iso_date` | `date` | `2026-12-31` (cho `<input type=date>` / `<time datetime>`) |
| `x\|expiry_label` | `date\|None` | None → `Liên tục`, có ngày → `31/12/2026` |
| `x\|num` | số | `18.420` (dấu chấm ngăn nghìn); không phải số → `""` |
| `ctr(clicks, views)` | global | `1,7%`; views = 0 → `—` |
| `x\|type_label` | id loại bonus | nhãn ngắn (`No-deposit`, `Deposit bonus`, `Cashback`, `Cuộc thi`, `Crypto` – sửa được ở admin) |
| `x\|markdown` | chuỗi Markdown | HTML đã lọc bằng nh3 (an toàn, không cần `\|safe`) |
| `x\|post_status_label` | `draft`/`published` | `Nháp` / `Đã đăng` |
| `x\|subscriber_status_label` | `pending`/`confirmed`/`unsubscribed` | `Chờ xác nhận` / `Đã xác nhận` / `Đã hủy` |
| `x\|placement_label` | vị trí banner | `Sau Bonus mới nhất` / `Trước Tin tức` / `Cột trái (hero)` / `Cột phải (hero)` |
| `x\|banner_state_label` | `running`/`paused`/`scheduled`/`ended` | `Đang chạy` / `Tạm dừng` / `Chưa bắt đầu` / `Đã kết thúc` |
| `x\|role_label` | `admin`/`editor` | `Quản trị` / `Biên tập` |
| `x\|kind_label` | `forex`/`crypto` | `Forex` / `Crypto` |

---

## 2. Public – biến có ở mọi trang

| Biến | Kiểu | Ghi chú |
|---|---|---|
| `site` | dict | Toàn bộ nội dung sửa được (mục 2.1) + `site.type_labels` (dict id→nhãn ngắn) + `site.year` (int) |
| `page` | `{"key": str\|None, "title": str, "desc": str}` | Tiêu đề + mô tả đầu trang (navy header của trang con) |
| `meta` | `{"title", "description", "keywords", "canonical", "og_image", "noindex": bool}` | Đặt vào `<head>`. `og_image` là URL tuyệt đối hoặc `""` (ẩn thẻ) |
| `crumbs` | `list[{"label", "url"}]` | Breadcrumb, phần tử đầu là “Trang chủ” |
| `current_path` | str | Để tô menu đang chọn (so với `site.menu[i].url`) |
| `flash` | xem 0.1 | |

`<head>` nên có: `<title>{{ meta.title }}</title>`, meta description/keywords, `<link rel="canonical">`,
`og:*`, favicon `site.branding.favicon_path`, `{% if meta.noindex %}<meta name="robots" content="noindex">{% endif %}`,
Google Fonts Be Vietnam Pro, và cuối `<head>`: `{{ site.analytics_head|safe }}` (chuỗi rỗng nếu chưa cấu hình).

### 2.1 `site` – khóa nội dung (bảng Setting)

| Khóa | Kiểu / trường | Dùng ở |
|---|---|---|
| `site_name` | str | logo chữ, title |
| `contact_email`, `partner_email`, `telegram` | str (rỗng → ẩn dòng) | trang Liên hệ, footer |
| `meta_title`, `meta_desc`, `meta_keywords` | str | đã đưa vào `meta` |
| `branding` | `{logo_path, favicon_path, og_image}` | header/footer logo, favicon |
| `social` | `list[{label, url}]` (url http(s)) | footer (rỗng → ẩn) |
| `analytics_head` | str (HTML) | cuối `<head>`, `\|safe` |
| `menu` | `list[{label, url}]` | menu header |
| `footer` | `{about_text, columns: list[{title, links: list[{label, url}]}], risk_note, copyright}` | footer |
| `hero` | `{eyebrow, headline, sub, cta, image_path}` | hero trang chủ (`image_path` mặc định `/static/img/hero-bg.webp`) |
| `sections` | `list[{id, label, on}]` | admin; public dùng `home_sections` |
| `home_about` | `{eyebrow, title, text, points: list[{title,text}], badge, count_label, images: [str,str,str]}` | section Về chúng tôi |
| `home_bonus` | `{eyebrow, title}` | tiêu đề section Bonus mới nhất |
| `home_why` | `{eyebrow, title, text, stat_value, stat_label, reasons: list[{title,text}], images: [str,str]}` | Tại sao chọn (số thứ tự `01.` FE tự in theo `loop.index`) |
| `home_types` | `{eyebrow, title, image}` | Loại bonus |
| `home_compare` | `{eyebrow, title}` | So sánh 3 sàn |
| `home_contact` | `{eyebrow, title, text, image, success_title, success_text}` | form đăng ký trang chủ |
| `home_blog` | `{eyebrow, title}` | Tin tức mới nhất |
| `bonus_types` | `list[{id, short, label, desc, points: list[str]}]` – luôn đủ 5 theo thứ tự `nodep, deposit, cashback, contest, crypto` | section Loại bonus, chip đăng ký. `short` = nhãn ngắn (tab/chip), `label` = nhãn dài |
| `about_blocks` | `{about|method|affiliate: {image: str, blocks: list[{title,text}]}}` | /gioi-thieu (đã chuyển thành `about_blocks` ở context trang) |
| `contact_page` | `{intro, topics: list[str], response_note, success_text}` | /lien-he |
| `pages` | `{bonus|san|tin|gioithieu|lienhe|terms|privacy: {title, desc, meta_title, meta_desc}}` | đã đưa vào `page`/`meta` |
| `legal` | `{terms_md, privacy_md}` | đã chuyển thành `body_html` |

### 2.2 Dict dùng chung

**BrokerMini** (sàn rút gọn, nằm trong bonus/banner):
```
{"id": int, "slug": str, "name": str, "mono": str (≤2 ký tự), "kind": "forex"|"crypto", "license": str,
 "logo_path": str, "url": "/san/<slug>", "go_url": "/go/broker/<id>" | None (None = không có link → ẩn nút)}
```

**Bonus**:
```
{"id": int, "type": "nodep"|"deposit"|"cashback"|"contest"|"crypto", "type_label": str, "amount": str,
 "value_num": float|None, "title": str, "min_deposit": str, "withdrawable": str,
 "expiry_date": date|None (dùng |expiry_label), "expires_soon": bool (≤ 14 ngày),
 "go_url": str|None ("Nhận bonus"), "broker": BrokerMini}
```
Chỉ bonus đang hiển thị (bật, sàn bật, chưa hết hạn) mới có ở public.

**Broker** (= BrokerMini + chi tiết):
```
BrokerMini + {"kind_label": str, "tagline": str, "summary": str, "min_deposit": str, "leverage": str,
 "platforms": str, "spread": str, "withdrawal": str, "founded": str,
 "pros": list[str], "cons": list[str],
 "accounts": list[{"name","min_deposit","spread","commission"}],
 "payment_methods": list[{"method","deposit","withdraw","time"}],
 "featured": bool, "in_compare": bool, "bonus_count": int, "top_bonus": Bonus|None}
```
`top_bonus` chỉ có giá trị ở trang chủ (`compare_brokers`) – dòng “Bonus nổi bật” = `top_bonus.type_label`
(+ `amount`); None → ẩn dòng. Ở trang khác luôn None.

**Post**:
```
{"id": int, "slug": str, "title": str, "category": "Hướng dẫn"|"Kiến thức"|"So sánh"|"Tin sàn",
 "excerpt": str, "cover_path": str, "read_minutes": int, "published_at": datetime|None, "views": int,
 "url": "/tin-tuc/<slug>"}
```
Hiển thị: `{{ p.published_at|short_date }} · {{ p.read_minutes }} phút đọc`.

**Banner**:
```
{"id": int, "name": str, "image_path": str, "placement": str, "url": "/go/ad/<id>" (luôn dùng link này),
 "broker": BrokerMini|None, "bonus": Bonus|None (bonus giá trị cao nhất của sàn đó)}
```
Có `image_path` → banner ảnh (`<a href="{{ b.url }}" rel="sponsored nofollow">`). Không có ảnh → thẻ “native”
dựng từ `broker` + `bonus`. Luôn có nhãn “Tài trợ”.

**Tab** (thanh tab dưới header trang con): `{"id": str, "label": str, "count": int|None, "url": str, "active": bool}`.
`count` None hoặc 0 → ẩn số.

---

## 3. Public – từng route

### `GET /` → `public/home.html`
| Biến | Kiểu |
|---|---|
| `home_sections` | `list[str]` – id section cần render **theo đúng thứ tự**: `hero, about, bonus, ad1, why, types, compare, signup, ad2, blog`. Đã loại section admin tắt và section cần dữ liệu mà rỗng (`bonus, ad1, compare, ad2, blog`). |
| `hero` | = `site.hero` |
| `hero_bonus` | `Bonus\|None` – thẻ “Nổi bật tuần này” (bonus tốt nhất của sàn `featured`); None → ẩn thẻ |
| `rail_left`, `rail_right` | `Banner\|None` – quảng cáo hai bên hero (vị trí `rail-left`/`rail-right`); None → ẩn |
| `active_bonus_count` | int – số “N+ Ưu đãi đang hoạt động” ở section About; 0 → ẩn khối số |
| `latest_bonuses` | `list[Bonus]` (≤ 8, mới nhất) |
| `bonus_filters` | `list[{"id", "label", "count"}]` – `all` + các loại có bonus; lọc phía client bằng `data-type="{{ b.type }}"` |
| `ad1`, `ad2` | `Banner\|None` – `after-bonus`, `before-blog` |
| `compare_brokers` | `list[Broker]` (≤ 3, sàn `featured` đứng đầu; thẻ nào `featured` thì nền navy + nhãn “Phổ biến”). Nút “Mở tài khoản” → `go_url` |
| `blog_posts` | `list[Post]` (≤ 3, bài đã đăng có `show_home`) |
| + chung | `site`, `page` (`title=""`), `meta`, `crumbs`, `flash` |

Form đăng ký (section `signup`, nên đặt `id="dang-ky"`):
```
<form method="post" action="/api/subscribe">
  name="name" (text), name="email" (email, bắt buộc),
  name="interests" (checkbox, value = bonus_types[i].id, lặp; chip chọn nhiều),
  name="website" (honeypot ẩn), name="next" (hidden, value="{{ current_path }}")
```
Sau POST luôn redirect 303 về `next#dang-ky` kèm flash `sub_ok|sub_invalid|sub_rate`.
Hành vi: email mới → gửi mail xác nhận; đã xác nhận → không gửi lại (vẫn báo `sub_ok`).

### `GET /bonus?type=&sort=` → `public/bonus_list.html`
`type ∈ nodep|deposit|cashback|contest|crypto` (khác → all), `sort ∈ new|value|expiry` (khác → new).
| Biến | Kiểu |
|---|---|
| `tabs` | `list[Tab]` – `all` + 5 loại (giữ nguyên sort hiện tại) |
| `sorts` | `list[{"id","label","url","active"}]` – Mới nhất / Giá trị cao / Sắp hết hạn |
| `bonuses` | `list[Bonus]` |
| `bonus_count` | int – “N ưu đãi” (0 → ẩn) |
| `current_type`, `current_sort` | str |
Empty: “Chưa có ưu đãi trong mục này.” Nút “Về sàn” → `b.broker.url`.

### `GET /san?kind=` → `public/broker_list.html`
| `tabs` | `list[Tab]` – all / forex / crypto / compare (`/san/so-sanh`, count None) |
| `brokers` | `list[Broker]` (đã lọc theo kind) |
| `current_kind` | `"all"|"forex"|"crypto"` |
Nút “Xem đánh giá” → `k.url`.

### `GET /san/so-sanh?ids=1,2,3` → `public/broker_compare.html`
Không có `ids` → dùng các sàn admin bật “so sánh”. Tối đa 3.
| `tabs` | như /san, tab `compare` active |
| `compare_pick` | `list[{"id","name","selected": bool,"url": str|None}]` – pill “Chọn tối đa 3 sàn”; `url` None = đã đủ 3, pill bị vô hiệu |
| `compare_brokers` | `list[Broker]` – các cột |
| `compare_rows` | `list[{"label": str, "cells": list[str|int]}]` – 8 dòng: Giấy phép, Nạp tối thiểu, Đòn bẩy tối đa, Spread / phí, Nền tảng, Rút tiền, Thành lập, Bonus đang có. `cells[i]` ứng với `compare_brokers[i]` |
| `max_compare` | 3 |
Grid: `grid-template-columns: 180px repeat({{ [compare_brokers|length,1]|max }}, minmax(200px,1fr))`.

### `GET /san/{slug}?tab=overview|bonus|accounts|pay` → `public/broker_detail.html` (404 nếu không có/ẩn)
| `broker` | Broker |
| `tabs` | `list[Tab]` – Tổng quan / Bonus (count) / Tài khoản & phí / Nạp & rút |
| `current_tab` | str |
| `bonuses` | `list[Bonus]` của sàn (giá trị cao trước) – dòng phụ: `{{ b.type_label }} · hết hạn {{ b.expiry_date|expiry_label }}` |
| `facts` | `list[{"label","value"}]` – 6 ô: Giấy phép, Nạp tối thiểu, Đòn bẩy tối đa, Spread / phí, Nền tảng, Rút tiền |
`page.title` = “Đánh giá <tên>”, `page.desc` = tagline + “Thành lập <năm>.”. Tab `accounts` dùng `broker.accounts`,
tab `pay` dùng `broker.payment_methods` (rỗng → empty state). Nút “Mở tài khoản {{ broker.name }}” → `broker.go_url`.

### `GET /tin-tuc?cat=&page=` → `public/post_list.html`
| `tabs` | `list[Tab]` – Tất cả + 4 chuyên mục |
| `posts` | `list[Post]` (12 bài/trang) |
| `current_cat` | str (`all` hoặc tên chuyên mục) |
| `pagination` | `{"page": int, "pages": int, "prev_url": str|None, "next_url": str|None}` (pages = 1 → ẩn) |

### `GET /tin-tuc/{slug}` → `public/post_detail.html` (404 nếu nháp/không có)
| `post` | Post + `{"body_html": str}` – HTML đã lọc, dùng `{{ post.body_html|safe }}` |
| `related_posts` | `list[Post]` (≤ 3 cùng chuyên mục) |
Nút “← Về danh sách” → `/tin-tuc`. Không có nhãn “Bài viết minh hoạ”.

### `GET /gioi-thieu`, `/gioi-thieu/cach-danh-gia`, `/gioi-thieu/affiliate` → `public/about.html`
| `tabs` | `list[Tab]` – Về chúng tôi / Cách đánh giá / Công bố affiliate / Liên hệ (`/lien-he`) |
| `current_tab` | `about|method|affiliate` |
| `about_blocks` | `list[{"n": "01.", "title", "text"}]` |
| `about_image` | str (ảnh cột phải; rỗng → khối nền) |

### `GET /lien-he` → `public/contact.html` (cũng render lại khi POST lỗi)
| `tabs` | như trang giới thiệu, tab `contact` active |
| `contact` | = `site.contact_page` (`intro`, `topics`, `response_note`, `success_text`) |
| `form` | `{"action": "/api/contact", "data": {"topic","name","email","body"}, "errors": dict}` |
Email/Telegram liên hệ: `site.contact_email`, `site.partner_email` (“Hợp tác với sàn”), `site.telegram`; rỗng → ẩn dòng.
Thành công: `flash.code == "contact_ok"` → hiện khối “Đã gửi”.
```
<form method="post" action="{{ form.action }}">
  name="topic" (pill/radio, value ∈ contact.topics), name="name", name="email", name="body" (textarea),
  name="website" (honeypot)
```
POST thành công → 303 `/lien-he` + flash. Lỗi → 400 (hoặc 429 khi gửi quá nhiều, lỗi ở `form.errors.form`).

### `GET /dieu-khoan`, `GET /bao-mat` → `public/legal.html`
| `body_html` | str – HTML đã lọc (`|safe`); rỗng → “Nội dung đang được cập nhật.” |
`page.title` = tiêu đề trang (admin sửa được).

### `GET /xac-nhan/{token}`, `GET /huy-dang-ky/{token}` → `public/subscription.html`
| `status` | `"confirmed"` (200) / `"unsubscribed"` (200) / `"invalid"` (404) |
`page.title` đã đặt sẵn (“Đã xác nhận đăng ký” / “Đã hủy đăng ký” / “Liên kết không hợp lệ”), `meta.noindex = True`.

### Trang lỗi → `public/404.html`, `public/500.html`
Context chung (`site`, `page.title`, `meta.noindex = True`). 500 có thể render không có `site` nếu DB hỏng:
template 500 nên chịu được `site` undefined (dùng `{% if site %}`) – backend có fallback HTML tối giản.

### Không có template
`/go/broker/{id}`, `/go/ad/{id}` (302 + đếm click; 404 khi không có link/hết hạn), `/sitemap.xml`, `/robots.txt`,
`/health` (JSON), `/media/*`, `/static/*` (FE sở hữu `static/`).

---

## 4. Admin – biến có ở mọi trang (trừ login)

| Biến | Kiểu |
|---|---|
| `user` | `{"id", "email", "role", "is_admin": bool}` |
| `csrf_token` | str – đưa vào mọi form POST |
| `nav` | `list[{"label": str|None, "links": list[{"id","label","url","count": int|None,"active": bool}]}]` – 5 nhóm: (không tên) Tổng quan · Dữ liệu (Bonus, Sàn, Bài viết, Quảng cáo) · Nội dung (Trang chủ, Trang, Thư viện ảnh) · Khách (Người đăng ký = số đã xác nhận, Tin nhắn = số chưa đọc) · Hệ thống (Cài đặt). Ẩn mục `settings` khi `not user.is_admin` (editor bị 403). |
| `active_nav` | id mục đang mở |
| `title` | tiêu đề trang |
| `subtabs` | `list[{"id","label","url","active"}]` (rỗng nếu trang không có tab con) |
| `drawer` | xem 4.1, None nếu đóng |
| `media_library` | xem 0.4 (rỗng nếu trang không cần) |
| `flash` | xem 0.1 |

Đăng xuất: `<form method="post" action="/admin/logout">` + csrf. Mọi trang admin có `<meta name="robots" content="noindex, nofollow">`
(server cũng gửi header `X-Robots-Tag`). Không đăng nhập → 303 về `/admin/login?next=...`.

### 4.1 Drawer (form thêm/sửa ở Bonus, Sàn, Quảng cáo, Bài viết)

Mở bằng URL (không cần JS): `GET /admin/<nhóm>/new` hoặc `GET /admin/<nhóm>/{id}/edit` render **cùng template danh
sách** với `drawer` khác None. Nút đóng = link về `/admin/<nhóm>`.
```
drawer = {"title": str ("Thêm bonus"/"Sửa bonus"...), "action": str (URL POST),
          "data": dict (giá trị trường), "errors": dict, "is_new": bool,
          "delete_url": str|None (form POST riêng, có csrf; None khi thêm mới),
          "view_url": str|None ("Xem trên site ↗")}
```
Lưu thành công → 303 về danh sách + flash `created`/`saved`. Lỗi → 400, drawer mở lại với `data` vừa nhập.
Khi so sánh id trong `<select>` dùng `{{ x.id|string == drawer.data.broker_id|string }}` (sau lỗi giá trị là chuỗi).

### 4.2 Nút bật/tắt (công tắc tròn)

Mỗi công tắc là một form nhỏ: `<form method="post" action="{{ row.toggle_url }}">` + csrf + (nếu có) `field`,
+ `<input type="hidden" name="back" value="{{ request.url.path }}?{{ request.url.query }}">` để quay về đúng tab/lọc
(áp dụng Bonus, Sàn, Bài viết, Quảng cáo). Redirect 303 + flash `toggled`.

---

## 5. Admin – từng màn

### `GET /admin/login` → `admin/login.html` (cũng render lại khi đăng nhập lỗi)
| `csrf_token` | str |
| `next` | str (đường dẫn admin để quay lại) |
| `email` | str (giữ lại khi lỗi) |
| `error` | str\|None (sai mật khẩu 401, quá 5 lần/15 phút 429, hết phiên form 403) |
| `action` | `/admin/login` |
| `flash` | (`logged_out`) |
Form: `POST /admin/login` – `email`, `password`, `csrf_token`, `next`. Không có biến `nav/user`.

### `GET /admin` → `admin/overview.html` (Tổng quan, số thật từ DB)
| `stats` | `list[{"id","label","value": str}]` – id: `bonus` (“3/8”), `banners`, `ad_clicks` (30 ngày), `broker_clicks` (30 ngày), `subscribers` (đã xác nhận) |
| `expiring` | `list[Bonus]` – đang hiển thị, hết hạn trong ≤ 14 ngày (sớm nhất trước) |
| `click_days` | `list[{"day": date, "clicks": int, "percent": int 0–100}]` – 30 ngày, click affiliate + quảng cáo; cột cuối = hôm nay |
| `click_total` | int |
| `top_brokers` | `list[{"id","name","clicks"}]` (≤ 5, click tích lũy) |
| `unread_messages` | int |

### `/admin/bonus?tab=all|on|off|exp&type=&q=` → `admin/bonus.html`
| `subtabs` | Tất cả / Đang hiển thị / Đã ẩn / Sắp hết hạn |
| `current_tab`, `current_type`, `q` | str |
| `type_filters` | `list[{"id","label"}]` (all + 5 loại) – link `/admin/bonus?tab={{current_tab}}&type={{id}}&q={{q}}` |
| `bonuses` | `list[Bonus + {"is_active", "expired", "broker_active", "visible": bool, "edit_url", "toggle_url", "delete_url"}]` |
| `broker_options` | `list[{"id","name","is_active"}]` |
| `type_options` | `list[{"id","label"}]` |
| `add_url`, `add_label` | `/admin/bonus/new`, “Thêm bonus” |
| `drawer` | 4.1 |
Tìm kiếm: `<form method="get">` với `q` (+ giữ `tab`, `type` bằng hidden).
Form drawer (`POST drawer.action`): `broker_id` (select), `type` (pill/radio), `title`*, `amount`, `value_num`
(số để sort, có thể trống), `min_deposit`, `withdrawable`, `expiry_date` (`<input type=date>`, trống = Liên tục),
`is_active` (checkbox value=1). Khóa `drawer.data` trùng tên trường. Toggle: `POST /admin/bonus/{id}/toggle`. Xóa: `POST /admin/bonus/{id}/delete`.

### `/admin/brokers?tab=list|links` → `admin/brokers.html`
| `subtabs` | Danh sách / Link affiliate |
| `brokers` | `list[{"id","slug","name","mono","kind","license","min_deposit","leverage","platforms","affiliate_url","logo_path","in_compare","featured","is_active","clicks","clicks_30d","bonus_count","view_url","edit_url","toggle_url","link_url","delete_url"}]` |
| `compare_count`, `max_compare` | int, 3 – hiện “2/3 sàn so sánh” |
| `kind_options` | `list[{"id","label"}]` |
| `add_url`, `add_label`, `drawer`, `media_library` (khi drawer mở) | |
Công tắc: `POST {{ k.toggle_url }}` với `field` = `is_active` | `in_compare` | `featured`.
Bật so sánh khi đã đủ 3 → flash `compare_limit`. Bật nổi bật → tự tắt nổi bật ở sàn khác (tối đa 1).
Tab Link affiliate: mỗi dòng `<form method="post" action="{{ k.link_url }}">` với `affiliate_url` + csrf; cột Click = `clicks` (tổng), `clicks_30d`.
Form drawer: `name`*, `slug` (trống = tự tạo từ tên), `mono` (trống = tự lấy 2 ký tự), `kind`, `tagline`, `summary` (textarea),
`license`, `min_deposit`, `leverage`, `platforms`, `spread`, `withdrawal`, `founded`, `affiliate_url` (http/https),
`logo_path` + `logo_path_file` (0.4), `pros` (textarea, mỗi dòng 1 ý), `cons` (như pros),
tài khoản: các trường lặp cùng thứ tự `account_name`, `account_min_deposit`, `account_spread`, `account_commission`
(một dòng = 4 input; dòng trống bị bỏ),
nạp/rút: `payment_method`, `payment_deposit`, `payment_withdraw`, `payment_time` (lặp như trên),
`in_compare`, `featured`, `is_active` (checkbox value=1).
`drawer.data.pros/cons` là `list[str]` (in vào textarea bằng `|join('\n')`), `accounts`/`payment_methods` là list dict
như mục 2.2. Lỗi có thể ở: `name, slug, kind, affiliate_url, in_compare, logo_path`.

### `/admin/ads?tab=banner|stats` → `admin/ads.html`
| `subtabs` | Banner / Thống kê |
| `banners` | `list[{"id","name","image_path","placement","target_url","broker": {"id","name"}|None,"start_date": date|None,"end_date": date|None,"is_active","state","views","clicks","edit_url","toggle_url","delete_url"}]` – `state|banner_state_label`, CTR = `ctr(b.clicks, b.views)` |
| `totals` | `{"views", "clicks"}` |
| `ad_click_days` | như `click_days` nhưng chỉ click quảng cáo |
| `broker_options`, `placement_options` (`list[{"id","label"}]`) | |
| `add_url`, `add_label`, `drawer`, `media_library` (khi drawer mở) | |
Form drawer: `name`*, `broker_id` (select, có lựa chọn rỗng), `placement`*, `target_url` (http/https; trống = dùng link
affiliate của sàn), `image_path` + `image_path_file`, `start_date`, `end_date` (`type=date`), `is_active`.
Lỗi: `name, broker_id, placement, target_url, start_date, end_date, image_path`.

### `/admin/posts?tab=all|pub|draft&q=` → `admin/posts.html`
| `posts` | `list[Post + {"status","show_home","view_url": str|None,"edit_url","toggle_url","delete_url"}]` |
| `category_options` | `list[str]` |
| `q`, `current_tab`, `add_url`, `add_label`, `drawer`, `media_library` (khi drawer mở) | |
Công tắc “Trang chủ” = `POST toggle_url` (bật/tắt `show_home`).
Form drawer: `title`*, `slug`, `category`, `excerpt` (textarea), `body_md` (textarea Markdown), `cover_path` + `cover_path_file`,
`status` (`draft`|`published`), `published_at` (`type=date`; trống + đăng → lấy giờ hiện tại), `show_home`.
Số phút đọc tự tính. Lỗi: `title, slug, category, status, published_at, cover_path`.

### `/admin/home?tab=sections|hero|about|why|types|contact|menu` → `admin/home.html` (Nội dung trang chủ)
| `settings` | dict = toàn bộ `site` (mục 2.1) – đọc giá trị hiện tại từ đây |
| `sections` | `list[{"id","label","on","n": "01","toggle_url","move_url","first": bool,"last": bool}]` |
| `form` | `{"action": "/admin/home/<tab>", "data": dict (chỉ có khi lỗi), "errors": dict}` |
| `view_url` | link “Xem trên site ↗” |
| `media_library` | luôn có |
Mọi form tab là `POST {{ form.action }}` + csrf + `enctype="multipart/form-data"`. Trường theo tab:
- **sections**: công tắc từng dòng `POST s.toggle_url`; lên/xuống `POST s.move_url` với `direction=up|down`
  (ẩn nút up khi `first`, down khi `last`). Thêm form tiêu đề section: `bonus_eyebrow`, `bonus_title`,
  `compare_eyebrow`, `compare_title`, `blog_eyebrow`, `blog_title` (→ `settings.home_bonus/home_compare/home_blog`).
- **hero**: `eyebrow`, `headline`, `sub` (textarea), `cta`, `image_path` + `image_path_file`.
- **about**: `eyebrow`, `title`, `text`, `badge`, `count_label`, điểm nổi bật lặp `point_title` + `point_text`,
  ảnh `image_0`, `image_1`, `image_2` (+ `_file`).
- **why**: `eyebrow`, `title`, `text`, `stat_value`, `stat_label`, lý do lặp `reason_title` + `reason_text`, ảnh `image_0`, `image_1`.
- **types**: `eyebrow`, `title`, `image` (+ `image_file`); với mỗi loại `id` trong `settings.bonus_types`:
  `<id>_short`, `<id>_label`, `<id>_desc`, `<id>_points` (textarea, mỗi dòng 1 ý). Không thêm/xóa loại.
- **contact**: `eyebrow`, `title`, `text`, `success_title`, `success_text`, `image` (+ `image_file`).
- **menu**: menu lặp `menu_label` + `menu_url`; footer: `about_text`, `risk_note`, `copyright`; mỗi cột footer:
  `footer_col_title` + `footer_col_links` (textarea, mỗi dòng `Nhãn | /url`), lặp theo số cột.
  Link hợp lệ: `/đường-dẫn` (không khoảng trắng), `http(s)://`, `mailto:`, `#neo`. Lỗi: `menu`, `footer_col_links`.

### `/admin/pages?tab=bonus|san|tin|gioithieu|lienhe|terms|privacy` → `admin/pages.html` (Trang)
| `settings` | dict = `site` |
| `form` | `{"action": "/admin/pages/<tab>", "errors": dict}` |
| `view_url` | URL public của trang |
| `about_tabs` | `list[{"id","label"}]` – 3 khối của trang Giới thiệu |
| `media_library` | luôn có |
Trường chung: `title`*, `desc`, `meta_title`, `meta_desc` (giá trị hiện tại: `settings.pages[current_tab]`).
Thêm theo tab:
- **gioithieu**: với mỗi `t` trong `about_tabs`: `<t>_image` (+ `_file`), khối lặp `<t>_block_title` + `<t>_block_text`
  (hiện tại: `settings.about_blocks[t]`).
- **lienhe**: `intro`, `topics` (textarea, mỗi dòng 1 chủ đề), `response_note`, `success_text` (`settings.contact_page`).
- **terms** / **privacy**: `body_md` (Markdown; hiện tại `settings.legal.terms_md` / `privacy_md`).

### `/admin/media?q=` → `admin/media.html` (Thư viện ảnh)
| `media` | `list[{"id","path","alt","width","height","size": int bytes,"created_at","in_use": bool,"edit_url","delete_url"}]` |
| `q` | str (tìm theo alt) |
| `upload_action` | `/admin/media/upload` |
| `errors` | dict (`files`) – lỗi upload, HTTP 400 |
Upload: `POST upload_action`, multipart, `files` (`<input type=file multiple>`), `alt`. Sửa alt: `POST edit_url` với `alt`.
Xóa: `POST delete_url` (bị chặn khi `in_use`, flash `media_in_use` – nên disable nút). “Copy link” = `path` (JS phía FE).

### `/admin/subscribers?tab=list|mail&status=&q=&aud=` → `admin/subscribers.html`
| `subtabs` | Danh sách / Gửi email |
| `status_filters` | `list[{"id","label","count","url","active"}]` – Tất cả / Đã xác nhận / Chờ xác nhận / Đã hủy |
| `subscribers` | `list[{"id","name","email","interests": list[str],"interest_labels": list[str],"status","created_at","confirmed_at","delete_url"}]` (chỉ có ở tab list) |
| `current_status`, `q` | |
| `audience_options` | `list[{"id","label","selected": bool,"count": int}]` – pill chọn nhóm nhận |
| `audience_count` | int – số người nhận theo lựa chọn hiện tại (đổi lựa chọn: link/GET `?tab=mail&aud=deposit&aud=cashback`) |
| `mail_form` | `{"action": "/admin/subscribers/mail", "subject", "body", "audience": list[str], "errors": dict}` |
| `campaigns` | `list[{"id","subject","audience_labels","status": "draft"|"sending"|"sent","sent_count","sent_at","created_at"}]` (20 gần nhất) |
Gửi: `POST mail_form.action` – `subject`*, `body`* (văn bản thuần), `audience` (checkbox lặp; trống = tất cả),
`action` = `send` | `draft` (hai nút submit cùng name). Chỉ gửi người **đã xác nhận**; mỗi email tự kèm link hủy.
Xóa người đăng ký: `POST delete_url`.

### `/admin/messages?tab=all|unread` và `/admin/messages/{id}` → `admin/messages.html` (Tin nhắn)
| `messages` | `list[{"id","topic","name","email","body","is_read","created_at","open_url","toggle_url","delete_url"}]` |
| `selected` | message dict\|None – mở bằng `GET open_url` (drawer xem chi tiết, tự đánh dấu đã đọc) |
Công tắc đã đọc/chưa đọc: `POST toggle_url`. Xóa: `POST delete_url`. Trả lời: `mailto:{{ m.email }}`.

### `/admin/settings?tab=general|seo|social|tracking|users` → `admin/settings.html` (chỉ role admin)
| `settings` | dict = `site` |
| `form` | `{"action": "/admin/settings/<tab>", "errors": dict}` |
| `users` | (tab users) `list[{"id","email","role","is_active","last_login_at","is_self","edit_url","toggle_url","delete_url"}]` |
| `role_options` | `list[{"id","label"}]` |
| `user_create_action` | `/admin/settings/users/new` |
| `media_library` | chỉ ở tab general |
Trường:
- **general**: `site_name`*, `contact_email`, `partner_email`, `telegram`, `logo_path` (+`_file`), `favicon_path` (+`_file`)
  (hiện tại ở `settings.branding`).
- **seo**: `meta_title`, `meta_desc`, `meta_keywords`, `og_image` (+`_file`).
- **social**: lặp `social_label` + `social_url` (http/https).
- **tracking**: `analytics_head` (textarea HTML, ví dụ đoạn gtag).
- **users**: thêm `POST user_create_action` – `email`, `password` (≥ 10 ký tự), `role`;
  sửa `POST u.edit_url` – `role` và/hoặc `password` (trống = giữ); khóa/mở `POST u.toggle_url`; xóa `POST u.delete_url`.
  Với `is_self`: ẩn khóa/xóa (server trả flash `self_delete`) và không cho tự hạ quyền.

---

## 6. Ghi chú hành vi để FE không phải đọc code

- Bonus hết hạn (ngày < hôm nay giờ VN) tự biến khỏi public; sàn tắt → bonus của sàn cũng ẩn, trang sàn 404.
- Banner chỉ hiện khi bật **và** hôm nay nằm trong [start_date, end_date] (trống = không giới hạn).
- Mỗi lần trang chủ render một banner, `views` +1; click qua `/go/ad/{id}` → `clicks` +1.
- Chạy local cho FE: đặt `APP_ENV=development` (mặc định là production, cần `SECRET_KEY`), `PORT=8011`/`8012`,
  `DATABASE_URL=sqlite:///<thư mục tạm>/fe.db`, `UPLOAD_DIR=<thư mục tạm>/up`, rồi `python run.py`.
  Tạo tài khoản: `python -m app.cli create-admin --email ban@example.test`.
- Các file stub do backend tạo: `templates/public/{home,bonus_list,broker_list,broker_compare,broker_detail,post_list,
  post_detail,about,contact,legal,subscription,404,500}.html`, `templates/admin/{login,overview,bonus,brokers,ads,posts,
  home,pages,media,subscribers,messages,settings}.html`. Test backend kiểm tra **context** (không kiểm tra markup),
  nên FE ghi đè thoải mái; chỉ cần giữ đúng tên file và template render không lỗi với context trong tài liệu này
  (test render mọi trang với DB rỗng và có dữ liệu – template lỗi Jinja sẽ làm test đỏ).
