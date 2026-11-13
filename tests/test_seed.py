from app.seed import seed_sample_data
from tests.base import AppTestCase


class SeedAndSmokeTests(AppTestCase):
    def test_seed_is_idempotent_and_pages_render(self):
        with self.app.app_context():
            self.assertTrue(seed_sample_data())
            self.assertFalse(seed_sample_data())
        self.make_user("admin@example.com", role="admin")
        self.make_user("stu@example.com")
        self.login()
        for standard in range(1, 11):
            for view in ("matching", "all"):
                resp = self.client.get(f"/exams/?standard={standard}&view={view}")
                self.assertEqual(resp.status_code, 200, (standard, view))
        body = self.client.get("/exams/?standard=8").get_data(as_text=True)
        self.assertIn("Sample data", body)
        self.assertIn("Sample District Talent Search", body)   # no-rules exam -> verify notice
        for url in ("/", "/select-standard", "/notes/", "/bookmarks/", "/payments/my-orders",
                    "/exams/1", "/notes/1", "/notes/2"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/notes/1/download").status_code, 200)   # free sample note
        self.assertEqual(self.client.get("/notes/2/download").status_code, 403)   # paid sample note locked
        self.assertEqual(self.client.get("/does-not-exist").status_code, 404)
