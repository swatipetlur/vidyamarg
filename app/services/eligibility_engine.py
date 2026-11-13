"""Eligibility matching engine.

Compares a student's standard with the eligibility rules stored for an
examination. It never guesses: missing or incomplete data produces a
"verify" result instead of a match.
"""
from dataclasses import dataclass, field

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"
VERIFY = "verify"

DISCLAIMER = (
    "Based on data entered by the administrator. This does not replace the official "
    "rules - always confirm on the official website."
)


@dataclass(frozen=True)
class EligibilityResult:
    status: str
    label: str
    message: str
    criteria: tuple = field(default_factory=tuple)  # criteria_text of the rules that matched


def _is_complete(rule):
    return rule["min_standard"] is not None and rule["max_standard"] is not None


def evaluate(rules, standard):
    """Return an EligibilityResult for one exam.

    - ELIGIBLE: at least one complete rule has min <= standard <= max.
    - VERIFY: there are no rules, or some rule lacks a bound and no complete
      rule matched (the incomplete rule might cover this standard).
    - NOT_ELIGIBLE: complete rules exist and none contain the standard.
    """
    if not isinstance(standard, int) or not 1 <= standard <= 10:
        raise ValueError("standard must be an integer from 1 to 10")

    rules = list(rules)
    if not rules:
        return EligibilityResult(
            VERIFY, "Verify eligibility",
            "Eligibility data is not available for this examination. Please verify it on the official website.",
        )

    complete = [r for r in rules if _is_complete(r)]
    matched = [r for r in complete if r["min_standard"] <= standard <= r["max_standard"]]
    if matched:
        criteria = tuple(r["criteria_text"] for r in matched if r["criteria_text"])
        return EligibilityResult(
            ELIGIBLE, "Meets stored criteria",
            f"Standard {standard} is within the stored eligibility criteria.", criteria,
        )

    if len(complete) < len(rules):
        return EligibilityResult(
            VERIFY, "Verify eligibility",
            "The stored eligibility data is incomplete. Please verify it on the official website.",
        )

    ranges = ", ".join(_range_text(r) for r in complete)
    return EligibilityResult(
        NOT_ELIGIBLE, "Not for this standard",
        f"Stored criteria cover {ranges}, which does not include Standard {standard}.",
    )


def _range_text(rule):
    low, high = rule["min_standard"], rule["max_standard"]
    return f"Standard {low}" if low == high else f"Standards {low}-{high}"


def evaluate_many(exams, rules_by_exam, standard):
    """[(exam_row, EligibilityResult), ...] in the same order as `exams`."""
    return [(exam, evaluate(rules_by_exam.get(exam["id"], []), standard)) for exam in exams]
