"""Template placeholder extraction and rendering."""
import html as _html_module
import re

# Matches both [Variable Name] and {{variable_name}}
_PLACEHOLDER_RE = re.compile(r'\[([^\]]+)\]|\{\{([^}]+)\}\}')

# System placeholders that are injected automatically — hide from mapping UI
_SYSTEM_PLACEHOLDERS = {"[SIGNATURE]", "[ticket]"}


def extract_placeholders(html: str) -> list[str]:
    """Return unique placeholder tokens found in the template HTML."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _PLACEHOLDER_RE.finditer(html):
        raw = m.group(0)
        if raw not in seen and raw not in _SYSTEM_PLACEHOLDERS:
            seen.add(raw)
            found.append(raw)
    return found


def render_dynamic(html: str, row: dict, mapping: dict) -> str:
    """Replace placeholders in HTML with row values according to mapping.

    mapping = { "[Customer Name]": "Full Name", "{{order_code}}": "Order Code", ... }
    row     = { "Full Name": "John Doe", "Order Code": "DH001", ... }
    Values are HTML-escaped to prevent XSS.
    """
    for placeholder, column in mapping.items():
        value = _html_module.escape(str(row.get(column, "")))
        html = html.replace(placeholder, value)
    return html
