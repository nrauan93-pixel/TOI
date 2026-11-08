from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import BookingRequest, BusySlot, Category, City, Review, Service, ServicePackage

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
        if data.get("date"):
            queryset = queryset.free_on(data["date"])
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
        fields = ["name", "phone", "event_date", "event_time", "guests", "package", "message"]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "event_time": forms.TimeInput(attrs={"type": "time"}),
            "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Например: свадьба, нужен зал и ведущий"}),
            "phone": forms.TextInput(attrs={"type": "tel", "placeholder": "+7 700 000 00 00", "autocomplete": "tel"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
        }

    def __init__(self, *args, service=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = service
        packages = service.packages.all() if service else ServicePackage.objects.none()
        if packages:
            self.fields["package"].queryset = packages
            self.fields["package"].empty_label = "Без пакета"
            self.fields["package"].label_from_instance = lambda p: f"{p.title} — {p.price:,} ₸".replace(",", " ")
        else:
            del self.fields["package"]

    def clean(self):
        data = super().clean()
        date, time = data.get("event_date"), data.get("event_time")
        if self.service and date:
            slots = self.service.busy_slots.filter(date=date)
            if any(slot.is_all_day for slot in slots):
                self.add_error("event_date", "В этот день исполнитель занят. Выберите другую дату.")
            elif time and any(slot.start_time <= time < slot.end_time for slot in slots):
                busy = ", ".join(slot.time_label for slot in slots)
                self.add_error("event_time", f"В это время уже занято ({busy}). Выберите другое время.")
        return data

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


class ServiceForm(forms.ModelForm):
    """Карточка услуги, которую исполнитель заполняет сам в кабинете."""

    class Meta:
        model = Service
        fields = [
            "category", "city", "title", "short_description", "description",
            "price_from", "price_unit", "capacity_min", "capacity_max", "address", "phone", "instagram",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Например: Тамада Ерлан с командой"}),
            "short_description": forms.TextInput(attrs={"placeholder": "Одна строка: чем вы хороши"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Что входит, сколько длится, опыт"}),
            "phone": forms.TextInput(attrs={"type": "tel", "placeholder": "+7 700 000 00 00"}),
            "instagram": forms.TextInput(attrs={"placeholder": "@toiim"}),
        }
        help_texts = {
            "capacity_min": "Для площадок. Исполнителям можно оставить пустым.",
            "price_from": "Примерная цена в тенге, только цифры. Поставьте 0, если цена по запросу.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "Выберите категорию"
        self.fields["city"].empty_label = "Выберите город"

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if phone and not 10 <= len(digits) <= 15:
            raise forms.ValidationError("Введите номер телефона, например +7 700 000 00 00.")
        return phone

    def clean_instagram(self):
        return self.cleaned_data.get("instagram", "").strip().lstrip("@")

    def clean(self):
        data = super().clean()
        low, high = data.get("capacity_min"), data.get("capacity_max")
        if low and high and low > high:
            self.add_error("capacity_max", "«Гостей до» должно быть не меньше, чем «гостей от».")
        return data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Поле для нескольких файлов сразу (как в документации Django)."""

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(item, initial) for item in data]
        return [single(data, initial)]


class PhotoUploadForm(forms.Form):
    photos = MultipleFileField(
        label="Выберите фото", widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        help_text="Можно сразу несколько: главный вид, зал, сцена, детали. До 10 фото на услугу.",
    )


class ServicePackageForm(forms.ModelForm):
    class Meta:
        model = ServicePackage
        fields = ["title", "includes", "price"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Например: Тамада с командой"}),
            "includes": forms.Textarea(attrs={"rows": 5, "placeholder": "Ведущий\nДиджей и звук\nПевец\n2 танцора"}),
        }


class BusySlotForm(forms.ModelForm):
    all_day = forms.BooleanField(label="Занят весь день", required=False, initial=True)

    class Meta:
        model = BusySlot
        fields = ["date", "all_day", "start_time", "end_time", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "note": forms.TextInput(attrs={"placeholder": "Например: свадьба Асель"}),
        }
        help_texts = {"start_time": "Если заняты только часть дня, снимите галочку и укажите время."}

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date < timezone.localdate():
            raise forms.ValidationError("Дата уже прошла.")
        return date

    def clean(self):
        data = super().clean()
        if data.get("all_day"):
            data["start_time"] = data["end_time"] = None
        else:
            start, end = data.get("start_time"), data.get("end_time")
            if not start or not end:
                self.add_error("start_time", "Укажите время «с» и «до» или поставьте «весь день».")
            elif start >= end:
                self.add_error("end_time", "Время «до» должно быть позже, чем «с».")
        return data

    def save(self, commit=True):
        slot = super().save(commit=False)
        if self.cleaned_data.get("all_day"):
            slot.start_time = slot.end_time = None
        if commit:
            slot.save()
        return slot
