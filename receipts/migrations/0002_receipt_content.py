from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("receipts", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="receipt",
            name="content",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
