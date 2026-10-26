"""Кабинет исполнителя: свои услуги и заявки клиентов к ним."""

import uuid
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import ServiceForm
from .models import BookingRequest, Service, ServiceImage
from .telegram import notify_service_for_review

# Статусы, которые исполнитель ставит заявке сам. «Отменена клиентом» ставит только клиент.
PROVIDER_STATUSES = [
    BookingRequest.Status.NEW, BookingRequest.Status.CONTACTED,
    BookingRequest.Status.CONFIRMED, BookingRequest.Status.DECLINED,
]

TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяәғқңөұүһі",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "i", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
     "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya", "a", "g", "k", "n", "o", "u", "u", "h", "i"],
))


def unique_slug(title):
    """«Тамада Ерлан» → «tamada-erlan-3f9a1c». Хвост из случайных букв, чтобы адрес не совпал с чужим."""
    base = slugify("".join(TRANSLIT.get(ch, ch) for ch in title.lower()))[:150] or "service"
    while True:
        slug = f"{base}-{uuid.uuid4().hex[:6]}"
        if not Service.objects.filter(slug=slug).exists():
            return slug


def provider_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if not (profile and profile.is_provider):
            messages.info(request, "Кабинет нужен исполнителям и площадкам. Включить его можно в профиле.")
            return redirect("accounts:profile")
        return view(request, *args, **kwargs)
    return wrapper


@provider_required
def dashboard(request):
    services = (
        request.user.services.select_related("category", "city")
        .annotate(new_requests=Count("requests", filter=Q(requests__status=BookingRequest.Status.NEW)))
        .order_by("-created_at")
    )
    requests = (
        BookingRequest.objects.filter(service__owner=request.user)
        .select_related("service").order_by("-created_at")[:50]
    )
    return render(request, "catalog/cabinet.html", {
        "services": services,
        "requests": requests,
        "provider_statuses": [(value, BookingRequest.Status(value).label) for value in PROVIDER_STATUSES],
    })


@provider_required
def service_create(request):
    return _service_form(request, None)


@provider_required
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk, owner=request.user)
    return _service_form(request, service)


def _service_form(request, service):
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST":
        if form.is_valid():
            service = form.save(commit=False)
            if not service.pk:
                service.owner = request.user
                service.slug = unique_slug(service.title)
            # Любая правка снова уходит на проверку, чтобы в каталоге не появилось лишнего.
            service.status = Service.Status.PENDING
            service.is_demo = False
            service.save()
            _save_photo(service, form.cleaned_data.get("photo_url"))
            notify_service_for_review(service, request.build_absolute_uri("/").rstrip("/"))
            messages.success(request, "Сохранили и отправили на проверку. После проверки услуга появится в каталоге.")
            return redirect("catalog:cabinet")
        messages.error(request, "Проверьте поля формы: есть ошибки.")
    return render(request, "catalog/service_form.html", {"form": form, "service": service})


def _save_photo(service, url):
    """Фото по ссылке: одна обложка. Пустое поле убирает её."""
    if url:
        ServiceImage.objects.update_or_create(
            service=service, order=0, image="", defaults={"image_url": url, "alt": service.title},
        )
    else:
        service.images.filter(image="").delete()


@provider_required
@require_POST
def request_status(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk, service__owner=request.user)
    status = request.POST.get("status")
    if status in PROVIDER_STATUSES and booking.status != BookingRequest.Status.CANCELLED:
        booking.status = status
        booking.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Заявка #{booking.pk}: {booking.get_status_display().lower()}.")
    else:
        messages.error(request, "Этот статус поставить нельзя.")
    return redirect("catalog:cabinet")
