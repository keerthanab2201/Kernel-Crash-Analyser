"""Best-effort log redaction. Not a guarantee of anonymization."""

import hashlib
import hmac
import re
import secrets


class Redactor:
    def __init__(self, key: bytes | None = None):
        self.key = key or secrets.token_bytes(32)

    def token(self, kind: str, value: str) -> str:
        digest = hmac.new(self.key, value.encode(), hashlib.sha256).hexdigest()[:12]
        return f"[{kind}_{digest}]"

    def redact(self, text: str) -> str:
        text = re.sub(
            r"(?i)\b(IMSI|IMEI|SUPI|ICCID|MSISDN|password|token|api[_-]?key)\s*[:=]\s*([^\s,;]+)",
            lambda m: m[1] + "=" + self.token(m[1].upper(), m[2]),
            text,
        )
        text = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            lambda m: self.token("EMAIL", m[0]),
            text,
        )
        text = re.sub(
            r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b",
            lambda m: self.token("MAC", m[0]),
            text,
        )
        text = re.sub(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b", lambda m: self.token("IP", m[0]), text
        )
        return text
