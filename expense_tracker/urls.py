from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/receipts/", include("receipts.urls")),
    path("api/", include("api.urls")),
     path("api/", include("forecasting.urls")),
    # path("accounts/", include("accounts.urls")),
    path("", include("expenses.urls")),
]