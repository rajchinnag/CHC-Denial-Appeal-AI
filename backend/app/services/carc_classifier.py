"""
Denial classification.

Strategy: CARC codes are standardized by X12, so a lookup table is faster and
more reliable than asking an LLM to classify every time. Gemini is reserved
for the codes we haven't seeded yet, and for reasoning about the policy itself
later in the pipeline — not for this categorization step.
"""
import json
import os
from app.models.schemas import DenialClassification

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "carc_codes.json")

with open(_DATA_PATH, "r") as f:
    _CARC_TABLE = json.load(f)

VALID_CATEGORIES = {"coding", "medical_necessity", "experimental", "authorization", "bill_type"}


def classify_denial(denial_code: str) -> DenialClassification:
    """Look up a CARC code. Returns 'unclassified' if not in the seed table —
    the caller should fall back to Gemini reasoning in that case."""
    code = denial_code.strip().upper().replace("CO-", "").replace("PR-", "").replace("CO", "").strip()
    # Try exact and a couple of common formatting variants
    entry = _CARC_TABLE.get(denial_code.strip()) or _CARC_TABLE.get(code)

    if entry:
        return DenialClassification(
            category=entry["category"],
            carc_description=entry["description"],
            confidence="lookup",
        )

    return DenialClassification(
        category="unclassified",
        carc_description=None,
        confidence="lookup",
    )
