from datetime import datetime, timedelta

import pandas as pd
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from expenses.models import Expense
from forecasting import services

TODAY = pd.Timestamp("2026-11-07")   # a Saturday


def add(user, day, amount):
    Expense.objects.create(owner=user, date=day, amount=amount, category="Groceries",
                           content="x", source="Cash")


class ForecastTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("alice", password="pw")
        self.other = User.objects.create_user("bob", password="pw")

    def fill(self, user, days=120, weekday_amount=None):
        for back in range(1, days + 1):
            d = (TODAY - pd.Timedelta(days=back)).to_pydatetime()
            add(user, d, (weekday_amount or {}).get(d.weekday(), 10))

    def test_not_enough_data_is_reported_with_numbers(self):
        add(self.user, datetime(2026, 11, 1), 5)
        out = services.forecast(self.user, today=TODAY)
        self.assertEqual(out["status"], "not_enough_data")
        self.assertEqual(out["active_days"], 1)

    def test_old_gap_does_not_drown_recent_history(self):
        add(self.user, datetime(2023, 5, 8), 7)           # three years ago
        self.fill(self.user, days=90)
        out = services.forecast(self.user, today=TODAY)
        self.assertEqual(out["status"], "ok")
        self.assertLessEqual(out["data"]["days_of_history"], services.WINDOW_DAYS)

    def test_baseline_is_same_weekday_average(self):
        self.fill(self.user, days=120, weekday_amount={5: 50})   # Saturdays cost 50, others 10
        out = services.forecast(self.user, today=TODAY)
        saturday = out["daily"][0]                                # 2026-11-07 (today) is a Saturday
        sunday = out["daily"][1]                                  # 2026-11-08 is a Sunday
        self.assertEqual(sunday["baseline"], 10.0)
        self.assertEqual(saturday["baseline"], 50.0)

    def test_future_dated_expense_is_counted_as_scheduled_not_as_history(self):
        self.fill(self.user, days=120)
        add(self.user, datetime(2026, 11, 12), 570)
        out = services.forecast(self.user, today=TODAY)
        self.assertEqual(out["month"]["scheduled"], 570.0)
        self.assertEqual(out["recent_actual"][-1]["date"], "2026-11-06")   # history ends yesterday
        self.assertEqual(out["recent_actual"][-1]["amount"], 10.0)

    def test_users_only_see_their_own_data(self):
        self.fill(self.user, days=120, weekday_amount={d: 10 for d in range(7)})
        self.fill(self.other, days=120, weekday_amount={d: 99 for d in range(7)})
        out = services.forecast(self.user, today=TODAY)
        self.assertTrue(all(d["baseline"] == 10.0 for d in out["daily"]))

    def test_endpoint_returns_json_and_requires_login(self):
        client = APIClient()
        self.assertEqual(client.get("/api/forecast/").status_code, 401)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(AccessToken.for_user(self.user)))
        res = client.get("/api/forecast/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/json")   # NOT the React index.html
        self.assertIn("status", res.json())
