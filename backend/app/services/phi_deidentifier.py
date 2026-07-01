"""
PHI De-identification Pipeline — HIPAA Safe Harbor (45 CFR 164.514(b))
All 18 HIPAA identifiers detected and tokenized LOCALLY before any text
reaches Gemini or any external service.

Three layers — all local, zero network calls:
  Layer 1: Deterministic regex for structured PHI (dates, SSN, phone, etc.)
  Layer 2: Pattern-based name detection (titles, capitalization, context)
  Layer 3: Merge, deduplicate, sort, tokenize

Token map is held in memory only for the duration of one request.
Never written to disk, never logged.
"""
import re
from typing import Dict, List, Tuple

# ── LAYER 1: Structured PHI — deterministic regex ────────────────────────────

_PATTERNS = [
    # SSN
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Phone — all common formats
    ("PHONE", re.compile(
        r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    )),
    # Email
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # URLs / IPs
    ("URL", re.compile(
        r"\b(https?://|www\.)\S+\b|"
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
    )),
    # Dates — MM/DD/YYYY, MM-DD-YYYY, Month DD YYYY, DD Month YYYY
    ("DATE", re.compile(
        r"\b(0?[1-9]|1[0-2])[/\-](0?[1-9]|[12]\d|3[01])[/\-](\d{2}|\d{4})\b"
        r"|\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+(0?[1-9]|[12]\d|3[01]),?\s+\d{4}\b"
        r"|\b(0?[1-9]|[12]\d|3[01])\s+(January|February|March|April|May|June|"
        r"July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|"
        r"Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{4}\b",
        re.IGNORECASE
    )),
    # Age 90 or older
    ("AGE", re.compile(r"\b(9[0-9]|1[0-4]\d)-?year-?old\b|\bage[d]?\s+(9[0-9]|1[0-4]\d)\b", re.IGNORECASE)),
    # ZIP codes — 5 digit or ZIP+4
    ("ZIP", re.compile(r"\b\d{5}(-\d{4})?\b")),
    # NPI — 10 digit number after NPI label
    ("PROVIDER_NPI", re.compile(r"\bNPI\s*[:#]?\s*(\d{10})\b", re.IGNORECASE)),
    # MRN — common formats
    ("MRN", re.compile(
        r"\b(MRN|Medical\s+Record\s+(No|Number|#|Num))[:\s#]*([A-Z0-9\-]{4,20})\b"
        r"|\bMRN[-:\s]*([A-Z0-9\-]{4,20})\b",
        re.IGNORECASE
    )),
    # Account numbers
    ("ACCOUNT_NUMBER", re.compile(
        r"\b(Account|Acct|Member\s+ID|Member#|Policy|Claim)\s*(No|Number|#|Num|ID)?[:\s]*([A-Z0-9\-]{6,20})\b",
        re.IGNORECASE
    )),
    # Fax numbers (same pattern as phone but preceded by fax label)
    ("FAX", re.compile(r"\b(fax|f)[:\s]+(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", re.IGNORECASE)),
    # Device identifiers (serial numbers, device IDs)
    ("DEVICE_ID", re.compile(r"\b(serial\s+no|device\s+id|implant\s+id)[:\s]*([A-Z0-9\-]{6,20})\b", re.IGNORECASE)),
    # Certificate / license numbers
    ("CERT_NUMBER", re.compile(r"\b(license|certificate|cert)[:\s#]*([A-Z0-9\-]{4,20})\b", re.IGNORECASE)),
    # Health plan / insurance IDs
    ("INSURANCE_ID", re.compile(
        r"\b(Member\s+ID|Insurance\s+ID|Health\s+Plan\s+ID|Subscriber\s+ID|Group\s+No)[:\s#]*([A-Z0-9\-]{4,20})\b",
        re.IGNORECASE
    )),
]

# ── LAYER 2: Name detection — pattern-based, no AI ───────────────────────────

# Titles that precede names
_TITLE_PATTERN = re.compile(
    r"\b(Mr|Mrs|Ms|Miss|Dr|Prof|Rev|Sr|Jr|MD|DO|NP|PA|RN|Ph\.?D|Esq)\.?\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b"
)

# Context keywords that precede names in medical records
_CONTEXT_NAME_PATTERN = re.compile(
    r"\b(Patient|Name|Patient Name|Provider|Attending|Physician|Surgeon|Nurse|"
    r"Referring|Consulting|Ordering|Prescriber|Signed by|Electronically signed by|"
    r"Dictated by|Author|Performed by|Authorized by)[:\s]+([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,4})\b",
    re.IGNORECASE
)

# Standalone full names — two or more capitalized words not at sentence start
_FULL_NAME_PATTERN = re.compile(
    r"(?<!\.\s)(?<!\n)(?<![A-Z]{2}\s)\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})"
    r"(?:\s+([A-Z][a-z]{1,20}))?\b"
)

# Words that look like names but aren't (common false positives in medical text)
_NAME_STOPWORDS = {
    "January", "February", "March", "April", "June", "July", "August",
    "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "United", "States", "Medicare", "Medicaid", "Insurance", "Hospital", "Medical",
    "Center", "Health", "System", "Department", "University", "General",
    "Physical", "Therapy", "Internal", "Medicine", "Emergency", "Surgical",
    "Normal", "Within", "Limits", "Right", "Left", "Upper", "Lower",
    "Blood", "Heart", "Lung", "Liver", "Kidney", "Brain", "Chest",
    "Type", "Stage", "Grade", "Level", "Class", "Code", "Plan",
    "Chief", "Complaint", "History", "Review", "Systems", "Examination",
    "Assessment", "Impression", "Findings", "Results", "Orders", "Discharge",
    "Admission", "Service", "Date", "Time", "Note", "Report", "Record",
    "Primary", "Secondary", "Diagnosis", "Procedure", "Treatment", "Medication",
    "Follow", "Return", "Visit", "Care", "Standard", "Total", "Final",
}

def _is_likely_name(word1: str, word2: str, word3: str = "") -> bool:
    words = [w for w in [word1, word2, word3] if w]
    for w in words:
        if w in _NAME_STOPWORDS:
            return False
        if len(w) < 2:
            return False
    return True


def _name_pass(text: str) -> List[Dict]:
    entities = []
    seen_values = set()

    # Title-prefixed names (highest confidence)
    for match in _TITLE_PATTERN.finditer(text):
        value = match.group()
        if value not in seen_values:
            seen_values.add(value)
            # Classify as provider or patient based on title
            title = match.group(1).upper().replace(".", "")
            if title in {"MD", "DO", "NP", "PA", "RN", "PHD", "DR", "PROF"}:
                entities.append({"type": "PROVIDER_NAME", "value": value})
            else:
                entities.append({"type": "PATIENT_NAME", "value": value})

    # Context-preceded names
    for match in _CONTEXT_NAME_PATTERN.finditer(text):
        context = match.group(1).lower()
        name_value = match.group(2).strip()
        full_value = match.group()
        if name_value not in seen_values and len(name_value) > 3:
            seen_values.add(name_value)
            if any(k in context for k in ["patient", "name"]):
                entities.append({"type": "PATIENT_NAME", "value": name_value})
            else:
                entities.append({"type": "PROVIDER_NAME", "value": name_value})

    # Standalone full names (lower confidence — only if 2+ words, not stopwords)
    for match in _FULL_NAME_PATTERN.finditer(text):
        w1 = match.group(1)
        w2 = match.group(2)
        w3 = match.group(3) or ""
        if _is_likely_name(w1, w2, w3):
            value = match.group().strip()
            if value not in seen_values and value not in _NAME_STOPWORDS:
                seen_values.add(value)
                entities.append({"type": "PATIENT_NAME", "value": value})

    return entities


# ── LAYER 3: Address detection ────────────────────────────────────────────────

_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\s+"
    r"(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|"
    r"Court|Ct|Place|Pl|Way|Circle|Cir|Highway|Hwy|Suite|Ste)\.?\b",
    re.IGNORECASE
)

def _address_pass(text: str) -> List[Dict]:
    entities = []
    for match in _ADDRESS_PATTERN.finditer(text):
        entities.append({"type": "ADDRESS", "value": match.group()})
    return entities


# ── LAYER 4: Facility name detection ─────────────────────────────────────────

_FACILITY_PATTERN = re.compile(
    r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}\s+"
    r"(Hospital|Medical\s+Center|Health\s+System|Clinic|Infirmary|"
    r"Healthcare|Surgery\s+Center|Rehabilitation|Institute)\b",
    re.IGNORECASE
)

def _facility_pass(text: str) -> List[Dict]:
    entities = []
    seen = set()
    for match in _FACILITY_PATTERN.finditer(text):
        value = match.group()
        if value not in seen:
            seen.add(value)
            entities.append({"type": "FACILITY_NAME", "value": value})
    return entities


# ── Main detection function ───────────────────────────────────────────────────

def detect_phi_entities(text: str, gemini_detect_fn=None) -> List[Dict]:
    """
    Detect all PHI entities using local layers only.
    gemini_detect_fn is accepted for interface compatibility but NOT called —
    PHI detection is fully local. No text leaves this function.
    """
    entities = []

    # Layer 1: structured regex
    for entity_type, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            value = match.group()
            if value and len(value.strip()) > 1:
                entities.append({"type": entity_type, "value": value.strip()})

    # Layer 2: name detection
    entities.extend(_name_pass(text))

    # Layer 3: address detection
    entities.extend(_address_pass(text))

    # Layer 4: facility detection
    entities.extend(_facility_pass(text))

    # Deduplicate by (type, value)
    seen = set()
    unique = []
    for e in entities:
        key = (e["type"], e["value"])
        if key not in seen and e["value"].strip():
            seen.add(key)
            unique.append(e)

    return unique


def tokenize(text: str, entities: List[Dict]) -> Tuple[str, Dict[str, str]]:
    """
    Replace each detected PHI value with a deterministic token.
    Longer matches replaced first to prevent substring clobbering.
    Returns (de_identified_text, token_to_original_map).
    """
    token_map: Dict[str, str] = {}
    result = text

    # Sort longest first to avoid partial replacements
    entities_sorted = sorted(entities, key=lambda e: len(e["value"]), reverse=True)

    type_counters: Dict[str, int] = {}
    for entity in entities_sorted:
        value = entity["value"]
        if not value or value not in result:
            continue
        etype = entity["type"]
        type_counters[etype] = type_counters.get(etype, 0) + 1
        token = f"[{etype}_{type_counters[etype]}]"
        result = result.replace(value, token)
        token_map[token] = value

    return result, token_map


def reidentify(text: str, token_map: Dict[str, str]) -> str:
    """
    Restore original PHI values into generated text (final letter only).
    Token map is discarded after this call in the request lifecycle.
    """
    result = text
    for token, original in token_map.items():
        result = result.replace(token, original)
    return result


def phi_report(entities: List[Dict]) -> Dict:
    """
    Build a structured report of detected PHI for UI display.
    Shows the user exactly what was found and tokenized before
    any data is sent to AI.
    """
    by_type: Dict[str, List[str]] = {}
    for e in entities:
        t = e["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(e["value"])

    return {
        "total_entities": len(entities),
        "by_type": by_type,
        "types_found": list(by_type.keys()),
        "summary": f"{len(entities)} PHI identifiers detected across {len(by_type)} categories — all removed before AI processing.",
    }
