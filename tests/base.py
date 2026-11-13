import os
import shutil
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app, security
from app.models import examination as exam_model
from app.models import eligibility as rule_model
from app.models import note as note_model
from app.models import user as user_model
from app.seed import make_pdf
from config import TestConfig

PASSWORD = "correct-horse-1"


class AppTestCase(unittest.TestCase):
    config_overrides = {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        tmp = self.tmp
        overrides = dict(self.config_overrides)

        class Cfg(TestConfig):
            DATABASE = os.path.join(tmp, "test.db")
            UPLOAD_DIR = os.path.join(tmp, "uploads")

        for key, value in overrides.items():
            setattr(Cfg, key, value)
        self.app = create_app(Cfg)
        self.client = self.app.test_client()
        security.reset_throttle()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------- helpers
    def post(self, url, data=None, client=None, **kwargs):
        client = client or self.client
        with client.session_transaction() as sess:
            sess["csrf_token"] = "test-token"
        payload = dict(data or {})
        payload["csrf_token"] = "test-token"
        return client.post(url, data=payload, **kwargs)

    def make_user(self, email="stu@example.com", role="student", standard=None, name="Test Student"):
        with self.app.app_context():
            return user_model.create_user(name, email, generate_password_hash(PASSWORD), role, standard)

    def login(self, email="stu@example.com", admin=False, client=None):
        url = "/auth/admin/login" if admin else "/auth/login"
        return self.post(url, {"email": email, "password": PASSWORD}, client=client)

    def new_client(self):
        return self.app.test_client()

    def add_exam(self, name="Sample Exam", rules=((1, 10, "ok"),), **overrides):
        data = {
            "name": name, "conducting_body": "Body", "description": "Desc", "category": "Olympiad",
            "board": "All", "medium": "All", "exam_date": None, "registration_start": None,
            "registration_end": None, "fee_info": None, "official_url": None, "link_last_checked": None,
            "is_sample": 0, "is_published": 1,
        }
        data.update(overrides)
        with self.app.app_context():
            exam_id = exam_model.create_exam(data)
            for low, high, text in rules:
                rule_model.create_rule(exam_id, {"min_standard": low, "max_standard": high,
                                                 "criteria_text": text, "source_note": None})
        return exam_id

    def add_note(self, exam_id=None, title="A note", free=True, price=0, file=True, published=1):
        stored = None
        if file:
            stored = f"{title.replace(' ', '_')}.pdf"
            os.makedirs(self.app.config["UPLOAD_DIR"], exist_ok=True)
            with open(os.path.join(self.app.config["UPLOAD_DIR"], stored), "wb") as handle:
                handle.write(make_pdf(title, ["secret body"]))
        with self.app.app_context():
            return note_model.create_note({
                "exam_id": exam_id, "subject": "Maths", "topic": None, "title": title,
                "description": "preview", "is_free": 1 if free else 0, "price_paise": 0 if free else price,
                "is_published": published, "is_sample": 0,
            }, stored, f"{title}.pdf" if stored else None)
