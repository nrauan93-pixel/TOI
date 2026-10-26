"""
Отправка сообщений в Telegram через Bot API.

Токен берётся только из настроек (переменная окружения TELEGRAM_BOT_TOKEN)
и никогда не попадает в логи, HTML или ответы API.
"""

import html
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SECONDS = 5


def send_message(chat_id, text):
    """Отправить сообщение. Возвращает True, если Telegram его принял."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        return False
    payload = json.dumps({
        "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
    }).encode()
    request = urllib.request.Request(
        API_URL.format(token=token), data=payload, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response).get("ok", False)
    except urllib.error.HTTPError as error:
        # В тексте ошибки нет адреса с токеном, только код ответа.
        logger.warning("Telegram отклонил сообщение: HTTP %s", error.code)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        logger.warning("Не удалось отправить сообщение в Telegram: %s", type(error).__name__)
    return False


def booking_text(booking, site_url=""):
    service = booking.service
    lines = [
        "<b>Новая заявка #{}</b> ({})".format(booking.pk, booking.get_source_display()),
        "",
        "<b>Услуга:</b> {}".format(html.escape(service.title)),
        "<b>Город:</b> {}".format(html.escape(service.city.name_ru)),
        "<b>Имя:</b> {}".format(html.escape(booking.name)),
        "<b>Телефон:</b> {}".format(html.escape(booking.phone)),
    ]
    if booking.event_date:
        lines.append("<b>Дата:</b> {:%d.%m.%Y}".format(booking.event_date))
    if booking.guests:
        lines.append("<b>Гостей:</b> {}".format(booking.guests))
    if booking.message:
        lines.append("<b>Сообщение:</b> {}".format(html.escape(booking.message)))
    if site_url:
        lines += ["", "Страница услуги: {}".format(html.escape(site_url + service.get_absolute_url()))]
    return "\n".join(lines)


def notify_new_booking(booking_id, site_url=""):
    """Сообщить о заявке админу и исполнителю (если он привязал Telegram)."""
    from .models import BookingRequest

    booking = (
        BookingRequest.objects.select_related("service__city", "service__owner__profile")
        .filter(pk=booking_id).first()
    )
    if booking is None or booking.telegram_notified_at:
        return False

    recipients = []
    if settings.TELEGRAM_ADMIN_CHAT_ID:
        recipients.append(settings.TELEGRAM_ADMIN_CHAT_ID)
    owner = booking.service.owner
    owner_chat = getattr(getattr(owner, "profile", None), "telegram_chat_id", None) if owner else None
    if owner_chat and str(owner_chat) not in recipients:
        recipients.append(str(owner_chat))

    text = booking_text(booking, site_url)
    sent = [chat for chat in recipients if send_message(chat, text)]
    if sent:
        BookingRequest.objects.filter(pk=booking.pk).update(telegram_notified_at=timezone.now())
    return bool(sent)


def notify_service_for_review(service, site_url=""):
    """Сообщить админу, что исполнитель добавил или изменил услугу и её надо проверить."""
    if not settings.TELEGRAM_ADMIN_CHAT_ID:
        return False
    lines = [
        "<b>Услуга на проверку</b>",
        "",
        "<b>Название:</b> {}".format(html.escape(service.title)),
        "<b>Категория:</b> {}".format(html.escape(service.category.name_ru)),
        "<b>Город:</b> {}".format(html.escape(service.city.name_ru)),
        "<b>Исполнитель:</b> {}".format(html.escape(service.owner.get_username() if service.owner else "—")),
    ]
    if site_url:
        lines += ["", "Проверить: {}/admin/catalog/service/{}/change/".format(html.escape(site_url), service.pk)]
    return send_message(settings.TELEGRAM_ADMIN_CHAT_ID, "\n".join(lines))


def notify_service_published(service, site_url=""):
    """Сообщить исполнителю, что его услугу опубликовали."""
    owner = service.owner
    chat_id = getattr(getattr(owner, "profile", None), "telegram_chat_id", None) if owner else None
    if not chat_id:
        return False
    text = "<b>Ваша услуга опубликована в TOIIM</b>\n\n{}".format(html.escape(service.title))
    if site_url:
        text += "\n{}".format(html.escape(site_url + service.get_absolute_url()))
    return send_message(chat_id, text)
