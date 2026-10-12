"""Профиль пользователя: клиент или исполнитель, телефон, город, связь с Telegram."""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    class Role(models.TextChoices):
        CLIENT = "client", "Клиент"
        PROVIDER = "provider", "Исполнитель / площадка"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField("роль", max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField("телефон", max_length=30, blank=True)
    city = models.ForeignKey(
        "catalog.City", verbose_name="город", on_delete=models.SET_NULL, null=True, blank=True,
    )
    telegram_chat_id = models.BigIntegerField("Telegram chat id", null=True, blank=True, unique=True)

    class Meta:
        verbose_name = "профиль"
        verbose_name_plural = "профили"

    def __str__(self):
        return f"Профиль {self.user}"

    @property
    def is_provider(self):
        return self.role == self.Role.PROVIDER


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """У каждого нового пользователя автоматически появляется профиль."""
    if created:
        Profile.objects.get_or_create(user=instance)
