"""Server-side validation of every form. Each function returns (clean, errors)."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from .models.examination import BOARDS, CATEGORIES, MEDIUMS

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _text(form, name, label, *, required=False, max_len=200, errors=None):
    value = (form.get(name) or "").strip()
    if required and not value:
        errors[name] = f"{label} is required."
    elif len(value) > max_len:
        errors[name] = f"{label} must be at most {max_len} characters."
    return value or None


def _int_in_range(form, name, label, low, high, errors):
    raw = (form.get(name) or "").strip()
    if not raw:
        return None
    try:
        number = int(raw)
    except ValueError:
        errors[name] = f"{label} must be a whole number."
        return None
    if not low <= number <= high:
        errors[name] = f"{label} must be between {low} and {high}."
        return None
    return number


def _date(form, name, label, errors):
    raw = (form.get(name) or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        errors[name] = f"{label} must be a valid date (YYYY-MM-DD)."
        return None


# ------------------------------------------------------------------ auth
def validate_registration(form):
    errors = {}
    name = (form.get("full_name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    if not 2 <= len(name) <= 80:
        errors["full_name"] = "Enter your full name (2 to 80 characters)."
    if not EMAIL_RE.match(email) or len(email) > 254:
        errors["email"] = "Enter a valid email address."
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters."
    elif len(password) > 128:
        errors["password"] = "Use at most 128 characters."
    if password != (form.get("confirm_password") or ""):
        errors["confirm_password"] = "The two passwords do not match."
    standard = _int_in_range(form, "standard", "Standard", 1, 10, errors)
    return {"full_name": name, "email": email, "password": password, "standard": standard}, errors


# ----------------------------------------------------------------- exams
def validate_exam(form):
    errors = {}
    clean = {
        "name": _text(form, "name", "Name", required=True, max_len=200, errors=errors),
        "conducting_body": _text(form, "conducting_body", "Conducting body", max_len=200, errors=errors),
        "description": _text(form, "description", "Description", max_len=3000, errors=errors),
        "fee_info": _text(form, "fee_info", "Fee information", max_len=200, errors=errors),
        "category": form.get("category") or "Other",
        "board": form.get("board") or "All",
        "medium": form.get("medium") or "All",
        "exam_date": _date(form, "exam_date", "Exam date", errors),
        "registration_start": _date(form, "registration_start", "Registration start", errors),
        "registration_end": _date(form, "registration_end", "Registration end", errors),
        "link_last_checked": _date(form, "link_last_checked", "Link last checked", errors),
        "is_sample": 1 if form.get("is_sample") else 0,
        "is_published": 1 if form.get("is_published") else 0,
    }
    if clean["category"] not in CATEGORIES:
        errors["category"] = "Choose a valid category."
    if clean["board"] not in BOARDS:
        errors["board"] = "Choose a valid board."
    if clean["medium"] not in MEDIUMS:
        errors["medium"] = "Choose a valid medium."
    start, end = clean["registration_start"], clean["registration_end"]
    if start and end and start > end:
        errors["registration_end"] = "Registration end cannot be before the start."

    url = _text(form, "official_url", "Official link", max_len=500, errors=errors)
    if url and "official_url" not in errors:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors["official_url"] = "Enter a full link starting with http:// or https://."
    clean["official_url"] = url
    return clean, errors


def validate_rule(form):
    errors = {}
    low = _int_in_range(form, "min_standard", "Lowest standard", 1, 10, errors)
    high = _int_in_range(form, "max_standard", "Highest standard", 1, 10, errors)
    if low is not None and high is not None and low > high:
        errors["max_standard"] = "Highest standard cannot be lower than the lowest."
    clean = {
        "min_standard": low,
        "max_standard": high,
        "criteria_text": _text(form, "criteria_text", "Criteria", max_len=500, errors=errors),
        "source_note": _text(form, "source_note", "Source note", max_len=300, errors=errors),
    }
    return clean, errors


# ----------------------------------------------------------------- notes
def validate_note(form, valid_exam_ids):
    errors = {}
    clean = {
        "title": _text(form, "title", "Title", required=True, max_len=200, errors=errors),
        "subject": _text(form, "subject", "Subject", required=True, max_len=100, errors=errors),
        "topic": _text(form, "topic", "Topic", max_len=150, errors=errors),
        "description": _text(form, "description", "Description", max_len=2000, errors=errors),
        "is_published": 1 if form.get("is_published") else 0,
        "is_sample": 1 if form.get("is_sample") else 0,
    }
    exam_id = _int_in_range(form, "exam_id", "Examination", 1, 10**9, errors)
    if exam_id is not None and exam_id not in valid_exam_ids:
        errors["exam_id"] = "Choose an examination from the list."
        exam_id = None
    clean["exam_id"] = exam_id

    access = form.get("access")
    if access not in ("free", "paid"):
        errors["access"] = "Choose free or paid."
        access = "free"
    clean["is_free"] = 1 if access == "free" else 0
    price_paise = 0
    if access == "paid":
        raw = (form.get("price") or "").strip()
        try:
            price = Decimal(raw)
            if price <= 0 or price > Decimal("100000") or price != price.quantize(Decimal("0.01")):
                raise InvalidOperation
            price_paise = int(price * 100)
        except InvalidOperation:
            errors["price"] = "Enter a price in rupees greater than 0 (up to 2 decimals)."
    clean["price_paise"] = price_paise
    return clean, errors
