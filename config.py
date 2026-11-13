"""Application configuration for Vidyamarga.

Values are read from environment variables (optionally from a .env file).
Nothing secret is hard-coded except a development-only fallback secret key,
which the app refuses to use when VIDYAMARGA_ENV=production.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"

try:  # python-dotenv is optional
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass

DEFAULT_SECRET = "dev-only-change-me"


def _flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    ENV_NAME = os.environ.get("VIDYAMARGA_ENV", "development")
    SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET)

    # Storage
    DATABASE = os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "vidyamarga.db"))
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", str(INSTANCE_DIR / "protected_notes"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB per request
    ALLOWED_NOTE_EXTENSIONS = {
        "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "odt", "txt",
    }

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Login throttling (per process, per IP + email)
    LOGIN_MAX_FAILURES = 5
    LOGIN_WINDOW_SECONDS = 15 * 60

    # Payments
    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock").lower()  # mock | razorpay
    ALLOW_MOCK_PAYMENTS = _flag("ALLOW_MOCK_PAYMENTS", True)
    MOCK_PAYMENT_SECRET = os.environ.get("MOCK_PAYMENT_SECRET", "")
    CURRENCY = "INR"
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")


class TestConfig(Config):
    TESTING = True
    ENV_NAME = "testing"
    SECRET_KEY = "test-secret-key"
    PAYMENT_PROVIDER = "mock"
    ALLOW_MOCK_PAYMENTS = True
    MOCK_PAYMENT_SECRET = "test-mock-secret"
    RAZORPAY_KEY_ID = ""
    RAZORPAY_KEY_SECRET = ""
    RAZORPAY_WEBHOOK_SECRET = ""
