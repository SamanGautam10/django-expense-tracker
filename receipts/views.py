from datetime import datetime, time
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from expenses.models import Expense
from .models import Receipt
from .serializers import ConfirmSerializer, ReceiptSerializer, ReceiptUploadSerializer
from .services.classifier import classify
from .services.extractor import extract_fields
from .services.ocr import extract_ocr


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def receipts(request):
    if request.method == "GET":
        data = Receipt.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response(ReceiptSerializer(data, many=True).data)
    serializer = ReceiptUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    receipt = Receipt.objects.create(user=request.user, image=serializer.validated_data["image"])
    try:
        with receipt.image.open("rb") as file:
            raw_text = extract_ocr(file)
        values = extract_fields(raw_text)
        predicted_category, confidence = classify(raw_text)
        receipt.raw_text = raw_text
        receipt.merchant = values["merchant"]
        receipt.content = values["content"]
        receipt.purchase_date = values["purchase_date"]
        receipt.total = values["total"]
        receipt.predicted_category = predicted_category
        receipt.confidence = confidence
        receipt.status = Receipt.Status.REVIEW
        receipt.save()
    except Exception:
        # Keep OCR failures from being mistaken for successful processing.
        receipt.status = Receipt.Status.FAILED
        receipt.error_message = "OCR failed. Check that Tesseract is installed and the image is readable."
        receipt.save(update_fields=["status", "error_message"])
    return Response(ReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def receipt_detail(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user)
    if request.method == "GET":
        return Response(ReceiptSerializer(receipt).data)
    if receipt.expense_id:
        return Response({"detail": "Cannot delete a confirmed receipt; the expense remains linked."}, status=409)
    receipt.image.delete(save=False)
    receipt.delete()
    return Response(status=204)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def receipt_image(request, pk):
    from django.http import FileResponse
    receipt = get_object_or_404(Receipt, pk=pk, user=request.user)
    response = FileResponse(receipt.image.open("rb"), content_type="image/jpeg" if receipt.image.name.lower().endswith((".jpg", ".jpeg")) else "image/png")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_receipt(request, pk):
    serializer = ConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        receipt = get_object_or_404(Receipt.objects.select_for_update(), pk=pk, user=request.user)
        if receipt.expense_id:
            return Response({"detail": "Already confirmed", "expense": receipt.expense_id}, status=200)
        if receipt.status != Receipt.Status.REVIEW:
            return Response({"detail": "Receipt is not ready for review."}, status=409)
        date_time = timezone.make_aware(datetime.combine(data["purchase_date"], time(12, 0)), timezone.get_current_timezone())
        expense = Expense.objects.create(owner=request.user, amount=data["total"], content=data["content"], category=data["category"], source=data["source"], date=date_time)
        receipt.expense = expense
        receipt.merchant = data["source"]
        receipt.content = data["content"]
        receipt.purchase_date = data["purchase_date"]
        receipt.total = data["total"]
        receipt.status = Receipt.Status.CONFIRMED
        receipt.save(update_fields=["expense", "merchant", "content", "purchase_date", "total", "status"])
    return Response({"detail": "Expense created", "expense": expense.id}, status=201)
