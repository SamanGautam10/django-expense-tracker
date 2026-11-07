"""
Creates a SEPARATE demo user with ~150 days of realistic (synthetic) expenses so the
forecast has enough history to work on. Your real users' data is never touched.

    python manage.py seed_forecast_demo
    -> log in with  forecast_demo / demo12345
"""
import random
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from expenses.models import Expense

USERNAME, PASSWORD = "forecast_demo", "demo12345"

# category -> (typical amount, spread, label); Fri/Sat are busier, Sunday is quiet
CATEGORIES = [
    ("Groceries", 18, 8, "Supermarket"),
    ("Taxi fare", 12, 5, "Taxi"),
    ("Bar tabs", 25, 10, "Bar"),
    ("Online shopping", 30, 15, "Online order"),
    ("Miscellaneous", 9, 4, "Misc"),
]


class Command(BaseCommand):
    help = "Create demo user 'forecast_demo' with synthetic daily expenses."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=150)

    def handle(self, *args, **opts):
        rng = random.Random(42)
        user, _ = User.objects.get_or_create(username=USERNAME)
        user.set_password(PASSWORD)
        user.save()
        Expense.objects.filter(owner=user).delete()

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        created = 0
        for back in range(opts["days"], 0, -1):
            day = today - timedelta(days=back)
            p_spend = {4: 0.85, 5: 0.9, 6: 0.35}.get(day.weekday(), 0.6)
            if rng.random() > p_spend:
                continue
            for _ in range(rng.choice([1, 1, 2])):
                cat, mid, spread, label = rng.choice(CATEGORIES)
                boost = 1.5 if day.weekday() in (4, 5) else 1.0
                amount = max(2, round(rng.gauss(mid * boost, spread), 2))
                Expense.objects.create(owner=user, date=day, amount=amount,
                                       category=cat, content=label, source="Cash")
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Created {created} expenses for '{USERNAME}' (password: {PASSWORD})."))
