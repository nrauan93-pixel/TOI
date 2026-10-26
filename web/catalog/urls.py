from django.urls import path

from . import api, cabinet, views

app_name = "catalog"

urlpatterns = [
    path("catalog/", views.catalog_list, name="list"),
    path("services/<slug:slug>/", views.service_detail, name="detail"),
    path("services/<slug:slug>/favorite/", views.toggle_favorite, name="favorite"),
    path("services/<slug:slug>/review/", views.submit_review, name="review"),
    path("cabinet/", cabinet.dashboard, name="cabinet"),
    path("cabinet/services/new/", cabinet.service_create, name="service-create"),
    path("cabinet/services/<int:pk>/edit/", cabinet.service_edit, name="service-edit"),
    path("cabinet/requests/<int:pk>/status/", cabinet.request_status, name="request-status"),
    path("api/cities/", api.CityList.as_view(), name="api-cities"),
    path("api/categories/", api.CategoryList.as_view(), name="api-categories"),
    path("api/services/", api.ServiceList.as_view(), name="api-services"),
    path("api/services/<int:pk>/", api.ServiceDetail.as_view(), name="api-service-detail"),
    path("api/requests/", api.BookingRequestCreate.as_view(), name="api-requests"),
]
