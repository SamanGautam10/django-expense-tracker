import uuid
from django.conf import settings
from django.db import models


def receipt_path(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f"receipts/{instance.user_id}/{uuid.uuid4().hex}.{extension}"


class Receipt(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        REVIEW = "review", "Needs review"
        FAILED = "failed", "Failed"
        CONFIRMED = "confirmed", "Confirmed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="receipts")
    image = models.ImageField(upload_to=receipt_path)
    merchant = models.CharField(max_length=100, blank=True)  # saved to Expense.source
    content = models.CharField(max_length=100, blank=True)  # saved to Expense.content (items bought)
    purchase_date = models.DateField(null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    predicted_category = models.CharField(max_length=20, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    raw_text = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROCESSING)
    error_message = models.CharField(max_length=300, blank=True)
    expense = models.OneToOneField("expenses.Expense", on_delete=models.SET_NULL, null=True, blank=True, related_name="receipt")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
