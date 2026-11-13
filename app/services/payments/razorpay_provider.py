"""Razorpay driver (use TEST keys). Uses only the standard library.

Flow
1. create_order  -> POST /v1/orders (amount comes from the database).
2. Browser opens Razorpay Checkout, then posts order id, payment id, signature.
3. verify_payment checks the HMAC-SHA256 signature with the secret key, then
   asks Razorpay's API for the payment itself and confirms order id, status
   and amount. Only status 'captured' counts as paid.
4. parse_webhook handles Razorpay's server-to-server events (signature header).
"""
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request

from .base import PaymentConfigError, PaymentError, PaymentProvider, VerificationResult

API_BASE = "https://api.razorpay.com/v1"


class RazorpayProvider(PaymentProvider):
    name = "razorpay"

    def __init__(self, key_id, key_secret, webhook_secret=""):
        if not key_id or not key_secret:
            raise PaymentConfigError(
                "Razorpay is selected but RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set."
            )
        self.key_id = key_id
        self._secret = key_secret.encode()
        self._webhook_secret = (webhook_secret or "").encode()

    # ------------------------------------------------------------ HTTP
    def _request(self, method, path, data=None):
        url = API_BASE + path
        body = json.dumps(data).encode() if data is not None else None
        token = base64.b64encode(self.key_id.encode() + b":" + self._secret).decode()
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", "Basic " + token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise PaymentError(f"Razorpay rejected the request ({exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise PaymentError("Could not reach Razorpay.") from exc

    # ------------------------------------------------------- interface
    def create_order(self, *, amount_paise, currency, receipt):
        data = self._request("POST", "/orders", {
            "amount": int(amount_paise), "currency": currency,
            "receipt": str(receipt)[:40], "payment_capture": 1,
        })
        return {
            "provider_order_id": data["id"],
            "checkout": {"key_id": self.key_id, "amount": int(amount_paise), "currency": currency},
        }

    def _signature_ok(self, order_id, payment_id, signature):
        message = f"{order_id}|{payment_id}".encode()
        expected = hmac.new(self._secret, message, hashlib.sha256).hexdigest()
        return bool(signature) and hmac.compare_digest(str(signature).encode(), expected.encode())

    def verify_payment(self, payload):
        order_id = str(payload.get("razorpay_order_id") or "")
        payment_id = str(payload.get("razorpay_payment_id") or "")
        signature = payload.get("razorpay_signature") or ""
        raw = {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id}

        if not order_id or not payment_id or not self._signature_ok(order_id, payment_id, signature):
            return VerificationResult(False, "unverified", order_id, None, None, "Signature check failed.", raw)

        try:
            payment = self._request("GET", f"/payments/{payment_id}")
            if payment.get("status") == "authorized":
                payment = self._request(
                    "POST", f"/payments/{payment_id}/capture",
                    {"amount": payment["amount"], "currency": payment["currency"]},
                )
        except PaymentError as exc:
            # Signature is genuine but we cannot confirm the status: stay locked.
            return VerificationResult(True, "pending", order_id, payment_id, None, str(exc), raw)

        if payment.get("order_id") != order_id:
            return VerificationResult(False, "unverified", order_id, None, None, "Payment belongs to another order.", raw)

        remote = payment.get("status")
        status = {"captured": "paid", "failed": "failed"}.get(remote, "pending")
        raw["razorpay_status"] = remote
        return VerificationResult(True, status, order_id, payment_id, payment.get("amount"), "Confirmed with Razorpay.", raw)

    def parse_webhook(self, raw_body, headers):
        if not self._webhook_secret:
            return None
        signature = headers.get("X-Razorpay-Signature", "")
        expected = hmac.new(self._webhook_secret, raw_body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature.encode(), expected.encode()):
            return VerificationResult(False, "unverified", message="Webhook signature failed.")
        try:
            event = json.loads(raw_body.decode())
            entity = event["payload"]["payment"]["entity"]
        except (ValueError, KeyError, TypeError):
            return None
        kind = event.get("event")
        status = {"payment.captured": "paid", "order.paid": "paid", "payment.failed": "failed"}.get(kind)
        if status is None:
            return None
        return VerificationResult(
            True, status, entity.get("order_id"), entity.get("id"), entity.get("amount"),
            f"Webhook {kind}", {"event": kind, "payment_id": entity.get("id")},
        )
