# Visual Editor — Todo & Progress

## Mục tiêu
Admin vào trang `/admin/visual-editor` → thấy trang chủ public trong iframe → click vào text để sửa trực tiếp → nhấn "Lưu" → thay đổi được ghi vào DB.

---

## Kiến trúc

```
admin.tradingbonushub.com/admin/visual-editor
  └── hiển thị iframe trỏ tới:
        /admin/public-edit-mode?page=home
          └── render templates/public/index.html với edit_mode=True
                └── inject /static/js/public-inline-editor.js
                      └── click text → contenteditable → Save → PUT /api/page-content/bulk
```

---

## Đã làm ✅

### 1. `/static/js/public-inline-editor.js` — TẠO MỚI ✅
- Floating toolbar "EDIT MODE" ở đầu trang
- Click vào element có `data-edit-field` → `contenteditable=true`
- Hover highlight (outline xanh)
- Escape / Enter blur để kết thúc chỉnh sửa
- Theo dõi số trường đã thay đổi (dirty count)
- Nút "Lưu thay đổi" → `PUT /api/page-content/bulk`
- Nút "Thoát" → redirect về `/admin/visual-editor`
- postMessage cho giao tiếp iframe ↔ parent

### 2. `templates/admin/visual_editor.html` — TẠO MỚI ✅
- Extends `base.html` (admin layout)
- Toolbar: tab chọn trang (Trang chủ / About / Blog), nút Lưu, nút Xem trang ↗, nút Reload
- Iframe trỏ `/admin/public-edit-mode?page=home`
- JS nhận postMessage từ iframe (`efSaved`, `efExit`, `efDirty`)

### 3. `app/views/admin.py` — CHỈNH SỬA ✅
- Thêm `public_tpl = Jinja2Templates(directory="templates/public")`
- Thêm route `/admin/visual-editor` → render `visual_editor.html`
- Thêm route `/admin/public-edit-mode?page=home` → render `public/index.html` với `edit_mode=True` + đầy đủ context data (pc, ps, brokers, promotions, faq, etc.)

### 4. `templates/admin/base.html` — CHỈNH SỬA ✅
- Thêm link "✏️ Visual Editor" vào sidebar nav (sau "🎨 Giao diện")

### 5. `templates/public/index.html` — CHỈNH SỬA ✅
- Hero section: `hero_eyebrow`, `hero_title_line1`, `hero_title_accent`, `hero_sub`, `hero_hl1-4`, `hero_btn_primary`, `hero_btn_secondary`
- Broker marquee: `marquee_label`
- Benefits section: `benefits_tag`, `benefits_title`, `benefits_sub`, `b1-4_icon/title/big/desc`
- Calculator section: `calc_tag`, `calc_title`, `calc_sub`
- Leaderboard section: `lb_tag`, `lb_title`, `lb_sub`
- Inject `public-inline-editor.js` ở cuối `</body>` khi `edit_mode=True`

### 6. `app/api/page_content.py` — CHỈNH SỬA ✅
- Thêm `_require_admin(request)` check vào `PUT /api/page-content` và `PUT /api/page-content/bulk`
- Chỉ admin đã login mới được ghi content

---

## Chưa làm / Cần kiểm tra ❌

### QUAN TRỌNG — Cần test ngay:
- [ ] **Khởi động app và truy cập `/admin/visual-editor`** — kiểm tra iframe load được không
- [ ] **Click vào text trong iframe** — kiểm tra `data-edit-field` hoạt động
- [ ] **Lưu thay đổi** — kiểm tra `PUT /api/page-content/bulk` nhận session admin đúng không
- [ ] **Dirty count postMessage** — JS trong iframe hiện chưa gửi `efDirty` lên parent → nút Save trên toolbar admin không sáng

### Bug đã biết:
- [x] **`efDirty` postMessage** — đã fix trong `markChanged()` của `public-inline-editor.js`
- [x] **Tab "About" và "Blog"** — đã fix route `public-edit-mode` switch theo `page` param (about → about.html, blog → blog.html, default → index.html)

### Mở rộng sau:
- [ ] Thêm các trang khác: `/about`, `/blog`, `/brokers`
- [ ] Editable fields cho leaderboard rows (lb_r1-7 name/vol/reward)
- [ ] Editable fields cho FAQ section
- [ ] Editable fields cho CTA section (nếu có)
- [ ] Hỗ trợ edit hình ảnh (upload ảnh trực tiếp từ visual editor)
- [ ] Hiển thị "xem trước trên thiết bị di động" (responsive preview)

---

## Files đã thay đổi

| File | Trạng thái |
|------|-----------|
| `static/js/public-inline-editor.js` | Tạo mới |
| `templates/admin/visual_editor.html` | Tạo mới |
| `app/views/admin.py` | Chỉnh sửa (thêm 2 routes + public_tpl) |
| `templates/admin/base.html` | Chỉnh sửa (thêm nav link) |
| `templates/public/index.html` | Chỉnh sửa (data-edit-field + inject JS) |
| `app/api/page_content.py` | Chỉnh sửa (thêm auth check) |

---

## Cách test nhanh

1. Khởi động server: `docker-compose up` hoặc `python run.py`
2. Vào `http://localhost/admin/` → đăng nhập
3. Click sidebar "✏️ Visual Editor"
4. Trang chủ hiện ra trong iframe
5. Click vào text (hero title, benefits, etc.) → sửa → Lưu
6. Reload trang chủ bình thường → xem thay đổi

---

## Fix ưu tiên tiếp theo (phiên làm việc sau)

1. **Test end-to-end** — chạy app, kiểm tra save hoạt động
2. **Thêm `data-edit-field` cho about.html** — hiện tại trang About chưa có field nào có thể edit
3. **Thêm các trang khác** theo mục "Mở rộng sau"
