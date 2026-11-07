
import random
from datetime import datetime, time
from decimal import Decimal
from calendar import monthrange

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from expenses.models import Expense

User = get_user_model()

# Change this to your actual Django username
username = "testuser1"

user = User.objects.get(username=username)

expense_data = {
    "Bar tabs": [
        "Restaurant dinner", "Coffee with friends",
        "Weekend drinks", "Cafe visit", "Food and beverages"
    ],
    "Monthly bill": [
        "Electricity bill", "Internet subscription",
        "Mobile phone bill", "Water bill", "Gas bill"
    ],
    "Online shopping": [
        "Amazon purchase", "Clothing purchase",
        "Online accessories", "Household items", "Online order"
    ],
    "Electronics": [
        "Headphones", "USB cable", "Computer accessories",
        "Mobile charger", "Keyboard purchase"
    ],
    "Groceries": [
        "Weekly groceries", "Supermarket shopping",
        "Fruit and vegetables", "Household groceries",
        "Food shopping"
    ],
    "Taxi fare": [
        "Uber journey", "Taxi to university",
        "Evening taxi", "Airport transport", "Local journey"
    ],
    "Miscellaneous": [
        "Personal expenses", "Stationery",
        "Gift purchase", "Daily expenses", "Other purchases"
    ],
}

categories = list(expense_data.keys())

sources = [
    "Debit Card",
    "Cash",
    "Bank Transfer",
    "PayPal",
    "Credit Card",
]

# September, October and November 2026
months = [
    (2026, 9),
    (2026, 10),
    (2026, 11),
]

expenses = []

for year, month in months:

    # Generate 25 expenses per month
    # November is limited to the 7th (today)
    last_day = monthrange(year, month)[1]

    if year == 2026 and month == 11:
        last_day = 7

    for _ in range(25):

        category = random.choice(categories)

        day = random.randint(1, last_day)

        expense_datetime = datetime.combine(
            datetime(year, month, day).date(),
            time(
                random.randint(8, 22),
                random.randint(0, 59)
            )
        )

        expense_datetime = timezone.make_aware(
            expense_datetime,
            timezone.get_current_timezone()
        )

        amount = Decimal(
            str(round(random.uniform(5, 250), 2))
        )

        content = random.choice(expense_data[category])

        source = random.choice(sources)

        expenses.append(
            Expense(
                amount=amount,
                content=content,
                category=category,
                source=source,
                date=expense_datetime,
                owner=user,
            )
        )

with transaction.atomic():
    Expense.objects.bulk_create(expenses)

print("Successfully generated test expenses!")
print(f"Total records created: {len(expenses)}")
print("September: 25")
print("October: 25")
print("November: 25")
