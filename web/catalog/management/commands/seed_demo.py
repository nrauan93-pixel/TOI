"""
Заполняет базу демо-данными: города, категории, услуги и отзывы.

Запуск:  python manage.py seed_demo
Повторный запуск безопасен: записи обновляются, а не дублируются.
Все услуги помечены is_demo=True и «(демо)» в названии: это примеры,
а не настоящие компании.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, City, Review, Service

CITIES = [
    ("almaty", "Алматы", "Алматы"),
    ("astana", "Астана", "Астана"),
    ("shymkent", "Шымкент", "Шымкент"),
    ("karaganda", "Караганда", "Қарағанды"),
    ("aktobe", "Актобе", "Ақтөбе"),
    ("atyrau", "Атырау", "Атырау"),
    ("taraz", "Тараз", "Тараз"),
]

CATEGORIES = [
    # slug, рус., каз., тип, иконка Lucide
    ("toikhana", "Тойханы и банкетные залы", "Тойханалар", "venue", "building-2"),
    ("restaurant", "Рестораны", "Мейрамханалар", "venue", "utensils"),
    ("host", "Ведущие и тамада", "Асабалар", "performer", "mic"),
    ("music", "Музыканты и DJ", "Әншілер мен DJ", "performer", "music"),
    ("photo-video", "Фото и видео", "Фото және бейне", "performer", "camera"),
    ("decor", "Декор и оформление", "Безендіру", "service", "flower-2"),
    ("cake", "Торты и сладости", "Торттар", "service", "cake-slice"),
]

# slug, категория, город, название, коротко, цена, единица, гостей от/до, рейтинг демо-отзывов
SERVICES = [
    ("altyn-saray-almaty", "toikhana", "almaty", "Тойхана «Алтын Сарай»", "Большой зал с национальным интерьером и сценой", 18000, "guest", 150, 600, [5, 5, 4]),
    ("ak-orda-hall-almaty", "toikhana", "almaty", "Банкетный зал «Ак Орда»", "Светлый зал для свадеб и юбилеев в центре города", 14000, "guest", 80, 300, [5, 4, 4]),
    ("dala-restaurant-almaty", "restaurant", "almaty", "Ресторан «Дала»", "Камерный ресторан с террасой и видом на горы", 12000, "guest", 30, 120, [5, 5]),
    ("nurlan-host-almaty", "host", "almaty", "Ведущий Нурлан", "Двуязычный ведущий: казахский и русский, 10 лет опыта", 350000, "event", None, None, [5, 5, 5]),
    ("aru-sound-almaty", "music", "almaty", "Группа «Ару Саунд»", "Живая музыка, домбра и современные хиты", 400000, "event", None, None, [5, 4]),
    ("sapa-studio-almaty", "photo-video", "almaty", "Фотостудия «Сапа»", "Репортаж, love story и свадебный фильм", 250000, "event", None, None, [4, 5]),
    ("gulder-decor-almaty", "decor", "almaty", "Декор-студия «Гүлдер»", "Оформление зала, арки, цветы и свет", 300000, "event", None, None, [5]),
    ("baiterek-palace-astana", "toikhana", "astana", "Тойхана «Бәйтерек Палас»", "Два зала, парковка на 200 машин, своя кухня", 16000, "guest", 200, 800, [5, 4, 5]),
    ("esil-hall-astana", "restaurant", "astana", "Ресторан «Есіл»", "Панорамный зал у набережной для небольших тоев", 15000, "guest", 40, 150, [4, 4]),
    ("aigerim-host-astana", "host", "astana", "Ведущая Айгерим", "Свадьбы, қыз ұзату и юбилеи, своя программа конкурсов", 300000, "event", None, None, [5, 5]),
    ("dj-arman-astana", "music", "astana", "DJ Арман", "Звук и свет под ключ, плейлист под гостей", 200000, "event", None, None, [4, 5]),
    ("kadr-media-astana", "photo-video", "astana", "«Кадр Медиа»", "Команда из двух операторов и фотографа, дрон", 350000, "event", None, None, [5]),
    ("tatti-cake-astana", "cake", "astana", "Кондитерская «Тәтті»", "Свадебные торты и шашу-наборы на заказ", 8000, "guest", None, None, [5, 4]),
    ("shymkent-grand-shymkent", "toikhana", "shymkent", "Тойхана «Шымкент Гранд»", "Самый большой зал города, до 1000 гостей", 11000, "guest", 300, 1000, [4, 5, 4]),
    ("kazyna-restaurant-shymkent", "restaurant", "shymkent", "Ресторан «Қазына»", "Национальная кухня и уютные залы", 9000, "guest", 50, 200, [5]),
    ("erlan-host-shymkent", "host", "shymkent", "Тамада Ерлан", "Весёлый тамада с южным колоритом", 200000, "event", None, None, [5, 4]),
    ("saule-band-shymkent", "music", "shymkent", "Ансамбль «Сәуле»", "Народные песни и эстрадная программа", 250000, "event", None, None, [4]),
    ("sary-arka-karaganda", "toikhana", "karaganda", "Банкетный зал «Сарыарқа»", "Классический зал с хорошей акустикой", 10000, "guest", 100, 400, [4, 4]),
    ("moment-photo-karaganda", "photo-video", "karaganda", "Фотограф «Moment»", "Тёплые живые кадры и быстрый монтаж", 150000, "event", None, None, [5]),
    ("aktobe-saltanat-aktobe", "toikhana", "aktobe", "Тойхана «Салтанат»", "Новый зал с современным светом", 9500, "guest", 120, 450, [4]),
    ("dina-decor-aktobe", "decor", "aktobe", "Декор «Дина»", "Оформление в национальном и европейском стиле", 180000, "event", None, None, [5, 5]),
    ("atyrau-zhaiyk-atyrau", "restaurant", "atyrau", "Ресторан «Жайық»", "Банкеты у реки, морская и казахская кухня", 13000, "guest", 40, 180, [4, 5]),
    ("asyl-host-atyrau", "host", "atyrau", "Ведущий Асыл", "Солидный ведущий для юбилеев и корпоративов", 220000, "event", None, None, [4]),
    ("taraz-aulie-taraz", "toikhana", "taraz", "Тойхана «Әулие-Ата»", "Доступные цены и просторный зал", 8000, "guest", 100, 500, [4, 4]),
]

DEMO_REVIEW_TEXTS = {
    5: "Всё прошло отлично, гости довольны. Рекомендуем!",
    4: "Хорошо, но были небольшие задержки. В целом довольны.",
    3: "Нормально, ожидали немного большего.",
}


class Command(BaseCommand):
    help = "Заполнить базу демо-данными (города, категории, услуги, отзывы)."

    @transaction.atomic
    def handle(self, *args, **options):
        cities = {}
        for order, (slug, ru, kk) in enumerate(CITIES):
            cities[slug], _ = City.objects.update_or_create(
                slug=slug, defaults={"name_ru": ru, "name_kk": kk, "order": order},
            )

        categories = {}
        for order, (slug, ru, kk, kind, icon) in enumerate(CATEGORIES):
            categories[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"name_ru": ru, "name_kk": kk, "kind": kind, "icon": icon, "order": order},
            )

        reviewers = self._demo_reviewers()

        created_count = 0
        for slug, cat, city, title, short, price, unit, cap_min, cap_max, ratings in SERVICES:
            service, created = Service.objects.update_or_create(
                slug=slug,
                defaults={
                    "category": categories[cat],
                    "city": cities[city],
                    "title": f"{title} (демо)",
                    "short_description": short,
                    "description": (
                        f"{short}.\n\nЭто демонстрационная карточка TOIIM: компания вымышленная, "
                        "цены примерные. Настоящие исполнители появятся после регистрации и модерации."
                    ),
                    "price_from": price,
                    "price_unit": unit,
                    "capacity_min": cap_min,
                    "capacity_max": cap_max,
                    "address": f"г. {cities[city].name_ru}" if cap_max else "",
                    "status": Service.Status.PUBLISHED,
                    "is_demo": True,
                    "is_verified": False,
                },
            )
            created_count += created
            for reviewer, rating in zip(reviewers, ratings):
                Review.objects.update_or_create(
                    service=service, user=reviewer,
                    defaults={"rating": rating, "text": DEMO_REVIEW_TEXTS[rating]},
                )

        if options["verbosity"] > 0:
            self.stdout.write(self.style.SUCCESS(
                f"Готово: городов {len(cities)}, категорий {len(categories)}, "
                f"услуг {len(SERVICES)} (новых {created_count}), отзывов {Review.objects.count()}."
            ))

    def _demo_reviewers(self):
        """Демо-пользователи для отзывов. Войти под ними нельзя (пароль не задан)."""
        User = get_user_model()
        reviewers = []
        for username, first_name in [("demo_aliya", "Алия"), ("demo_daniyar", "Данияр"), ("demo_madina", "Мадина")]:
            user, created = User.objects.get_or_create(username=username, defaults={"first_name": first_name})
            if created:
                user.set_unusable_password()
                user.save()
            reviewers.append(user)
        return reviewers
