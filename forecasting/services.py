"""
Spending forecast: same-weekday-average baseline vs RandomForestRegressor.

Python does the maths (this file); Gemini only explains the result elsewhere.
"""
import hashlib
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Sum
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from expenses.models import Expense

FEATURES = ["h", "dow", "dom", "is_weekend", "r7", "r28", "dow_mean"]
HORIZON = 31            # forecast far enough to cover the rest of any month
WINDOW_DAYS = 180       # only learn from recent habits (old gaps/zeros would swamp the signal)
MIN_DAYS = 60           # minimum length of the daily series
MIN_ACTIVE_DAYS = 20    # minimum number of days that actually have spending
CACHE_SECONDS = 60 * 60
MODEL_DIR = Path(settings.BASE_DIR) / "forecasting" / "saved_models"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def _expenses_df(user):
    """All of THIS user's expenses (never anyone else's), one row per expense."""
    rows = list(Expense.objects.filter(owner=user).values("date", "amount"))
    df = pd.DataFrame(rows, columns=["date", "amount"])
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is not None:                 # in case USE_TZ is ever switched on
        df["date"] = df["date"].dt.tz_localize(None)
    df["date"] = df["date"].dt.normalize()           # 2026-11-06 14:30 -> 2026-11-06
    df["amount"] = df["amount"].astype(float)
    return df


def daily_series(df, today):
    """Daily totals for the last WINDOW_DAYS COMPLETED days (up to yesterday), zero-filled.

    Today is left out on purpose: it isn't over, so "nothing entered yet" is not a real 0
    and would drag every average down. Future-dated expenses are excluded too.
    """
    yesterday = today - pd.Timedelta(days=1)
    past = df[df["date"] <= yesterday]
    if past.empty:
        return pd.Series(dtype=float)
    totals = past.groupby("date")["amount"].sum()
    start = max(totals.index.min(), yesterday - pd.Timedelta(days=WINDOW_DAYS - 1))
    return totals.reindex(pd.date_range(start, yesterday, freq="D"), fill_value=0.0)


# --------------------------------------------------------------------------
# Features (everything is "as of the origin day", so there is no future leakage)
# --------------------------------------------------------------------------
def _origin_features(s, i):
    hist = s.iloc[: i + 1]
    last56 = hist[-56:]
    return {
        "r7": hist[-7:].mean(),
        "r28": hist[-28:].mean(),
        "dow_mean": last56.groupby(last56.index.dayofweek).mean().to_dict(),
    }


def _row(f, t, h):
    return {
        "h": h, "dow": t.dayofweek, "dom": t.day, "is_weekend": int(t.dayofweek >= 5),
        "r7": f["r7"], "r28": f["r28"],
        "dow_mean": f["dow_mean"].get(t.dayofweek, f["r28"]),   # the same-weekday baseline
    }


def build_rows(s, horizon=HORIZON):
    rows = []
    for i in range(28, len(s) - 1):
        f = _origin_features(s, i)
        for h in range(1, min(horizon, len(s) - 1 - i) + 1):
            t = s.index[i + h]
            rows.append({**_row(f, t, h), "origin": s.index[i], "target": t, "y": s.iloc[i + h]})
    return pd.DataFrame(rows)


def new_rf():
    return RandomForestRegressor(n_estimators=150, min_samples_leaf=3, random_state=42, n_jobs=-1)


# --------------------------------------------------------------------------
# Evaluation: time-based split, MAE + RMSE for both models
# --------------------------------------------------------------------------
def evaluate(rows, last_day, test_days=42):
    cutoff = last_day - pd.Timedelta(days=test_days)
    train, test = rows[rows.target <= cutoff], rows[rows.origin > cutoff]
    if len(train) < 100 or test.empty:
        return None
    rf = new_rf().fit(train[FEATURES], train.y)
    preds = {"same_weekday": test.dow_mean.values, "random_forest": rf.predict(test[FEATURES])}
    out = {
        name: {
            "mae": round(float(mean_absolute_error(test.y, p)), 2),
            "rmse": round(float(mean_squared_error(test.y, p) ** 0.5), 2),
        }
        for name, p in preds.items()
    }
    out["winner"] = min(preds, key=lambda k: out[k]["mae"])
    out["test_days"] = test_days
    return out


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def forecast(user, today=None):
    today = pd.Timestamp(today or date.today()).normalize()

    # Cache per user; the key changes whenever the user's expenses change.
    stats = Expense.objects.filter(owner=user).aggregate(
        n=Count("id"), total=Sum("amount"), last_id=Max("id"), last_date=Max("date"))
    key = "forecast:" + hashlib.md5(f"{user.id}|{today}|{stats}".encode()).hexdigest()
    result = cache.get(key)
    if result is None:
        result = _compute(user, today)
        cache.set(key, result, CACHE_SECONDS)

    return _with_budget(result, user)


def _with_budget(result, user):
    """Budget is looked up outside the cache so editing it shows up immediately."""
    if result.get("status") != "ok":
        return result
    budget = float(Expense.objects.get_budget(user) or 0)
    month = dict(result["month"], budget=budget or None)
    if budget:
        month["vs_budget"] = round(month["projected"] - budget, 2)   # + means over budget
    return dict(result, month=month)


def _compute(user, today):
    df = _expenses_df(user)
    s = daily_series(df, today)
    active = int((s > 0).sum()) if len(s) else 0
    if len(s) < MIN_DAYS or active < MIN_ACTIVE_DAYS:
        return {
            "status": "not_enough_data",
            "days_of_history": int(len(s)), "active_days": active,
            "needed_days": MIN_DAYS, "needed_active_days": MIN_ACTIVE_DAYS,
            "window_days": WINDOW_DAYS,
        }

    rows = build_rows(s)
    metrics = evaluate(rows, s.index[-1])

    rf = new_rf().fit(rows[FEATURES], rows.y)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(rf, MODEL_DIR / f"user_{user.id}.joblib")

    f = _origin_features(s, len(s) - 1)
    days = [s.index[-1] + pd.Timedelta(days=h) for h in range(1, HORIZON + 1)]
    X = pd.DataFrame([_row(f, t, h) for h, t in enumerate(days, 1)])[FEATURES]
    base, rfp = X["dow_mean"].values, rf.predict(X)
    use_rf = bool(metrics) and metrics["winner"] == "random_forest"
    best = rfp if use_rf else base

    # Monthly forecast = spent so far (incl. today) + already-dated future expenses
    #                    + what's still expected today + predicted days after today
    first = today.replace(day=1)
    month_end = today + pd.offsets.MonthEnd(0)
    mtd = float(df[(df.date >= first) & (df.date <= today)].amount.sum())
    spent_today = float(df[df.date == today].amount.sum())
    scheduled = float(df[(df.date > today) & (df.date <= month_end)].amount.sum())
    rest_of_today = max(0.0, float(best[0]) - spent_today)            # days[0] is today
    later_days = float(sum(best[k] for k, d in enumerate(days) if today < d <= month_end))
    projected = mtd + scheduled + rest_of_today + later_days

    prev_start = first - pd.DateOffset(months=1)
    previous = float(df[(df.date >= prev_start) & (df.date < first)].amount.sum())

    return {
        "status": "ok",
        "daily": [
            {"date": d.strftime("%Y-%m-%d"), "baseline": round(float(b), 2), "random_forest": round(float(r), 2)}
            for d, b, r in list(zip(days, base, rfp))[:7]
        ],
        "recent_actual": [{"date": d.strftime("%Y-%m-%d"), "amount": round(float(v), 2)} for d, v in s[-14:].items()],
        "metrics": metrics,
        "month": {
            "to_date": round(mtd, 2),
            "scheduled": round(scheduled, 2),
            "projected": round(projected, 2),
            "previous": round(previous, 2),
            "direction": "higher" if projected > previous else "lower",
            "model_used": "random_forest" if use_rf else "same_weekday",
        },
        "data": {"days_of_history": int(len(s)), "active_days": active, "window_days": WINDOW_DAYS,
                 "last_complete_day": s.index[-1].strftime("%Y-%m-%d")},
    }
