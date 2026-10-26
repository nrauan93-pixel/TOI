from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AccountTests(TestCase):
    signup_data = {
        "username": "aliya", "first_name": "Алия", "email": "aliya@example.kz", "phone": "+7 700 111 22 33",
        "role": "provider", "password1": "Toi-Strong-Pass-2026", "password2": "Toi-Strong-Pass-2026",
    }

    def test_signup_creates_user_with_profile_and_logs_in(self):
        response = self.client.post(reverse("accounts:signup"), self.signup_data, follow=True)
        self.assertContains(response, "Добро пожаловать")
        user = User.objects.get(username="aliya")
        self.assertEqual(user.profile.role, "provider")
        self.assertEqual(user.profile.phone, "+7 700 111 22 33")
        self.assertTrue(response.context["user"].is_authenticated)

    def test_signup_rejects_weak_password_and_duplicate_email(self):
        User.objects.create_user("other", email="aliya@example.kz", password="x-Strong-Pass-1")
        data = dict(self.signup_data, password1="12345", password2="12345")
        response = self.client.post(reverse("accounts:signup"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже есть")
        self.assertFalse(User.objects.filter(username="aliya").exists())

    def test_login_and_logout(self):
        User.objects.create_user("daniyar", password="Toi-Strong-Pass-2026")
        response = self.client.post(reverse("accounts:login"), {"username": "daniyar", "password": "Toi-Strong-Pass-2026"})
        self.assertRedirects(response, reverse("accounts:profile"))
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertRedirects(self.client.get(reverse("accounts:profile")), reverse("accounts:login") + "?next=/accounts/profile/")

    def test_wrong_password_shows_error(self):
        User.objects.create_user("daniyar", password="Toi-Strong-Pass-2026")
        response = self.client.post(reverse("accounts:login"), {"username": "daniyar", "password": "wrong"})
        self.assertContains(response, "Неверный логин или пароль")

    def test_profile_update(self):
        user = User.objects.create_user("madina", password="Toi-Strong-Pass-2026")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:profile"), {"first_name": "Мадина", "email": "m@example.kz", "phone": "+77011234567"})
        self.assertRedirects(response, reverse("accounts:profile"))
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Мадина")
        self.assertEqual(user.profile.phone, "+77011234567")

    def test_signup_next_rejects_external_redirect(self):
        data = dict(self.signup_data, role="client", next="https://evil.example.com/")
        response = self.client.post(reverse("accounts:signup"), data)
        self.assertRedirects(response, reverse("accounts:profile"))

    def test_provider_signup_opens_cabinet(self):
        response = self.client.post(reverse("accounts:signup"), self.signup_data)
        self.assertRedirects(response, reverse("catalog:cabinet"))

    def test_provider_saves_telegram_id_and_gets_test_message(self):
        from unittest import mock

        user = User.objects.create_user("erlan", password="Toi-Strong-Pass-2026")
        user.profile.role = "provider"
        user.profile.save()
        self.client.force_login(user)
        data = {"first_name": "Ерлан", "email": "e@example.kz", "telegram_chat_id": "123456789"}
        with mock.patch("accounts.views.send_message", return_value=True) as send:
            response = self.client.post(reverse("accounts:profile"), data, follow=True)
        send.assert_called_once()
        self.assertContains(response, "пробное сообщение")
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.telegram_chat_id, 123456789)

    def test_telegram_id_must_be_unique_and_hidden_for_clients(self):
        taken = User.objects.create_user("taken", password="Toi-Strong-Pass-2026")
        taken.profile.telegram_chat_id = 42
        taken.profile.save()
        user = User.objects.create_user("erlan", password="Toi-Strong-Pass-2026")
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("accounts:profile")), "Telegram ID")
        user.profile.role = "provider"
        user.profile.save()
        response = self.client.post(reverse("accounts:profile"), {"first_name": "Е", "email": "e@example.kz", "telegram_chat_id": "42"})
        self.assertContains(response, "уже привязан")
