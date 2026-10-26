from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from catalog.models import City

from .models import Profile

User = get_user_model()


def validate_phone(value):
    digits = "".join(ch for ch in value if ch.isdigit())
    if value and not 10 <= len(digits) <= 15:
        raise forms.ValidationError("Введите номер телефона, например +7 700 000 00 00.")


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(label="Имя", max_length=150)
    email = forms.EmailField(label="Почта")
    phone = forms.CharField(label="Телефон", max_length=30, required=False, validators=[validate_phone])
    role = forms.ChoiceField(
        label="Я регистрируюсь как", choices=Profile.Role.choices, initial=Profile.Role.CLIENT,
        widget=forms.RadioSelect,
    )

    field_order = ["username", "first_name", "email", "phone", "role", "password1", "password2"]

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с такой почтой уже есть. Попробуйте войти.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()  # профиль создаётся сигналом
            profile = user.profile
            profile.role = self.cleaned_data["role"]
            profile.phone = self.cleaned_data.get("phone", "")
            profile.save()
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Имя", max_length=150)
    email = forms.EmailField(label="Почта")
    phone = forms.CharField(label="Телефон", max_length=30, required=False, validators=[validate_phone])
    city = forms.ModelChoiceField(label="Город", queryset=City.objects.all(), required=False, empty_label="Не выбран")
    telegram_chat_id = forms.IntegerField(
        label="Мой Telegram ID", required=False,
        help_text=(
            "Сюда будут приходить заявки клиентов. 1) Откройте "
            f'<a href="https://t.me/{settings.TELEGRAM_BOT_USERNAME}" target="_blank" rel="noopener">нашего бота</a> '
            "и нажмите Start. 2) Напишите боту "
            '<a href="https://t.me/userinfobot" target="_blank" rel="noopener">@userinfobot</a>, '
            "он пришлёт ваш ID (число). 3) Вставьте число сюда."
        ),
    )

    class Meta:
        model = User
        fields = ["first_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = self.instance.profile
        self.fields["phone"].initial = profile.phone
        self.fields["city"].initial = profile.city
        if profile.is_provider:
            self.fields["telegram_chat_id"].initial = profile.telegram_chat_id
        else:
            del self.fields["telegram_chat_id"]

    def clean_telegram_chat_id(self):
        chat_id = self.cleaned_data.get("telegram_chat_id")
        if chat_id and Profile.objects.filter(telegram_chat_id=chat_id).exclude(user=self.instance).exists():
            raise forms.ValidationError("Этот Telegram ID уже привязан к другому аккаунту.")
        return chat_id

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Эта почта уже занята другим пользователем.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile = user.profile
        profile.phone = self.cleaned_data.get("phone", "")
        profile.city = self.cleaned_data.get("city")
        if "telegram_chat_id" in self.fields:
            profile.telegram_chat_id = self.cleaned_data.get("telegram_chat_id")
        if commit:
            profile.save()
        return user
