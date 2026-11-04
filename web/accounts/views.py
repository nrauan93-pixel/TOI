from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode

from catalog.models import Favorite
from catalog.telegram import send_message

from .forms import EmailForm, ProfileForm, ResetForm, SignUpForm
from .security import activation_token, hit_limit, send_activation_email

User = get_user_model()
TOO_MANY = "Слишком много попыток с вашего устройства. Попробуйте через час."


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    next_url = request.POST.get("next") or request.GET.get("next", "")
    form = SignUpForm(request.POST or None)
    if request.method == "POST":
        # Скрытое поле: человек его не видит и не заполняет, а боты заполняют всё подряд.
        if request.POST.get("website"):
            return redirect("accounts:signup")
        if hit_limit(request, "signup", settings.SIGNUPS_PER_IP_PER_HOUR):
            messages.error(request, TOO_MANY)
            return render(request, "accounts/signup.html", {"form": form, "next": next_url}, status=429)
        if form.is_valid():
            if settings.EMAIL_VERIFICATION:
                user = form.save(commit=False)
                user.is_active = False  # войти можно только после подтверждения почты
                form.save_with_profile(user)
                send_activation_email(request, user)
                return render(request, "accounts/check_email.html", {"email": user.email})
            user = form.save()
            login(request, user)
            return _welcome(request, user, next_url)
    return render(request, "accounts/signup.html", {"form": form, "next": next_url})


def _welcome(request, user, next_url=""):
    messages.success(request, f"Добро пожаловать в TOIIM, {user.first_name or user.username}!")
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return redirect(next_url)
    if user.profile.is_provider:
        return redirect("catalog:cabinet")
    return redirect("accounts:profile")


def activate(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is not None and user.is_active:
        messages.info(request, "Почта уже подтверждена. Войдите в аккаунт.")
        return redirect("accounts:login")
    if user is None or not activation_token.check_token(user, token):
        messages.error(request, "Ссылка устарела или неверная. Отправьте письмо ещё раз.")
        return redirect("accounts:resend_activation")
    user.is_active = True
    user.save(update_fields=["is_active"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return _welcome(request, user)


def resend_activation(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if hit_limit(request, "email", settings.EMAILS_PER_IP_PER_HOUR):
            messages.error(request, TOO_MANY)
        else:
            user = User.objects.filter(email__iexact=form.cleaned_data["email"], is_active=False).first()
            if user:
                send_activation_email(request, user)
            # Один и тот же ответ, чтобы по форме нельзя было узнать, чья почта зарегистрирована.
            return render(request, "accounts/check_email.html", {"email": form.cleaned_data["email"]})
    return render(request, "accounts/resend_activation.html", {"form": form})


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = ResetForm
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        if hit_limit(self.request, "email", settings.EMAILS_PER_IP_PER_HOUR):
            messages.error(self.request, TOO_MANY)
            return self.form_invalid(form)
        self.use_https = self.request.is_secure()
        return super().form_valid(form)


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


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

