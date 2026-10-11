import uuid

from rest_framework import serializers

from .models import Category, City, Service


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "slug", "name_ru", "name_kk"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "slug", "name_ru", "name_kk", "kind", "icon"]


class ServiceSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            "id", "slug", "title", "short_description", "city", "category",
            "price_from", "price_unit", "capacity_min", "capacity_max",
            "rating_avg", "reviews_count", "is_demo", "is_verified", "cover_url",
        ]

    def get_cover_url(self, obj):
        cover = obj.cover
        return cover.url if cover else None


class ServiceDetailSerializer(ServiceSerializer):
    """Одна услуга целиком: для бота, когда человек пришёл по ссылке с сайта."""

    url = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + ["description", "address", "instagram", "url", "images"]

    def get_url(self, obj):
        request = self.context.get("request")
        path = obj.get_absolute_url()
        return request.build_absolute_uri(path) if request else path

    def get_images(self, obj):
        return [image.url for image in obj.images.all() if image.url]


class BookingRequestCreateSerializer(serializers.Serializer):
    """Заявка из Telegram-бота. Проверки такие же, как у формы на сайте."""

    service = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30)
    event_date = serializers.DateField(required=False, allow_null=True)
    guests = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    idempotency_key = serializers.UUIDField(required=False)
    telegram_chat_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_service(self, value):
        service = Service.objects.published().filter(pk=value).first()
        if service is None:
            raise serializers.ValidationError("Услуга не найдена или не опубликована.")
        return service

    def validate(self, attrs):
        from .forms import BookingRequestForm

        form = BookingRequestForm(data={
            "name": attrs.get("name"), "phone": attrs.get("phone"),
            "event_date": attrs.get("event_date") or "", "guests": attrs.get("guests") or "",
            "message": attrs.get("message", ""), "idempotency_key": attrs.get("idempotency_key") or uuid.uuid4(),
        })
        if not form.is_valid():
            raise serializers.ValidationError({
                field: [error["message"] for error in errors] for field, errors in form.errors.get_json_data().items()
            })
        attrs.update(form.cleaned_data)
        return attrs
