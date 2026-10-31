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
    path("cabinet/services/<int:pk>/photos/", cabinet.service_photos, name="service-photos"),
    path("cabinet/photos/<int:pk>/", cabinet.photo_action, name="photo-action"),
    path("cabinet/services/<int:pk>/packages/", cabinet.service_packages, name="service-packages"),
    path("cabinet/services/<int:pk>/packages/<int:package_pk>/", cabinet.service_packages, name="package-edit"),
    path("cabinet/packages/<int:pk>/delete/", cabinet.package_delete, name="package-delete"),
    path("cabinet/services/<int:pk>/busy/", cabinet.service_busy, name="service-busy"),
    path("cabinet/busy/<int:pk>/delete/", cabinet.busy_delete, name="busy-delete"),
    path("cabinet/requests/<int:pk>/status/", cabinet.request_status, name="request-status"),
    path("photos/<int:pk>.jpg", views.service_photo, name="photo"),
    path("api/cities/", api.CityList.as_view(), name="api-cities"),
    path("api/categories/", api.CategoryList.as_view(), name="api-categories"),
    path("api/services/", api.ServiceList.as_view(), name="api-services"),
    path("api/services/<int:pk>/", api.ServiceDetail.as_view(), name="api-service-detail"),
    path("api/requests/", api.BookingRequestCreate.as_view(), name="api-requests"),
]
