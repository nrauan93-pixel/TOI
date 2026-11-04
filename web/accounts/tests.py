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

    def test_signup_starts_with_role_choice(self):
        page = self.client.get(reverse("accounts:signup")).content.decode()
        self.assertLess(page.index('name="role"'), page.index('name="username"'))

    def test_menu_has_budget_calculator_not_duplicate_catalog_links(self):
        page = self.client.get(reverse("core:home"))
        self.assertContains(page, "Калькулятор бюджета")
        nav = page.content.decode().split('data-nav>')[1].split('</nav>')[0]
        self.assertNotIn("kind=venue", nav)
        self.assertNotIn("kind=performer", nav)


from django.core import mail  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.test import override_settings  # noqa: E402


@override_settings(EMAIL_VERIFICATION=True)
class EmailVerificationTests(TestCase):
    data = {
        "username": "dana", "first_name": "Дана", "email": "dana@example.kz", "phone": "",
        "role": "client", "password1": "Toi-Strong-Pass-2026", "password2": "Toi-Strong-Pass-2026",
    }

    def setUp(self):
        cache.clear()

    def _link(self):
        import re

        return re.search(r"http://testserver(/\S+)", mail.outbox[-1].body).group(1)

    def test_signup_requires_email_confirmation(self):
        response = self.client.post(reverse("accounts:signup"), self.data)
        self.assertContains(response, "Проверьте почту")
        user = User.objects.get(username="dana")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["dana@example.kz"])

        # До подтверждения войти нельзя, и сайт говорит почему.
        response = self.client.post(reverse("accounts:login"), {"username": "dana", "password": "Toi-Strong-Pass-2026"})
        self.assertContains(response, "подтвердите почту")

        response = self.client.get(self._link(), follow=True)
        self.assertTrue(response.context["user"].is_authenticated)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # Ссылка одноразовая.
        self.client.logout()
        response = self.client.get(self._link(), follow=True)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_resend_does_not_reveal_unknown_email(self):
        response = self.client.post(reverse("accounts:resend_activation"), {"email": "nobody@example.kz"})
        self.assertContains(response, "Проверьте почту")
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_blocks_bots(self):
        self.client.post(reverse("accounts:signup"), dict(self.data, website="http://spam"))
        self.assertFalse(User.objects.filter(username="dana").exists())

    @override_settings(SIGNUPS_PER_IP_PER_HOUR=2)
    def test_signup_rate_limit_per_ip(self):
        for i in range(2):
            self.client.post(reverse("accounts:signup"), dict(self.data, username=f"bot{i}", email=f"bot{i}@x.kz"))
        response = self.client.post(reverse("accounts:signup"), dict(self.data, username="bot9", email="bot9@x.kz"))
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(username="bot9").exists())


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_reset_password_by_email(self):
        import re

        User.objects.create_user("aru", email="aru@example.kz", password="Old-Strong-Pass-2026")
        response = self.client.post(reverse("accounts:password_reset"), {"email": "aru@example.kz"}, follow=True)
        self.assertContains(response, "Проверьте почту")
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"http://testserver(/\S+)", mail.outbox[0].body).group(1)
        response = self.client.get(link, follow=True)
        new = "New-Strong-Pass-2026"
        response = self.client.post(response.redirect_chain[-1][0], {"new_password1": new, "new_password2": new}, follow=True)
        self.assertContains(response, "Пароль изменён")
        self.assertTrue(self.client.login(username="aru", password=new))

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("accounts:login")), reverse("accounts:password_reset"))


class PasswordResetOtherEmailTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_reset_for_foreign_email_sends_nothing(self):
        User.objects.create_user("aru2", email="mine@example.kz", password="Old-Strong-Pass-2026")
        response = self.client.post(reverse("accounts:password_reset"), {"email": "other@example.kz"}, follow=True)
        self.assertContains(response, "Проверьте почту")
        self.assertEqual(len(mail.outbox), 0)
