"""CMS articles + categories repository."""
import re
import unicodedata

from app.db.connection import get_conn


# ── Slug helper ────────────────────────────────────────────────────────────────

# Not needed — unicodedata.normalize("NFD") + remove combining marks handles Vietnamese


def slugify(text: str) -> str:
    """Convert Vietnamese text to URL-safe slug."""
    # Normalize unicode (NFD → separate base chars + combining marks)
    text = unicodedata.normalize("NFD", text)
    # Remove combining marks
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Lowercase
    text = text.lower()
    # Replace non-alphanumeric with dash
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing dashes, collapse multiple dashes
    text = text.strip("-")
    return text or "article"


def unique_slug(base: str, exclude_id: int | None = None) -> str:
    """Ensure slug is unique by appending -2, -3, etc. if needed."""
    slug = slugify(base)
    with get_conn() as conn:
        n = 0
        candidate = slug
        while True:
            if exclude_id:
                row = conn.execute(
                    "SELECT 1 FROM cms_articles WHERE slug=? AND id<>?",
                    (candidate, exclude_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM cms_articles WHERE slug=?", (candidate,)
                ).fetchone()
            if not row:
                return candidate
            n += 1
            candidate = f"{slug}-{n}"


# ── Categories ─────────────────────────────────────────────────────────────────

def get_all_categories() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cms_article_categories ORDER BY display_order, id"
        ).fetchall()
    return [dict(r) for r in rows]


def create_category(name: str, slug: str, parent_id: int | None,
                    display_order: int = 0) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO cms_article_categories (name, slug, parent_id, display_order)
               OUTPUT INSERTED.id VALUES (?, ?, ?, ?)""",
            (name, slug, parent_id, display_order),
        ).fetchone()
    return row["id"]


def update_category(cid: int, name: str, slug: str,
                    parent_id: int | None, display_order: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE cms_article_categories
               SET name=?, slug=?, parent_id=?, display_order=? WHERE id=?""",
            (name, slug, parent_id, display_order, cid),
        )


def delete_category(cid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM cms_article_categories WHERE id=?", (cid,))


# ── Articles ───────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    d = dict(row)
    # Ensure datetime fields are serialisable
    for k in ("published_at", "created_at", "updated_at"):
        if d.get(k) and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    return d


def list_articles(
    status: str | None = None,
    type_: str | None = None,
    lang: str | None = None,
    category_id: int | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    wheres = []
    params = []

    if status:
        wheres.append("a.status=?")
        params.append(status)
    if type_:
        wheres.append("a.type=?")
        params.append(type_)
    if lang:
        wheres.append("a.lang=?")
        params.append(lang)
    if category_id:
        wheres.append("a.category_id=?")
        params.append(category_id)
    if search:
        wheres.append("(a.title LIKE ? OR a.excerpt LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]

    where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""

    with get_conn() as conn:
        total = conn.execute(
            f"""SELECT COUNT(*) AS cnt FROM cms_articles a
                LEFT JOIN cms_article_categories c ON a.category_id = c.id
                {where_sql}""",
            params or None,
        ).fetchone()["cnt"]

        rows = conn.execute(
            f"""SELECT a.*, c.name AS category_name,
                       m.url AS cover_url, m_en.url AS cover_url_en
                FROM cms_articles a
                LEFT JOIN cms_article_categories c ON a.category_id = c.id
                LEFT JOIN media_files m ON a.cover_image_id = m.id
                LEFT JOIN media_files m_en ON a.cover_image_id_en = m_en.id
                {where_sql}
                ORDER BY a.created_at DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
            params + [offset, limit],
        ).fetchall()

    return {"items": [_row_to_dict(r) for r in rows], "total": total}


def get_article_by_id(aid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT a.*, c.name AS category_name,
                      m.url AS cover_url, m_en.url AS cover_url_en
               FROM cms_articles a
               LEFT JOIN cms_article_categories c ON a.category_id = c.id
               LEFT JOIN media_files m ON a.cover_image_id = m.id
               LEFT JOIN media_files m_en ON a.cover_image_id_en = m_en.id
               WHERE a.id=?""",
            (aid,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_article_by_slug(slug: str, status: str = "published") -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT a.*, c.name AS category_name, c.slug AS category_slug,
                      m.url AS cover_url, m_en.url AS cover_url_en
               FROM cms_articles a
               LEFT JOIN cms_article_categories c ON a.category_id = c.id
               LEFT JOIN media_files m ON a.cover_image_id = m.id
               LEFT JOIN media_files m_en ON a.cover_image_id_en = m_en.id
               WHERE a.slug=? AND a.status=?""",
            (slug, status),
        ).fetchone()
    return _row_to_dict(row) if row else None


def create_article(
    slug: str, type_: str, status: str, lang: str,
    title: str, excerpt: str, content: str,
    cover_image_id: int | None, category_id: int | None,
    author: str,
    seo_title: str, seo_desc: str, seo_image: str,
    title_en: str | None = None, excerpt_en: str | None = None,
    content_en: str | None = None,
    seo_title_en: str | None = None, seo_desc_en: str | None = None,
    cover_image_id_en: int | None = None,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO cms_articles
               (slug, type, status, lang, title, excerpt, content,
                cover_image_id, category_id, author,
                seo_title, seo_desc, seo_image,
                title_en, excerpt_en, content_en, seo_title_en, seo_desc_en,
                cover_image_id_en)
               OUTPUT INSERTED.id
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, type_, status, lang, title, excerpt, content,
             cover_image_id, category_id, author,
             seo_title, seo_desc, seo_image,
             title_en, excerpt_en, content_en, seo_title_en, seo_desc_en,
             cover_image_id_en),
        ).fetchone()
    return row["id"]


def update_article(
    aid: int, slug: str, type_: str, status: str, lang: str,
    title: str, excerpt: str, content: str,
    cover_image_id: int | None, category_id: int | None,
    author: str,
    seo_title: str, seo_desc: str, seo_image: str,
    published_at_sql: str | None,
    title_en: str | None = None, excerpt_en: str | None = None,
    content_en: str | None = None,
    seo_title_en: str | None = None, seo_desc_en: str | None = None,
    cover_image_id_en: int | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE cms_articles
               SET slug=?, type=?, status=?, lang=?,
                   title=?, excerpt=?, content=?,
                   cover_image_id=?, category_id=?, author=?,
                   seo_title=?, seo_desc=?, seo_image=?,
                   published_at=?, updated_at=GETDATE(),
                   title_en=?, excerpt_en=?, content_en=?,
                   seo_title_en=?, seo_desc_en=?,
                   cover_image_id_en=?
               WHERE id=?""",
            (slug, type_, status, lang,
             title, excerpt, content,
             cover_image_id, category_id, author,
             seo_title, seo_desc, seo_image,
             published_at_sql,
             title_en, excerpt_en, content_en,
             seo_title_en, seo_desc_en,
             cover_image_id_en,
             aid),
        )


def delete_article(aid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM cms_articles WHERE id=?", (aid,))


def publish_article(aid: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE cms_articles
               SET status='published',
                   published_at=COALESCE(published_at, GETDATE()),
                   updated_at=GETDATE()
               WHERE id=?""",
            (aid,),
        )


def unpublish_article(aid: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE cms_articles SET status='draft', updated_at=GETDATE() WHERE id=?",
            (aid,),
        )
