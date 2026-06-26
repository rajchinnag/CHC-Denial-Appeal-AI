"""
Gemini integration layer.

Two modes, selected by settings.GEMINI_MODE:

  "api_key" — uses google-generativeai with an API key from Google AI Studio.
              Fast to set up (one env var). NO BAA available. Use this only
              while building/testing with synthetic or already-de-identified
              text — never with raw PHI.

  "vertex"  — uses Vertex AI (google-cloud-aiplatform / vertexai SDK) with a
              GCP service account. Requires a GCP project + a signed BAA with
              Google Cloud. This is the only mode that should ever see real
              PHI in production.

Both modes expose the same three functions below, so the rest of the app
doesn't need to know which one is active.

Policy lookup uses Google Search grounding so Gemini fetches real, current
payor policy pages instead of generating plausible-sounding but possibly
wrong policy names from memory.
"""
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
    """Plain text generation, no grounding. Used for PHI entity detection
    and other steps that don't need live web data."""
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
    """Search-grounded lookup of the payor's actual current policy / LCD/NCD
    relevant to this denial. Returns parsed JSON: policy findings + a
    determination of whether the denial appears valid or invalid, with
    reasoning grounded in the fetched sources."""

    prompt = f"""You are a healthcare reimbursement policy researcher. Use live web search to find
{payor}'s current, real medical policy, LCD/NCD, or coverage guideline relevant to this denial.
Do not rely on memory alone — search and ground your findings in actual current sources.

Denial category: {category}
CARC denial code: {denial_code}
Relevant codes: {codes_summary}

Find the specific policy that governs this situation, then determine whether the denial was
applied correctly given the codes and category above.

Return ONLY valid JSON (no markdown fences, no preamble) in this exact shape:
{{
  "denial_valid": true or false,
  "policy_findings": [
    {{"policy_name": "...", "source_url": "...", "summary": "2-3 sentences in your own words"}}
  ],
  "reasoning_summary": "2-4 sentences explaining the determination"
}}
"""

    if settings.GEMINI_MODE == "vertex":
        GenerativeModel = _get_vertex_client()
        from vertexai.generative_models import Tool, grounding
        model = GenerativeModel(
            settings.GEMINI_MODEL,
            tools=[Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())],
        )
        response = model.generate_content(prompt)
        raw = response.text
    else:
        genai = _get_api_key_client()
        model = genai.GenerativeModel(
            settings.GEMINI_MODEL,
            tools="google_search_retrieval",
        )
        response = model.generate_content(prompt)
        raw = response.text

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").replace("json", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "denial_valid": None,
            "policy_findings": [],
            "reasoning_summary": "Policy research returned non-JSON output — review raw_response.",
            "raw_response": raw,
        }


def generate_letter(intake_summary: str, classification: dict, policy_result: dict) -> str:
    """Generate the appeal (if denial invalid) or reconsideration (if denial
    valid) letter, citing the policy findings by name. Operates entirely on
    de-identified text — tokens get swapped back to real PHI by the caller
    after this returns."""

    denial_valid = policy_result.get("denial_valid")
    findings = policy_result.get("policy_findings", [])
    findings_text = "\n".join(
        f"- {f.get('policy_name')}: {f.get('summary')}" + (f" (Source: {f.get('source_url')})" if f.get('source_url') else "")
        for f in findings
    ) or "No specific policy located — reason from general CMS/coding guidelines."

    if denial_valid:
        stance = (
            "The denial appears VALID based on the policy research below. Write a RECONSIDERATION "
            "letter that still makes the strongest legitimate case for payment — e.g. citing corrected "
            "documentation, an appropriate modifier, additional medical necessity justification, or any "
            "applicable exception in the cited policy — without misrepresenting the claim."
        )
    else:
        stance = (
            "The denial appears INVALID based on the policy research below. Write a formal APPEAL letter "
            "explaining specifically why the denial was incorrect, citing the policy names and guidelines below."
        )

    prompt = f"""You are a healthcare reimbursement specialist drafting a formal claim appeal/reconsideration
letter to an insurance payor. Use a professional, factual, non-emotional tone appropriate for a payor's
appeals department.

CLAIM CONTEXT (de-identified — tokens like [PATIENT_NAME_1] are placeholders, keep them exactly as-is,
do not alter or remove them, they will be restored to real values after you respond):
{intake_summary}

POLICY RESEARCH:
{findings_text}

REASONING: {policy_result.get('reasoning_summary', '')}

INSTRUCTION: {stance}

Write the complete letter now, including a placeholder header (date, payor name, claim reference using
the de-identified tokens), a clear subject line, body paragraphs citing the specific policy names above,
and a professional closing. Do not include any text outside the letter itself."""

    return simple_generate(prompt)
