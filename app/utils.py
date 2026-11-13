"""Small helpers shared by routes, services and templates."""
from datetime import date, datetime
from decimal import Decimal


def parse_date(value):
    """'YYYY-MM-DD' (or datetime text) -> date, or None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def today():
    return date.today()


def fmt_date(value):
    parsed = parse_date(value)
    return f"{parsed.day} {parsed.strftime('%b %Y')}" if parsed else ""


def fmt_datetime(value):
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return f"{parsed.day} {parsed.strftime('%b %Y, %H:%M')}"


def rupees(paise):
    if paise is None:
        return ""
    amount = Decimal(int(paise)) / Decimal(100)
    if amount == amount.to_integral():
        return f"\u20b9{int(amount):,}"
    return f"\u20b9{amount:,.2f}"


def registration_state(exam, on=None):
    """Return (key, label) describing where the exam is in its timeline."""
    on = on or today()
    start = parse_date(exam["registration_start"])
    end = parse_date(exam["registration_end"])
    held = parse_date(exam["exam_date"])
    if end and on > end:
        return "closed", "Registration closed"
    if start and on < start:
        return "upcoming", "Registration opens " + fmt_date(exam["registration_start"])
    if start or end:
        return "open", "Registration open"
    if held:
        if on > held:
            return "closed", "Exam date passed"
        return "scheduled", "Exam on " + fmt_date(exam["exam_date"])
    return "unknown", "Dates not announced"


STATE_RANK = {"open": 0, "upcoming": 1, "scheduled": 2, "unknown": 3, "closed": 4}


def is_valid_standard(value):
    return isinstance(value, int) and 1 <= value <= 10


def parse_standard(raw):
    """Return an int 1-10 from user input, or None if invalid."""
    try:
        number = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 10 else None
