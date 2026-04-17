"""User-agent parsing and email client detection."""
import re

from user_agents import parse as ua_parse


def detect_email_client(raw_ua: str) -> str:
    raw = raw_ua or ""
    if re.search(r"Outlook|MSOffice|microsoft\.outlook", raw, re.I):
        return "Outlook"
    if re.search(r"Thunderbird", raw, re.I):
        return "Thunderbird"
    if re.search(r"AppleMail|Apple Mail", raw, re.I):
        return "Apple Mail"
    if re.search(r"Googlebot-Image|Google Image Proxy|Gmail", raw, re.I):
        return "Gmail"
    if re.search(r"YahooMailProxy|YahooMail", raw, re.I):
        return "Yahoo Mail"
    if re.search(r"com\.google\.android\.gm", raw, re.I):
        return "Gmail (Android)"
    return "Other"


def parse_ua(raw_ua: str) -> tuple[str, str, str]:
    """Return (device_type, os_name, email_client)."""
    ua = ua_parse(raw_ua or "")
    device_type = "Mobile" if ua.is_mobile else ("Tablet" if ua.is_tablet else "Desktop")
    return device_type, ua.os.family or "Unknown", detect_email_client(raw_ua)
