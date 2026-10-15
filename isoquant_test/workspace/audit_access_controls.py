"""Rule-16 audit: scan all Python files for patterns that would bypass
authentication, CAPTCHA, rate limits, or other access controls.

This is a read-only compliance check. It looks for red-flag constructs:
proxy/VPN/IP rotation, CAPTCHA-solving, credential forging, aggressive
retry storms, and header/cookie manipulation intended to defeat
bot-detection or access controls. It prints a short report per finding.

This script excludes its own file to avoid self-referential false
positives from the search patterns.
"""
import re
from pathlib import Path

SELF = Path(__file__).resolve()

RED_FLAGS = {
    r"\bproxy\b|proxies": "proxy usage (possible IP-mask / geo-block evasion)",
    r"captcha|recaptcha|2captcha|anticaptcha": "CAPTCHA solving",
    r"rotat(e|ing).*(ip|user.agent)|ip.?rotat": "IP / fingerprint rotation",
    r"retry|backoff|while\s+True": "retry loop (check it backs off, not hammers)",
    r"csrf|xsrf|forg": "token forgery / bypass attempt",
    r"webdriver|selenium|playwright|undetected": "browser automation (possible bot-detection evasion)",
    r"Cookie:": "manual cookie handling (check intent)",
    r"\btor\b|socks|vpn": "anonymising network",
    r"429": "rate-limit handling (should back off, not push through)",
    r"api[_-]?key|secret|password": "credential handling (should never be hard-coded)",
}

PY_FILES = sorted(p for p in Path(".").rglob("*.py")
                  if "__pycache__" not in p.parts and p.resolve() != SELF)

findings = 0
for path in PY_FILES:
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern, label in RED_FLAGS.items():
        for m in re.finditer(pattern, text, re.IGNORECASE):
            line_no = text.count("\n", 0, m.start()) + 1
            line = text.splitlines()[line_no - 1].strip()
            print(f"{path}:{line_no}  [{label}]\n    {line[:120]}")
            findings += 1

print(f"\nScanned {len(PY_FILES)} Python files -> {findings} finding(s).")
