from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Favorite
from catalog.telegram import send_message

from .forms import ProfileForm, SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    next_url = request.POST.get("next") or request.GET.get("next", "")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Добро пожаловать в TOIIM, {user.first_name}!")
        if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
            return redirect(next_url)
        if user.profile.is_provider:
            return redirect("catalog:cabinet")
        return redirect("accounts:profile")
    return render(request, "accounts/signup.html", {"form": form, "next": next_url})


@login_required
def profile(request):
    old_chat_id = request.user.profile.telegram_chat_id
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль сохранён.")
            chat_id = request.user.profile.telegram_chat_id
            if chat_id and chat_id != old_chat_id:
                _check_telegram(request, chat_id)
            return redirect("accounts:profile")
        messages.error(request, "Проверьте поля формы: есть ошибки.")
    return render(request, "accounts/profile.html", {
        "form": form,
        "requests": request.user.booking_requests.select_related("service").all()[:20],
        "reviews": request.user.reviews.select_related("service").all()[:20],
        "favorites_count": request.user.favorites.count(),
    })


@login_required
def favorites(request):
    items = (
        Favorite.objects.filter(user=request.user)
        .select_related("service__city", "service__category").prefetch_related("service__images")
    )
    return render(request, "accounts/favorites.html", {"services": [item.service for item in items]})


def _check_telegram(request, chat_id):
    """Сразу отправить пробное сообщение, чтобы исполнитель увидел, что всё работает."""
    if send_message(chat_id, "TOIIM: уведомления подключены. Сюда будут приходить заявки клиентов."):
        messages.success(request, "Отправили пробное сообщение в Telegram. Проверьте чат с ботом.")
    else:
        messages.warning(
            request,
            "Не получилось написать вам в Telegram. Откройте нашего бота, нажмите Start "
            "и проверьте, что ID без ошибок.",
        )


@login_required
@require_POST
def become_provider(request):
    profile = request.user.profile
    profile.role = profile.Role.PROVIDER
    profile.save(update_fields=["role"])
    messages.success(request, "Кабинет исполнителя включён. Добавьте свою первую услугу.")
    return redirect("catalog:cabinet")
