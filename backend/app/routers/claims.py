"""
Denial appeal pipeline endpoints.

Two-step HIPAA-safe flow:
  STEP 1 — POST /api/claims/scan
    Takes only the medical record file.
    Runs PHI detection LOCALLY (zero AI, zero network).
    Returns PHI report + tokenized text to frontend.
    User reviews what was redacted BEFORE anything goes to AI.

  STEP 2 — POST /api/claims/submit
    Takes form data + pre-tokenized text (sent back from frontend).
    Gemini only ever sees the tokenized text — never raw PHI.
    Returns full appeal result including letters.
"""
import json
from fastapi import APIRouter, UploadFile, Form, HTTPException

from app.models.schemas import (
    ClaimIntake, AppealResult, DenialClassification, PolicyFinding,
    CodingRecommendations, CptChange, DxChange, ModifierChange,
    RevenueCodeChange, OtherRecommendation,
    MedicalNecessityResult, MNPolicy, MNRecord, MNCorrectedClaim,
    PhiReport
)
from app.services.carc_classifier import classify_denial
from app.services.record_extractor import extract_text
from app.services.phi_deidentifier import detect_phi_entities, tokenize, reidentify, phi_report
from app.services import gemini_service

router = APIRouter()

MN_CARC_CODES = {"50", "CO50", "CO-50", "OA50", "OA-50"}


def _is_mn_denial(denial_code: str) -> bool:
    normalized = denial_code.strip().upper().replace(" ", "")
    return normalized in MN_CARC_CODES or normalized.lstrip("COOA-") == "50"


def _build_intake_summary(intake: ClaimIntake, classification: DenialClassification) -> str:
    lines = [
        f"Payor: {intake.claim_payor}",
        f"Denial Code (CARC): {intake.denial_code}" + (f" - {classification.carc_description}" if classification.carc_description else ""),
        f"Denial Reason Code (RARC): {intake.denial_reason_code or 'N/A'}",
        f"Denial Category: {classification.category}",
        f"Billed CPT/HCPCS: {', '.join(intake.billed_codes) or 'N/A'}",
        f"Dx Codes: {', '.join(intake.dx_codes) or 'N/A'}",
        f"Revenue Codes: {', '.join(intake.revenue_codes or []) or 'N/A'}",
        f"Condition Codes: {', '.join(intake.condition_codes or []) or 'N/A'}",
        f"Occurrence Codes: {', '.join(intake.occurrence_codes or []) or 'N/A'}",
        f"Value Codes: {', '.join(f'{v.code}=${v.amount}' for v in (intake.value_codes or [])) or 'N/A'}",
        f"DRG: {intake.drg_code or 'N/A'}",
        f"Type of Bill: {intake.type_of_bill or 'N/A'}",
        f"Visit Type: {intake.visit_type or 'N/A'}",
        f"Specialty Type: {intake.specialty_type or 'N/A'}",
        f"Taxonomy Code: {intake.taxonomy_code or 'N/A'}",
    ]
    return "\n".join(lines)


def _codes_summary(intake: ClaimIntake) -> str:
    return f"CPT/HCPCS: {', '.join(intake.billed_codes)} | Dx: {', '.join(intake.dx_codes)} | Revenue: {', '.join(intake.revenue_codes or [])} | DRG: {intake.drg_code or 'N/A'}"


def _build_coding_recommendations(raw: dict) -> CodingRecommendations:
    return CodingRecommendations(
        has_recommendations=raw.get("has_recommendations", False),
        cpt_changes=[CptChange(**x) for x in raw.get("cpt_changes", [])],
        dx_changes=[DxChange(**x) for x in raw.get("dx_changes", [])],
        modifier_changes=[ModifierChange(**x) for x in raw.get("modifier_changes", [])],
        revenue_code_changes=[RevenueCodeChange(**x) for x in raw.get("revenue_code_changes", [])],
        other_recommendations=[OtherRecommendation(**x) for x in raw.get("other_recommendations", [])],
        summary=raw.get("summary", ""),
    )


def _build_mn_result(raw: dict, token_map: dict) -> MedicalNecessityResult:
    p = raw.get("policy", {})
    r = raw.get("record", {})
    c = raw.get("corrected_claim", {})
    return MedicalNecessityResult(
        training_status=raw.get("training_status", "general_mn_logic"),
        logic_path=raw.get("logic_path", ""),
        policy=MNPolicy(
            cms_supports=p.get("cms_supports"),
            cms_policy_name=p.get("cms_policy_name"),
            cms_policy_number=p.get("cms_policy_number"),
            cms_policy_summary=p.get("cms_policy_summary"),
            payer_supports=p.get("payer_supports"),
            payer_policy_name=p.get("payer_policy_name"),
            payer_policy_number=p.get("payer_policy_number"),
            payer_policy_summary=p.get("payer_policy_summary"),
            required_conditions=p.get("required_conditions", []),
            missing_conditions=p.get("missing_conditions", []),
            overall_policy_supports=p.get("overall_policy_supports"),
            policy_reasoning=p.get("policy_reasoning"),
        ),
        record=MNRecord(
            record_supports_mn=r.get("record_supports_mn", False),
            documented_conditions=r.get("documented_conditions", []),
            missing_documentation=r.get("missing_documentation", []),
            can_correct_codes=r.get("can_correct_codes", False),
            record_summary=r.get("record_summary"),
        ),
        corrected_claim=MNCorrectedClaim(
            has_corrections=c.get("has_corrections", False),
            cpt_changes=[CptChange(**x) for x in c.get("cpt_changes", [])],
            dx_changes=[DxChange(**x) for x in c.get("dx_changes", [])],
            modifier_changes=[ModifierChange(**x) for x in c.get("modifier_changes", [])],
            revenue_code_changes=[RevenueCodeChange(**x) for x in c.get("revenue_code_changes", [])],
        ),
        reprocess_letter=reidentify(raw.get("reprocess_letter", ""), token_map),
        appeal_letter=reidentify(raw.get("appeal_letter", ""), token_map),
    )


# ── STEP 1: PHI Scan endpoint ─────────────────────────────────────────────────

@router.post("/claims/scan")
async def scan_record(medical_record: UploadFile):
    """
    Scan uploaded medical record for PHI locally.
    Zero AI calls. Zero network. Returns PHI report + tokenized text.
    Frontend shows report to user before anything goes to Gemini.
    """
    file_bytes = await medical_record.read()
    raw_text = extract_text(file_bytes, medical_record.filename)

    # Local PHI detection — no AI, no network
    entities = detect_phi_entities(raw_text)

    # Build token map and tokenized text
    deidentified_text, token_map = tokenize(raw_text, entities)

    # Build report for UI
    report = phi_report(entities)

    return {
        "phi_report": report,
        "deidentified_text": deidentified_text,
        "token_map": token_map,
        "entity_count": len(entities),
    }


# ── STEP 2: Submit endpoint ───────────────────────────────────────────────────

@router.post("/claims/submit", response_model=AppealResult)
async def submit_claim(
    intake_json: str = Form(..., description="JSON-encoded ClaimIntake"),
    deidentified_text: str = Form(default="", description="Pre-tokenized record text from scan step"),
    token_map_json: str = Form(default="{}", description="JSON token map from scan step"),
    medical_record: UploadFile = None,
):
    """
    Run full denial appeal pipeline.
    Gemini only ever sees deidentified_text — never raw PHI.
    If deidentified_text is provided (from scan step), use it directly.
    If not, run scan inline (fallback for no-record submissions).
    """
    try:
        intake = ClaimIntake(**json.loads(intake_json))
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid intake data: {e}")

    if intake.specialty_type and not intake.taxonomy_code:
        if intake.denial_code.strip().upper().lstrip("CO-") == "B7":
            raise HTTPException(
                status_code=422,
                detail="Taxonomy code is required for NPI/specialty-related denials (e.g. CARC B7).",
            )

    # Step 1: classify
    classification = classify_denial(intake.denial_code)

    # Step 2: use pre-tokenized text from scan step if available
    token_map = {}
    deidentified_record_excerpt = "No medical record provided."
    phi_report_data = PhiReport()

    if deidentified_text and deidentified_text.strip():
        # Frontend already scanned and user confirmed — use tokenized text directly
        try:
            token_map = json.loads(token_map_json)
        except json.JSONDecodeError:
            token_map = {}
        deidentified_record_excerpt = deidentified_text[:6000]
        phi_report_data = PhiReport(
            total_entities=len(token_map),
            by_type={},
            types_found=[],
            summary=f"{len(token_map)} PHI tokens replaced before AI processing."
        )

    elif medical_record is not None:
        # Fallback: no pre-scan, run inline (no record case)
        file_bytes = await medical_record.read()
        raw_text = extract_text(file_bytes, medical_record.filename)
        entities = detect_phi_entities(raw_text)
        phi_report_data = PhiReport(**phi_report(entities))
        deidentified_text_inline, token_map = tokenize(raw_text, entities)
        deidentified_record_excerpt = deidentified_text_inline[:6000]

    intake_summary = _build_intake_summary(intake, classification)
    full_context = f"{intake_summary}\n\nMedical Record Excerpt (de-identified):\n{deidentified_record_excerpt}"

    # ── Route: MN vs standard ─────────────────────────────────────────────────
    if _is_mn_denial(intake.denial_code) or classification.category == "medical_necessity":

        mn_raw = gemini_service.medical_necessity_analysis(
            payor=intake.claim_payor,
            intake_summary=intake_summary,
            codes_summary=_codes_summary(intake),
            record_text=deidentified_record_excerpt,
            denial_code=intake.denial_code,
        )
        mn_result = _build_mn_result(mn_raw, token_map)

        policy_result = gemini_service.grounded_policy_research(
            payor=intake.claim_payor,
            category=classification.category,
            codes_summary=_codes_summary(intake),
            denial_code=intake.denial_code,
        )

        return AppealResult(
            classification=classification,
            denial_valid=bool(policy_result.get("denial_valid")),
            policy_findings=[PolicyFinding(**f) for f in policy_result.get("policy_findings", [])],
            letter=mn_result.appeal_letter,
            reasoning_summary=policy_result.get("reasoning_summary", ""),
            coding_recommendations=None,
            medical_necessity=mn_result,
            phi_report=phi_report_data,
        )

    else:
        policy_result = gemini_service.grounded_policy_research(
            payor=intake.claim_payor,
            category=classification.category,
            codes_summary=_codes_summary(intake),
            denial_code=intake.denial_code,
        )

        coding_raw = gemini_service.analyze_coding_gaps(
            intake_summary=intake_summary,
            record_text=deidentified_record_excerpt,
        )
        coding_recommendations = _build_coding_recommendations(coding_raw)

        letter_tokenized = gemini_service.generate_letter(
            intake_summary=full_context,
            classification=classification.model_dump(),
            policy_result=policy_result,
        )
        final_letter = reidentify(letter_tokenized, token_map)

        return AppealResult(
            classification=classification,
            denial_valid=bool(policy_result.get("denial_valid")),
            policy_findings=[PolicyFinding(**f) for f in policy_result.get("policy_findings", [])],
            letter=final_letter,
            reasoning_summary=policy_result.get("reasoning_summary", ""),
            coding_recommendations=coding_recommendations,
            medical_necessity=None,
            phi_report=phi_report_data,
        )
