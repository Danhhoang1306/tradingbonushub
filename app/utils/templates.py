"""Jinja2 template factory — supports shared template directory."""
import hashlib
import pathlib

from markupsafe import Markup
from jinja2 import ChoiceLoader, FileSystemLoader
from fastapi.templating import Jinja2Templates

from app.utils.i18n import t as _t, freq_label as _freq_label
from app.utils.sanitize import sanitize_html as _sanitize_html

_SHARED = "templates/shared"
_STATIC_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "static"

# Build a version map at startup: file path → short hash of content
_CSS_VERSIONS: dict[str, str] = {}


def _build_css_versions() -> None:
    """Compute short content hashes for all CSS files at startup."""
    for css_file in _STATIC_DIR.rglob("*.css"):
        rel = "/" + css_file.relative_to(_STATIC_DIR).as_posix()
        content_hash = hashlib.md5(css_file.read_bytes()).hexdigest()[:8]
        _CSS_VERSIONS[rel] = content_hash


_build_css_versions()


def _static_url(path: str) -> str:
    """Return /static/path?v=<hash> for cache-busting."""
    # Strip leading /static if present
    rel = path.replace("/static", "", 1) if path.startswith("/static") else path
    version = _CSS_VERSIONS.get(rel, "")
    suffix = f"?v={version}" if version else ""
    return f"/static{rel}{suffix}"


def _csrf_input(request) -> Markup:
    """Render a hidden input with the CSRF token for use in forms."""
    token = getattr(getattr(request, "state", None), "csrf_token", "")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


def _csp_nonce(request) -> str:
    """Return the CSP nonce for the current request."""
    return getattr(getattr(request, "state", None), "csp_nonce", "")


def _lang_url(path: str, lang: str) -> str:
    """Build a URL that carries the current language when non-default.

    Vietnamese is the default — VI URLs stay clean. English URLs get `lang=en`
    appended so the page renders correctly even without a cookie (shared links,
    SEO, cookie expiry). Handles both `?` and `&` joiners.
    """
    if lang != "en":
        return path
    if "lang=" in path:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}lang=en"


def make_templates(*dirs: str) -> Jinja2Templates:
    """Return a Jinja2Templates instance that searches `dirs` then `templates/shared`."""
    tpl = Jinja2Templates(directory=dirs[0])
    all_dirs = list(dirs) + [_SHARED]
    tpl.env.loader = ChoiceLoader([FileSystemLoader(d) for d in all_dirs])
    # Make csrf_input() available in all templates:  {{ csrf_input(request) }}
    tpl.env.globals["csrf_input"] = _csrf_input
    tpl.env.globals["csp_nonce"] = _csp_nonce
    tpl.env.globals["freq_label"] = _freq_label
    tpl.env.globals["t"] = _t
    tpl.env.globals["static_url"] = _static_url
    tpl.env.globals["lang_url"] = _lang_url
    tpl.env.filters["sanitize"] = _sanitize_html
    return tpl
