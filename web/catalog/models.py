"""
Модели каталога TOIIM: города, категории, услуги (площадки и исполнители),
фото, отзывы, избранное и заявки на бронирование.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils.translation import get_language


class TranslatedNameMixin(models.Model):
    """Название на русском и казахском. `name` отдаёт нужный язык сам."""

    name_ru = models.CharField("название (рус.)", max_length=100)
    name_kk = models.CharField("название (каз.)", max_length=100, blank=True)

    class Meta:
        abstract = True

    @property
    def name(self):
        if (get_language() or "ru").startswith("kk") and self.name_kk:
            return self.name_kk
        return self.name_ru

    def __str__(self):
        return self.name_ru


class City(TranslatedNameMixin):
    slug = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField("порядок", default=0)

    class Meta:
        ordering = ["order", "name_ru"]
        verbose_name = "город"
        verbose_name_plural = "города"


class Category(TranslatedNameMixin):
    class Kind(models.TextChoices):
        VENUE = "venue", "Площадка"
        PERFORMER = "performer", "Исполнитель"
        SERVICE = "service", "Услуга"

    slug = models.SlugField(unique=True)
    kind = models.CharField("тип", max_length=20, choices=Kind.choices, default=Kind.SERVICE)
    icon = models.CharField(
        "иконка Lucide", max_length=50, default="sparkles",
        help_text="Имя иконки с lucide.dev, например: building-2, mic, camera",
    )
    order = models.PositiveSmallIntegerField("порядок", default=0)

    class Meta:
        ordering = ["order", "name_ru"]
        verbose_name = "категория"
        verbose_name_plural = "категории"


class ServiceQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Service.Status.PUBLISHED)


class Service(models.Model):
    """Площадка или исполнитель, которого можно найти в каталоге."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PENDING = "pending", "На модерации"
        PUBLISHED = "published", "Опубликовано"
        REJECTED = "rejected", "Отклонено"

    class PriceUnit(models.TextChoices):
        EVENT = "event", "за мероприятие"
        GUEST = "guest", "за гостя"
        HOUR = "hour", "за час"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="владелец", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="services",
    )
    category = models.ForeignKey(Category, verbose_name="категория", on_delete=models.PROTECT, related_name="services")
    city = models.ForeignKey(City, verbose_name="город", on_delete=models.PROTECT, related_name="services")

    title = models.CharField("название", max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    short_description = models.CharField("коротко", max_length=200)
    description = models.TextField("описание", blank=True)

    price_from = models.PositiveIntegerField("цена от, ₸")
    price_unit = models.CharField("за что цена", max_length=10, choices=PriceUnit.choices, default=PriceUnit.EVENT)
    capacity_min = models.PositiveIntegerField("гостей от", null=True, blank=True)
    capacity_max = models.PositiveIntegerField("гостей до", null=True, blank=True)

    address = models.CharField("адрес", max_length=200, blank=True)
    phone = models.CharField("телефон", max_length=30, blank=True)
    instagram = models.CharField("Instagram", max_length=60, blank=True)

    status = models.CharField("статус", max_length=20, choices=Status.choices, default=Status.PENDING)
    is_demo = models.BooleanField(
        "демо-запись", default=False,
        help_text="Пример для показа. Не настоящая компания.",
    )
    is_verified = models.BooleanField("проверено TOIIM", default=False)

    rating_avg = models.DecimalField("рейтинг", max_digits=3, decimal_places=2, default=0)
    reviews_count = models.PositiveIntegerField("отзывов", default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceQuerySet.as_manager()

    class Meta:
        ordering = ["-rating_avg", "-created_at"]
        verbose_name = "услуга"
        verbose_name_plural = "услуги"
        indexes = [
            models.Index(fields=["status", "city", "category"]),
            models.Index(fields=["price_from"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity_min__isnull=True)
                | models.Q(capacity_max__isnull=True)
                | models.Q(capacity_min__lte=models.F("capacity_max")),
                name="service_capacity_range_valid",
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:detail", kwargs={"slug": self.slug})

    @property
    def cover(self):
        """Первое фото услуги (или None)."""
        images = list(self.images.all())
        return images[0] if images else None

    def update_rating(self):
        """Пересчитать средний рейтинг по опубликованным отзывам."""
        stats = self.reviews.filter(is_published=True).aggregate(avg=Avg("rating"), count=Count("id"))
        self.rating_avg = round(stats["avg"] or 0, 2)
        self.reviews_count = stats["count"]
        self.save(update_fields=["rating_avg", "reviews_count"])


class ServiceImage(models.Model):
    """Фото услуги: загруженный файл или ссылка на фото (для демо-данных)."""

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("файл", upload_to="services/%Y/%m/", blank=True)
    image_url = models.URLField("или ссылка на фото", blank=True)
    alt = models.CharField("описание фото", max_length=150, blank=True)
    order = models.PositiveSmallIntegerField("порядок", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "фото"
        verbose_name_plural = "фото"

    def __str__(self):
        return self.alt or f"Фото #{self.pk}"

    @property
    def url(self):
        if self.image:
            return self.image.url
        return self.image_url


class Review(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        "оценка", validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField("отзыв", max_length=2000)
    is_published = models.BooleanField("опубликован", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "отзыв"
        verbose_name_plural = "отзывы"
        constraints = [
            models.UniqueConstraint(fields=["service", "user"], name="one_review_per_user_per_service"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
        ]

    def __str__(self):
        return f"{self.service} — {self.rating}★"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.service.update_rating()

    def delete(self, *args, **kwargs):
        service = self.service
        result = super().delete(*args, **kwargs)
        service.update_rating()
        return result


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "избранное"
        verbose_name_plural = "избранное"
        constraints = [
            models.UniqueConstraint(fields=["user", "service"], name="unique_favorite"),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.service}"


class BookingRequest(models.Model):
    """Заявка клиента исполнителю (с сайта или из Telegram-бота)."""

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        CONTACTED = "contacted", "Связались"
        CONFIRMED = "confirmed", "Подтверждена"
        DECLINED = "declined", "Отклонена"
        CANCELLED = "cancelled", "Отменена клиентом"

    class Source(models.TextChoices):
        WEBSITE = "website", "Сайт"
        TELEGRAM = "telegram", "Telegram-бот"

    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="requests")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="booking_requests",
    )
    name = models.CharField("имя", max_length=100)
    phone = models.CharField("телефон", max_length=30)
    event_date = models.DateField("дата мероприятия", null=True, blank=True)
    guests = models.PositiveIntegerField("гостей", null=True, blank=True)
    message = models.TextField("сообщение", blank=True, max_length=2000)

    status = models.CharField("статус", max_length=20, choices=Status.choices, default=Status.NEW)
    source = models.CharField("откуда", max_length=20, choices=Source.choices, default=Source.WEBSITE)
    # Уникальный ключ запроса: если форму отправят дважды, вторая заявка не создастся.
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    telegram_notified_at = models.DateTimeField("уведомление в Telegram", null=True, blank=True)
    telegram_chat_id = models.BigIntegerField(
        "Telegram chat id клиента", null=True, blank=True,
        help_text="Заполняется, если заявка пришла из бота: по нему бот может ответить клиенту.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "заявка"
        verbose_name_plural = "заявки"

    def __str__(self):
        return f"Заявка #{self.pk}: {self.name} → {self.service}"
