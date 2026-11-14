from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from decimal import Decimal
from datetime import date
from .models import Receipt
from .services.extractor import extract_fields


class ExtractionTests(TestCase):
    def test_total_prioritises_total_over_subtotal(self):
        values = extract_fields("SHOP\nSUBTOTAL 12.50\nVAT 2.50\nTOTAL £15.00")
        self.assertEqual(values["total"], Decimal("15.00"))

    def test_uncertain_date_is_not_guessed(self):
        self.assertIsNone(extract_fields("SHOP\n03/04/2026\nTOTAL 5.00")["purchase_date"])


LIDL_OCR = """123 Main Street
City, State ZIP
(555) 555-5555
Store: 7645 | Register: 08
Date: 11/25/2025 | Time: 10:21 AM
Organic Milk $5,99
Whole Grain Bread $3,49
Fresh Bananas $3, 98
Subtotal $13,406
Tax $1,14
Total $14,60
Payment Credit Card
Thank you for choosing Lidl!
We hope to see you again soon,
"""


class ExpenseFieldTests(TestCase):
    def test_lidl_receipt_fills_every_expense_field(self):
        v = extract_fields(LIDL_OCR)
        self.assertEqual(v["merchant"], "Lidl")  # not the street address
        self.assertEqual(v["content"], "Organic Milk, Whole Grain Bread, Fresh Bananas")
        self.assertEqual(v["total"], Decimal("14.60"))
        self.assertEqual(v["purchase_date"], date(2025, 11, 25))

    def test_text_month_date_is_read(self):
        self.assertEqual(extract_fields("The Red Lion\n12 Mar 2026\nLager £4.60\nTOTAL £4.60")["purchase_date"], date(2026, 3, 12))

    def test_field_lengths_fit_expense_model(self):
        v = extract_fields("A" * 80 + "\n" + "\n".join(f"Item number {i} here £1.00" for i in range(20)) + "\nTOTAL £20.00")
        self.assertLessEqual(len(v["merchant"]), 30)
        self.assertLessEqual(len(v["content"]), 100)


class ConfirmTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner_receipt", password="pass1234")
        self.other = User.objects.create_user(username="other_receipt", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)
        self.receipt = Receipt.objects.create(user=self.owner, image="receipts/test.png", status="review", merchant="Tesco")
        self.payload = {"source": "Tesco", "content": "milk, bread", "purchase_date": "2026-01-13", "total": "12.50", "category": "Groceries"}

    def test_confirmation_is_idempotent(self):
        url = reverse("receipt-confirm", kwargs={"pk": self.receipt.pk})
        self.assertEqual(self.client.post(url, self.payload, format="json").status_code, 201)
        self.assertEqual(self.client.post(url, self.payload, format="json").status_code, 200)
        from expenses.models import Expense
        self.assertEqual(Expense.objects.filter(owner=self.owner).count(), 1)
        exp = Expense.objects.get(owner=self.owner)
        self.assertEqual((exp.source, exp.content, exp.amount), ("Tesco", "milk, bread", Decimal("12.50")))

    def test_user_cannot_confirm_another_users_receipt(self):
        self.client.force_authenticate(user=self.other)
        url = reverse("receipt-confirm", kwargs={"pk": self.receipt.pk})
        self.assertEqual(self.client.post(url, self.payload, format="json").status_code, 404)
