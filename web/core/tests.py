from django.test import TestCase
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
