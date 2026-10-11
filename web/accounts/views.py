from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from catalog.models import Favorite

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
        return redirect("accounts:profile")
    return render(request, "accounts/signup.html", {"form": form, "next": next_url})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль сохранён.")
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
