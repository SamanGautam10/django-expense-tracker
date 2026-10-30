"""
AI insights + month-end spending prediction for the expense tracker.

Design: Python does the maths, Gemini does the explaining.
  1. build_summary()  - aggregates the user's expenses into a small, anonymous
                        summary (monthly totals, month-to-date pace, categories).
  2. build_prediction() - a deterministic "will this month be up or down" call.
  3. ask_gemini()     - sends the summary to Gemini and gets back plain-English
                        insights as JSON. Gemini never invents the numbers.
"""
import calendar
import hashlib
import json
import logging
from collections import defaultdict
from datetime import date, datetime

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CACHE_SECONDS = 60 * 60 * 6          # re-use an answer for 6h unless the data changes
SAME_THRESHOLD = 0.05                # within +/-5% of usual counts as "about the same"
MIN_PRIOR_MONTHS = 2                 # need at least this much history to predict


def _to_date(d):
    if isinstance(d, datetime):
        if timezone.is_aware(d):
            d = timezone.localtime(d)
        return d.date()
    return d


def _round(x):
    return round(float(x), 2)


# --------------------------------------------------------------------------
# 1. Aggregation
# --------------------------------------------------------------------------
def build_summary(rows, budget=0, today=None):
    """
    rows: iterable of dicts with keys 'date', 'amount', 'category'
          (and optionally 'content' - used for the top-5 list).
    """
    today = today or date.today()   # settings has USE_TZ = False, so localdate() would raise
    rows = [
        {**r, "date": _to_date(r["date"]), "amount": float(r["amount"])}
        for r in rows
    ]
    cur_key = (today.year, today.month)
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    month_totals = defaultdict(float)             # (y, m) -> full month total
    month_to_date = defaultdict(float)            # (y, m) -> spend up to today's day-of-month
    cat_cur = defaultdict(float)                  # category spend this month so far
    cat_prior = defaultdict(lambda: defaultdict(float))   # category -> (y, m) -> MTD-equivalent
    weekday_totals = defaultdict(float)
    weekday_days = defaultdict(set)
    cur_rows = []

    for r in rows:
        key = (r["date"].year, r["date"].month)
        month_totals[key] += r["amount"]
        if r["date"].day <= today.day:
            month_to_date[key] += r["amount"]
        cat = r.get("category") or "Uncategorised"
        if key == cur_key:
            if r["date"] <= today:
                cat_cur[cat] += r["amount"]
                cur_rows.append(r)
        elif r["date"].day <= today.day:
            cat_prior[cat][key] += r["amount"]
        weekday_totals[r["date"].weekday()] += r["amount"]
        weekday_days[r["date"].weekday()].add(r["date"])

    prior_keys = sorted(k for k in month_totals if k < cur_key)[-6:]   # last 6 earlier months
    prior_full = [month_totals[k] for k in prior_keys]
    prior_mtd = [month_to_date[k] for k in prior_keys]

    mtd = month_to_date[cur_key]
    summary = {
        "today": today.isoformat(),
        "day_of_month": today.day,
        "days_in_month": days_in_month,
        "currency": getattr(settings, "CURRENCY", "€"),
        "month_budget": _round(budget) if budget else None,
        "spent_so_far_this_month": _round(mtd),
        "previous_months": [
            {"month": f"{y}-{m:02d}", "total": _round(month_totals[(y, m)]),
             "spent_by_same_day": _round(month_to_date[(y, m)])}
            for (y, m) in prior_keys
        ],
        "avg_previous_month_total": _round(sum(prior_full) / len(prior_full)) if prior_full else None,
        "avg_previous_spent_by_same_day": _round(sum(prior_mtd) / len(prior_mtd)) if prior_mtd else None,
    }

    # category comparison: this month so far vs the average for the same point in earlier months
    cats = []
    for cat, amt in sorted(cat_cur.items(), key=lambda kv: -kv[1]):
        prev = cat_prior[cat]
        prev_avg = sum(prev.get(k, 0) for k in prior_keys) / len(prior_keys) if prior_keys else None
        cats.append({"category": cat, "this_month_so_far": _round(amt),
                     "usual_by_same_day": _round(prev_avg) if prev_avg is not None else None})
    summary["categories"] = cats[:8]

    summary["biggest_purchases_this_month"] = [
        {"what": (r.get("content") or "")[:40], "category": r.get("category"), "amount": _round(r["amount"])}
        for r in sorted(cur_rows, key=lambda r: -r["amount"])[:5]
    ]

    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    summary["avg_spend_on_days_with_spending_by_weekday"] = {
        names[d]: _round(weekday_totals[d] / len(weekday_days[d])) for d in sorted(weekday_days)
    }
    summary["prediction"] = build_prediction(summary)
    return summary


# --------------------------------------------------------------------------
# 2. Deterministic prediction
# --------------------------------------------------------------------------
def build_prediction(s):
    usual = s["avg_previous_month_total"]
    usual_mtd = s["avg_previous_spent_by_same_day"]
    n_prior = len(s["previous_months"])
    mtd, day, dim = s["spent_so_far_this_month"], s["day_of_month"], s["days_in_month"]

    if n_prior < MIN_PRIOR_MONTHS or not usual:
        return {"direction": "unknown", "reason": "Not enough history yet (need 2+ earlier months)."}

    # Pace-adjusted: if you're 20% ahead of where you normally are by this day,
    # assume the month ends ~20% above a normal month.
    if usual_mtd and usual_mtd > 0:
        projected = usual * (mtd / usual_mtd)
        method = "pace_vs_usual"
    else:
        projected = mtd / day * dim
        method = "daily_run_rate"

    # Very early in the month the pace signal is noisy - blend towards "usual".
    weight = min(day / 15, 1.0)
    projected = weight * projected + (1 - weight) * usual

    change = (projected - usual) / usual
    direction = "same" if abs(change) <= SAME_THRESHOLD else ("up" if change > 0 else "down")
    confidence = "low" if (n_prior < 3 or day < 7) else ("medium" if day < 20 else "high")
    return {
        "direction": direction,
        "projected_month_total": _round(projected),
        "usual_month_total": _round(usual),
        "change_percent": round(change * 100, 1),
        "method": method,
        "confidence": confidence,
    }


# --------------------------------------------------------------------------
# 3. Gemini
# --------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a friendly, concise personal-finance assistant inside an expense tracker. "
    "You receive a JSON summary of one user's spending. Rules: use ONLY numbers present in "
    "the JSON; never invent figures; do not change the 'prediction' block, just explain it; "
    "refer to amounts with the given currency symbol; be specific (name categories and amounts); "
    "no generic advice like 'track your spending'; this is not professional financial advice."
)

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "insights": {"type": "ARRAY", "items": {"type": "STRING"}},
        "prediction_explanation": {"type": "STRING"},
        "tip": {"type": "STRING"},
    },
    "required": ["insights", "prediction_explanation", "tip"],
}


def ask_gemini(summary):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    prompt = (
        "Spending summary (JSON):\n" + json.dumps(summary) + "\n\n"
        "Return JSON with: 'insights' (3-4 short, specific observations about spending patterns: "
        "categories rising/falling vs usual, weekday habits, big purchases), "
        "'prediction_explanation' (1-2 sentences on why the month is predicted to go "
        "up/down/stay the same, using the prediction block; if direction is 'unknown' say more data is needed), "
        "and 'tip' (one concrete suggestion tied to a specific category or the budget)."
    )
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    resp = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=20,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


# --------------------------------------------------------------------------
# Entry point used by the view
# --------------------------------------------------------------------------
def get_ai_insights(user, rows, budget=0):
    summary = build_summary(rows, budget)
    result = {"prediction": summary["prediction"], "summary": {
        "spent_so_far_this_month": summary["spent_so_far_this_month"],
        "currency": summary["currency"],
        "month_budget": summary["month_budget"],
    }, "insights": [], "prediction_explanation": "", "tip": "", "ai_error": None}

    if not summary["previous_months"] and summary["spent_so_far_this_month"] == 0:
        result["ai_error"] = "Add some expenses to get insights."
        return result

    cache_key = "ai_insights:%s:%s" % (
        user.pk, hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()[:16])
    cached = cache.get(cache_key)
    if cached:
        result.update(cached)
        return result

    try:
        ai = ask_gemini(summary)
        payload = {k: ai.get(k, "" if k != "insights" else []) for k in
                   ("insights", "prediction_explanation", "tip")}
        cache.set(cache_key, payload, CACHE_SECONDS)
        result.update(payload)
    except Exception as exc:       # network, quota, bad JSON, missing key...
        logger.warning("Gemini insights failed: %s", exc)
        result["ai_error"] = "AI insights are unavailable right now."
    return result