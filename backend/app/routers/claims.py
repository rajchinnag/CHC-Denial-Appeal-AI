"""
The single orchestration endpoint for the denial appeal pipeline.

Flow:
  1. Parse + validate the structured intake form.
  2. Classify the denial via CARC lookup (fallback: treat as unclassified,
     let Gemini's policy research step reason about category from context).
  3. Extract text from the uploaded medical record.
  4. De-identify PHI -> de-identified text + in-memory token map.
  5. Gemini, with Search grounding: find the payor's actual policy and
     determine validity of the denial.
  6. Gemini: generate the appeal or reconsideration letter (still token'd).
  7. Re-identify -> swap tokens back to real PHI in the final letter only.
  8. Return result. The token map is discarded when this function returns —
     never persisted, never logged.
"""
import json
from fastapi import APIRouter, UploadFile, Form, HTTPException

from app.models.schemas import ClaimIntake, AppealResult, DenialClassification, PolicyFinding
from app.services.carc_classifier import classify_denial
from app.services.record_extractor import extract_text
from app.services.phi_deidentifier import detect_phi_entities, tokenize, reidentify
from app.services import gemini_service

router = APIRouter()


def _build_intake_summary(intake: ClaimIntake, classification: DenialClassification) -> str:
    lines = [
        f"Payor: {intake.claim_payor}",
        f"Denial Code (CARC): {intake.denial_code}" + (f" — {classification.carc_description}" if classification.carc_description else ""),
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
    return f"CPT/HCPCS: {', '.join(intake.billed_codes)} | Dx: {', '.join(intake.dx_codes)} | DRG: {intake.drg_code or 'N/A'}"


@router.post("/claims/submit", response_model=AppealResult)
async def submit_claim(
    intake_json: str = Form(..., description="JSON-encoded ClaimIntake"),
    medical_record: UploadFile = None,
):
    try:
        intake = ClaimIntake(**json.loads(intake_json))
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid intake data: {e}")

    # Conditional validation: specialty/NPI denials require taxonomy
    if intake.specialty_type and not intake.taxonomy_code:
        # Soft check — only enforce if this clearly looks like a specialty/NPI denial.
        # CARC B7 and similar codes relate to provider eligibility/specialty.
        if intake.denial_code.strip().upper().lstrip("CO-") == "B7":
            raise HTTPException(
                status_code=422,
                detail="Taxonomy code is required for NPI/specialty-related denials (e.g. CARC B7).",
            )

    # Step 1: classify
    classification = classify_denial(intake.denial_code)

    # Step 2: extract + de-identify the medical record (if provided)
    token_map = {}
    deidentified_record_excerpt = "No medical record provided."
    if medical_record is not None:
        file_bytes = await medical_record.read()
        raw_text = extract_text(file_bytes, medical_record.filename)

        entities = detect_phi_entities(raw_text, gemini_detect_fn=gemini_service.simple_generate)
        deidentified_text, token_map = tokenize(raw_text, entities)
        deidentified_record_excerpt = deidentified_text[:6000]  # keep prompt size sane

    intake_summary = _build_intake_summary(intake, classification)
    full_context = f"{intake_summary}\n\nMedical Record Excerpt (de-identified):\n{deidentified_record_excerpt}"

    # Step 3: grounded policy research + validity determination
    policy_result = gemini_service.grounded_policy_research(
        payor=intake.claim_payor,
        category=classification.category,
        codes_summary=_codes_summary(intake),
        denial_code=intake.denial_code,
    )

    # Step 4: generate the letter (still contains PHI tokens)
    letter_tokenized = gemini_service.generate_letter(
        intake_summary=full_context,
        classification=classification.model_dump(),
        policy_result=policy_result,
    )

    # Step 5: re-identify — restore real PHI into the final letter only.
    # token_map goes out of scope and is garbage-collected once this returns.
    final_letter = reidentify(letter_tokenized, token_map)

    return AppealResult(
        classification=classification,
        denial_valid=bool(policy_result.get("denial_valid")),
        policy_findings=[PolicyFinding(**f) for f in policy_result.get("policy_findings", [])],
        letter=final_letter,
        reasoning_summary=policy_result.get("reasoning_summary", ""),
    )
