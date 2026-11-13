"""Offline sandbox gateway.

It behaves like a real provider: the *gateway side* (simulate_gateway) signs
the result with a server-only secret, and the *verification side*
(verify_payment) accepts nothing that is not correctly signed. A browser that
forges status or amount cannot produce a valid signature.
"""
import hashlib
import hmac
import uuid

from .base import PaymentProvider, VerificationResult

OUTCOMES = {"success": "paid", "fail": "failed", "cancel": "cancelled", "pending": "pending"}


class MockProvider(PaymentProvider):
    name = "mock"

    def __init__(self, secret):
        if not secret:
            raise ValueError("mock provider needs a secret")
        self._secret = secret.encode()

    def _sign(self, provider_order_id, payment_id, status, amount_paise):
        message = f"{provider_order_id}|{payment_id}|{status}|{amount_paise}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def create_order(self, *, amount_paise, currency, receipt):
        return {"provider_order_id": "mock_order_" + uuid.uuid4().hex[:16], "checkout": {}}

    def simulate_gateway(self, provider_order_id, outcome, amount_paise):
        """Server-side stand-in for the bank/gateway page. Returns the signed payload."""
        status = OUTCOMES[outcome]
        payment_id = "mock_pay_" + uuid.uuid4().hex[:16]
        return {
            "provider_order_id": provider_order_id,
            "provider_payment_id": payment_id,
            "status": status,
            "amount_paise": int(amount_paise),
            "signature": self._sign(provider_order_id, payment_id, status, int(amount_paise)),
        }

    def verify_payment(self, payload):
        order_id = str(payload.get("provider_order_id") or "")
        payment_id = str(payload.get("provider_payment_id") or "")
        status = str(payload.get("status") or "")
        signature = str(payload.get("signature") or "")
        try:
            amount = int(payload.get("amount_paise"))
        except (TypeError, ValueError):
            return VerificationResult(False, "unverified", order_id, None, None, "Malformed payment data.", dict(payload))

        expected = self._sign(order_id, payment_id, status, amount)
        if not signature or not hmac.compare_digest(signature.encode(), expected.encode()):
            return VerificationResult(False, "unverified", order_id, None, amount, "Signature check failed.", dict(payload))
        if status not in OUTCOMES.values():
            return VerificationResult(False, "unverified", order_id, None, amount, "Unknown status.", dict(payload))
        return VerificationResult(True, status, order_id, payment_id, amount, "Verified.", dict(payload))

    def parse_webhook(self, raw_body, headers):
        return None  # the mock gateway has no asynchronous notifications
