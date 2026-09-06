from __future__ import annotations
import json
import logging
import urllib.request
from email.utils import getaddresses
from typing import Iterable

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives, sanitize_address

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


def _parse(addr_list: Iterable[str]) -> list[str]:
    return [a for _, a in getaddresses(list(addr_list)) if a]


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if not self.fail_silently:
                raise RuntimeError("RESEND_API_KEY not configured.")
            return 0

        sent = 0
        for msg in email_messages:
            if self._send_one(msg, api_key):
                sent += 1
        return sent

    def _send_one(self, msg, api_key: str) -> bool:
        from_email = sanitize_address(msg.from_email, msg.encoding or "utf-8")
        payload = {
            "from": from_email,
            "to": _parse(msg.to),
            "subject": str(msg.subject),
            "text": msg.body or "",
        }
        if msg.cc:
            payload["cc"] = _parse(msg.cc)
        if msg.bcc:
            payload["bcc"] = _parse(msg.bcc)
        if msg.reply_to:
            payload["reply_to"] = _parse(msg.reply_to)

        if isinstance(msg, EmailMultiAlternatives):
            for body, mimetype in msg.alternatives:
                if mimetype == "text/html":
                    payload["html"] = body
                    break

        req = urllib.request.Request(
            RESEND_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    return True
                body = resp.read().decode("utf-8", errors="replace")
                logger.error("Resend rejected message: status=%s body=%s", resp.status, body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error("Resend HTTPError status=%s body=%s subject=%r", exc.code, body, msg.subject)
        except Exception:
            logger.exception("Resend send failed (subject=%r)", msg.subject)

        if not self.fail_silently:
            raise RuntimeError("Resend send failed — see logs.")
        return False
