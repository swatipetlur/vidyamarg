"""Single source of truth for "may this person open this note?".

Every route that serves or describes a note's availability must go through
can_user_access(). Paid notes are locked unless the database holds an order
with status 'paid' for that exact user and note.
"""
from dataclasses import dataclass

from ..models import order as order_model


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    code: str      # free | admin | purchased | login_required | payment_required | unavailable
    message: str


def can_user_access(user, note, paid_ids=None):
    if note is None:
        return AccessDecision(False, "unavailable", "This note does not exist.")

    is_admin = user is not None and user["role"] == "admin"
    if not note["is_published"] and not is_admin:
        return AccessDecision(False, "unavailable", "This note is not available.")

    if is_admin:
        return AccessDecision(True, "admin", "Administrator access.")

    if note["is_free"]:
        return AccessDecision(True, "free", "Free note.")

    if user is None:
        return AccessDecision(False, "login_required", "Log in as a student to buy this note.")

    purchased = note["id"] in paid_ids if paid_ids is not None else order_model.has_paid(user["id"], note["id"])
    if purchased:
        return AccessDecision(True, "purchased", "You own this note.")

    return AccessDecision(False, "payment_required", "This note unlocks after your payment is confirmed.")


def access_for_notes(user, notes):
    """{note_id: AccessDecision}, using a single query for the user's purchases."""
    paid = order_model.paid_note_ids(user["id"]) if user is not None else set()
    return {note["id"]: can_user_access(user, note, paid_ids=paid) for note in notes}
