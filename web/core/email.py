"""
Отправка писем через HTTP API Brevo.

Бесплатный Render закрывает SMTP-порты (25, 465, 587), поэтому обычный SMTP там не работает.
Brevo отправляет письма по HTTPS, бесплатно до 300 писем в день.
Нужны переменные окружения BREVO_API_KEY и DEFAULT_FROM_EMAIL (адрес, подтверждённый в Brevo).
"""

import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message):
        name, address = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            "sender": {"email": address, "name": name or "TOIIM"},
            "to": [{"email": parseaddr(to)[1]} for to in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["htmlContent"] = content
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "api-key": settings.BREVO_API_KEY,
                "content-type": "application/json",
                "accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, TimeoutError) as error:
            logger.warning("Brevo: письмо не отправлено: %s", error)
            if not self.fail_silently:
                raise
            return False
