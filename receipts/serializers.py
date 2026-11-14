from rest_framework import serializers
from expenses.models import Expense
from .models import Receipt
from .services.ocr import validate_receipt_image


class ReceiptUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

    def validate_image(self, value):
        validate_receipt_image(value)
        return value


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = ("id", "merchant", "content", "purchase_date", "total", "predicted_category", "confidence", "status", "error_message", "expense", "created_at")
        read_only_fields = fields


class ConfirmSerializer(serializers.Serializer):
    source = serializers.CharField(max_length=30)      # shop -> Expense.source
    content = serializers.CharField(max_length=100)    # items bought -> Expense.content
    purchase_date = serializers.DateField()
    total = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    category = serializers.ChoiceField(choices=Expense.CATEGORY_CHOICES)
