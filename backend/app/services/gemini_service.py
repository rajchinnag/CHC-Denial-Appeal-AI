import json
from app.config import settings


def _get_api_key_client():
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai


def _get_vertex_client():
    import vertexai
    vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
    from vertexai.generative_models import GenerativeModel
    return GenerativeModel


def simple_generate(prompt: str) -> str:
    if settings.GEMINI_MODE == "vertex":
        GenerativeModel = _get_vertex_client()
        model = GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    else:
        genai = _get_api_key_client()
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text


def grounded_policy_research(payor: str, category: str, codes_summary: str, denial_code: str) -> dict:
    prompt = f"""You are a healthcare reimbursement policy expert with deep knowledge of CMS guidelines,
LCD/NCD policies, CARC/RARC codes, and major US payor medical policies.

Payor: {payor}
Denial category: {category}
CARC denial code: {denial_code}
Relevant codes: {codes_summary}

Based on your knowledge of {payor} policies and CMS/AMA guidelines, determine whether this denial
appears valid or invalid, and identify the most relevant policy or guideline that governs this situation.

Return ONLY valid JSON (no markdown fences, no preamble) in this exact shape:
{{
  "denial_valid": true or false,
  "policy_findings": [
    {{"policy_name": "...", "source_url": "...", "summary": "2-3 sentences explaining the policy"}}
  ],
  "reasoning_summary": "2-4 sentences explaining the determination"
}}
"""
    raw = simple_generate(prompt)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "denial_valid": None,
            "policy_findings": [],
            "reasoning_summary": "Policy research returned non-JSON output - review raw_response.",
            "raw_response": raw,
        }


def generate_letter(intake_summary: str, classification: dict, policy_result: dict) -> str:
    denial_valid = policy_result.get("denial_valid")
    findings = policy_result.get("policy_findings", [])
    findings_text = "\n".join(
        f"- {f.get('policy_name')}: {f.get('summary')}" + (f" (Source: {f.get('source_url')})" if f.get('source_url') else "")
        for f in findings
    ) or "No specific policy located - reason from general CMS/coding guidelines."

    if denial_valid:
        stance = (
            "The denial appears VALID based on the policy research below. Write a RECONSIDERATION "
            "letter that still makes the strongest legitimate case for payment - e.g. citing corrected "
            "documentation, an appropriate modifier, additional medical necessity justification, or any "
            "applicable exception in the cited policy - without misrepresenting the claim."
        )
    else:
        stance = (
            "The denial appears INVALID based on the policy research below. Write a formal APPEAL letter "
            "explaining specifically why the denial was incorrect, citing the policy names and guidelines below."
        )

    prompt = f"""You are a healthcare reimbursement specialist drafting a formal claim appeal/reconsideration
letter to an insurance payor. Use a professional, factual, non-emotional tone appropriate for a payor's
appeals department.

CLAIM CONTEXT (de-identified - tokens like [PATIENT_NAME_1] are placeholders, keep them exactly as-is):
{intake_summary}

POLICY RESEARCH:
{findings_text}

REASONING: {policy_result.get('reasoning_summary', '')}

INSTRUCTION: {stance}

Write the complete letter now, including a placeholder header (date, payor name, claim reference using
the de-identified tokens), a clear subject line, body paragraphs citing the specific policy names above,
and a professional closing. Do not include any text outside the letter itself."""

    return simple_generate(prompt)


def analyze_coding_gaps(intake_summary: str, record_text: str) -> dict:
    """Analyze the medical record against billed codes and suggest corrections."""

    prompt = f"""You are a certified professional coder (CPC) and healthcare reimbursement expert.
Review the billed claim information and the medical record below, then identify any coding
corrections or additions that could support a corrected claim submission.

BILLED CLAIM INFORMATION:
{intake_summary}

MEDICAL RECORD (de-identified):
{record_text}

Analyze and return ONLY valid JSON (no markdown fences, no preamble) in this exact shape:
{{
  "has_recommendations": true or false,
  "cpt_changes": [
    {{"current": "...", "suggested": "...", "reason": "..."}}
  ],
  "dx_changes": [
    {{"action": "add/change/remove", "code": "...", "description": "...", "reason": "..."}}
  ],
  "modifier_changes": [
    {{"action": "add/remove", "modifier": "...", "reason": "..."}}
  ],
  "revenue_code_changes": [
    {{"current": "...", "suggested": "...", "reason": "..."}}
  ],
  "other_recommendations": [
    {{"recommendation": "...", "reason": "..."}}
  ],
  "summary": "2-3 sentence overall summary of corrections needed"
}}
"""
    raw = simple_generate(prompt)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "has_recommendations": False,
            "cpt_changes": [],
            "dx_changes": [],
            "modifier_changes": [],
            "revenue_code_changes": [],
            "other_recommendations": [],
            "summary": "Could not analyze coding gaps.",
            "raw_response": raw,
        }
