"""
PHI de-identification / re-identification.

Design note: the token<->PHI mapping produced here is used ONLY within the
lifetime of a single request (see routers/claims.py). It is never written to
disk, logged, or cached. Only the de-identified text is ever sent to Gemini.
The mapping is held in memory just long enough to re-insert real identifiers
into the final generated letter, then discarded.

Detection uses two layers:
  1. Regex safety net for highly patterned identifiers (SSN, phone, email,
     dates, MRN-like numbers) — cheap, deterministic, never misses these.
  2. Gemini structured-output pass for everything else (names, addresses,
     provider names, facility names, account numbers, etc.) — entities that
     don't follow a fixed pattern.

This is a starter implementation. Before this handles real patient records in
production, the entity list and regexes below should be reviewed against
actual record formats you see, and ideally validated against a sample set
with known PHI locations to measure recall.
"""
import re
import uuid
from typing import Dict, List, Tuple

# --- Layer 1: deterministic regex patterns for highly structured PHI ---
_REGEX_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "PHONE": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "DATE": re.compile(r"\b(0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])[/-](\d{2}|\d{4})\b"),
    "ZIP": re.compile(r"\b\d{5}(-\d{4})?\b"),
}

PHI_ENTITY_TYPES = [
    "PATIENT_NAME", "DOB", "SSN", "MRN", "ACCOUNT_NUMBER", "ADDRESS", "PHONE",
    "EMAIL", "PROVIDER_NAME", "PROVIDER_NPI", "FACILITY_NAME", "INSURANCE_ID",
    "DATE", "ZIP", "OTHER_PHI",
]

PHI_DETECTION_PROMPT = """You are a PHI detection engine for a HIPAA de-identification pipeline.
Read the medical record text below and identify every span containing a HIPAA identifier.

Return ONLY a JSON array (no markdown, no preamble) of objects with this exact shape:
[{{"type": "<one of: %s>", "value": "<exact substring as it appears>"}}]

Rules:
- "value" must be an exact, verbatim substring of the input text (so it can be located and replaced).
- Do not include the same value twice.
- Do not invent or paraphrase values. Only return what is literally present.
- If no PHI is found, return [].

TEXT:
\"\"\"
%s
\"\"\"
""" % (", ".join(PHI_ENTITY_TYPES), "{text}")


def _regex_pass(text: str) -> List[Dict]:
    entities = []
    for entity_type, pattern in _REGEX_PATTERNS.items():
        for match in pattern.finditer(text):
            entities.append({"type": entity_type, "value": match.group()})
    return entities


def detect_phi_entities(text: str, gemini_detect_fn) -> List[Dict]:
    """gemini_detect_fn: callable(prompt: str) -> str (raw model text response)."""
    entities = _regex_pass(text)

    prompt = PHI_DETECTION_PROMPT.replace("{text}", text)
    raw = gemini_detect_fn(prompt)

    import json
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        gemini_entities = json.loads(cleaned)
        for e in gemini_entities:
            if e.get("value") and e.get("type"):
                entities.append({"type": e["type"], "value": e["value"]})
    except (json.JSONDecodeError, ValueError):
        # If Gemini's output isn't parseable, we still have the regex pass as a floor.
        # Log this server-side in production so misses can be reviewed.
        pass

    # De-duplicate by (type, value)
    seen = set()
    unique = []
    for e in entities:
        key = (e["type"], e["value"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def tokenize(text: str, entities: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """Replace each detected PHI value with a generic token.
    Returns (de_identified_text, token_to_original_value_map)."""
    token_map: Dict[str, str] = {}
    result = text

    # Sort by length descending so longer matches are replaced before
    # substrings of them get clobbered.
    entities_sorted = sorted(entities, key=lambda e: len(e["value"]), reverse=True)

    type_counters: Dict[str, int] = {}
    for entity in entities_sorted:
        value = entity["value"]
        if value not in result:
            continue
        etype = entity["type"]
        type_counters[etype] = type_counters.get(etype, 0) + 1
        token = f"[{etype}_{type_counters[etype]}]"
        if value in result:
            result = result.replace(value, token)
            token_map[token] = value

    return result, token_map


def reidentify(text: str, token_map: Dict[str, str]) -> str:
    """Restore original PHI values into generated text (e.g. the final letter)."""
    result = text
    for token, original_value in token_map.items():
        result = result.replace(token, original_value)
    return result
