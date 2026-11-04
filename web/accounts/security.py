"""Подтверждение почты и простая защита от ботов (лимит по IP)."""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class ActivationTokenGenerator(PasswordResetTokenGenerator):
    """Ссылка из письма работает один раз: после подтверждения меняется is_active и хеш."""

    key_salt = "accounts.ActivationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{super()._make_hash_value(user, timestamp)}{user.is_active}"


activation_token = ActivationTokenGenerator()


def client_ip(request):
    # На Render настоящий IP клиента первый в X-Forwarded-For.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


def hit_limit(request, action, limit, period=60 * 60):
    """Посчитать попытку. True, если с этого IP уже слишком много попыток за период."""
    key = f"limit:{action}:{client_ip(request)}"
    cache.add(key, 0, period)
    try:
        count = cache.incr(key)
    except ValueError:  # ключ успел истечь
        cache.set(key, 1, period)
        count = 1
    return count > limit


def send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = request.build_absolute_uri(
        reverse("accounts:activate", args=[uid, activation_token.make_token(user)])
    )
    body = render_to_string("accounts/email/activation.txt", {"user": user, "link": link})
    send_mail("TOIIM: подтвердите почту", body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
