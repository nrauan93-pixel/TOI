from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import BookingRequest, Category, City, Review, Service

SORT_CHOICES = [
    ("popular", "Сначала популярные"),
    ("price_asc", "Сначала дешевле"),
    ("price_desc", "Сначала дороже"),
    ("new", "Сначала новые"),
]
SORT_ORDERING = {
    "popular": ["-rating_avg", "-reviews_count"],
    "price_asc": ["price_from"],
    "price_desc": ["-price_from"],
    "new": ["-created_at"],
}


class CatalogFilterForm(forms.Form):
    """Фильтры каталога. Все поля необязательные, ошибки просто игнорируются."""

    q = forms.CharField(label="Поиск", required=False, max_length=100)
    city = forms.ModelChoiceField(
        label="Город", queryset=City.objects.all(), to_field_name="slug", required=False, empty_label="Все города",
    )
    category = forms.ModelChoiceField(
        label="Категория", queryset=Category.objects.all(), to_field_name="slug", required=False,
        empty_label="Все категории",
    )
    kind = forms.ChoiceField(label="Тип", choices=[("", "Все")] + list(Category.Kind.choices), required=False)
    date = forms.DateField(label="Дата", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    guests = forms.IntegerField(label="Гостей", required=False, min_value=1, max_value=5000)
    budget = forms.IntegerField(label="Бюджет до, ₸", required=False, min_value=0, max_value=1_000_000_000)
    sort = forms.ChoiceField(label="Сортировка", choices=SORT_CHOICES, required=False)

    def filter(self, queryset):
        data = self.cleaned_data if self.is_valid() else {}
        if q := (data.get("q") or "").strip():
            queryset = queryset.filter(Q(title__icontains=q) | Q(short_description__icontains=q))
        if data.get("city"):
            queryset = queryset.filter(city=data["city"])
        if data.get("category"):
            queryset = queryset.filter(category=data["category"])
        if data.get("kind"):
            queryset = queryset.filter(category__kind=data["kind"])
        guests = data.get("guests")
        if guests:
            # Площадка должна вместить гостей; у исполнителей вместимость не указана.
            queryset = queryset.exclude(capacity_max__lt=guests)
        budget = data.get("budget")
        if budget:
            per_guest = Service.PriceUnit.GUEST
            if guests:
                queryset = queryset.exclude(price_unit=per_guest, price_from__gt=budget / guests)
            queryset = queryset.exclude(price_from__gt=budget)
        return queryset.order_by(*SORT_ORDERING.get(data.get("sort") or "popular", SORT_ORDERING["popular"]))


class BookingRequestForm(forms.ModelForm):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    class Meta:
        model = BookingRequest
        fields = ["name", "phone", "event_date", "guests", "message"]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Например: свадьба, нужен зал и ведущий"}),
            "phone": forms.TextInput(attrs={"type": "tel", "placeholder": "+7 700 000 00 00", "autocomplete": "tel"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError("Введите номер телефона, например +7 700 000 00 00.")
        return phone.strip()

    def clean_event_date(self):
        date = self.cleaned_data.get("event_date")
        if date and date < timezone.localdate():
            raise forms.ValidationError("Дата мероприятия не может быть в прошлом.")
        return date

    def clean_guests(self):
        guests = self.cleaned_data.get("guests")
        if guests is not None and not 1 <= guests <= 5000:
            raise forms.ValidationError("Укажите от 1 до 5000 гостей.")
        return guests


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "text"]
        widgets = {
            "rating": forms.RadioSelect(choices=[(i, str(i)) for i in range(5, 0, -1)]),
            "text": forms.Textarea(attrs={"rows": 4, "placeholder": "Что понравилось, что можно улучшить?"}),
        }

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 10:
            raise forms.ValidationError("Напишите хотя бы пару предложений (от 10 символов).")
        return text
