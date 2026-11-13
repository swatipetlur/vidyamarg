import hashlib
import hmac
import json
from unittest import mock

from app.models import order as order_model
from app.services import payments
from app.services.payments import service
from app.services.payments.razorpay_provider import RazorpayProvider
from tests.base import AppTestCase


class MockPaymentTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.note = self.add_note(title="Paid note", free=False, price=19900)
        self.uid = self.make_user()
        self.login()

    def _checkout(self, **extra):
        resp = self.post(f"/payments/checkout/{self.note}", extra)
        self.assertEqual(resp.status_code, 302)
        order_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        return order_id

    def _can_download(self):
        return self.client.get(f"/notes/{self.note}/download").status_code == 200

    def _gateway(self, order_id, outcome):
        return self.post(f"/payments/mock/pay/{order_id}", {"outcome": outcome})

    def test_price_comes_from_database_not_browser(self):
        order_id = self._checkout(amount="1", amount_paise="1", price="1", status="paid")
        with self.app.app_context():
            order = order_model.get_order(order_id)
        self.assertEqual(order["amount_paise"], 19900)
        self.assertEqual(order["status"], "pending")
        self.assertFalse(self._can_download())

    def test_successful_payment_unlocks(self):
        order_id = self._checkout()
        self._gateway(order_id, "success")
        with self.app.app_context():
            self.assertEqual(order_model.get_order(order_id)["status"], "paid")
        self.assertTrue(self._can_download())

    def test_failed_cancelled_pending_stay_locked(self):
        for outcome, expected in (("fail", "failed"), ("cancel", "cancelled"), ("pending", "pending")):
            order_id = self._checkout()
            self._gateway(order_id, outcome)
            with self.app.app_context():
                self.assertEqual(order_model.get_order(order_id)["status"], expected)
            self.assertFalse(self._can_download(), outcome)

    def test_browser_cannot_forge_a_paid_result(self):
        order_id = self._checkout()
        with self.app.app_context():
            provider_order = order_model.get_order(order_id)["provider_order_id"]
        resp = self.post("/payments/verify", {
            "order_id": str(order_id), "provider_order_id": provider_order,
            "provider_payment_id": "mock_pay_forged", "status": "paid",
            "amount_paise": "19900", "signature": "0" * 64})
        self.assertEqual(resp.status_code, 302)
        with self.app.app_context():
            self.assertNotEqual(order_model.get_order(order_id)["status"], "paid")
        self.assertFalse(self._can_download())

    def test_tampering_with_a_genuine_signature_fails(self):
        order_id = self._checkout()
        with self.app.app_context():
            order = order_model.get_order(order_id)
            provider = service.get_provider("mock")
            payload = provider.simulate_gateway(order["provider_order_id"], "pending", order["amount_paise"])
        payload["status"] = "paid"            # change status after signing
        self.post("/payments/verify", dict(payload, order_id=str(order_id)))
        self.assertFalse(self._can_download())

    def test_underpayment_is_rejected_even_if_signed(self):
        order_id = self._checkout()
        with self.app.app_context():
            order = order_model.get_order(order_id)
            provider = service.get_provider("mock")
            payload = provider.simulate_gateway(order["provider_order_id"], "success", 100)  # Rs 1
            fresh, message = service.apply_result(order, provider.verify_payment(payload))
            self.assertNotEqual(fresh["status"], "paid")
            self.assertIn("amount", message)
        self.assertFalse(self._can_download())

    def test_payment_cannot_be_replayed_on_another_order(self):
        first = self._checkout()
        self._gateway(first, "success")
        with self.app.app_context():
            paid_payment = order_model.payments_for_order(first)[0]["provider_payment_id"]
        other_note = self.add_note(title="Other paid", free=False, price=19900)
        resp = self.post(f"/payments/checkout/{other_note}")
        second = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        with self.app.app_context():
            order = order_model.get_order(second)
            provider = service.get_provider("mock")
            payload = provider.simulate_gateway(order["provider_order_id"], "success", 19900)
            payload["provider_payment_id"] = paid_payment
            payload["signature"] = provider._sign(order["provider_order_id"], paid_payment, "paid", 19900)
            fresh, _ = service.apply_result(order, provider.verify_payment(payload))
            self.assertNotEqual(fresh["status"], "paid")

    def test_paid_order_is_never_downgraded(self):
        order_id = self._checkout()
        self._gateway(order_id, "success")
        self.post(f"/payments/{order_id}/cancel")
        with self.app.app_context():
            order = order_model.get_order(order_id)
            provider = service.get_provider("mock")
            service.apply_result(order, provider.verify_payment(
                provider.simulate_gateway(order["provider_order_id"], "fail", 19900)))
            self.assertEqual(order_model.get_order(order_id)["status"], "paid")
        self.assertTrue(self._can_download())

    def test_cannot_buy_free_or_owned_notes(self):
        free = self.add_note(title="Freebie", free=True)
        resp = self.post(f"/payments/checkout/{free}")
        self.assertIn("/notes/", resp.headers["Location"])
        order_id = self._checkout()
        self._gateway(order_id, "success")
        resp = self.post(f"/payments/checkout/{self.note}")
        self.assertIn("/notes/", resp.headers["Location"])
        with self.app.app_context():
            self.assertEqual(order_model.count(), 1)

    def test_other_users_cannot_see_or_use_my_order(self):
        order_id = self._checkout()
        self.make_user("intruder@example.com")
        client = self.new_client()
        self.login("intruder@example.com", client=client)
        self.assertEqual(client.get(f"/payments/status/{order_id}").status_code, 404)
        self.assertEqual(self.post(f"/payments/mock/pay/{order_id}", {"outcome": "success"}, client=client).status_code, 404)
        self.assertEqual(self.post("/payments/verify", {"order_id": str(order_id)}, client=client).status_code, 404)

    def test_mock_gateway_disabled_when_not_allowed(self):
        order_id = self._checkout()
        self.app.config["ALLOW_MOCK_PAYMENTS"] = False
        self.assertEqual(self.client.get(f"/payments/mock/pay/{order_id}").status_code, 404)

    def test_anonymous_cannot_checkout(self):
        resp = self.post(f"/payments/checkout/{self.note}", client=self.new_client())
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login", resp.headers["Location"])

    def test_my_orders_page(self):
        order_id = self._checkout()
        self._gateway(order_id, "success")
        self.assertIn("Paid", self.client.get("/payments/my-orders").get_data(as_text=True))


class RazorpayTests(AppTestCase):
    config_overrides = {
        "PAYMENT_PROVIDER": "razorpay", "RAZORPAY_KEY_ID": "rzp_test_key",
        "RAZORPAY_KEY_SECRET": "sekret", "RAZORPAY_WEBHOOK_SECRET": "whsec",
    }

    def setUp(self):
        super().setUp()
        self.note = self.add_note(title="Paid note", free=False, price=19900)
        self.make_user()
        self.login()

    @staticmethod
    def _sig(order_id, payment_id, secret=b"sekret"):
        return hmac.new(secret, f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    def _checkout(self):
        with mock.patch.object(RazorpayProvider, "_request", return_value={"id": "order_RZ1"}):
            resp = self.post(f"/payments/checkout/{self.note}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("order_RZ1", resp.get_data(as_text=True))
        with self.app.app_context():
            return order_model.get_by_provider_order_id("order_RZ1")["id"]

    def _verify(self, order_id, payment_id="pay_1", signature=None, remote=None, fail=False):
        signature = signature if signature is not None else self._sig("order_RZ1", payment_id)
        remote = remote or {"order_id": "order_RZ1", "status": "captured", "amount": 19900, "currency": "INR"}
        patcher = mock.patch.object(RazorpayProvider, "_request",
                                    side_effect=payments.PaymentError("down") if fail else None,
                                    return_value=remote)
        with patcher:
            return self.post("/payments/verify", {
                "order_id": str(order_id), "razorpay_order_id": "order_RZ1",
                "razorpay_payment_id": payment_id, "razorpay_signature": signature})

    def _status(self, order_id):
        with self.app.app_context():
            return order_model.get_order(order_id)["status"]

    def test_checkout_page_uses_server_amount(self):
        order_id = self._checkout()
        with self.app.app_context():
            self.assertEqual(order_model.get_order(order_id)["amount_paise"], 19900)

    def test_valid_signature_and_captured_payment_unlocks(self):
        order_id = self._checkout()
        self._verify(order_id)
        self.assertEqual(self._status(order_id), "paid")
        self.assertEqual(self.client.get(f"/notes/{self.note}/download").status_code, 200)

    def test_bad_signature_rejected(self):
        order_id = self._checkout()
        self._verify(order_id, signature="deadbeef")
        self.assertEqual(self._status(order_id), "pending")
        self.assertEqual(self.client.get(f"/notes/{self.note}/download").status_code, 403)

    def test_amount_mismatch_rejected(self):
        order_id = self._checkout()
        self._verify(order_id, remote={"order_id": "order_RZ1", "status": "captured", "amount": 100, "currency": "INR"})
        self.assertEqual(self._status(order_id), "pending")

    def test_payment_for_another_order_rejected(self):
        order_id = self._checkout()
        self._verify(order_id, remote={"order_id": "order_OTHER", "status": "captured", "amount": 19900, "currency": "INR"})
        self.assertEqual(self._status(order_id), "pending")

    def test_unreachable_api_leaves_order_pending(self):
        order_id = self._checkout()
        self._verify(order_id, fail=True)
        self.assertEqual(self._status(order_id), "pending")

    def test_failed_payment_status(self):
        order_id = self._checkout()
        self._verify(order_id, remote={"order_id": "order_RZ1", "status": "failed", "amount": 19900, "currency": "INR"})
        self.assertEqual(self._status(order_id), "failed")

    def test_webhook_requires_valid_signature(self):
        order_id = self._checkout()
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
            "id": "pay_W1", "order_id": "order_RZ1", "amount": 19900, "status": "captured"}}}}).encode()
        bad = self.client.post("/payments/webhook/razorpay", data=body, headers={"X-Razorpay-Signature": "nope"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self._status(order_id), "pending")
        good_sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
        ok = self.client.post("/payments/webhook/razorpay", data=body, headers={"X-Razorpay-Signature": good_sig})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self._status(order_id), "paid")

    def test_webhook_wrong_amount_ignored(self):
        order_id = self._checkout()
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
            "id": "pay_W2", "order_id": "order_RZ1", "amount": 5, "status": "captured"}}}}).encode()
        sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
        self.client.post("/payments/webhook/razorpay", data=body, headers={"X-Razorpay-Signature": sig})
        self.assertEqual(self._status(order_id), "pending")

    def test_missing_keys_fail_cleanly(self):
        self.app.config["RAZORPAY_KEY_ID"] = ""
        resp = self.post(f"/payments/checkout/{self.note}")
        self.assertEqual(resp.status_code, 302)
        with self.app.app_context():
            self.assertEqual(order_model.count(), 0)

    def test_csp_allows_razorpay_only_in_razorpay_mode(self):
        self.assertIn("checkout.razorpay.com", self.client.get("/").headers["Content-Security-Policy"])
