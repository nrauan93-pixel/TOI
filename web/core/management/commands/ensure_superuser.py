"""
Создаёт администратора из переменных окружения, если его ещё нет.

Нужно для бесплатного Render, где нет консоли для `createsuperuser`.
Переменные: DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_PASSWORD, DJANGO_SUPERUSER_EMAIL.
Если переменные не заданы, команда ничего не делает.
Пароль существующего администратора не меняется.
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Создать администратора из переменных окружения (если его нет)."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD не заданы — пропускаю.")
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Администратор «{username}» уже есть — ничего не меняю.")
            return

        user = User(username=username, email=email)
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError("Пароль администратора слишком простой: " + " ".join(error.messages))

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Администратор «{username}» создан."))
