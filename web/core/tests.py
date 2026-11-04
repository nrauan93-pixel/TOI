from django.test import TestCase, override_settings
from django.urls import reverse


class SkeletonTests(TestCase):
    def test_home_page_opens(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TOIIM")
        self.assertContains(response, "https://t.me/toi3_bot")

    def test_health_endpoint_reports_ok(self):
        response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class EnsureSuperuserTests(TestCase):
    def test_creates_admin_once_from_env(self):
        from unittest import mock

        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        env = {"DJANGO_SUPERUSER_USERNAME": "boss", "DJANGO_SUPERUSER_PASSWORD": "Toi-Strong-Pass-2026"}
        with mock.patch.dict("os.environ", env):
            call_command("ensure_superuser", verbosity=0)
            call_command("ensure_superuser", verbosity=0)
        users = get_user_model().objects.filter(username="boss")
        self.assertEqual(users.count(), 1)
        self.assertTrue(users.get().is_superuser)

    def test_rejects_weak_password(self):
        from unittest import mock

        from django.core.management import CommandError, call_command

        env = {"DJANGO_SUPERUSER_USERNAME": "boss", "DJANGO_SUPERUSER_PASSWORD": "qwerty"}
        with mock.patch.dict("os.environ", env), self.assertRaises(CommandError):
            call_command("ensure_superuser", verbosity=0)


class CsrfFailurePageTests(TestCase):
    def test_csrf_failure_shows_friendly_page(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:signup"), {"username": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Форма устарела", status_code=403)
        self.assertContains(response, "Открыть в браузере", status_code=403)


class BrevoBackendTests(TestCase):
    @override_settings(BREVO_API_KEY="test-key")
    def test_sends_json_to_brevo(self):
        import json
        from unittest import mock

        from django.core.mail import EmailMessage

        from core.email import BrevoEmailBackend

        response = mock.MagicMock(status=201)
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            sent = BrevoEmailBackend().send_messages(
                [EmailMessage("Тема", "Текст", "TOIIM <hello@example.kz>", ["a@example.kz"])]
            )
        self.assertEqual(sent, 1)
        request = urlopen.call_args[0][0]
        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"email": "hello@example.kz", "name": "TOIIM"})
        self.assertEqual(payload["to"], [{"email": "a@example.kz"}])
        self.assertEqual(request.get_header("Api-key"), "test-key")
