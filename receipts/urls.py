from django.urls import path
from . import views

urlpatterns = [
    path("", views.receipts, name="receipt-list-upload"),
    path("<int:pk>/", views.receipt_detail, name="receipt-detail"),
    path("<int:pk>/image/", views.receipt_image, name="receipt-image"),
    path("<int:pk>/confirm/", views.confirm_receipt, name="receipt-confirm"),
]
