"""
Готовые карточки партнёров: одна папка = один исполнитель.

catalog/partners/<папка>/partner.json — данные аккаунта, карточки и пакетов,
рядом *.jpg — фото (первое по имени станет обложкой).

Запускается при каждом деплое. Если карточка с таким slug уже есть, она не трогается,
чтобы правки исполнителя в кабинете не затирались.

Пароль: поле password_hash в partner.json (хеш Django, не сам пароль)
или переменная окружения PASSWORD_<ЛОГИН> (например PASSWORD_SHOW_ARU).
Если нет ни того, ни другого, аккаунт создаётся без пароля, и пароль ставится в админке.
"""

import json
import os
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile
from catalog.models import Category, City, Service, ServiceImage, ServiceImageBlob, ServicePackage

PARTNERS_DIR = Path(__file__).resolve().parents[2] / "partners"
SERVICE_FIELDS = [
    "title", "short_description", "description", "price_from", "price_unit",
    "capacity_min", "capacity_max", "address", "phone", "instagram",
]


def password_env_name(username):
    return "PASSWORD_" + re.sub(r"[^A-Z0-9]", "_", username.upper())


class Command(BaseCommand):
    help = "Добавить партнёров из catalog/partners/*/partner.json, если их ещё нет."

    def handle(self, *args, **options):
        for path in sorted(PARTNERS_DIR.glob("*/partner.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            slug = data["service"]["slug"]
            if Service.objects.filter(slug=slug).exists():
                self.stdout.write(f"{slug}: уже на сайте — ничего не меняю.")
                continue
            with transaction.atomic():
                user = self._ensure_user(data)
                self._create_service(user, data, path.parent)
            self.stdout.write(self.style.SUCCESS(f"{slug}: добавлен."))

    def _ensure_user(self, data):
        User = get_user_model()
        username = data["username"]
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User(username=username, email=data.get("email", ""), first_name=data.get("first_name", ""))
            env_name = password_env_name(username)
            password = os.environ.get(env_name, "")
            if data.get("password_hash"):
                # В репозитории только хеш пароля, сам пароль передаётся исполнителю лично.
                user.password = data["password_hash"]
            elif password:
                try:
                    validate_password(password, user)
                except ValidationError as error:
                    raise CommandError(f"{env_name} слишком простой: " + " ".join(error.messages))
                user.set_password(password)
            else:
                user.set_unusable_password()
                self.stdout.write(f"{env_name} не задан — у {username} пока нет пароля, поставьте его в админке.")
            user.save()
        profile = user.profile
        profile.role = Profile.Role.PROVIDER
        profile.city = profile.city or City.objects.filter(slug=data["service"]["city"]).first()
        profile.phone = profile.phone or data["service"].get("phone", "")
        profile.save()
        return user

    def _create_service(self, user, data, folder):
        info = data["service"]
        fields = {name: info[name] for name in SERVICE_FIELDS if info.get(name) not in (None, "")}
        service = Service.objects.create(
            owner=user,
            slug=info["slug"],
            category=Category.objects.get(slug=info["category"]),
            city=City.objects.get(slug=info["city"]),
            status=Service.Status.PUBLISHED,
            is_demo=False,
            is_verified=True,
            **fields,
        )
        for order, package in enumerate(data.get("packages", [])):
            ServicePackage.objects.create(
                service=service, title=package["title"], price=package["price"],
                includes="\n".join(package["includes"]), order=order,
            )
        alts = data.get("photo_alts", {})
        for order, photo in enumerate(sorted(folder.glob("*.jpg"))):
            image = ServiceImage.objects.create(
                service=service, stored=True, order=order, alt=alts.get(photo.stem, service.title),
            )
            ServiceImageBlob.objects.create(image=image, data=photo.read_bytes())
