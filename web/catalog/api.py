"""
API каталога (только чтение). Его будут использовать страницы сайта и Telegram-бот.

GET /api/cities/
GET /api/categories/
GET /api/services/?city=almaty&category=host&q=ведущий&ordering=price_from
GET /api/services/12/            одна услуга (бот открывает её по ссылке t.me/toi3_bot?start=service_12)
POST /api/requests/              заявка из бота, только с заголовком X-Bot-Key
"""

import secrets

from django.conf import settings
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .booking import create_booking
from .models import BookingRequest, Category, City, Service
from .serializers import (
    BookingRequestCreateSerializer, CategorySerializer, CitySerializer, ServiceDetailSerializer, ServiceSerializer,
)

ORDERING_FIELDS = {"price_from", "-price_from", "rating_avg", "-rating_avg", "-created_at"}


class CityList(generics.ListAPIView):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    pagination_class = None


class CategoryList(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None


class ServiceList(generics.ListAPIView):
    serializer_class = ServiceSerializer

    def get_queryset(self):
        qs = Service.objects.published().select_related("city", "category").prefetch_related("images")
        params = self.request.query_params
        if city := params.get("city"):
            qs = qs.filter(city__slug=city)
        if category := params.get("category"):
            qs = qs.filter(category__slug=category)
        if q := params.get("q", "").strip():
            qs = qs.filter(Q(title__icontains=q) | Q(short_description__icontains=q))
        ordering = params.get("ordering")
        if ordering in ORDERING_FIELDS:
            qs = qs.order_by(ordering)
        return qs


class ServiceDetail(generics.RetrieveAPIView):
    serializer_class = ServiceDetailSerializer

    def get_queryset(self):
        return Service.objects.published().select_related("city", "category").prefetch_related("images")


class HasBotKey(permissions.BasePermission):
    """Пускает только запросы с правильным секретным ключом бота в заголовке X-Bot-Key."""

    message = "Нужен правильный ключ бота в заголовке X-Bot-Key."

    def has_permission(self, request, view):
        expected = settings.BOT_API_KEY
        given = request.headers.get("X-Bot-Key", "")
        return bool(expected) and secrets.compare_digest(given.encode(), expected.encode())


class BookingRequestCreate(APIView):
    authentication_classes = []  # бот входит по ключу, а не по логину и cookie
    permission_classes = [HasBotKey]

    def post(self, request):
        serializer = BookingRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking, created = create_booking(
            data["service"], data, source=BookingRequest.Source.TELEGRAM,
            telegram_chat_id=data.get("telegram_chat_id"),
            site_url=request.build_absolute_uri("/").rstrip("/"),
        )
        return Response(
            {"id": booking.pk, "status": booking.status, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
