from dataclasses import dataclass, field


class PaymentError(Exception):
    """Provider communication problem (network, bad response)."""


class PaymentConfigError(PaymentError):
    """Provider is selected but not configured."""


@dataclass
class VerificationResult:
    verified: bool                    # True only if the data is authentic (signature / server-side check)
    status: str                       # paid | failed | cancelled | pending | unverified
    provider_order_id: str = None
    provider_payment_id: str = None
    amount_paise: int = None
    message: str = ""
    raw: dict = field(default_factory=dict)


class PaymentProvider:
    name = "base"

    def create_order(self, *, amount_paise, currency, receipt):
        """Return {"provider_order_id": str, "checkout": dict}."""
        raise NotImplementedError

    def verify_payment(self, payload):
        """Verify a payment result submitted by the browser. Never trust it
        without a signature / server-side check. Returns VerificationResult."""
        raise NotImplementedError

    def parse_webhook(self, raw_body, headers):
        """Return VerificationResult for a provider-to-server notification, or
        None if the event is irrelevant. Must verify the webhook signature."""
        raise NotImplementedError
