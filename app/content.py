"""Nội dung site lưu trong bảng Setting.

Giá trị mặc định là chữ tĩnh lấy từ thiết kế (không phải dữ liệu mock): tên sàn, số liệu,
email demo đều đã bỏ. Admin sửa được mọi khóa; khóa chưa lưu thì dùng mặc định.
"""
import copy
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting

PAGE_KEYS = ("bonus", "san", "compare", "tin", "gioithieu", "method", "affiliate", "lienhe", "terms", "privacy")
ABOUT_TABS = ("about", "method", "affiliate")

# Bản nháp theo đúng những gì site đang làm. Chủ site cần đọc lại trước khi lên public; sửa ở Trang › Điều khoản, Bảo mật.
TERMS_MD = """## Về trang này

Trang này tổng hợp và so sánh thông tin về bonus của các sàn giao dịch forex và crypto. Nội dung chỉ để tham khảo, không phải lời khuyên đầu tư, tài chính hay pháp lý.

## Thông tin có thể thay đổi

Điều kiện bonus do từng sàn đặt ra và có thể thay đổi bất cứ lúc nào. Thông tin trên trang có thể chưa kịp cập nhật. Hãy kiểm tra trang chính thức của sàn trước khi nạp tiền hoặc nhận ưu đãi.

## Rủi ro

CFD và crypto là sản phẩm có rủi ro cao, bạn có thể mất tiền nhanh do đòn bẩy và biến động giá. Bạn tự chịu trách nhiệm về quyết định giao dịch của mình.

## Liên kết affiliate và quảng cáo

Một số liên kết trên trang là liên kết affiliate: khi bạn mở tài khoản qua các liên kết này, sàn có thể trả hoa hồng cho chúng tôi. Nội dung tài trợ có nhãn "Tài trợ". Khi bấm vào, bạn rời khỏi trang này và chịu điều khoản của trang đích.

## Email và form

Bạn chỉ nhận email sau khi đã xác nhận địa chỉ. Mỗi email có liên kết hủy đăng ký. Không dùng form của trang để gửi nội dung vi phạm pháp luật hoặc gửi thư rác.

## Thay đổi điều khoản

Điều khoản này có thể được cập nhật. Bản đang hiển thị trên trang là bản có hiệu lực.
"""

PRIVACY_MD = """## Dữ liệu chúng tôi thu thập

- **Đăng ký nhận email:** tên (nếu bạn nhập), địa chỉ email, loại ưu đãi bạn chọn, trạng thái xác nhận và thời điểm đăng ký.
- **Form liên hệ:** chủ đề, tên (nếu bạn nhập), địa chỉ email và nội dung tin nhắn.
- **Thống kê click:** số lượt bấm liên kết sàn và quảng cáo được đếm theo ngày. Số liệu này không gắn với danh tính hay địa chỉ IP của bạn.

Địa chỉ IP được dùng tạm trong bộ nhớ của máy chủ để giới hạn số lần gửi form và chống lạm dụng, không lưu vào cơ sở dữ liệu.

## Mục đích sử dụng

Chúng tôi dùng email đăng ký để gửi thông tin về ưu đãi theo lựa chọn của bạn, và dùng thông tin trong form liên hệ để trả lời bạn. Chúng tôi không bán dữ liệu của bạn.

## Cookie

Trang dùng cookie kỹ thuật ngắn hạn để hiện thông báo sau khi gửi form. Khu quản trị dùng cookie phiên đăng nhập, chỉ dành cho quản trị viên. Trang không dùng cookie quảng cáo của riêng mình.

## Dịch vụ bên thứ ba

- Font chữ tải từ Google Fonts, nên Google có thể nhận địa chỉ IP của bạn khi tải trang.
- Email được gửi qua nhà cung cấp dịch vụ email.
- Lưu lượng truy cập đi qua dịch vụ hạ tầng mạng của bên thứ ba.
- Khi bấm liên kết sàn hoặc quảng cáo, bạn chuyển sang trang của bên đó và chịu chính sách riêng của họ. Liên kết affiliate có thể chứa mã giới thiệu của chúng tôi.
- Nếu quản trị viên bật công cụ đo lường truy cập, công cụ đó có thể đặt cookie riêng.

## Quyền của bạn

Bạn có thể hủy nhận email bất cứ lúc nào qua liên kết trong email. Để yêu cầu xóa dữ liệu của bạn, hãy gửi yêu cầu qua trang [Liên hệ](/lien-he). Dữ liệu được giữ cho đến khi bạn yêu cầu xóa hoặc quản trị viên xóa.
"""

SYSTEM_TEXT_LABELS = {
    "header_cta_home": "Nút header ở trang chủ",
    "header_cta_page": "Nút header ở trang con",
    "not_found_title": "Trang 404: tiêu đề",
    "not_found_text": "Trang 404: mô tả",
    "error_title": "Trang lỗi 500: tiêu đề",
    "error_text": "Trang lỗi 500: mô tả",
    "sub_ask_confirm_title": "Xác nhận đăng ký: tiêu đề",
    "sub_ask_confirm_text": "Xác nhận đăng ký: mô tả",
    "sub_ask_confirm_button": "Xác nhận đăng ký: nút",
    "sub_confirmed_title": "Đã xác nhận: tiêu đề",
    "sub_confirmed_text": "Đã xác nhận: mô tả",
    "sub_ask_unsubscribe_title": "Hủy đăng ký: tiêu đề",
    "sub_ask_unsubscribe_text": "Hủy đăng ký: mô tả",
    "sub_ask_unsubscribe_button": "Hủy đăng ký: nút",
    "sub_unsubscribed_title": "Đã hủy: tiêu đề",
    "sub_unsubscribed_text": "Đã hủy: mô tả",
    "sub_invalid_title": "Liên kết sai: tiêu đề",
    "sub_invalid_text": "Liên kết sai: mô tả",
}

DEFAULTS: dict = {
    "site_name": "TradingBonusHub",
    "contact_email": "",
    "partner_email": "",
    "telegram": "",
    "meta_title": "TradingBonusHub – So sánh bonus sàn forex & crypto",
    "meta_desc": "Tổng hợp no-deposit, deposit bonus, cashback và cuộc thi giao dịch từ các sàn có giấy phép.",
    "meta_keywords": "bonus forex, no deposit bonus, cashback forex",
    "branding": {"logo_path": "/static/img/logo.png", "favicon_path": "/static/img/logo.png", "og_image": ""},
    "social": [],  # [{label, url}]
    "analytics_head": "",
    "hero": {
        "eyebrow": "Bonus Forex & Crypto",
        "headline": "Tổng hợp bonus sàn giao dịch, điều kiện rõ ràng",
        "sub": "So sánh no-deposit, deposit bonus, cashback, cuộc thi giao dịch và khuyến mãi crypto từ các sàn có giấy phép. Mỗi ưu đãi ghi rõ mức nạp tối thiểu, phần rút được và thời hạn.",
        "cta": "Xem tất cả bonus",
        "image_path": "",
        "card_label": "Nổi bật",
    },
    "sections": [
        {"id": "hero", "label": "Hero", "on": True},
        {"id": "about", "label": "Về chúng tôi", "on": True},
        {"id": "bonus", "label": "Bonus mới nhất", "on": True},
        {"id": "ad1", "label": "Quảng cáo #1", "on": True},
        {"id": "why", "label": "Tại sao chọn", "on": True},
        {"id": "types", "label": "Loại bonus", "on": True},
        {"id": "compare", "label": "So sánh 3 sàn", "on": True},
        {"id": "signup", "label": "Form đăng ký", "on": True},
        {"id": "ad2", "label": "Quảng cáo #2", "on": True},
        {"id": "blog", "label": "Tin tức", "on": True},
    ],
    "menu": [
        {"label": "Trang chủ", "url": "/"},
        {"label": "Bonus", "url": "/bonus"},
        {"label": "Sàn", "url": "/san"},
        {"label": "Tin tức", "url": "/tin-tuc"},
        {"label": "Giới thiệu", "url": "/gioi-thieu"},
        {"label": "Liên hệ", "url": "/lien-he"},
    ],
    "footer": {
        "about_text": "Trang tổng hợp và so sánh bonus từ các sàn forex & crypto. Một số liên kết là liên kết affiliate; chúng tôi có thể nhận hoa hồng mà không làm thay đổi điều kiện bạn nhận được.",
        "columns": [
            {"title": "Bonus", "links": [
                {"label": "No-deposit", "url": "/bonus?type=nodep"},
                {"label": "Deposit bonus", "url": "/bonus?type=deposit"},
                {"label": "Cashback", "url": "/bonus?type=cashback"},
                {"label": "Cuộc thi", "url": "/bonus?type=contest"},
                {"label": "Crypto", "url": "/bonus?type=crypto"},
            ]},
            {"title": "Liên kết", "links": [
                {"label": "So sánh sàn", "url": "/san/so-sanh"},
                {"label": "Tin tức", "url": "/tin-tuc"},
                {"label": "Giới thiệu", "url": "/gioi-thieu"},
                {"label": "Liên hệ", "url": "/lien-he"},
                {"label": "Điều khoản", "url": "/dieu-khoan"},
                {"label": "Bảo mật", "url": "/bao-mat"},
            ]},
        ],
        "risk_note": "Cảnh báo rủi ro: CFD là công cụ phức tạp và có rủi ro mất tiền nhanh do đòn bẩy. Bonus không phải lời khuyên đầu tư.",
        "copyright": "Copyright © {year} TradingBonusHub.",  # {year} được thay ở public
        "affiliate_note": "Một số liên kết là liên kết affiliate.",
    },
    "cta_note": "Liên kết affiliate. CFD có rủi ro mất vốn cao do đòn bẩy.",  # dưới nút mở tài khoản
    "ads_note": "CFD có rủi ro mất vốn cao.",  # dưới nút trong quảng cáo dọc
    "system_text": {
        "header_cta_home": "Xem bonus",
        "header_cta_page": "Xem bonus",
        "not_found_title": "Không tìm thấy trang",
        "not_found_text": "Trang bạn tìm không tồn tại hoặc đã được gỡ.",
        "error_title": "Đã có lỗi xảy ra",
        "error_text": "Hệ thống đang gặp sự cố. Vui lòng thử lại sau ít phút.",
        "sub_confirmed_title": "Đã xác nhận đăng ký",
        "sub_confirmed_text": "Email của bạn đã được xác nhận. Chúng tôi có thể gửi cho bạn email về ưu đãi mới; mỗi email đều có liên kết hủy đăng ký.",
        "sub_unsubscribed_title": "Đã hủy đăng ký",
        "sub_unsubscribed_text": "Bạn sẽ không nhận thêm email thông báo bonus.",
        "sub_invalid_title": "Liên kết không hợp lệ",
        "sub_invalid_text": "Liên kết đã hết hạn hoặc không đúng.",
        "sub_ask_confirm_title": "Xác nhận đăng ký",
        "sub_ask_confirm_text": "Bấm nút bên dưới để xác nhận nhận email về ưu đãi. Nếu bạn không đăng ký, hãy đóng trang này.",
        "sub_ask_confirm_button": "Xác nhận đăng ký",
        "sub_ask_unsubscribe_title": "Hủy đăng ký",
        "sub_ask_unsubscribe_text": "Bấm nút bên dưới để ngừng nhận email từ chúng tôi.",
        "sub_ask_unsubscribe_button": "Hủy đăng ký",
    },
    "pages": {
        "bonus": {"label": "Bonus", "title": "Tất cả bonus sàn giao dịch", "desc": "Lọc theo loại ưu đãi. Mỗi bonus ghi rõ mức nạp tối thiểu, phần rút được và thời hạn.", "meta_title": "", "meta_desc": ""},
        "san": {"label": "Sàn", "title": "Sàn giao dịch uy tín", "desc": "Thông tin giấy phép, tài khoản, phí và phương thức nạp rút của từng sàn.", "meta_title": "", "meta_desc": ""},
        "tin": {"label": "Tin tức", "title": "Tin tức & hướng dẫn", "desc": "Giải thích điều khoản bonus, so sánh sàn và cập nhật chương trình mới.", "meta_title": "", "meta_desc": ""},
        "gioithieu": {"label": "Giới thiệu", "title": "Về TradingBonusHub", "desc": "Chúng tôi tổng hợp bonus từ các sàn có giấy phép và tóm tắt điều khoản bằng tiếng Việt.", "meta_title": "", "meta_desc": ""},
        "lienhe": {"label": "Liên hệ", "title": "Liên hệ", "desc": "Gửi câu hỏi, báo lỗi thông tin bonus hoặc đề nghị hợp tác.", "meta_title": "", "meta_desc": ""},
        "compare": {"label": "So sánh", "title": "So sánh sàn giao dịch", "desc": "So sánh giấy phép, mức nạp, đòn bẩy, phí và bonus của tối đa 3 sàn.", "meta_title": "", "meta_desc": ""},
        "method": {"label": "Cách đánh giá", "title": "Cách chúng tôi đánh giá", "desc": "Các tiêu chí chúng tôi dùng khi tóm tắt bonus và thông tin sàn giao dịch.", "meta_title": "", "meta_desc": ""},
        "affiliate": {"label": "Công bố affiliate", "title": "Công bố affiliate", "desc": "Cách trang này có thu nhập và điều đó ảnh hưởng đến bạn thế nào.", "meta_title": "", "meta_desc": ""},
        "terms": {"label": "Điều khoản", "title": "Điều khoản sử dụng", "desc": "", "meta_title": "", "meta_desc": ""},
        "privacy": {"label": "Bảo mật", "title": "Chính sách bảo mật", "desc": "", "meta_title": "", "meta_desc": ""},
        "system": {"title": "Chữ hệ thống", "desc": "", "meta_title": "", "meta_desc": ""},  # tab admin, không phải trang public
    },
    "home_about": {
        "eyebrow": "Về TradingBonusHub",
        "title": "Giúp trader chọn đúng bonus, hiểu rõ trước khi nhận",
        "text": "Chúng tôi đọc điều khoản của từng chương trình và tóm tắt những gì trader cần biết: mức nạp tối thiểu, phần nào rút được và thời hạn.",
        "points": [{"title": "Chỉ sàn có giấy phép", "text": "Mỗi sàn đều ghi rõ cơ quan cấp phép để bạn tự đối chiếu."}],
        "badge": "",
        "count_label": "Ưu đãi đang hoạt động",
        "images": ["", "", ""],
    },
    "home_bonus": {"eyebrow": "Bonus mới nhất", "title": "Ưu đãi đang hoạt động từ các sàn đối tác"},
    "home_why": {
        "eyebrow": "Tại sao chọn chúng tôi",
        "title": "Bonus minh bạch, không chỉ là con số quảng cáo",
        "text": "Một khoản thưởng lớn chưa chắc có lợi. Chúng tôi chỉ ra phần nào rút được, mức nạp tối thiểu và thời hạn của ưu đãi.",
        "stat_value": "",
        "stat_label": "",
        "reasons": [
            {"title": "Tóm tắt điều khoản", "text": "Mức nạp tối thiểu, phần rút được và thời hạn hiển thị ngay trên mỗi ưu đãi."},
            {"title": "Chỉ sàn có giấy phép", "text": "Mỗi sàn được ghi rõ cơ quan cấp phép để bạn tự kiểm tra."},
            {"title": "Cập nhật khi ưu đãi thay đổi", "text": "Ưu đãi hết hạn được gỡ khỏi danh sách."},
        ],
        "images": ["", ""],
    },
    "home_types": {"eyebrow": "Loại ưu đãi", "title": "Hiểu từng loại bonus trước khi nhận", "image": ""},
    "home_compare": {"eyebrow": "So sánh sàn", "title": "Chọn sàn phù hợp với cách bạn giao dịch", "featured_label": "Nổi bật"},
    "home_contact": {
        "eyebrow": "Thông báo bonus",
        "title": "Nhận bonus mới qua email",
        "text": "Chọn loại ưu đãi bạn quan tâm.",
        "image": "",
        "success_title": "Đã đăng ký",
        "success_text": "Kiểm tra hộp thư để xác nhận email.",
    },
    "home_blog": {"eyebrow": "Tin tức mới nhất", "title": "Hướng dẫn dùng bonus hiệu quả"},
    "bonus_types": [
        {"id": "nodep", "short": "No-deposit", "label": "No-deposit bonus",
         "desc": "Sàn cấp một khoản tiền giao dịch khi bạn mở và xác minh tài khoản, không cần nạp tiền.",
         "points": ["Thường chỉ rút được phần lợi nhuận, không rút được tiền thưởng", "Có yêu cầu khối lượng lot tối thiểu", "Giới hạn theo quốc gia và một tài khoản mỗi người"]},
        {"id": "deposit", "short": "Deposit bonus", "label": "Deposit bonus",
         "desc": "Thưởng theo phần trăm số tiền nạp, giúp tăng ký quỹ khả dụng.",
         "points": ["Tiền thưởng có thể bị trừ khi rút tiền gốc", "Không dùng được để chịu lỗ ở một số sàn", "Kiểm tra mức thưởng tối đa và thời hạn"]},
        {"id": "cashback", "short": "Cashback", "label": "Cashback / rebate",
         "desc": "Hoàn lại một phần phí hoặc spread theo mỗi lot giao dịch.",
         "points": ["Thường rút được ngay", "Phù hợp trader có khối lượng đều đặn", "Tính theo lot đã đóng"]},
        {"id": "contest", "short": "Cuộc thi", "label": "Trading contest",
         "desc": "Cuộc thi xếp hạng theo lợi nhuận trên tài khoản demo hoặc thật.",
         "points": ["Đọc kỹ quy tắc tính điểm", "Giải thưởng có thể là tiền thưởng giao dịch", "Có thời gian đăng ký giới hạn"]},
        {"id": "crypto", "short": "Crypto", "label": "Khuyến mãi crypto",
         "desc": "Airdrop, thưởng đăng ký và nhiệm vụ trên sàn crypto.",
         "points": ["Thường cần KYC đầy đủ", "Phần thưởng có thể là voucher phí", "Biến động giá token ảnh hưởng giá trị thưởng"]},
    ],
    "about_blocks": {
        "about": {"image": "", "blocks": [
            {"title": "Chúng tôi làm gì", "text": "Đọc điều khoản của từng chương trình bonus và tóm tắt những gì trader cần biết trước khi nhận."},
            {"title": "Dành cho ai", "text": "Người mới cần hiểu bonus hoạt động thế nào, và trader có kinh nghiệm cần so sánh nhanh điều kiện."},
            {"title": "Cập nhật", "text": "Ưu đãi hết hạn được gỡ khỏi danh sách. Thay đổi điều khoản được ghi lại trong mục Tin sàn."},
        ]},
        "method": {"image": "", "blocks": [
            {"title": "Giấy phép", "text": "Chỉ liệt kê sàn có ít nhất một giấy phép từ cơ quan quản lý được công bố công khai."},
            {"title": "Điều kiện rút tiền", "text": "Ghi rõ phần nào rút được: tiền thưởng, lợi nhuận, hay chỉ dùng làm ký quỹ."},
            {"title": "Mức nạp và thời hạn", "text": "Ghi rõ mức nạp tối thiểu và thời hạn của từng ưu đãi để dễ so sánh giữa các sàn."},
        ]},
        "affiliate": {"image": "", "blocks": [
            {"title": "Cách chúng tôi có thu nhập", "text": "Một số liên kết trên trang là liên kết affiliate. Khi bạn mở tài khoản qua liên kết này, sàn có thể trả hoa hồng cho chúng tôi."},
            {"title": "Ảnh hưởng đến bạn", "text": "Hoa hồng không làm thay đổi điều kiện bonus bạn nhận được."},
            {"title": "Quảng cáo", "text": "Nội dung tài trợ luôn có nhãn \"Tài trợ\" hoặc \"Quảng cáo\"."},
        ]},
    },
    "contact_page": {
        "intro": "",
        "topics": ["Câu hỏi chung", "Báo lỗi thông tin bonus", "Hợp tác"],
        "response_note": "Chúng tôi sẽ trả lời qua email. Chúng tôi không tư vấn đầu tư cá nhân.",
        "success_title": "Đã gửi",
        "success_text": "Cảm ơn bạn. Chúng tôi sẽ trả lời qua email.",
    },
    "legal": {"terms_md": TERMS_MD, "privacy_md": PRIVACY_MD},
}


def _merge(default, stored):
    """Dict: trộn từng khóa (giữ khóa mới của mặc định). List/giá trị khác: dùng bản đã lưu."""
    if isinstance(default, dict) and isinstance(stored, dict):
        out = copy.deepcopy(default)
        for k, v in stored.items():
            out[k] = _merge(default[k], v) if k in default else v
        return out
    if stored is None:
        return copy.deepcopy(default)
    return stored


def _fix_sections(sections: list) -> list:
    known = {s["id"]: s for s in DEFAULTS["sections"]}
    out, seen = [], set()
    for s in sections:
        if isinstance(s, dict) and s.get("id") in known and s["id"] not in seen:
            seen.add(s["id"])
            out.append({"id": s["id"], "label": known[s["id"]]["label"], "on": bool(s.get("on", True))})
    out += [copy.deepcopy(s) for s in DEFAULTS["sections"] if s["id"] not in seen]
    return out


def _fix_bonus_types(types: list) -> list:
    stored = {t.get("id"): t for t in types if isinstance(t, dict)}
    return [_merge(d, stored.get(d["id"])) | {"id": d["id"]} for d in DEFAULTS["bonus_types"]]


def get_all(db: Session) -> dict:
    return resolve({s.key: s.value for s in db.scalars(select(Setting))})


def resolve(stored: dict) -> dict:
    """Trộn giá trị đã lưu với mặc định. `resolve({})` = nội dung mặc định, dùng được khi DB hỏng."""
    out = {k: _merge(v, stored.get(k)) for k, v in DEFAULTS.items()}
    out["sections"] = _fix_sections(out["sections"])
    out["bonus_types"] = _fix_bonus_types(out["bonus_types"])
    return out


def get(db: Session, key: str):
    return get_all(db)[key] if key in DEFAULTS else None


def put(db: Session, key: str, value) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = db.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = json.loads(json.dumps(value))  # bản sao mới để SQLAlchemy nhận thay đổi JSON


def type_labels(settings: dict) -> dict[str, str]:
    return {t["id"]: t["short"] for t in settings["bonus_types"]}


def media_paths_in_settings(db: Session) -> str:
    """Toàn bộ giá trị Setting dạng chuỗi JSON, dùng để kiểm tra ảnh còn được dùng không."""
    return json.dumps([s.value for s in db.scalars(select(Setting))], ensure_ascii=False)
