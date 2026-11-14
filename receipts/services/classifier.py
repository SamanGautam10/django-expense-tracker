import re
from functools import lru_cache
from pathlib import Path

import joblib

MODEL_FILE = Path(__file__).resolve().parents[1] / "ml" / "receipt_category.joblib"

# Used only while no trained model exists. Simple keyword rules, not AI,
# and the confidence is None so the UI never presents it as a model probability.
CATEGORY_KEYWORDS = {
    "Groceries": ["tesco", "lidl", "aldi", "asda", "sainsbury", "morrisons", "waitrose", "co-op", "iceland",
                  "carrefour", "supermarket", "grocer", "milk", "bread", "banana", "eggs", "cheese", "butter"],
    "Taxi fare": ["uber", "bolt", "taxi", "cab ", "minicab", "addison lee", "free now", "fare"],
    "Bar tabs": ["pub", "bar ", "tavern", "brewery", "lager", "cocktail", "gin &", "pint", "ale ", "inn "],
    "Electronics": ["currys", "hdmi", "charger", "laptop", "headphone", "usb", "cable", "samsung", "apple store", "phone case"],
    "Online shopping": ["amazon", "ebay", "asos", "etsy", "zalando", "order no", "dispatch", "delivery"],
    "Monthly bill": ["vodafone", "o2", "three ", "virgin media", "british gas", "octopus", "thames water", "council tax",
                     "netflix", "spotify", "audible", "gym", "membership", "subscription", "insurance", "broadband", "electricity"],
}


@lru_cache(maxsize=1)
def get_model():
    if not MODEL_FILE.exists():
        return None
    # Only load model artifacts trained locally / from a trusted source.
    return joblib.load(MODEL_FILE)


def keyword_category(text):
    lowered = " " + text.lower() + " "
    scores = {cat: sum(1 for k in words if re.search(r"(?<![a-z])" + re.escape(k), lowered))
              for cat, words in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else ""


def classify(text):
    if not text.strip():
        return "", None
    model = get_model()
    if model is None:
        return keyword_category(text), None
    probs = model.predict_proba([text])[0]
    idx = int(probs.argmax())
    return str(model.classes_[idx]), round(float(probs[idx]), 4)
