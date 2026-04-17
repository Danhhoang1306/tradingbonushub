"""HTML sanitization for user/admin-configurable content rendered with |safe.

Uses bleach to allow only safe HTML tags and attributes, stripping
potentially dangerous elements like <script>, <iframe>, event handlers, etc.
"""
import bleach

# Tags allowed in admin-editable content (headings, formatting, links, images)
_ALLOWED_TAGS = [
    "a", "abbr", "b", "br", "code", "em", "i", "li", "ol", "p",
    "pre", "small", "span", "strong", "sub", "sup", "u", "ul",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "img", "div", "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "hr", "figure", "figcaption", "mark",
]

_ALLOWED_ATTRS = {
    "*": ["class", "id", "data-*"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "span": ["style"],
    "div": ["style"],
    "p": ["style"],
}

# Inline styles are limited to safe CSS properties via css_sanitizer
try:
    from bleach.css_sanitizer import CSSSanitizer
    _css_sanitizer = CSSSanitizer(
        allowed_css_properties=[
            "color", "background-color", "font-size", "font-weight",
            "text-align", "text-decoration", "margin", "padding",
            "border", "border-radius", "display", "width", "height",
        ]
    )
except ImportError:
    _css_sanitizer = None


def sanitize_html(html: str) -> str:
    """Sanitize HTML string, removing dangerous tags/attributes."""
    if not html:
        return html
    return bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        css_sanitizer=_css_sanitizer,
        strip=True,
    )
