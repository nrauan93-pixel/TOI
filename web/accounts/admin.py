from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class AddUserForm(AdminUserCreationForm):
    """Админ создаёт аккаунт сразу рабочим: без письма с подтверждением почты."""

    email = forms.EmailField(label="Почта", required=False)
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    role = forms.ChoiceField(label="Кто это", choices=Profile.Role.choices, initial=Profile.Role.PROVIDER)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с такой почтой уже есть.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        user.first_name = self.cleaned_data.get("first_name", "")
        user.is_active = True
        if commit:
            user.save()
            self.save_profile(user)
        return user

    def save_profile(self, user):
        profile = user.profile  # создаётся сигналом при сохранении пользователя
        profile.role = self.cleaned_data["role"]
        profile.save()


admin.site.unregister(User)


@admin.register(User)
class UserWithProfileAdmin(UserAdmin):
    inlines = [ProfileInline]
    add_form = AddUserForm
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("role", "username", "first_name", "email", "usable_password", "password1", "password2"),
        }),
    )

    def get_inlines(self, request, obj):
        # При создании профиль появляется сам (сигнал), второй из формы вызвал бы ошибку.
        return [] if obj is None else super().get_inlines(request, obj)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and isinstance(form, AddUserForm):
            form.save_profile(obj)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "city")
    list_filter = ("role", "city")
    search_fields = ("user__username", "phone")
