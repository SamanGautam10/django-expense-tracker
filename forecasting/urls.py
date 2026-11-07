from django.urls import path

from forecasting.views import forecast_view

# Mounted under "api/" in expense_tracker/urls.py  ->  GET /api/forecast/
urlpatterns = [
    path("forecast/", forecast_view, name="forecast"),
]
