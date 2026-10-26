"""Админка каталога: здесь администратор проверяет и публикует услуги и отзывы."""

from django.contrib import admin

from .models import BookingRequest, Category, City, Favorite, Review, Service, ServiceImage
from .telegram import notify_service_published


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_kk", "slug", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_kk", "kind", "icon", "order")
    list_editable = ("order",)
    list_filter = ("kind",)
    prepopulated_fields = {"slug": ("name_ru",)}


class ServiceImageInline(admin.TabularInline):
    model = ServiceImage
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "city", "price_from", "status", "is_demo", "is_verified", "rating_avg")
    list_filter = ("status", "category", "city", "is_demo", "is_verified")
    search_fields = ("title", "short_description", "description", "address")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("rating_avg", "reviews_count", "created_at", "updated_at")
    autocomplete_fields = ("owner",)
    inlines = [ServiceImageInline]
    actions = ["publish", "reject"]

    @admin.action(description="Опубликовать выбранные услуги")
    def publish(self, request, queryset):
        newly_published = list(
            queryset.exclude(status=Service.Status.PUBLISHED).select_related("owner__profile")
        )
        updated = queryset.update(status=Service.Status.PUBLISHED)
        site_url = request.build_absolute_uri("/").rstrip("/")
        for service in newly_published:
            notify_service_published(service, site_url)
        self.message_user(request, f"Опубликовано: {updated}")

    @admin.action(description="Отклонить выбранные услуги")
    def reject(self, request, queryset):
        updated = queryset.update(status=Service.Status.REJECTED)
        self.message_user(request, f"Отклонено: {updated}")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("service", "user", "rating", "is_published", "created_at")
    list_filter = ("is_published", "rating")
    search_fields = ("text", "service__title", "user__username")
    actions = ["hide"]

    @admin.action(description="Скрыть выбранные отзывы")
    def hide(self, request, queryset):
        # Через save(), чтобы пересчитался рейтинг услуги.
        for review in queryset:
            review.is_published = False
            review.save()
        self.message_user(request, f"Скрыто: {queryset.count()}")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "service", "created_at")


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "service", "event_date", "guests", "status", "source", "created_at")
    list_filter = ("status", "source", "service__city")
    search_fields = ("name", "phone", "service__title")
    readonly_fields = ("idempotency_key", "telegram_notified_at", "telegram_chat_id", "created_at", "updated_at")
