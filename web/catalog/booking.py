"""Создание заявки: одно место и для формы на сайте, и для API бота."""

from django.db import IntegrityError, transaction

from .models import BookingRequest
from .telegram import notify_new_booking


def create_booking(service, data, *, source, user=None, telegram_chat_id=None, site_url=""):
    """
    Сохранить заявку. Если заявка с таким idempotency_key уже есть
    (форму отправили дважды), вернуть её и не создавать новую.
    Возвращает (заявка, создана_ли_сейчас).
    """
    key = data["idempotency_key"]
    booking = BookingRequest(
        service=service, user=user, source=source, idempotency_key=key, telegram_chat_id=telegram_chat_id,
        name=data["name"], phone=data["phone"], event_date=data.get("event_date"),
        guests=data.get("guests"), message=data.get("message") or "",
    )
    try:
        with transaction.atomic():
            booking.save()
    except IntegrityError:
        return BookingRequest.objects.get(idempotency_key=key), False

    # Уведомление уходит только после того, как заявка точно сохранена в базе.
    transaction.on_commit(lambda: notify_new_booking(booking.pk, site_url))
    return booking, True
