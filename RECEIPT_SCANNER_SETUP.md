# Receipt scanner — project integration

## What was added

- Django `receipts` app with a `Receipt` table, JPG/PNG validation, OCR, structured extraction, owner-scoped endpoints, atomic expense confirmation, and tests.
- React upload, editable review, and history screens linked into existing navbar and Router.
- Optional TF-IDF + Logistic Regression category classifier. **It deliberately does not fabricate a trained model**; you must train with enough properly labelled data.
- On confirmation, the existing `Expense` model is populated with `content=merchant`, `amount=total`, `category`, `source`, `date`, `owner=request.user`.

## Setup on Windows

1. Activate your existing virtual environment from this project's root.
2. Install your normal project requirements, then `pip install -r receipt-requirements.txt`.
3. Install Tesseract OCR for Windows (e.g. UB Mannheim build). Ensure `tesseract --version` works in a NEW terminal, or configure its executable path with `pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"` in `receipts/services/ocr.py`.
4. Run `python manage.py migrate`.
5. Run `python manage.py test receipts` (requires database and dependencies).
6. Run `python manage.py runserver`.
7. In `front-end`, run `npm install` and `npm start`.
8. Log in and choose **Scan Receipt** from navigation.

## Train the AI category classifier (optional but important for coursework)

Collect and label a real dataset. Make `receipts/ml/labelled_receipts.csv` with columns `text,category,group`. `text` should combine relevant OCR text and the merchant. `category` must match one of the existing Expense category values exactly. `group` must identify related merchants/sources, **not a unique value per row**. Group split prevents a merchant's similar receipts from appearing in both train and test. A *small example file* is included to show the layout but is **not** sufficient training data.

Run:

`python manage.py shell -c "from receipts.ml.train_model import train; from pathlib import Path; train(Path('receipts/ml/labelled_receipts.csv'), Path('receipts/ml/receipt_category.joblib'))"`

The code prints a classification report and confusion matrix. Restart Django after training so cached model loading refreshes. Do not load joblib files from untrusted sources.

## API endpoints

- `POST /api/receipts/` multipart form-data key `image` (synchronous OCR processing)
- `GET /api/receipts/` own history
- `GET /api/receipts/<id>/` result
- `GET /api/receipts/<id>/image/` authenticated image response (browser requests need JWT)
- `POST /api/receipts/<id>/confirm/` JSON `merchant`, `purchase_date`, `total`, `category`, `source`
- `DELETE /api/receipts/<id>/` only if unconfirmed

All routes require the project's JWT authentication. Receipts use `private_media/` and must not be exposed with public media routing or web server alias. Securely back up stored images, exclude private media from version control and provide a privacy/retention policy.

## Limitations and follow-ups

- OCR processing is synchronous: large or many concurrent uploads may require Celery + Redis.
- OCR and total/date extraction are heuristics; the review stage is mandatory.
- `source="Receipt Scan"` is used as a placeholder source; users can edit it.
- React shows the receipt via an authenticated fetch and a temporary browser blob URL.
- Existing user deletion is insecure (`api/views.py` `delete_user` disables authorization): restrict to account owner/admin before production use. This patch only fixes owner-scoping for update/delete expense operations.
- This is a development implementation; validate deployment configuration (DEBUG, secret keys, CORS restrictions, upload rate limits, file retention and storage capacity) before production.
