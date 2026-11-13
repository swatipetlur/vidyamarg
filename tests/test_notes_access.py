from app.db import execute
from tests.base import AppTestCase


class NoteAccessTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.free = self.add_note(title="Free note", free=True)
        self.paid = self.add_note(title="Paid note", free=False, price=9900)
        self.hidden = self.add_note(title="Hidden note", free=True, published=0)

    def _mark_paid(self, user_id, note_id, status="paid"):
        with self.app.app_context():
            execute("INSERT INTO orders (user_id, note_id, amount_paise, status, provider, provider_order_id) "
                    "VALUES (?, ?, 9900, ?, 'mock', ?)", (user_id, note_id, status, f"o_{user_id}_{note_id}_{status}"))

    def test_free_note_downloads_without_login(self):
        resp = self.client.get(f"/notes/{self.free}/download")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"%PDF"))
        self.assertIn("attachment", resp.headers["Content-Disposition"])

    def test_paid_note_requires_login(self):
        resp = self.client.get(f"/notes/{self.paid}/download")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login", resp.headers["Location"])

    def test_paid_note_forbidden_without_payment(self):
        self.make_user()
        self.login()
        resp = self.client.get(f"/notes/{self.paid}/download")
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn(b"secret body", resp.data)

    def test_pending_failed_cancelled_orders_do_not_unlock(self):
        uid = self.make_user()
        self.login()
        for status in ("created", "pending", "failed", "cancelled"):
            self._mark_paid(uid, self.paid, status)
        self.assertEqual(self.client.get(f"/notes/{self.paid}/download").status_code, 403)

    def test_paid_order_unlocks_only_that_user_and_note(self):
        buyer = self.make_user("buyer@example.com")
        self.make_user("other@example.com")
        self._mark_paid(buyer, self.paid)

        self.login("buyer@example.com")
        self.assertEqual(self.client.get(f"/notes/{self.paid}/download").status_code, 200)

        other_client = self.new_client()
        self.login("other@example.com", client=other_client)
        self.assertEqual(other_client.get(f"/notes/{self.paid}/download").status_code, 403)

    def test_unpublished_note_is_hidden(self):
        self.assertEqual(self.client.get(f"/notes/{self.hidden}").status_code, 404)
        self.assertEqual(self.client.get(f"/notes/{self.hidden}/download").status_code, 404)

    def test_admin_can_open_paid_note(self):
        self.make_user("admin@example.com", role="admin")
        self.login("admin@example.com", admin=True)
        self.assertEqual(self.client.get(f"/notes/{self.paid}/download").status_code, 200)

    def test_missing_file_is_handled(self):
        note = self.add_note(title="No file", free=True, file=False)
        resp = self.client.get(f"/notes/{note}/download")
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get(f"/notes/{note}")
        self.assertIn("not available right now", resp.get_data(as_text=True))

    def test_catalogue_shows_locks_and_groups(self):
        exam = self.add_exam("Grouped Exam")
        self.add_note(exam_id=exam, title="Grouped note", free=False, price=5000)
        body = self.client.get("/notes/").get_data(as_text=True)
        self.assertIn("Grouped Exam", body)
        self.assertIn("Locked", body)
        self.assertNotIn("Hidden note", body)
        self.assertNotIn("secret body", body)

    def test_path_traversal_not_possible_via_ids(self):
        self.assertEqual(self.client.get("/notes/..%2f..%2fetc/download").status_code, 404)
