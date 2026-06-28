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


def medical_necessity_analysis(
    payor: str,
    intake_summary: str,
    codes_summary: str,
    record_text: str,
    denial_code: str,
) -> dict:
    """
    Full medical necessity denial logic for CO-50 and untrained scenarios.
    Priority: CMS LCD/NCD first -> Payer policy second -> Medical record third.
    Returns: policy findings, logic path taken, corrected claim suggestions,
             reprocess letter, and appeal letter as separate outputs.
    """

    is_trained_scenario = denial_code.strip().upper().replace("CO-", "").replace("OA-", "") == "50"
    training_status = "trained" if is_trained_scenario else "general_mn_logic"

    # ── STEP 1: Policy check ──────────────────────────────────────────────────
    policy_prompt = f"""You are a healthcare reimbursement policy expert specializing in medical necessity.
A claim has been denied under CARC {denial_code} (Not Medically Necessary).

Payor: {payor}
Claim Details: {intake_summary}
Codes: {codes_summary}

Answer the following questions in strict JSON. CMS policies take priority over payer policies.

1. Is there a specific CMS LCD or NCD that states this service IS medically necessary for the billed diagnosis/revenue code?
2. Is there a specific CMS LCD or NCD that states this service is NOT medically necessary for the billed diagnosis/revenue code?
3. Is there a specific {payor} policy that states this service IS medically necessary?
4. Is there a specific {payor} policy that states this service is NOT medically necessary?
5. Are there required conditions, modifiers, or secondary diagnosis codes that must appear on the claim to support medical necessity?
6. What LCD/NCD numbers are relevant (if any)?

Return ONLY valid JSON (no markdown fences, no preamble):
{{
  "cms_supports": true or false or null,
  "cms_policy_name": "LCD/NCD name or null",
  "cms_policy_number": "L##### or A##### or null",
  "cms_policy_summary": "2-3 sentences or null",
  "payer_supports": true or false or null,
  "payer_policy_name": "policy name or null",
  "payer_policy_number": "policy number or null",
  "payer_policy_summary": "2-3 sentences or null",
  "required_conditions": ["list of required modifiers, dx codes, or conditions needed on claim"],
  "missing_conditions": ["conditions that appear to be missing from the claim as submitted"],
  "overall_policy_supports": true or false or null,
  "policy_reasoning": "2-3 sentences explaining the overall determination based on CMS first then payer"
}}
"""
    policy_raw = simple_generate(policy_prompt)
    policy_cleaned = policy_raw.strip()
    if policy_cleaned.startswith("```"):
        policy_cleaned = policy_cleaned.strip("`").replace("json", "", 1).strip()
    try:
        policy_result = json.loads(policy_cleaned)
    except json.JSONDecodeError:
        policy_result = {
            "cms_supports": None, "cms_policy_name": None, "cms_policy_number": None,
            "cms_policy_summary": None, "payer_supports": None, "payer_policy_name": None,
            "payer_policy_number": None, "payer_policy_summary": None,
            "required_conditions": [], "missing_conditions": [],
            "overall_policy_supports": None,
            "policy_reasoning": "Policy research could not be parsed.",
        }

    # ── STEP 2: Medical record check ──────────────────────────────────────────
    record_prompt = f"""You are a certified professional coder (CPC) and medical necessity expert.
Review the de-identified medical record below against the billed claim.

CLAIM DETAILS: {intake_summary}
CODES: {codes_summary}
MEDICAL RECORD (de-identified): {record_text}

Determine:
1. Does the medical record document medical necessity for the billed service?
2. Can any code corrections (CPT, Dx, modifier, revenue code) be made to better support medical necessity?
3. What specific documented conditions support the medical necessity?

Return ONLY valid JSON (no markdown fences, no preamble):
{{
  "record_supports_mn": true or false,
  "documented_conditions": ["list of conditions in record that support MN"],
  "missing_documentation": ["list of what is absent or insufficient in the record"],
  "can_correct_codes": true or false,
  "cpt_changes": [{{"current": "...", "suggested": "...", "reason": "..."}}],
  "dx_changes": [{{"action": "add/change/remove", "code": "...", "description": "...", "reason": "..."}}],
  "modifier_changes": [{{"action": "add/remove", "modifier": "...", "reason": "..."}}],
  "revenue_code_changes": [{{"current": "...", "suggested": "...", "reason": "..."}}],
  "record_summary": "2-3 sentences summarizing what the record does and does not support"
}}
"""
    record_raw = simple_generate(record_prompt)
    record_cleaned = record_raw.strip()
    if record_cleaned.startswith("```"):
        record_cleaned = record_cleaned.strip("`").replace("json", "", 1).strip()
    try:
        record_result = json.loads(record_cleaned)
    except json.JSONDecodeError:
        record_result = {
            "record_supports_mn": False, "documented_conditions": [],
            "missing_documentation": [], "can_correct_codes": False,
            "cpt_changes": [], "dx_changes": [], "modifier_changes": [],
            "revenue_code_changes": [], "record_summary": "Record analysis could not be parsed.",
        }

    # ── Determine logic path ──────────────────────────────────────────────────
    policy_supports = policy_result.get("overall_policy_supports")
    record_supports = record_result.get("record_supports_mn", False)
    can_correct = record_result.get("can_correct_codes", False)

    if policy_supports is True:
        logic_path = "policy_supports_reprocess"
    elif record_supports and can_correct:
        logic_path = "record_supports_corrected_claim"
    elif record_supports and not can_correct:
        logic_path = "record_supports_appeal_only"
    else:
        logic_path = "no_support_appeal_only"

    # ── Build policy citation block ───────────────────────────────────────────
    cms_name = policy_result.get("cms_policy_name") or ""
    cms_num = policy_result.get("cms_policy_number") or ""
    cms_summary = policy_result.get("cms_policy_summary") or ""
    payer_name = policy_result.get("payer_policy_name") or ""
    payer_num = policy_result.get("payer_policy_number") or ""
    payer_summary = policy_result.get("payer_policy_summary") or ""

    policy_citation_block = ""
    if cms_name:
        policy_citation_block += f"CMS Policy: {cms_name} ({cms_num}) — {cms_summary}\n"
    if payer_name:
        policy_citation_block += f"{payor} Policy: {payer_name} ({payer_num}) — {payer_summary}\n"
    if not policy_citation_block:
        policy_citation_block = "No specific LCD/NCD or payer policy located for this service/diagnosis combination."

    documented = ", ".join(record_result.get("documented_conditions", [])) or "Not documented in record"
    missing_doc = ", ".join(record_result.get("missing_documentation", [])) or "None identified"
    missing_conditions = ", ".join(policy_result.get("missing_conditions", [])) or "None identified"

    # ── REPROCESS LETTER ─────────────────────────────────────────────────────
    reprocess_prompt = f"""You are a healthcare reimbursement specialist. Write a formal REPROCESS REQUEST letter
to the insurance payer. This letter is used when calling the payer and requesting the representative
to reprocess the claim without a formal appeal.

Format the letter EXACTLY as follows — do not add any text outside this structure:

Dear [INSERT PAYER NAME],

Re: Claim Denial — CARC {denial_code} (Not Medically Necessary)
[Include claim number, patient name token, member ID token, and dates of service from context below]

This letter is in response to the denial of the above-referenced claim. The claim was denied under
CARC {denial_code} indicating the service was not considered medically necessary.

[If policy supports: Cite the specific CMS LCD/NCD or payer policy by name and number that supports
medical necessity for this service. State clearly that the service meets the criteria defined in the policy.]

[If record supports: Briefly explain the documented clinical condition that demonstrates medical necessity.]

Based on the above, we respectfully request that this claim be reprocessed for payment.
The medical records supporting the medical necessity of the billed service are attached for your reference.

[Provider Name — Placeholder]
[Contact Number — Placeholder]

CONTEXT:
{intake_summary}

POLICY FINDINGS:
{policy_citation_block}

DOCUMENTED CONDITIONS:
{documented}

LOGIC PATH: {logic_path}

Write only the letter. No preamble, no commentary."""

    reprocess_letter = simple_generate(reprocess_prompt)

    # ── APPEAL LETTER ────────────────────────────────────────────────────────
    if logic_path == "no_support_appeal_only":
        appeal_stance = (
            f"The medical record does not clearly support medical necessity. "
            f"However, the following conditions are documented: {documented}. "
            f"Appeal by explaining the clinical context and what conditions were present, "
            f"and request payment based on the overall clinical picture. "
            f"Note what documentation would have strengthened the case: {missing_doc}."
        )
    elif logic_path in ("record_supports_corrected_claim", "record_supports_appeal_only"):
        appeal_stance = (
            f"The medical record documents the following conditions supporting necessity: {documented}. "
            f"Build the appeal around these documented conditions and request payment."
        )
    else:
        appeal_stance = (
            f"Policy supports this service. If the payer representative refuses to reprocess, "
            f"use this appeal citing: {policy_citation_block}"
        )

    appeal_prompt = f"""You are a healthcare reimbursement specialist. Write a formal APPEAL LETTER
to the insurance payer's appeals department. This letter is the backup if the reprocess request is refused.

Format the letter EXACTLY as follows:

Dear [INSERT PAYER NAME] Appeals Department,

Re: Formal Appeal — Claim Denied CARC {denial_code} (Not Medically Necessary)
[Include claim number, patient name token, member ID token, and dates of service from context]

We are formally appealing the denial of the above-referenced claim under CARC {denial_code},
indicating the service was not considered medically necessary.

Reason for Denial:
[State the denial reason as received]

[If applicable — Policy Supporting Medical Necessity:]
[Cite CMS LCD/NCD name and number OR payer policy name and number]
[Explain what the policy states and how this claim meets the criteria]

Medical Necessity Justification:
[Explain the patient's condition and why the service was medically necessary based on documented findings]

[If corrected claim path: Note any coding corrections being submitted with this appeal]

As the service was medically necessary and appropriate for the patient's documented condition,
we respectfully request that this claim be processed towards payment.
The complete medical records are attached for your review.

[Provider Name — Placeholder]
[Contact Number — Placeholder]

CONTEXT:
{intake_summary}

POLICY FINDINGS:
{policy_citation_block}

APPEAL STANCE:
{appeal_stance}

MISSING CONDITIONS ON CLAIM:
{missing_conditions}

Write only the letter. No preamble, no commentary."""

    appeal_letter = simple_generate(appeal_prompt)

    return {
        "training_status": training_status,
        "logic_path": logic_path,
        "policy": {
            "cms_supports": policy_result.get("cms_supports"),
            "cms_policy_name": cms_name,
            "cms_policy_number": cms_num,
            "cms_policy_summary": cms_summary,
            "payer_supports": policy_result.get("payer_supports"),
            "payer_policy_name": payer_name,
            "payer_policy_number": payer_num,
            "payer_policy_summary": payer_summary,
            "required_conditions": policy_result.get("required_conditions", []),
            "missing_conditions": policy_result.get("missing_conditions", []),
            "overall_policy_supports": policy_supports,
            "policy_reasoning": policy_result.get("policy_reasoning", ""),
        },
        "record": {
            "record_supports_mn": record_supports,
            "documented_conditions": record_result.get("documented_conditions", []),
            "missing_documentation": record_result.get("missing_documentation", []),
            "can_correct_codes": can_correct,
            "record_summary": record_result.get("record_summary", ""),
        },
        "corrected_claim": {
            "has_corrections": can_correct,
            "cpt_changes": record_result.get("cpt_changes", []),
            "dx_changes": record_result.get("dx_changes", []),
            "modifier_changes": record_result.get("modifier_changes", []),
            "revenue_code_changes": record_result.get("revenue_code_changes", []),
        },
        "reprocess_letter": reprocess_letter,
        "appeal_letter": appeal_letter,
    }
