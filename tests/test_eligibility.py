import unittest

from app.services import eligibility_engine as engine
from tests.base import AppTestCase


def rule(low, high, text=None):
    return {"min_standard": low, "max_standard": high, "criteria_text": text}


class EngineTests(unittest.TestCase):
    def test_eligible_inside_range(self):
        result = engine.evaluate([rule(5, 8, "Pass Std 4")], 6)
        self.assertEqual(result.status, engine.ELIGIBLE)
        self.assertEqual(result.criteria, ("Pass Std 4",))

    def test_boundaries_are_inclusive(self):
        for std in (5, 8):
            self.assertEqual(engine.evaluate([rule(5, 8)], std).status, engine.ELIGIBLE)

    def test_not_eligible_outside_range(self):
        result = engine.evaluate([rule(5, 8)], 9)
        self.assertEqual(result.status, engine.NOT_ELIGIBLE)
        self.assertIn("Standards 5-8", result.message)

    def test_no_rules_asks_to_verify(self):
        self.assertEqual(engine.evaluate([], 3).status, engine.VERIFY)

    def test_incomplete_rule_asks_to_verify(self):
        self.assertEqual(engine.evaluate([rule(4, None)], 9).status, engine.VERIFY)
        self.assertEqual(engine.evaluate([rule(None, None, "text only")], 2).status, engine.VERIFY)

    def test_complete_match_beats_incomplete_rule(self):
        self.assertEqual(engine.evaluate([rule(4, None), rule(6, 7)], 6).status, engine.ELIGIBLE)

    def test_incomplete_rule_blocks_a_definite_no(self):
        self.assertEqual(engine.evaluate([rule(6, 7), rule(None, None)], 2).status, engine.VERIFY)

    def test_multiple_ranges(self):
        rules = [rule(5, 5), rule(8, 8)]
        self.assertEqual(engine.evaluate(rules, 8).status, engine.ELIGIBLE)
        self.assertEqual(engine.evaluate(rules, 6).status, engine.NOT_ELIGIBLE)

    def test_invalid_standard_rejected(self):
        for bad in (0, 11, "5", None):
            with self.assertRaises(ValueError):
                engine.evaluate([rule(1, 10)], bad)


class ExamRouteTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.match = self.add_exam("Std 5 Olympiad", rules=[(5, 5, "Std 5 only")])
        self.other = self.add_exam("Std 9 Contest", rules=[(9, 9, None)])
        self.unknown = self.add_exam("No Data Quiz", rules=[])
        self.hidden = self.add_exam("Hidden Exam", rules=[(5, 5, None)], is_published=0)

    def test_standard_required(self):
        resp = self.client.get("/exams/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/select-standard", resp.headers["Location"])

    def test_invalid_standard_rejected(self):
        for bad in ("0", "11", "abc", ""):
            resp = self.client.get(f"/exams/?standard={bad}")
            self.assertEqual(resp.status_code, 302, bad)

    def test_matching_view_shows_eligible_and_verify_only(self):
        body = self.client.get("/exams/?standard=5").get_data(as_text=True)
        self.assertIn("Std 5 Olympiad", body)
        self.assertIn("Meets stored criteria", body)
        self.assertIn("No Data Quiz", body)
        self.assertIn("Eligibility data is not available", body)
        self.assertNotIn("Std 9 Contest", body)
        self.assertNotIn("Hidden Exam", body)

    def test_all_view_includes_other_standards(self):
        body = self.client.get("/exams/?standard=5&view=all").get_data(as_text=True)
        self.assertIn("Std 9 Contest", body)
        self.assertIn("Meant for other standards", body)

    def test_no_match_shows_empty_state(self):
        body = self.client.get("/exams/?standard=5&q=zzzznothing").get_data(as_text=True)
        self.assertIn("No examinations match Standard 5", body)

    def test_board_filter(self):
        self.add_exam("CBSE Only", rules=[(5, 5, None)], board="CBSE")
        self.add_exam("State Only", rules=[(5, 5, None)], board="State Board")
        body = self.client.get("/exams/?standard=5&board=CBSE").get_data(as_text=True)
        self.assertIn("CBSE Only", body)
        self.assertNotIn("State Only", body)
        self.assertIn("Std 5 Olympiad", body)  # board 'All' stays visible

    def test_search_treats_wildcards_literally(self):
        body = self.client.get("/exams/?standard=5&q=%25").get_data(as_text=True)
        self.assertIn("No examinations match", body)

    def test_detail_hides_unpublished_from_students(self):
        self.assertEqual(self.client.get(f"/exams/{self.hidden}").status_code, 404)
        self.assertEqual(self.client.get(f"/exams/{self.match}").status_code, 200)
        self.assertEqual(self.client.get("/exams/99999").status_code, 404)

    def test_detail_uses_selected_standard(self):
        self.client.get("/exams/?standard=9")
        body = self.client.get(f"/exams/{self.match}").get_data(as_text=True)
        self.assertIn("Not for this standard", body)

    def test_bookmarks(self):
        self.make_user()
        self.login()
        self.post(f"/bookmarks/{self.match}/toggle")
        self.assertIn("Std 5 Olympiad", self.client.get("/bookmarks/").get_data(as_text=True))
        self.post(f"/bookmarks/{self.match}/toggle")
        self.assertIn("not saved any", self.client.get("/bookmarks/").get_data(as_text=True))

    def test_bookmarks_require_student_login(self):
        resp = self.post(f"/bookmarks/{self.match}/toggle")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login", resp.headers["Location"])
