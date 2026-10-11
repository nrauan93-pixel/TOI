from django.conf import settings


def site_settings(request):
    """Данные, нужные во всех шаблонах (например, ссылка на Telegram-бота)."""
    username = settings.TELEGRAM_BOT_USERNAME
    favorite_ids = set()
    if getattr(request, "user", None) and request.user.is_authenticated:
        favorite_ids = set(request.user.favorites.values_list("service_id", flat=True))
    return {
        "TELEGRAM_BOT_USERNAME": username,
        "TELEGRAM_BOT_URL": f"https://t.me/{username}",
        # Меняется с каждым шагом, чтобы браузер не показывал старые стили из кэша.
        "ASSET_VERSION": settings.ASSET_VERSION,
        "FAVORITE_IDS": favorite_ids,
    }
