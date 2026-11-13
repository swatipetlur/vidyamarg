from tests.base import PASSWORD, AppTestCase


class AuthTests(AppTestCase):
    def test_register_logs_in_a_student(self):
        resp = self.post("/auth/register", {
            "full_name": "Asha Patil", "email": "Asha@Example.com", "password": PASSWORD,
            "confirm_password": PASSWORD, "standard": "7"})
        self.assertEqual(resp.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)
            self.assertEqual(sess["standard"], 7)

    def test_register_validation(self):
        resp = self.post("/auth/register", {"full_name": "A", "email": "bad", "password": "short",
                                            "confirm_password": "other"})
        self.assertEqual(resp.status_code, 400)
        body = resp.get_data(as_text=True)
        self.assertIn("valid email", body)
        self.assertIn("at least 8", body)

    def test_duplicate_email_rejected(self):
        self.make_user("dup@example.com")
        resp = self.post("/auth/register", {"full_name": "Someone", "email": "DUP@example.com",
                                            "password": PASSWORD, "confirm_password": PASSWORD})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already exists", resp.get_data(as_text=True))

    def test_login_and_wrong_password(self):
        self.make_user()
        bad = self.post("/auth/login", {"email": "stu@example.com", "password": "nope-nope-1"})
        self.assertEqual(bad.status_code, 401)
        good = self.login()
        self.assertEqual(good.status_code, 302)

    def test_roles_cannot_cross_login_pages(self):
        self.make_user("admin@example.com", role="admin", name="Admin")
        self.make_user("stu@example.com")
        self.assertEqual(self.login("admin@example.com").status_code, 401)           # admin at student login
        self.assertEqual(self.login("stu@example.com", admin=True).status_code, 401)  # student at admin login
        self.assertEqual(self.login("admin@example.com", admin=True).status_code, 302)

    def test_login_is_throttled(self):
        self.make_user()
        for _ in range(5):
            self.post("/auth/login", {"email": "stu@example.com", "password": "wrong-pass-1"})
        resp = self.login()
        self.assertEqual(resp.status_code, 429)

    def test_open_redirect_is_blocked(self):
        self.make_user()
        resp = self.post("/auth/login?next=//evil.example", {"email": "stu@example.com", "password": PASSWORD})
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("evil.example", resp.headers["Location"])

    def test_csrf_required_on_post(self):
        resp = self.client.post("/auth/login", data={"email": "a@b.co", "password": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_logout_clears_session(self):
        self.make_user()
        self.login()
        self.post("/auth/logout")
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_security_headers_present(self):
        resp = self.client.get("/")
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", resp.headers["Content-Security-Policy"])
