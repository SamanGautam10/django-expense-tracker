from django.contrib import admin
from .models import Receipt

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "merchant", "total", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("merchant", "user__username")
