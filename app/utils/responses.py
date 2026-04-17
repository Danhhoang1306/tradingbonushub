"""Standardized API response helpers for consistent JSON structure."""
from fastapi.responses import JSONResponse


def success_response(data=None, message: str = "OK", status_code: int = 200) -> JSONResponse:
    """Wrap a successful response in a standard envelope."""
    body = {"ok": True, "message": message}
    if data is not None:
        body["data"] = data
    return JSONResponse(body, status_code=status_code)


def error_response(message: str, status_code: int = 400, errors: list | None = None) -> JSONResponse:
    """Wrap an error response in a standard envelope."""
    body = {"ok": False, "message": message}
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status_code)
