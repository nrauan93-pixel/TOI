"""
Заполняет базу демо-данными: города, категории, услуги и отзывы.

Запуск:  python manage.py seed_demo
Повторный запуск безопасен: записи обновляются, а не дублируются.
Все услуги помечены is_demo=True: это примеры, а не настоящие компании.
На сайте об этом говорит одна плашка на странице услуги и строка в подвале.
Фото берутся с Unsplash (бесплатная лицензия, можно использовать без оплаты).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, City, Review, Service, ServiceImage

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

# Фото с Unsplash (https://unsplash.com/license): slug услуги -> (id фото, описание).
PHOTOS = {
    "altyn-saray-almaty": ("photo-1712314947761-a8d718bd8c32", "банкетный зал с люстрами"),
    "ak-orda-hall-almaty": ("photo-1763429338698-439aa108e7fb", "светлый зал, накрытый для банкета"),
    "baiterek-palace-astana": ("photo-1783314867628-220ab03cac99", "большой зал с множеством столов"),
    "shymkent-grand-shymkent": ("photo-1768851142332-75f3d1b47452", "банкетный зал с круглыми столами"),
    "sary-arka-karaganda": ("photo-1768508951405-10e83c4a2872", "зал с круглыми столами"),
    "aktobe-saltanat-aktobe": ("photo-1665607437981-973dcd6a22bb", "зал, накрытый для свадьбы"),
    "taraz-aulie-taraz": ("photo-1723832348105-2e69f948135a", "просторный зал со столами"),
    "dala-restaurant-almaty": ("photo-1779301674216-506de8607c87", "ресторан с большими окнами"),
    "esil-hall-astana": ("photo-1631615535272-1106aa1b3854", "ресторан с подвесными лампами"),
    "kazyna-restaurant-shymkent": ("photo-1687648431656-da99da578d50", "уютный зал с белыми скатертями"),
    "atyrau-zhaiyk-atyrau": ("photo-1695094411862-0e047fbddcb1", "зал ресторана со столами"),
    "nurlan-host-almaty": ("photo-1772030828446-9e8531d25e7b", "микрофон"),
    "aigerim-host-astana": ("photo-1527529482837-4698179dc6ce", "гости поднимают бокалы"),
    "erlan-host-shymkent": ("photo-1758810409996-583f3bad7d51", "гости танцуют на празднике"),
    "asyl-host-atyrau": ("photo-1502635385003-ee1e6a1a742d", "бокалы на праздничном столе"),
    "aru-sound-almaty": ("photo-1581663838011-fdc391797402", "музыканты на сцене"),
    "saule-band-shymkent": ("photo-1560523159-4a9692d222ef", "выступление на сцене"),
    "dj-arman-astana": ("photo-1544785349-c4a5301826fd", "DJ-пульт с подсветкой"),
    "sapa-studio-almaty": ("photo-1519741497674-611481863552", "свадебная фотосессия"),
    "kadr-media-astana": ("photo-1769635177236-116c95222fab", "фотограф снимает пару"),
    "moment-photo-karaganda": ("photo-1622277430358-f4d134452e2e", "невеста у окна"),
    "gulder-decor-almaty": ("photo-1641834919507-b0271fe5186b", "арка из цветов"),
    "dina-decor-aktobe": ("photo-1738025277281-582526f674c4", "арка с розовыми и белыми цветами"),
    "tatti-cake-astana": ("photo-1525257831700-183b9b8bf5c4", "свадебный торт с цветами"),
}
PHOTO_URL = "https://images.unsplash.com/{}?auto=format&fit=crop&w=1200&q=80"

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
                    "title": title,
                    "short_description": short,
                    "description": f"{short}.",
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
            if slug in PHOTOS:
                photo_id, alt = PHOTOS[slug]
                ServiceImage.objects.update_or_create(
                    service=service, order=0, image="",
                    defaults={"image_url": PHOTO_URL.format(photo_id), "alt": f"Фото для примера: {alt}"},
                )
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
