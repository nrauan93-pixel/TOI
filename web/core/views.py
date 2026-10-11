from django.contrib.staticfiles import finders
from django.db import connection
from django.db.models import Count, Q
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalog.forms import CatalogFilterForm
from catalog.models import Category, City, Service


def home(request):
    """Главная страница: всё берётся из базы данных."""
    published = Service.objects.published().select_related("city", "category").prefetch_related("images")
    categories = Category.objects.annotate(
        total=Count("services", filter=Q(services__status=Service.Status.PUBLISHED))
    ).order_by("order", "name_ru")  # с annotate() порядок из Meta не применяется
    return render(request, "core/home.html", {
        "search_form": CatalogFilterForm(),
        "categories": categories,
        "venues": published.filter(category__kind=Category.Kind.VENUE)[:3],
        "performers": published.exclude(category__kind=Category.Kind.VENUE)[:3],
        "stats": {
            "services": Service.objects.published().count(),
            "cities": City.objects.filter(services__status=Service.Status.PUBLISHED).distinct().count(),
            "categories": Category.objects.count(),
        },
        # Фото для главного экрана: положите файл static/img/hero.jpg, и он появится сам.
        "hero_image": "img/hero.jpg" if finders.find("img/hero.jpg") else None,
    })


@api_view(["GET"])
def health(request):
    """Проверка, что сервер и база данных живы. Пригодится после деплоя."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok", "database": connection.vendor})
