"""
Pydantic schemas for Admin Portal API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class SourceType(str, Enum):
    WEBSITE = "website"
    PDF = "pdf"
    DOC = "doc"
    FAQ = "faq"
    SOP = "sop"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# =============================================================================
# Auth Schemas
# =============================================================================

class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class AdminUser(BaseModel):
    username: str
    role: str = "admin"


# =============================================================================
# Practice Schemas
# =============================================================================

class PracticeInfo(BaseModel):
    practice_id: str
    name: str
    status: str = "active"
    document_count: int = 0
    last_indexed_at: Optional[datetime] = None


class PracticeListResponse(BaseModel):
    practices: List[PracticeInfo]
    total: int


# =============================================================================
# Document Schemas
# =============================================================================

class DocumentInfo(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    source_uri: Optional[str] = None
    status: DocumentStatus
    subagents_allowed: List[str] = ["chat", "clinical"]
    chunk_count: int = 0
    last_indexed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int
    practice_id: str


class DocumentPreview(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    status: DocumentStatus
    preview_text: str
    chunk_count: int
    metadata: dict = {}


class SourceInfo(BaseModel):
    source_type: SourceType
    document_count: int
    total_chunks: int
    status: str
    last_indexed_at: Optional[datetime] = None


class SourceListResponse(BaseModel):
    sources: List[SourceInfo]
    practice_id: str


# =============================================================================
# Re-index Schemas
# =============================================================================

class ReindexRequest(BaseModel):
    force: bool = False


class ReindexResponse(BaseModel):
    status: str
    message: str
    job_id: Optional[str] = None


# =============================================================================
# Health Schemas
# =============================================================================

class EndpointHealth(BaseModel):
    status: HealthStatus
    response_time_ms: Optional[int] = None
    last_checked: datetime
    error: Optional[str] = None


class PineconeHealth(BaseModel):
    status: HealthStatus
    vectors_count: int = 0
    namespace: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    practice_id: str
    chat_endpoint: EndpointHealth
    clinical_endpoint: EndpointHealth
    pinecone: PineconeHealth
    overall_status: HealthStatus


# =============================================================================
# Clinical Advisor Config Schemas (Practice Intelligence Intake)
# =============================================================================

class PhilosophyBias(str, Enum):
    """Supported clinical philosophy biases."""
    SPEAR = "spear"
    KOIS = "kois"
    DAWSON = "dawson"
    PANKEY = "pankey"
    AGD = "agd"
    CONSERVATIVE = "conservative"
    MIXED = "mixed"


class BiasStrength(str, Enum):
    """How strongly the philosophy influences decisions."""
    STRONG = "strong"
    MODERATE = "moderate"
    GENERAL = "general"


class ImplantApproach(str, Enum):
    """Implant service approach."""
    RESTORATIVE_ONLY = "restorative_only"
    PLACEMENT_AND_RESTORATION = "placement_and_restoration"
    NOT_PERFORMED = "not_performed"


class TeamStability(str, Enum):
    """Team experience/stability level."""
    HIGHLY_EXPERIENCED = "highly_experienced"
    MIXED = "mixed"
    NEWER_TEAM = "newer_team"


class HygieneModel(str, Enum):
    """Hygiene service model."""
    TRADITIONAL = "traditional"
    ASSISTED = "assisted"
    STRUCTURED_PERIO = "structured_perio"


class ReferralView(str, Enum):
    """View on referrals."""
    CORE_TO_QUALITY = "core_to_quality"
    SITUATIONAL = "situational"
    TRYING_TO_REDUCE = "trying_to_reduce"


class DocumentationLevel(str, Enum):
    """Documentation practice level."""
    STRONG = "strong"
    ADEQUATE = "adequate"
    NEEDS_IMPROVEMENT = "needs_improvement"


class TreatmentApproach(str, Enum):
    """Overall treatment approach."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    COMPREHENSIVE = "comprehensive"


class CaseComplexity(str, Enum):
    """How complexity is handled."""
    REFER_EARLY = "refer_early"
    MODERATE_IN_HOUSE = "moderate_in_house"
    ADVANCED_IN_HOUSE = "advanced_in_house"


# Nested config schemas
class PhilosophyConfig(BaseModel):
    """Clinical philosophy configuration."""
    primary_bias: PhilosophyBias = PhilosophyBias.AGD
    secondary_bias: Optional[PhilosophyBias] = None
    bias_strength: BiasStrength = BiasStrength.MODERATE
    additional_context: Optional[str] = Field(None, max_length=500)


class PediatricConfig(BaseModel):
    """Pediatric services configuration."""
    min_age: Optional[int] = Field(None, ge=0, le=18)
    limited: bool = False
    referred: bool = False


class ProceduresConfig(BaseModel):
    """Procedures performed in-house."""
    endodontics: List[str] = Field(default_factory=list)  # anterior, premolar, molar, referred
    extractions: List[str] = Field(default_factory=list)  # simple, surgical, third_molars, referred
    implants: ImplantApproach = ImplantApproach.NOT_PERFORMED
    sedation: List[str] = Field(default_factory=list)  # none, oral, nitrous, iv
    pediatric: Optional[PediatricConfig] = None
    other_services: List[str] = Field(default_factory=list)


class EquipmentConfig(BaseModel):
    """Equipment and technology configuration."""
    imaging: List[str] = Field(default_factory=list)  # digital_pa, panoramic, cbct
    digital_dentistry: List[str] = Field(default_factory=list)  # intraoral_scanner, cad_cam, digital_impressions
    other: List[str] = Field(default_factory=list)
    limitations: Optional[str] = Field(None, max_length=300)


class TeamConfig(BaseModel):
    """Team experience configuration."""
    provider_years: Optional[str] = None  # 0-5, 5-10, 10-20, 20+
    team_stability: Optional[TeamStability] = None
    hygiene_model: Optional[HygieneModel] = None


class ReferralConfig(BaseModel):
    """Referral philosophy configuration."""
    primary_reasons: List[str] = Field(default_factory=list)  # complexity, time, risk, philosophy
    view: Optional[ReferralView] = None


class RiskConfig(BaseModel):
    """Risk sensitivity configuration."""
    documentation_level: Optional[DocumentationLevel] = None
    extra_caution_areas: List[str] = Field(default_factory=list)  # board_scrutiny, malpractice, conservative_culture


class OperationalConfig(BaseModel):
    """Operational preferences configuration."""
    treatment_approach: Optional[TreatmentApproach] = None
    case_complexity: Optional[CaseComplexity] = None


class ClinicalAdvisorConfig(BaseModel):
    """
    Complete Clinical Advisor configuration from Practice Intelligence Intake.

    This is the main schema for clinical_advisor_config stored in profile_json.
    """
    philosophy: PhilosophyConfig = Field(default_factory=PhilosophyConfig)
    procedures_in_house: ProceduresConfig = Field(default_factory=ProceduresConfig)
    equipment_technology: EquipmentConfig = Field(default_factory=EquipmentConfig)
    team_experience: TeamConfig = Field(default_factory=TeamConfig)
    referral_philosophy: ReferralConfig = Field(default_factory=ReferralConfig)
    risk_sensitivity: RiskConfig = Field(default_factory=RiskConfig)
    operational_preferences: OperationalConfig = Field(default_factory=OperationalConfig)
    additional_notes: Optional[str] = Field(None, max_length=1000)


class ClinicalConfigResponse(BaseModel):
    """Response for clinical config GET endpoint."""
    practice_id: str
    practice_name: str
    config: Optional[ClinicalAdvisorConfig] = None
    profile_version: int = 0
    has_cached_summary: bool = False
    injection_preview: Optional[str] = None
    estimated_tokens: Optional[int] = None
    updated_at: Optional[datetime] = None


class ClinicalConfigUpdateRequest(BaseModel):
    """Request to update clinical advisor config."""
    config: ClinicalAdvisorConfig


class ClinicalConfigUpdateResponse(BaseModel):
    """Response after updating clinical config."""
    status: str
    message: str
    practice_id: str
    profile_version: int
    injection_preview: str
    estimated_tokens: int
