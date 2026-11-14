from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
from django.conf import settings
import pytesseract

pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000


def validate_receipt_image(upload):
    from rest_framework.exceptions import ValidationError
    if upload.size > MAX_BYTES:
        raise ValidationError({"image": "Maximum file size is 5 MB."})
    if upload.size == 0:
        raise ValidationError({"image": "Image cannot be empty."})
    try:
        with Image.open(upload) as img:
            if img.format not in ("PNG", "JPEG"):
                raise ValidationError({"image": "Only genuine JPG/PNG images are accepted."})
            if img.width * img.height > MAX_PIXELS:
                raise ValidationError({"image": "Image dimensions are too large."})
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError({"image": "Invalid image file."})
    finally:
        upload.seek(0)


def extract_ocr(file_handle):
    file_handle.seek(0)
    with Image.open(file_handle) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        original_text = pytesseract.image_to_string(image, config="--psm 6")
        gray = ImageOps.grayscale(image)
        enhanced = ImageEnhance.Contrast(gray).enhance(2)
        processed_text = pytesseract.image_to_string(enhanced, config="--psm 6")
    # A heuristic for initial deployment; compare real extraction accuracy on labelled receipts.
    def score(txt):
        return sum(bool(k in txt.lower()) for k in ("total", "amount", "date")) * 100 + sum(c.isalnum() for c in txt)
    return processed_text if score(processed_text) > score(original_text) else original_text
