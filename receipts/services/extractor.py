"""Rule-based extraction of the fields the Expense model needs.

Expense field  <- receipt value
--------------------------------------------------
source   (<=30) <- shop / merchant name
content  (<=100)<- short list of items bought
amount          <- grand total
date            <- purchase date
category        <- see classifier.py

Anything we are not sure about is returned empty / None so the user types it
in on the review screen instead of saving a wrong guess.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from dateutil import parser

SOURCE_MAX = 30
CONTENT_MAX = 100

TOTAL_WORDS = re.compile(r"\b(grand\s+total|total\s+due|amount\s+due|balance\s+due|total\s+paid|total)\b", re.I)
BAD_LINES = re.compile(r"\b(subtotal|sub\s*total|vat|tax|change|cashback|discount|saving|savings)\b", re.I)
MONEY = re.compile(r"(?<!\d)(?:£|\$|€)?\s*(\d{1,3}(?:,\d{3})*|\d{1,6})[.,]\s?(\d{2})(?!\d)")
LINE_PRICE = re.compile(r"(?:£|\$|€)?\s*-?\d{1,6}[.,]\s?\d{2}\s*[A-Za-z]?\s*$")

MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
NUMERIC_DATE = re.compile(r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b")
TEXT_DATE = re.compile(
    rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\.?,?\s+\d{{2,4}}|{MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{2,4}})\b",
    re.I,
)

# Shops people actually buy from; matched anywhere in the text.
KNOWN_MERCHANTS = {
    "tesco": "Tesco", "lidl": "Lidl", "aldi": "Aldi", "asda": "Asda", "sainsbury": "Sainsbury's",
    "morrisons": "Morrisons", "waitrose": "Waitrose", "co-op": "Co-op", "iceland": "Iceland",
    "carrefour": "Carrefour", "marks & spencer": "Marks & Spencer", "m&s": "M&S", "boots": "Boots",
    "superdrug": "Superdrug", "greggs": "Greggs", "costa": "Costa", "starbucks": "Starbucks",
    "mcdonald": "McDonald's", "kfc": "KFC", "subway": "Subway", "pret": "Pret A Manger",
    "wilko": "Wilko", "argos": "Argos", "currys": "Currys", "amazon": "Amazon", "uber": "Uber",
    "bolt": "Bolt", "primark": "Primark", "ikea": "IKEA", "b&q": "B&Q", "screwfix": "Screwfix",
}

NOT_A_NAME = re.compile(
    r"\b(street|st\.?|road|rd\.?|avenue|ave\.?|lane|ln\.?|drive|close|way|city|state|zip|postcode|tel|phone|"
    r"store|register|checkout|vat|receipt|invoice|date|time|welcome|thank|please|visit|www|http|order|table|server|cashier)\b",
    re.I,
)
ITEM_SKIP = re.compile(
    r"\b(subtotal|sub\s*total|total|tax|vat|change|cash|card|credit|debit|visa|mastercard|payment|paid|balance|"
    r"saving|savings|promotion|promotions|reduced|clubcard|points|discount|each|tender|rounding|amount|due)\b",
    re.I,
)


def _clean(s):
    return re.sub(r"\s+", " ", s).strip(" -:;|.,'\"")


def extract_merchant(lines, text):
    lowered = text.lower()
    # 1. A shop we know, anywhere on the receipt (logo text is often not OCR'd, but the footer is).
    found = [(lowered.find(key), name) for key, name in KNOWN_MERCHANTS.items() if re.search(r"(?<![a-z])" + re.escape(key), lowered)]
    if found:
        return min(found)[1][:SOURCE_MAX]
    # 2. "Thank you for shopping at / choosing X"
    m = re.search(r"(?:shopping|shopped)\s+(?:at|with)\s+([A-Za-z][\w&' .-]{1,28}?)\s*[!.\n]", text, re.I) or \
        re.search(r"(?:choosing|visiting)\s+([A-Za-z][\w&' .-]{1,28}?)\s*[!.\n]", text, re.I)
    if m:
        return _clean(m.group(1))[:SOURCE_MAX]
    # 3. Website domain, e.g. www.example.com
    m = re.search(r"(?:www\s?\.\s?)([a-z0-9-]{3,})\s?\.\s?(?:com|co\.uk|uk|net|org)", lowered)
    if m:
        return m.group(1).capitalize()[:SOURCE_MAX]
    # 4. First header line that looks like a name (not an address, phone number or noise).
    for line in lines[:8]:
        letters = sum(c.isalpha() for c in line)
        if (len(line) >= 3 and letters >= 3 and letters / len(line) > 0.6 and not line[0].isdigit()
                and not NOT_A_NAME.search(line) and not TOTAL_WORDS.search(line) and not MONEY.search(line)):
            return _clean(line)[:SOURCE_MAX]
    return ""


def extract_content(lines):
    """Short description built from the item lines (lines that end in a price)."""
    items = []
    for line in lines:
        if not LINE_PRICE.search(line) or ITEM_SKIP.search(line):
            continue
        name = LINE_PRICE.sub("", line)
        name = re.sub(r"^\s*\d+\s*[xX@]\s*", "", name)           # "2 x Milk"
        name = re.sub(r"[^A-Za-z0-9&'%/.\- ]", " ", name)       # OCR junk
        name = _clean(name)
        if len(name) >= 3 and sum(c.isalpha() for c in name) >= 3:
            items.append(name)
    out = ""
    for name in items:
        candidate = f"{out}, {name}" if out else name
        if len(candidate) > CONTENT_MAX:
            break
        out = candidate
    return out


def extract_total(lines):
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if BAD_LINES.search(line) or not TOTAL_WORDS.search(line):
            continue
        matches = list(MONEY.finditer(line))
        if not matches and i + 1 < len(lines):          # amount wrapped onto the next line
            matches = list(MONEY.finditer(lines[i + 1]))
        if matches:
            m = matches[-1]
            try:
                return Decimal(m.group(1).replace(",", "") + "." + m.group(2))
            except InvalidOperation:
                continue
    return None


def extract_date(lines):
    today = date.today()
    for line in lines:
        # Unambiguous text dates first ("25 Nov 2025")
        for match in TEXT_DATE.finditer(line):
            try:
                value = parser.parse(match.group(0)).date()
            except (ValueError, OverflowError):
                continue
            if date(2000, 1, 1) <= value <= today:
                return value
        for match in NUMERIC_DATE.finditer(line):
            s = match.group(0)
            try:
                parts = re.split(r"[-/.]", s)
                # Don't silently guess ambiguous formats such as 03/04/2026.
                if len(parts[0]) != 4 and int(parts[0]) <= 12 and int(parts[1]) <= 12 and parts[0] != parts[1]:
                    continue
                value = parser.parse(s, dayfirst=True).date()
                if date(2000, 1, 1) <= value <= today:
                    return value
            except (ValueError, OverflowError):
                continue
    return None


def extract_fields(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merchant = extract_merchant(lines, text)
    return {
        "merchant": merchant,               # -> Expense.source
        "content": extract_content(lines),  # -> Expense.content
        "purchase_date": extract_date(lines),
        "total": extract_total(lines),
    }
