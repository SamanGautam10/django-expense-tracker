"""Train on YOUR labelled real receipts: python -m receipts.ml.train_model --csv receipts/ml/labelled_receipts.csv
Columns: text,category,group (group = receipt source / merchant to avoid leakage).
"""
import argparse
import csv
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from expenses.models import Expense

VALID_CATEGORIES = {choice[0] for choice in Expense.CATEGORY_CHOICES}

def train(csv_path, output_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    if not records or not all({"text", "category", "group"}.issubset(r) for r in records):
        raise ValueError("CSV requires text,category,group columns")
    records = [r for r in records if r["text"].strip() and r["category"] in VALID_CATEGORIES and r["group"].strip()]
    if len(records) < 30 or len(set(r["category"] for r in records)) < 2 or len(set(r["group"] for r in records)) < 4:
        raise ValueError("Provide at least 30 labelled receipts, 2 categories and 4 independent groups; more recommended")
    x = [r["text"] for r in records]; y = [r["category"] for r in records]; groups = [r["group"] for r in records]
    train_indices, test_indices = next(GroupShuffleSplit(test_size=0.25, n_splits=1, random_state=42).split(x, y, groups))
    train_x = [x[i] for i in train_indices]; test_x = [x[i] for i in test_indices]
    train_y = [y[i] for i in train_indices]; test_y = [y[i] for i in test_indices]
    if len(set(train_y)) < 2: raise ValueError("Training split lacks two classes; collect more distinct receipt groups")
    model = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1,2), min_df=1, max_features=8000)),("classifier", LogisticRegression(max_iter=2000, class_weight="balanced"))])
    model.fit(train_x, train_y)
    predictions = model.predict(test_x)
    print(classification_report(test_y, predictions, zero_division=0))
    print("Confusion matrix (model class order):", model.classes_.tolist())
    print(confusion_matrix(test_y, predictions, labels=model.classes_))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    print("Model saved to:", output_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("receipt_category.joblib"))
    args = parser.parse_args()
    train(args.csv, args.output)
