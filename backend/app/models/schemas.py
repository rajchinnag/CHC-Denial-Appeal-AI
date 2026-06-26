"""
Schemas for the denial appeal intake form and pipeline output.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ValueCodeAmount(BaseModel):
    code: str
    amount: float


class ClaimIntake(BaseModel):
    # --- Claim / payor context ---
    claim_payor: str = Field(..., description="Name of the insurance payor")
    denial_code: str = Field(..., description="CARC - Claim Adjustment Reason Code")
    denial_reason_code: Optional[str] = Field(None, description="RARC - Remittance Advice Remark Code")

    # --- Billed codes ---
    billed_codes: List[str] = Field(default_factory=list, description="CPT / HCPCS codes billed")
    dx_codes: List[str] = Field(default_factory=list, description="ICD-10 Dx codes billed")
    revenue_codes: Optional[List[str]] = Field(default_factory=list)
    condition_codes: Optional[List[str]] = Field(default_factory=list)
    occurrence_codes: Optional[List[str]] = Field(default_factory=list)
    value_codes: Optional[List[ValueCodeAmount]] = Field(default_factory=list)
    drg_code: Optional[str] = None

    # --- Claim form / visit context ---
    type_of_bill: Optional[str] = Field(None, description="UB-04 Type of Bill, e.g. 131")
    visit_type: Optional[str] = Field(None, description="e.g. Inpatient, Outpatient, ED, Office visit")
    specialty_type: Optional[str] = Field(None, description="Rendering provider specialty")

    # --- Conditional: only required if the denial is specialty/NPI related ---
    taxonomy_code: Optional[str] = Field(
        None, description="NPI taxonomy code — required when denial relates to provider specialty/NPI mismatch"
    )

    @field_validator("billed_codes", "dx_codes")
    @classmethod
    def not_empty_core_codes(cls, v):
        return v or []


class DenialClassification(BaseModel):
    category: str  # coding | medical_necessity | experimental | authorization | bill_type | unclassified
    carc_description: Optional[str] = None
    confidence: str  # "lookup" | "gemini_inferred"


class PolicyFinding(BaseModel):
    policy_name: str
    source_url: Optional[str] = None
    summary: str  # Claude/Gemini's own words, not quoted text from the source


class AppealResult(BaseModel):
    classification: DenialClassification
    denial_valid: bool
    policy_findings: List[PolicyFinding]
    letter: str
    reasoning_summary: str
