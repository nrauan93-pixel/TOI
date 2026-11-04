import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .booking import create_booking
from .forms import BookingRequestForm, CatalogFilterForm, ReviewForm
from .models import BookingRequest, Category, Favorite, Review, Service, ServiceImageBlob

PAGE_SIZE = 9


def catalog_list(request):
    form = CatalogFilterForm(request.GET or None)
    services = Service.objects.published().select_related("city", "category").prefetch_related("images")
    if form.is_bound:
        services = form.filter(services)
    else:
        services = services.order_by("-rating_avg", "-reviews_count")

    page = Paginator(services, PAGE_SIZE).get_page(request.GET.get("page"))
    kind = request.GET.get("kind", "")
    titles = {"venue": "Площадки", "performer": "Исполнители", "service": "Услуги"}
    return render(request, "catalog/list.html", {
        "form": form,
        "page": page,
        "categories": Category.objects.all(),
        "page_title": titles.get(kind, "Каталог"),
        "active_kind": kind,
        "has_filters": any(value for key, value in request.GET.items() if key not in {"page", "sort"}),
    })


def service_detail(request, slug):
    service = get_object_or_404(
        Service.objects.published().select_related("city", "category").prefetch_related("images"), slug=slug,
    )

    if request.method == "POST":
        form = BookingRequestForm(request.POST, service=service)
        if form.is_valid():
            # Повторная отправка той же формы (двойной клик) новую заявку не создаёт.
            create_booking(
                service, form.cleaned_data, source=BookingRequest.Source.WEBSITE,
                user=request.user if request.user.is_authenticated else None,
                site_url=request.build_absolute_uri("/").rstrip("/"),
            )
            messages.success(request, "Заявка отправлена. Исполнитель свяжется с вами по телефону.")
            return redirect(service.get_absolute_url() + "#request")
        messages.error(request, "Проверьте поля формы: есть ошибки.")
    else:
        initial = {"idempotency_key": uuid.uuid4()}
        if request.user.is_authenticated:
            initial["name"] = request.user.get_full_name() or request.user.username
            initial["phone"] = getattr(getattr(request.user, "profile", None), "phone", "")
        if request.GET.get("package", "").isdigit():
            initial["package"] = int(request.GET["package"])
        form = BookingRequestForm(initial=initial, service=service)

    my_review = None
    if request.user.is_authenticated:
        my_review = Review.objects.filter(service=service, user=request.user).first()

    similar = (
        Service.objects.published().filter(category=service.category).exclude(pk=service.pk)
        .select_related("city", "category").prefetch_related("images")[:3]
    )
    return render(request, "catalog/detail.html", {
        "service": service,
        "form": form,
        "reviews": service.reviews.filter(is_published=True).select_related("user")[:10],
        "similar": similar,
        "booking_count": BookingRequest.objects.filter(service=service).count(),
        "review_form": ReviewForm(instance=my_review),
        "my_review": my_review,
        "is_owner": request.user.is_authenticated and service.owner_id == request.user.pk,
        "can_review": request.user.is_authenticated and service.owner_id != request.user.pk
        and not _is_provider(request.user),
        "packages": service.packages.all(),
        "busy_slots": service.busy_slots.filter(
            date__gte=timezone.localdate(), date__lte=timezone.localdate() + timedelta(days=90),
        ),
    })


def service_photo(request, pk):
    """Фото, загруженное исполнителем. Адрес у каждого фото свой и не меняется, поэтому кэшируем надолго."""
    blob = get_object_or_404(ServiceImageBlob.objects.only("data", "content_type"), image_id=pk)
    response = HttpResponse(bytes(blob.data), content_type=blob.content_type)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def _back(request, fallback):
    """Вернуть пользователя на страницу, с которой он пришёл (только на наш сайт)."""
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return redirect(next_url)
    return redirect(fallback)


@login_required
@require_POST
def toggle_favorite(request, slug):
    service = get_object_or_404(Service.objects.published(), slug=slug)
    favorite, created = Favorite.objects.get_or_create(user=request.user, service=service)
    if created:
        messages.success(request, "Добавлено в избранное.")
    else:
        favorite.delete()
        messages.success(request, "Убрано из избранного.")
    return _back(request, service.get_absolute_url())


def _is_provider(user):
    """Исполнители не оценивают друг друга: так конкуренты не испортят рейтинг."""
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_provider)


@login_required
@require_POST
def submit_review(request, slug):
    service = get_object_or_404(Service.objects.published(), slug=slug)
    if service.owner_id == request.user.pk:
        messages.error(request, "Нельзя оставить отзыв о своей услуге.")
        return redirect(service.get_absolute_url() + "#reviews")
    if _is_provider(request.user):
        messages.error(request, "Отзывы и оценки оставляют только клиенты.")
        return redirect(service.get_absolute_url() + "#reviews")

    existing = Review.objects.filter(service=service, user=request.user).first()
    form = ReviewForm(request.POST, instance=existing)
    if form.is_valid():
        review = form.save(commit=False)
        review.service = service
        review.user = request.user
        review.save()  # пересчитывает рейтинг услуги
        messages.success(request, "Отзыв обновлён." if existing else "Спасибо за отзыв!")
    else:
        errors = " ".join(e for field in form.errors.values() for e in field)
        messages.error(request, f"Отзыв не сохранён: {errors}")
    return redirect(service.get_absolute_url() + "#reviews")
