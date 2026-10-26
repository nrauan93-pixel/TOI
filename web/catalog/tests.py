from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import BookingRequest, Category, City, Favorite, Review, Service, ServiceImage

User = get_user_model()


class CatalogModelTests(TestCase):
    def setUp(self):
        self.city = City.objects.create(name_ru="Алматы", slug="almaty")
        self.category = Category.objects.create(name_ru="Ведущие", slug="host", kind="performer")
        self.service = Service.objects.create(
            category=self.category, city=self.city, title="Тест", slug="test",
            short_description="Коротко", price_from=100000, status=Service.Status.PUBLISHED,
        )
        self.user = User.objects.create_user("aliya", password="pass12345!")

    def test_profile_created_automatically(self):
        self.assertEqual(self.user.profile.role, "client")

    def test_rating_recalculated_from_reviews(self):
        other = User.objects.create_user("daniyar", password="pass12345!")
        Review.objects.create(service=self.service, user=self.user, rating=5, text="Отлично")
        Review.objects.create(service=self.service, user=other, rating=4, text="Хорошо")
        self.service.refresh_from_db()
        self.assertEqual(float(self.service.rating_avg), 4.5)
        self.assertEqual(self.service.reviews_count, 2)

    def test_one_review_per_user(self):
        Review.objects.create(service=self.service, user=self.user, rating=5, text="1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(service=self.service, user=self.user, rating=3, text="2")

    def test_rating_must_be_1_to_5(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(service=self.service, user=self.user, rating=6, text="x")

    def test_favorite_is_unique(self):
        Favorite.objects.create(user=self.user, service=self.service)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favorite.objects.create(user=self.user, service=self.service)

    def test_booking_request_duplicate_key_rejected(self):
        first = BookingRequest.objects.create(service=self.service, name="Алия", phone="+77001234567")
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookingRequest.objects.create(
                service=self.service, name="Алия", phone="+77001234567", idempotency_key=first.idempotency_key,
            )


class SeedDemoTests(TestCase):
    def test_seed_is_idempotent_and_marks_demo(self):
        call_command("seed_demo", verbosity=0)
        first_count = Service.objects.count()
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Service.objects.count(), first_count)
        self.assertGreaterEqual(City.objects.count(), 3)
        self.assertFalse(Service.objects.filter(is_demo=False).exists())
        self.assertFalse(Service.objects.filter(is_verified=True).exists())
        self.assertFalse(any("(демо)" in title for title in Service.objects.values_list("title", flat=True)))
        self.assertFalse(Service.objects.filter(images__isnull=True).exists())
        self.assertEqual(ServiceImage.objects.count(), Service.objects.count())


class CatalogApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_services_filter_by_city_and_category(self):
        response = self.client.get(reverse("catalog:api-services"), {"city": "almaty", "category": "host"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(results)
        self.assertTrue(all(r["city"]["slug"] == "almaty" and r["category"]["slug"] == "host" for r in results))

    def test_services_sorted_by_price(self):
        response = self.client.get(reverse("catalog:api-services"), {"category": "toikhana", "ordering": "price_from"})
        prices = [r["price_from"] for r in response.json()["results"]]
        self.assertEqual(prices, sorted(prices))

    def test_unpublished_services_hidden(self):
        Service.objects.filter(slug="nurlan-host-almaty").update(status=Service.Status.PENDING)
        response = self.client.get(reverse("catalog:api-services"), {"q": "Нурлан"})
        self.assertEqual(response.json()["count"], 0)

    def test_cities_list(self):
        response = self.client.get(reverse("catalog:api-cities"))
        self.assertIn("almaty", [c["slug"] for c in response.json()])


class CatalogPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.service = Service.objects.get(slug="nurlan-host-almaty")

    def test_home_shows_services_from_database(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тойыңызға керектінің бәрі")
        self.assertContains(response, Category.objects.get(slug="toikhana").name_ru)

    def test_catalog_filters_by_city_and_kind(self):
        response = self.client.get(reverse("catalog:list"), {"city": "astana", "kind": "venue"})
        services = list(response.context["page"].object_list)
        self.assertTrue(services)
        self.assertTrue(all(s.city.slug == "astana" and s.category.kind == "venue" for s in services))

    def test_catalog_guests_excludes_small_venues(self):
        response = self.client.get(reverse("catalog:list"), {"kind": "venue", "guests": 700})
        for service in response.context["page"].object_list:
            self.assertGreaterEqual(service.capacity_max, 700)

    def test_catalog_sort_by_price(self):
        response = self.client.get(reverse("catalog:list"), {"category": "host", "sort": "price_asc"})
        prices = [s.price_from for s in response.context["page"].object_list]
        self.assertEqual(prices, sorted(prices))

    def test_catalog_empty_state(self):
        response = self.client.get(reverse("catalog:list"), {"q": "такого-нет-точно"})
        self.assertContains(response, "Ничего не нашлось")

    def test_catalog_invalid_filter_does_not_crash(self):
        response = self.client.get(reverse("catalog:list"), {"guests": "abc", "city": "nowhere"})
        self.assertEqual(response.status_code, 200)

    def test_detail_page(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, self.service.title)
        self.assertContains(response, "Учебный проект TOIIM")
        self.assertContains(response, f"https://t.me/toi3_bot?start=service_{self.service.pk}")

    def test_unpublished_detail_is_404(self):
        Service.objects.filter(pk=self.service.pk).update(status=Service.Status.PENDING)
        self.assertEqual(self.client.get(self.service.get_absolute_url()).status_code, 404)

    def _booking_data(self, **overrides):
        import uuid

        data = {
            "name": "Алия", "phone": "+7 700 123 45 67", "guests": 150,
            "message": "Свадьба", "idempotency_key": str(uuid.uuid4()),
        }
        data.update(overrides)
        return data

    def test_booking_request_saved(self):
        response = self.client.post(self.service.get_absolute_url(), self._booking_data(), follow=True)
        self.assertContains(response, "Заявка отправлена")
        booking = BookingRequest.objects.get()
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.guests, 150)

    def test_booking_double_submit_creates_one_request(self):
        data = self._booking_data()
        self.client.post(self.service.get_absolute_url(), data)
        self.client.post(self.service.get_absolute_url(), data)
        self.assertEqual(BookingRequest.objects.count(), 1)

    def test_booking_validation(self):
        response = self.client.post(
            self.service.get_absolute_url(), self._booking_data(phone="123", event_date="2000-01-01"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Введите номер телефона")
        self.assertContains(response, "не может быть в прошлом")
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_booking_requires_csrf(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        response = client.post(self.service.get_absolute_url(), self._booking_data())
        self.assertEqual(response.status_code, 403)


class FavoriteAndReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.service = Service.objects.get(slug="dala-restaurant-almaty")
        cls.user = User.objects.create_user("erlan", first_name="Ерлан", password="Toi-Strong-Pass-2026")

    def test_favorite_requires_login(self):
        response = self.client.post(reverse("catalog:favorite", args=[self.service.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(Favorite.objects.exists())

    def test_favorite_toggle_saved_in_database(self):
        self.client.force_login(self.user)
        url = reverse("catalog:favorite", args=[self.service.slug])
        self.client.post(url)
        self.assertTrue(Favorite.objects.filter(user=self.user, service=self.service).exists())
        response = self.client.get(reverse("accounts:favorites"))
        self.assertContains(response, self.service.title)
        self.client.post(url)
        self.assertFalse(Favorite.objects.filter(user=self.user).exists())

    def test_favorite_get_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("catalog:favorite", args=[self.service.slug])).status_code, 405)

    def test_review_submit_updates_rating(self):
        self.client.force_login(self.user)
        before = self.service.reviews_count
        self.client.post(reverse("catalog:review", args=[self.service.slug]), {"rating": 3, "text": "Неплохо, но шумно было."})
        self.service.refresh_from_db()
        self.assertEqual(self.service.reviews_count, before + 1)
        # повторная отправка обновляет отзыв, а не создаёт второй
        self.client.post(reverse("catalog:review", args=[self.service.slug]), {"rating": 5, "text": "Передумал: всё было отлично!"})
        self.assertEqual(Review.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Review.objects.get(user=self.user).rating, 5)

    def test_review_validation(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("catalog:review", args=[self.service.slug]), {"rating": 9, "text": "ok"}, follow=True)
        self.assertContains(response, "Отзыв не сохранён")
        self.assertFalse(Review.objects.filter(user=self.user).exists())

    def test_owner_cannot_review_own_service(self):
        Service.objects.filter(pk=self.service.pk).update(owner=self.user)
        self.client.force_login(self.user)
        self.client.post(reverse("catalog:review", args=[self.service.slug]), {"rating": 5, "text": "Лучшая площадка в мире!"})
        self.assertFalse(Review.objects.filter(user=self.user).exists())

    def test_anonymous_cannot_review(self):
        self.client.post(reverse("catalog:review", args=[self.service.slug]), {"rating": 5, "text": "Аноним пишет отзыв"})
        self.assertFalse(Review.objects.filter(text__startswith="Аноним").exists())

    def test_my_requests_in_profile(self):
        BookingRequest.objects.create(service=self.service, user=self.user, name="Ерлан", phone="+77001112233")
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, self.service.title)
        self.assertContains(response, "Новая")


class TelegramIntegrationTests(TestCase):
    """Связь с ботом: API услуги, заявки из бота и уведомления. Telegram не вызывается по-настоящему."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.service = Service.objects.published().first()

    def _payload(self, **overrides):
        import uuid

        data = {
            "service": self.service.pk, "name": "Данияр", "phone": "+7 701 111 22 33",
            "guests": 120, "idempotency_key": str(uuid.uuid4()), "telegram_chat_id": 555,
        }
        data.update(overrides)
        return data

    def test_service_detail_api(self):
        response = self.client.get(reverse("catalog:api-service-detail", args=[self.service.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], self.service.title)
        self.assertTrue(response.json()["url"].endswith(self.service.get_absolute_url()))

    def test_unpublished_service_detail_is_404(self):
        Service.objects.filter(pk=self.service.pk).update(status=Service.Status.PENDING)
        response = self.client.get(reverse("catalog:api-service-detail", args=[self.service.pk]))
        self.assertEqual(response.status_code, 404)

    def test_bot_request_needs_key(self):
        url = reverse("catalog:api-requests")
        with self.settings(BOT_API_KEY=""):
            self.assertEqual(self.client.post(url, self._payload(), content_type="application/json").status_code, 403)
        with self.settings(BOT_API_KEY="secret-key"):
            response = self.client.post(url, self._payload(), content_type="application/json", HTTP_X_BOT_KEY="wrong")
            self.assertEqual(response.status_code, 403)
        self.assertEqual(BookingRequest.objects.count(), 0)

    @override_settings(BOT_API_KEY="secret-key")
    def test_bot_request_created_once(self):
        url = reverse("catalog:api-requests")
        payload = self._payload()
        first = self.client.post(url, payload, content_type="application/json", HTTP_X_BOT_KEY="secret-key")
        second = self.client.post(url, payload, content_type="application/json", HTTP_X_BOT_KEY="secret-key")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        booking = BookingRequest.objects.get()
        self.assertEqual(booking.source, BookingRequest.Source.TELEGRAM)
        self.assertEqual(booking.telegram_chat_id, 555)

    @override_settings(BOT_API_KEY="secret-key")
    def test_bot_request_validation(self):
        response = self.client.post(
            reverse("catalog:api-requests"), self._payload(phone="12", event_date="2000-01-01"),
            content_type="application/json", HTTP_X_BOT_KEY="secret-key",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.json())
        self.assertIn("event_date", response.json())
        self.assertEqual(BookingRequest.objects.count(), 0)

    @override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_ADMIN_CHAT_ID="1001")
    def test_website_booking_notifies_admin(self):
        import uuid
        from unittest import mock

        data = {"name": "Алия", "phone": "+7 700 123 45 67", "guests": 80, "idempotency_key": str(uuid.uuid4())}
        with mock.patch("catalog.telegram.send_message", return_value=True) as send:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.service.get_absolute_url(), data)
        send.assert_called_once()
        chat_id, text = send.call_args.args
        self.assertEqual(chat_id, "1001")
        self.assertIn("Алия", text)
        self.assertIn(self.service.title, text)
        self.assertIsNotNone(BookingRequest.objects.get().telegram_notified_at)

    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_ADMIN_CHAT_ID="")
    def test_booking_works_without_telegram_settings(self):
        import uuid

        data = {"name": "Алия", "phone": "+7 700 123 45 67", "idempotency_key": str(uuid.uuid4())}
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.service.get_absolute_url(), data, follow=True)
        self.assertContains(response, "Заявка отправлена")
        self.assertIsNone(BookingRequest.objects.get().telegram_notified_at)

    def test_notification_text_escapes_html(self):
        from .telegram import booking_text

        booking = BookingRequest.objects.create(service=self.service, name="<b>Хак</b>", phone="+77001234567")
        text = booking_text(booking)
        self.assertIn("&lt;b&gt;Хак&lt;/b&gt;", text)

    @override_settings(TELEGRAM_BOT_TOKEN="test-token")
    def test_send_message_failure_is_logged_without_token(self):
        import urllib.error
        from unittest import mock

        from .telegram import send_message

        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertLogs("catalog.telegram", level="WARNING") as logs:
                self.assertFalse(send_message("1001", "привет"))
        self.assertNotIn("test-token", " ".join(logs.output))
