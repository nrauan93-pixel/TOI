"""
Убрать демо-данные с сайта: выдуманные услуги и демо-пользователей, которые писали их отзывы.

Настоящие карточки не трогаются: удаляются только услуги с пометкой is_demo и без владельца.
Команда запускается при каждом деплое; если демо уже нет, она ничего не делает.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Service

DEMO_USERNAMES = ["demo_aliya", "demo_daniyar", "demo_madina"]


class Command(BaseCommand):
    help = "Удалить демо-услуги и демо-пользователей."

    @transaction.atomic
    def handle(self, *args, **options):
        services, _ = Service.objects.filter(is_demo=True, owner__isnull=True).delete()
        users, _ = get_user_model().objects.filter(username__in=DEMO_USERNAMES).delete()
        if options["verbosity"] > 0:
            if services or users:
                self.stdout.write(self.style.SUCCESS("Демо-данные удалены."))
            else:
                self.stdout.write("Демо-данных нет — ничего не удаляю.")
