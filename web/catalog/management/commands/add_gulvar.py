"""
Первый настоящий партнёр: ресторан и банкетный зал Gulvar (Алматы).

Запускается при каждом деплое, но создаёт всё только один раз:
если карточка уже есть, ничего не трогает, чтобы правки ресторана в кабинете не затирались.

Аккаунт ресторана: логин gulvar. Пароль берётся из переменной окружения GULVAR_PASSWORD
(задаётся в Render → Environment). Если переменной нет, аккаунт создаётся без пароля,
и пароль можно поставить в админке. Пароль существующего аккаунта команда не меняет.
"""

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile
from catalog.models import Category, City, Service, ServiceImage, ServiceImageBlob, ServicePackage

USERNAME = "gulvar"
EMAIL = "gulvar.hall@gmail.com"
SLUG = "gulvar-almaty"
PHOTOS_DIR = Path(__file__).resolve().parents[2] / "partners" / "gulvar"

DESCRIPTION = """Gulvar — ресторан и банкетный зал для свадеб, юбилеев, қыз ұзату и корпоративов.

Залы:
• Большой зал — от 120 до 324 гостей.
• Малый зал — от 36 до 72 гостей. По будням (пн–чт) работает отдельно вечером, в пт–вс объединяется с большим залом.
• Летняя терраса — для выездной регистрации и фуршета.

Ас (поминальный обед) в малом зале каждый день, 36–72 гостя.

Акция по будням (пн–чт): банкет от 20 000 ₸ с человека, в меню бешбармак и норвежский судак.

Банкетные меню с человека: Standard 29 000 ₸, Platinum 33 000 ₸, Diamond 39 000 ₸, Diamond 2 45 000 ₸.

Аренда оборудования для банкета в большом зале — 500 000 ₸. В малом зале: банкет 150 000 ₸, ас 50 000 ₸."""

PACKAGES = [
    ("Акция по будням", 20000, [
        "Только пн–чт",
        "Холодные закуски: мясное и рыбное плато",
        "Горячая закуска, 4 салата",
        "Бешбармак или норвежский судак",
        "Выпечка и десерт",
        "Аренда оборудования 500 000 ₸ отдельно",
    ]),
    ("Standard", 29000, [
        "Холодные закуски и ассорти",
        "Горячая закуска на выбор",
        "4 салата",
        "2 основных блюда на выбор, есть бешбармак",
        "Выпечка и десерты",
        "Безалкогольные напитки без лимита",
        "Алкоголь ваш",
    ]),
    ("Platinum", 33000, [
        "Расширенные закуски и салаты",
        "2 основных блюда на выбор, есть бешбармак",
        "Выпечка, десерты и восточные сладости",
        "Безалкогольные напитки без лимита",
        "Алкоголь ваш",
    ]),
    ("Diamond", 39000, [
        "Закуски с бураттой, 5 салатов",
        "2 основных блюда на выбор: бешбармак, сирне, дорадо",
        "Выпечка и десерты",
        "Безалкогольные напитки без лимита",
        "Алкоголь включён: водка, вино, коньяк, шампанское",
    ]),
    ("Diamond 2", 45000, [
        "Самое полное меню: закуски, 5 салатов, горячие закуски на выбор",
        "2 основных блюда на выбор: бешбармак, шашлык, дорадо, сирне",
        "Выпечка, десерты и национальные сладости",
        "Безалкогольные напитки без лимита",
        "Алкоголь включён, есть виски",
    ]),
    ("Новогодний корпоратив", 36000, [
        "Для 200–324 гостей",
        "Меню 36 000, 43 000 или 50 000 ₸ с человека",
        "Аренда зала со светом, звуком и LED-экраном 700 000 ₸",
    ]),
]

PHOTO_ALTS = {
    "01-glavnyi-zal": "Главный зал Gulvar",
    "02-zal-s-servirovkoi": "Зал с банкетной сервировкой",
    "03-svadebnoe-oformlenie": "Свадебное оформление зала",
    "04-terrasa-ceremoniya": "Выездная регистрация на террасе",
    "05-letnyaya-terrasa": "Летняя терраса",
    "06-zal-dekor": "Зал с декором",
    "07-stol-zakuski": "Банкетный стол с закусками",
    "08-floristika": "Флористика на столе",
    "09-vhod-vyveska": "Вход и вывеска Gulvar",
}


class Command(BaseCommand):
    help = "Добавить ресторан Gulvar (Алматы) с аккаунтом, фото и пакетами, если его ещё нет."

    def handle(self, *args, **options):
        user = self._ensure_user()
        if Service.objects.filter(slug=SLUG).exists():
            self.stdout.write("Gulvar уже на сайте — ничего не меняю.")
            return
        with transaction.atomic():
            self._create_service(user)
        self.stdout.write(self.style.SUCCESS("Gulvar добавлен: карточка, фото и пакеты."))

    def _ensure_user(self):
        User = get_user_model()
        user = User.objects.filter(username=USERNAME).first()
        if user is None:
            user = User(username=USERNAME, email=EMAIL, first_name="Gulvar")
            password = os.environ.get("GULVAR_PASSWORD", "")
            if password:
                try:
                    validate_password(password, user)
                except ValidationError as error:
                    raise CommandError("GULVAR_PASSWORD слишком простой: " + " ".join(error.messages))
                user.set_password(password)
            else:
                user.set_unusable_password()
                self.stdout.write("GULVAR_PASSWORD не задан — аккаунт gulvar без пароля, поставьте его в админке.")
            user.save()
        profile = user.profile
        profile.role = Profile.Role.PROVIDER
        profile.city = profile.city or City.objects.filter(slug="almaty").first()
        profile.phone = profile.phone or "+7 700 200 4101"
        profile.save()
        return user

    def _create_service(self, user):
        service = Service.objects.create(
            owner=user,
            category=Category.objects.get(slug="toikhana"),
            city=City.objects.get(slug="almaty"),
            title="Gulvar — ресторан и банкетный зал",
            slug=SLUG,
            short_description="Два зала на 36–324 гостя, летняя терраса для выездной регистрации",
            description=DESCRIPTION,
            price_from=20000,
            price_unit=Service.PriceUnit.GUEST,
            capacity_min=36,
            capacity_max=324,
            address="Парк им. 28 гвардейцев-панфиловцев, ул. Казыбек би, 43",
            phone="+7 700 200 4101",
            instagram="gulvar.kz",
            status=Service.Status.PUBLISHED,
            is_demo=False,
            is_verified=True,
        )
        for order, (title, price, items) in enumerate(PACKAGES):
            ServicePackage.objects.create(
                service=service, title=title, price=price, order=order,
                includes="\n".join(["Цена указана за 1 гостя", *items]),
            )
        for order, path in enumerate(sorted(PHOTOS_DIR.glob("*.jpg"))):
            image = ServiceImage.objects.create(
                service=service, stored=True, order=order, alt=PHOTO_ALTS.get(path.stem, service.title),
            )
            ServiceImageBlob.objects.create(image=image, data=path.read_bytes())
