"""
Schemas for the denial appeal intake form and pipeline output.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class ValueCodeAmount(BaseModel):
    code: str
    amount: float


class ClaimIntake(BaseModel):
    claim_payor: str = Field(..., description="Name of the insurance payor")
    denial_code: str = Field(..., description="CARC - Claim Adjustment Reason Code")
    denial_reason_code: Optional[str] = Field(None, description="RARC - Remittance Advice Remark Code")
    billed_codes: List[str] = Field(default_factory=list, description="CPT / HCPCS codes billed")
    dx_codes: List[str] = Field(default_factory=list, description="ICD-10 Dx codes billed")
    revenue_codes: Optional[List[str]] = Field(default_factory=list)
    condition_codes: Optional[List[str]] = Field(default_factory=list)
    occurrence_codes: Optional[List[str]] = Field(default_factory=list)
    value_codes: Optional[List[ValueCodeAmount]] = Field(default_factory=list)
    drg_code: Optional[str] = None
    type_of_bill: Optional[str] = Field(None, description="UB-04 Type of Bill, e.g. 131")
    visit_type: Optional[str] = Field(None, description="e.g. Inpatient, Outpatient, ED, Office visit")
    specialty_type: Optional[str] = Field(None, description="Rendering provider specialty")
    taxonomy_code: Optional[str] = Field(None, description="NPI taxonomy code")

    @field_validator("billed_codes", "dx_codes")
    @classmethod
    def not_empty_core_codes(cls, v):
        return v or []


class DenialClassification(BaseModel):
    category: str
    carc_description: Optional[str] = None
    confidence: str


class PolicyFinding(BaseModel):
    policy_name: str
    source_url: Optional[str] = None
    summary: str


class CptChange(BaseModel):
    current: Optional[str] = None
    suggested: Optional[str] = None
    reason: Optional[str] = None


class DxChange(BaseModel):
    action: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None


class ModifierChange(BaseModel):
    action: Optional[str] = None
    modifier: Optional[str] = None
    reason: Optional[str] = None


class RevenueCodeChange(BaseModel):
    current: Optional[str] = None
    suggested: Optional[str] = None
    reason: Optional[str] = None


class OtherRecommendation(BaseModel):
    recommendation: Optional[str] = None
    reason: Optional[str] = None


class CodingRecommendations(BaseModel):
    has_recommendations: bool = False
    cpt_changes: List[CptChange] = []
    dx_changes: List[DxChange] = []
    modifier_changes: List[ModifierChange] = []
    revenue_code_changes: List[RevenueCodeChange] = []
    other_recommendations: List[OtherRecommendation] = []
    summary: str = ""


class AppealResult(BaseModel):
    classification: DenialClassification
    denial_valid: bool
    policy_findings: List[PolicyFinding]
    letter: str
    reasoning_summary: str
    coding_recommendations: Optional[CodingRecommendations] = None
