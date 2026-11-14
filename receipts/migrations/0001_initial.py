from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import receipts.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("expenses", "0020_auto_20210527_2203")]
    operations = [migrations.CreateModel(name="Receipt", fields=[
        ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("image", models.ImageField(upload_to=receipts.models.receipt_path)),
        ("merchant", models.CharField(blank=True, max_length=100)),
        ("purchase_date", models.DateField(blank=True, null=True)),
        ("total", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        ("predicted_category", models.CharField(blank=True, max_length=20)),
        ("confidence", models.FloatField(blank=True, null=True)),
        ("raw_text", models.TextField(blank=True)),
        ("status", models.CharField(choices=[("processing", "Processing"), ("review", "Needs review"), ("failed", "Failed"), ("confirmed", "Confirmed")], default="processing", max_length=12)),
        ("error_message", models.CharField(blank=True, max_length=300)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("expense", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="receipt", to="expenses.expense")),
        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to=settings.AUTH_USER_MODEL)),
    ], options={"ordering": ["-created_at"]})]
