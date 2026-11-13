import io
import os

from app.db import execute
from app.models import audit as audit_model
from app.models import examination as exam_model
from app.models import note as note_model
from app.seed import make_pdf
from tests.base import AppTestCase

EXAM_FORM = {"name": "New Olympiad", "category": "Olympiad", "board": "All", "medium": "All",
             "is_published": "1", "official_url": "https://example.org"}


class AdminTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.make_user("admin@example.com", role="admin", name="Admin")
        self.make_user("stu@example.com")

    def as_admin(self):
        self.login("admin@example.com", admin=True)

    def test_anonymous_redirected_to_admin_login(self):
        for url in ("/admin/", "/admin/exams", "/admin/notes", "/admin/orders", "/admin/audit"):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn("/auth/admin/login", resp.headers["Location"])

    def test_student_gets_403_everywhere(self):
        self.login("stu@example.com")
        for url in ("/admin/", "/admin/exams", "/admin/exams/new", "/admin/notes/new", "/admin/orders"):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.post("/admin/exams/new", EXAM_FORM).status_code, 403)
        self.assertEqual(self.post("/admin/exams/1/delete").status_code, 403)

    def test_admin_pages_render(self):
        self.as_admin()
        exam_id = self.add_exam("Existing")
        note_id = self.add_note(exam_id=exam_id)
        for url in ("/admin/", "/admin/exams", "/admin/exams/new", f"/admin/exams/{exam_id}/edit",
                    f"/admin/exams/{exam_id}/rules/new", "/admin/notes", "/admin/notes/new",
                    f"/admin/notes/{note_id}/edit", "/admin/orders", "/admin/audit"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_exam_crud_and_audit(self):
        self.as_admin()
        resp = self.post("/admin/exams/new", EXAM_FORM)
        self.assertEqual(resp.status_code, 302)
        with self.app.app_context():
            exam = exam_model.list_exams(published_only=False)[0]
        eid = exam["id"]
        self.assertEqual(exam["name"], "New Olympiad")

        self.post(f"/admin/exams/{eid}/edit", dict(EXAM_FORM, name="Renamed", registration_start="2026-01-01",
                                                   registration_end="2026-02-01"))
        with self.app.app_context():
            self.assertEqual(exam_model.get_exam(eid)["name"], "Renamed")

        self.post(f"/admin/exams/{eid}/delete")
        with self.app.app_context():
            self.assertIsNone(exam_model.get_exam(eid))
            actions = [a["action"] for a in audit_model.recent()]
        self.assertEqual(actions[:3], ["delete", "update", "create"])

    def test_exam_validation(self):
        self.as_admin()
        bad = dict(EXAM_FORM, name="", official_url="javascript:alert(1)", registration_start="2026-05-01",
                   registration_end="2026-04-01", category="Nope")
        resp = self.post("/admin/exams/new", bad)
        self.assertEqual(resp.status_code, 400)
        body = resp.get_data(as_text=True)
        for text in ("Name is required", "http://", "cannot be before", "valid category"):
            self.assertIn(text, body)

    def test_rule_crud_and_validation(self):
        self.as_admin()
        eid = self.add_exam("With rules", rules=[])
        self.assertEqual(self.post(f"/admin/exams/{eid}/rules/new", {"min_standard": "9", "max_standard": "3"}).status_code, 400)
        self.assertEqual(self.post(f"/admin/exams/{eid}/rules/new", {"min_standard": "0", "max_standard": "11"}).status_code, 400)
        self.post(f"/admin/exams/{eid}/rules/new", {"min_standard": "3", "max_standard": "6", "criteria_text": "x"})
        self.post("/select-standard", {"standard": "4"})
        self.assertIn("Meets stored criteria", self.client.get(f"/exams/{eid}").get_data(as_text=True))
        with self.app.app_context():
            from app.models import eligibility as rm
            rule = rm.rules_for_exam(eid)[0]
        self.post(f"/admin/rules/{rule['id']}/edit", {"min_standard": "4", "max_standard": "4"})
        with self.app.app_context():
            self.assertEqual(rm.get_rule(rule["id"])["max_standard"], 4)
        self.post(f"/admin/rules/{rule['id']}/delete")
        with self.app.app_context():
            self.assertEqual(rm.rules_for_exam(eid), [])

    def _note_form(self, **extra):
        data = {"title": "Algebra", "subject": "Maths", "access": "paid", "price": "149", "is_published": "1",
                "file": (io.BytesIO(make_pdf("Algebra", ["x"])), "algebra.pdf")}
        data.update(extra)
        return data

    def test_note_create_with_pdf_and_price(self):
        self.as_admin()
        resp = self.post("/admin/notes/new", self._note_form(), content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 302)
        with self.app.app_context():
            note = note_model.list_notes(published_only=False)[0]
        self.assertEqual(note["price_paise"], 14900)
        self.assertTrue(os.path.isfile(os.path.join(self.app.config["UPLOAD_DIR"], note["file_path"])))
        self.assertNotIn("algebra.pdf", note["file_path"])  # random stored name

    def test_note_upload_rules(self):
        self.as_admin()
        cases = [
            self._note_form(file=(io.BytesIO(b"MZ\x90\x00"), "virus.exe")),
            self._note_form(file=(io.BytesIO(b"not really a pdf"), "fake.pdf")),
            self._note_form(file=(io.BytesIO(b""), "empty.pdf")),
            self._note_form(price="0"),
            self._note_form(price="abc"),
            self._note_form(access="maybe"),
        ]
        for data in cases:
            resp = self.post("/admin/notes/new", data, content_type="multipart/form-data")
            self.assertEqual(resp.status_code, 400, data)
        with self.app.app_context():
            self.assertEqual(note_model.count(), 0)

    def test_note_accepts_general_documents(self):
        self.as_admin()
        resp = self.post("/admin/notes/new", self._note_form(
            access="free", price="", file=(io.BytesIO(b"plain notes"), "notes.txt")), content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 302)

    def test_note_edit_replaces_file(self):
        self.as_admin()
        nid = self.add_note(title="Old", free=True)
        with self.app.app_context():
            old = note_model.get_note(nid)["file_path"]
        self.post(f"/admin/notes/{nid}/edit", self._note_form(access="free", price="", title="New title"),
                  content_type="multipart/form-data")
        with self.app.app_context():
            fresh = note_model.get_note(nid)
        self.assertEqual(fresh["title"], "New title")
        self.assertNotEqual(fresh["file_path"], old)
        self.assertFalse(os.path.isfile(os.path.join(self.app.config["UPLOAD_DIR"], old)))

    def test_note_delete_and_unpublish_when_purchased(self):
        self.as_admin()
        plain = self.add_note(title="Plain", free=True)
        sold = self.add_note(title="Sold", free=False, price=5000)
        buyer = self.make_user("buyer@example.com")
        with self.app.app_context():
            execute("INSERT INTO orders (user_id, note_id, amount_paise, status, provider, provider_order_id) "
                    "VALUES (?, ?, 5000, 'paid', 'mock', 'o1')", (buyer, sold))
        self.post(f"/admin/notes/{plain}/delete")
        self.post(f"/admin/notes/{sold}/delete")
        with self.app.app_context():
            self.assertIsNone(note_model.get_note(plain))
            self.assertEqual(note_model.get_note(sold)["is_published"], 0)

    def test_deleting_exam_keeps_its_notes(self):
        self.as_admin()
        eid = self.add_exam("Doomed")
        nid = self.add_note(exam_id=eid, title="Survivor")
        self.post(f"/admin/exams/{eid}/delete")
        with self.app.app_context():
            self.assertIsNone(note_model.get_note(nid)["exam_id"])
