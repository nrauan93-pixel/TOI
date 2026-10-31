"""Кабинет исполнителя: свои услуги и заявки клиентов к ним."""

import uuid
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import BusySlotForm, PhotoUploadForm, ServiceForm, ServicePackageForm
from .models import BookingRequest, BusySlot, Service, ServiceImage, ServicePackage
from .photos import MAX_PHOTOS, add_photos, make_main
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
        .annotate(
            new_requests=Count("requests", filter=Q(requests__status=BookingRequest.Status.NEW), distinct=True),
            photos_count=Count("images", distinct=True),
            packages_count=Count("packages", distinct=True),
            busy_count=Count("busy_slots", filter=Q(busy_slots__date__gte=timezone.localdate()), distinct=True),
        )
        .order_by("-created_at")
    )
    requests = (
        BookingRequest.objects.filter(service__owner=request.user)
        .select_related("service", "package").order_by("-created_at")[:50]
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
            is_new = not service.pk
            if is_new:
                service.owner = request.user
                service.slug = unique_slug(service.title)
            # Любая правка снова уходит на проверку, чтобы в каталоге не появилось лишнего.
            service.status = Service.Status.PENDING
            service.is_demo = False
            service.save()
            notify_service_for_review(service, request.build_absolute_uri("/").rstrip("/"))
            if is_new:
                messages.success(request, "Услуга сохранена и отправлена на проверку. Теперь добавьте фото.")
                return redirect("catalog:service-photos", pk=service.pk)
            messages.success(request, "Сохранили и отправили на проверку. После проверки услуга появится в каталоге.")
            return redirect("catalog:cabinet")
        messages.error(request, "Проверьте поля формы: есть ошибки.")
    return render(request, "catalog/service_form.html", {"form": form, "service": service, "tab": "info"})


def _own_service(request, pk):
    return get_object_or_404(Service, pk=pk, owner=request.user)


@provider_required
def service_photos(request, pk):
    service = _own_service(request, pk)
    form = PhotoUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            errors = add_photos(service, form.cleaned_data["photos"])
            for error in errors:
                messages.error(request, error)
            if len(errors) < len(form.cleaned_data["photos"]):
                messages.success(request, "Фото загружены. Первое фото в списке — главное, оно на обложке в каталоге.")
            return redirect("catalog:service-photos", pk=service.pk)
        messages.error(request, "Выберите хотя бы одно фото.")
    return render(request, "catalog/service_photos.html", {
        "service": service, "form": form, "images": service.images.all(), "max_photos": MAX_PHOTOS, "tab": "photos",
    })


@provider_required
@require_POST
def photo_action(request, pk):
    image = get_object_or_404(ServiceImage, pk=pk, service__owner=request.user)
    service_pk = image.service_id
    if request.POST.get("action") == "main":
        make_main(image)
        messages.success(request, "Это фото теперь главное.")
    elif request.POST.get("action") == "delete":
        image.delete()
        messages.success(request, "Фото удалено.")
    return redirect("catalog:service-photos", pk=service_pk)


@provider_required
def service_packages(request, pk, package_pk=None):
    service = _own_service(request, pk)
    package = get_object_or_404(ServicePackage, pk=package_pk, service=service) if package_pk else None
    form = ServicePackageForm(request.POST or None, instance=package)
    if request.method == "POST":
        if form.is_valid():
            item = form.save(commit=False)
            item.service = service
            item.save()
            messages.success(request, "Пакет сохранён. Клиенты увидят его на странице услуги.")
            return redirect("catalog:service-packages", pk=service.pk)
        messages.error(request, "Проверьте поля формы: есть ошибки.")
    return render(request, "catalog/service_packages.html", {
        "service": service, "form": form, "editing": package, "packages": service.packages.all(), "tab": "packages",
    })


@provider_required
@require_POST
def package_delete(request, pk):
    package = get_object_or_404(ServicePackage, pk=pk, service__owner=request.user)
    package.delete()
    messages.success(request, "Пакет удалён.")
    return redirect("catalog:service-packages", pk=package.service_id)


@provider_required
def service_busy(request, pk):
    service = _own_service(request, pk)
    form = BusySlotForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            slot = form.save(commit=False)
            slot.service = service
            slot.save()
            messages.success(request, f"Отмечено: {slot.date:%d.%m.%Y}, {slot.time_label}.")
            return redirect("catalog:service-busy", pk=service.pk)
        messages.error(request, "Проверьте поля формы: есть ошибки.")
    return render(request, "catalog/service_busy.html", {
        "service": service, "form": form, "tab": "busy",
        "slots": service.busy_slots.filter(date__gte=timezone.localdate()),
    })


@provider_required
@require_POST
def busy_delete(request, pk):
    slot = get_object_or_404(BusySlot, pk=pk, service__owner=request.user)
    slot.delete()
    messages.success(request, "Дата снова свободна.")
    return redirect("catalog:service-busy", pk=slot.service_id)


@provider_required
@require_POST
def request_status(request, pk):
    booking = get_object_or_404(BookingRequest, pk=pk, service__owner=request.user)
    status = request.POST.get("status")
    if status in PROVIDER_STATUSES and booking.status != BookingRequest.Status.CANCELLED:
        booking.status = status
        booking.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Заявка #{booking.pk}: {booking.get_status_display().lower()}.")
        if status == BookingRequest.Status.CONFIRMED and booking.event_date:
            # Подтвердили той — этот день сразу становится занятым, чтобы не взять вторую заявку.
            if not booking.service.busy_slots.filter(date=booking.event_date).exists():
                BusySlot.objects.create(service=booking.service, date=booking.event_date, note=f"Заявка #{booking.pk}")
                messages.info(request, f"{booking.event_date:%d.%m.%Y} отмечено занятым в календаре.")
    else:
        messages.error(request, "Этот статус поставить нельзя.")
    return redirect("catalog:cabinet")
