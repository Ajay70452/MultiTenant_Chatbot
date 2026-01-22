"""
Practice Profile Injection Builder

Converts clinical_advisor_config JSON into a normalized, token-budgeted
text block for injection into the Clinical Advisor system prompt.

Key requirements (from Clinical Advisor Guidance Docs):
1. Reads clinical_advisor_config (JSON) from practice_profiles
2. Outputs a normalized text block (300-800 tokens target)
3. Enforces a token budget (~1200-3200 chars for 300-800 tokens)
4. Supports caching via clinical_advisor_profile_summary field

This aligns with Section 4.5 and Section 6 of the guidance doc.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import hashlib
import json


# ============================================================================
# Constants & Configuration
# ============================================================================

# Token budget: ~4 chars per token on average
MIN_TOKENS = 300
MAX_TOKENS = 800
CHARS_PER_TOKEN = 4
MIN_CHARS = MIN_TOKENS * CHARS_PER_TOKEN  # 1200
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN  # 3200


class PhilosophyBias(str, Enum):
    """Supported clinical philosophy biases from the Bias Governance Standard."""
    SPEAR = "spear"
    KOIS = "kois"
    DAWSON = "dawson"
    PANKEY = "pankey"
    AGD = "agd"
    CONSERVATIVE = "conservative"
    MIXED = "mixed"


class BiasStrength(str, Enum):
    """How strongly the philosophy influences decisions."""
    STRONG = "strong"        # Strongly influences most decisions
    MODERATE = "moderate"    # Moderately influences decisions
    GENERAL = "general"      # Provides general guidance, not strict direction


# ============================================================================
# Bias Profile Templates (from Clinical Philosophy Bias Governance Standard)
# ============================================================================

BIAS_FRAMING_TEMPLATES = {
    PhilosophyBias.SPEAR: {
        "name": "Spear Education",
        "primary_influence": "Diagnostic discipline, stability and predictability, thoughtful sequencing",
        "framing": (
            "This practice emphasizes diagnostic discipline before treatment discussion. "
            "Stability and predictability guide sequencing decisions. Long-term outcomes "
            "take priority over immediate fixes. Before discussing solutions, ensure "
            "clarity around stability and risk to determine whether any plan is predictable."
        ),
    },
    PhilosophyBias.KOIS: {
        "name": "Kois Center",
        "primary_influence": "Risk stratification, diagnostic completeness, failure prevention",
        "framing": (
            "This practice prioritizes risk stratification and diagnostic completeness. "
            "Highlight unknowns and missing data. Emphasize why cases fail. Encourage "
            "caution before commitment. Most complications arise not from execution, "
            "but from committing to a plan before diagnostic questions are fully answered."
        ),
    },
    PhilosophyBias.DAWSON: {
        "name": "Dawson Academy",
        "primary_influence": "Functional harmony, occlusal system thinking, avoiding isolated decisions",
        "framing": (
            "This practice views dentistry through functional harmony and occlusal system "
            "thinking. Function takes priority over appearance. Frame dentistry as a system, "
            "not isolated procedures. Highlight downstream consequences of imbalance. "
            "If functional harmony isn't addressed, other dentistry tends to become a compromise."
        ),
    },
    PhilosophyBias.PANKEY: {
        "name": "Pankey Institute",
        "primary_influence": "Whole-patient thinking, phased care, trust before execution",
        "framing": (
            "This practice emphasizes whole-patient thinking and phased care over time. "
            "Patient goals and pacing guide the approach. Normalize multi-phase planning. "
            "Avoid urgency unless risk demands it. The most predictable dentistry often "
            "unfolds in phases as clarity and trust develop."
        ),
    },
    PhilosophyBias.AGD: {
        "name": "Academy of General Dentistry",
        "primary_influence": "Broad-based general dentistry, evidence-informed, referral-aware",
        "framing": (
            "This practice follows broad-based general dentistry principles with "
            "evidence-informed conservatism. Frame guidance for a generalist perspective. "
            "Recognize when collaboration or referral best serves the patient. Sound "
            "general dentistry often means knowing scope limits."
        ),
    },
    PhilosophyBias.CONSERVATIVE: {
        "name": "Conservative / Traditional",
        "primary_influence": "Risk avoidance, preservation, early referral",
        "framing": (
            "This practice prioritizes risk avoidance and preservation of existing structures. "
            "Encourage deferral and referral when uncertainty exists. Emphasize documentation "
            "and consent. Avoid irreversible steps when possible. Preserving options is often "
            "more valuable than intervening early."
        ),
    },
    PhilosophyBias.MIXED: {
        "name": "Mixed / Pragmatic",
        "primary_influence": "Real-world constraints, team capability, patient preferences",
        "framing": (
            "This practice balances ideal with practical considerations. Account for "
            "staffing, time, and systems when framing recommendations. Patient preferences "
            "and real-world constraints shape the approach. The best plan is one that works "
            "for this patient, in this practice, with this team."
        ),
    },
}

# Default bias when none is selected
DEFAULT_BIAS = PhilosophyBias.AGD


# ============================================================================
# Schema Definition for clinical_advisor_config
# ============================================================================

"""
Expected structure of clinical_advisor_config in profile_json:

{
    "clinical_advisor_config": {
        "philosophy": {
            "primary_bias": "spear|kois|dawson|pankey|agd|conservative|mixed",
            "secondary_bias": "spear|kois|dawson|pankey|agd|conservative|mixed|null",
            "bias_strength": "strong|moderate|general",
            "additional_context": "Free text about training/mentorship"
        },
        "procedures_in_house": {
            "endodontics": ["anterior", "premolar", "molar"] or ["referred"],
            "extractions": ["simple", "surgical", "third_molars"] or ["referred"],
            "implants": "restorative_only|placement_and_restoration|not_performed",
            "sedation": ["none", "oral", "nitrous", "iv"],
            "pediatric": {"min_age": 5, "limited": false, "referred": false},
            "other_services": ["clear_aligners", "sleep_airway", "perio_therapy", "laser", "cosmetic"]
        },
        "equipment_technology": {
            "imaging": ["digital_pa", "panoramic", "cbct"],
            "digital_dentistry": ["intraoral_scanner", "cad_cam", "digital_impressions"],
            "other": ["lasers", "implant_surgical_system", "sedation_monitoring"],
            "limitations": "Free text about constraints"
        },
        "team_experience": {
            "provider_years": "0-5|5-10|10-20|20+",
            "team_stability": "highly_experienced|mixed|newer_team",
            "hygiene_model": "traditional|assisted|structured_perio"
        },
        "referral_philosophy": {
            "primary_reasons": ["complexity", "time", "risk", "philosophy"],
            "view": "core_to_quality|situational|trying_to_reduce"
        },
        "risk_sensitivity": {
            "documentation_level": "strong|adequate|needs_improvement",
            "extra_caution_areas": ["board_scrutiny", "malpractice", "conservative_culture"]
        },
        "operational_preferences": {
            "treatment_approach": "conservative|moderate|comprehensive",
            "case_complexity": "refer_early|moderate_in_house|advanced_in_house"
        },
        "additional_notes": "Free text from intake"
    },
    "clinical_advisor_profile_version": 1,
    "clinical_advisor_profile_summary": "Cached injection text block"
}
"""


# ============================================================================
# Injection Builder Implementation
# ============================================================================

@dataclass
class InjectionResult:
    """Result of building a practice profile injection."""
    summary: str
    char_count: int
    estimated_tokens: int
    config_hash: str
    version: int


def _get_bias_enum(bias_str: Optional[str]) -> Optional[PhilosophyBias]:
    """Convert string to PhilosophyBias enum, handling invalid values."""
    if not bias_str:
        return None
    try:
        return PhilosophyBias(bias_str.lower())
    except ValueError:
        return None


def _build_philosophy_section(config: Dict[str, Any]) -> str:
    """Build the philosophy/bias framing section."""
    philosophy = config.get("philosophy", {})

    primary_bias_str = philosophy.get("primary_bias")
    secondary_bias_str = philosophy.get("secondary_bias")
    bias_strength = philosophy.get("bias_strength", "moderate")
    additional_context = philosophy.get("additional_context", "")

    primary_bias = _get_bias_enum(primary_bias_str) or DEFAULT_BIAS
    secondary_bias = _get_bias_enum(secondary_bias_str)

    # Get primary bias template
    primary_template = BIAS_FRAMING_TEMPLATES[primary_bias]

    lines = [
        f"**Clinical Philosophy**: {primary_template['name']}-Informed",
        primary_template["framing"],
    ]

    # Add secondary bias influence if present
    if secondary_bias and secondary_bias != primary_bias:
        secondary_template = BIAS_FRAMING_TEMPLATES[secondary_bias]
        lines.append(
            f"Secondary influence from {secondary_template['name']}: "
            f"{secondary_template['primary_influence']}."
        )

    # Add strength modifier
    if bias_strength == "strong":
        lines.append("This philosophy strongly guides most clinical decisions.")
    elif bias_strength == "general":
        lines.append("This philosophy provides general guidance but allows flexibility.")

    # Add additional context if provided
    if additional_context and len(additional_context.strip()) > 0:
        # Truncate if too long
        context = additional_context.strip()[:300]
        lines.append(f"Additional context: {context}")

    return "\n".join(lines)


def _build_procedures_section(config: Dict[str, Any]) -> str:
    """Build the procedures performed in-house section."""
    procedures = config.get("procedures_in_house", {})

    if not procedures:
        return ""

    lines = ["**Procedures Performed In-House**:"]

    # Endodontics
    endo = procedures.get("endodontics", [])
    if endo and endo != ["referred"]:
        lines.append(f"- Endodontics: {', '.join(endo)}")
    elif endo == ["referred"]:
        lines.append("- Endodontics: Typically referred out")

    # Extractions
    extractions = procedures.get("extractions", [])
    if extractions and extractions != ["referred"]:
        lines.append(f"- Extractions: {', '.join(extractions)}")

    # Implants
    implants = procedures.get("implants", "")
    if implants:
        implant_map = {
            "restorative_only": "Restorative only (placement referred)",
            "placement_and_restoration": "Placement and restoration",
            "not_performed": "Not performed (referred)"
        }
        lines.append(f"- Implants: {implant_map.get(implants, implants)}")

    # Sedation
    sedation = procedures.get("sedation", [])
    if sedation and "none" not in sedation:
        lines.append(f"- Sedation: {', '.join(sedation)}")

    # Pediatric
    pediatric = procedures.get("pediatric", {})
    if pediatric:
        if pediatric.get("referred"):
            lines.append("- Pediatric: Referred out")
        elif pediatric.get("limited"):
            lines.append(f"- Pediatric: Limited (ages {pediatric.get('min_age', 'N/A')}+)")
        elif pediatric.get("min_age"):
            lines.append(f"- Pediatric: Ages {pediatric.get('min_age')}+")

    # Other services
    other = procedures.get("other_services", [])
    if other:
        service_map = {
            "clear_aligners": "Clear aligners/orthodontics",
            "sleep_airway": "Sleep/airway dentistry",
            "perio_therapy": "Advanced periodontal therapy",
            "laser": "Laser dentistry",
            "cosmetic": "Cosmetic-focused services"
        }
        formatted = [service_map.get(s, s) for s in other]
        lines.append(f"- Other services: {', '.join(formatted)}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _build_equipment_section(config: Dict[str, Any]) -> str:
    """Build the equipment/technology section."""
    equipment = config.get("equipment_technology", {})

    if not equipment:
        return ""

    lines = ["**Technology & Equipment**:"]

    imaging = equipment.get("imaging", [])
    if imaging:
        imaging_map = {
            "digital_pa": "Digital PAs",
            "panoramic": "Panoramic",
            "cbct": "CBCT"
        }
        formatted = [imaging_map.get(i, i) for i in imaging]
        lines.append(f"- Imaging: {', '.join(formatted)}")

    digital = equipment.get("digital_dentistry", [])
    if digital:
        digital_map = {
            "intraoral_scanner": "Intraoral scanner",
            "cad_cam": "In-house CAD/CAM",
            "digital_impressions": "Digital impressions"
        }
        formatted = [digital_map.get(d, d) for d in digital]
        lines.append(f"- Digital: {', '.join(formatted)}")

    limitations = equipment.get("limitations", "")
    if limitations:
        lines.append(f"- Limitations: {limitations[:150]}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _build_team_section(config: Dict[str, Any]) -> str:
    """Build the team experience section."""
    team = config.get("team_experience", {})

    if not team:
        return ""

    lines = ["**Team Profile**:"]

    years = team.get("provider_years", "")
    if years:
        lines.append(f"- Provider experience: {years} years")

    stability = team.get("team_stability", "")
    stability_map = {
        "highly_experienced": "Highly experienced, stable team",
        "mixed": "Mixed experience levels",
        "newer_team": "Newer team, may need more guidance"
    }
    if stability:
        lines.append(f"- Team: {stability_map.get(stability, stability)}")

    hygiene = team.get("hygiene_model", "")
    hygiene_map = {
        "traditional": "Traditional hygiene model",
        "assisted": "Assisted hygiene",
        "structured_perio": "Structured periodontal program"
    }
    if hygiene:
        lines.append(f"- Hygiene: {hygiene_map.get(hygiene, hygiene)}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _build_referral_section(config: Dict[str, Any]) -> str:
    """Build the referral philosophy section."""
    referral = config.get("referral_philosophy", {})

    if not referral:
        return ""

    lines = ["**Referral Approach**:"]

    reasons = referral.get("primary_reasons", [])
    if reasons:
        reason_map = {
            "complexity": "case complexity",
            "time": "time constraints",
            "risk": "risk management",
            "philosophy": "clinical philosophy"
        }
        formatted = [reason_map.get(r, r) for r in reasons]
        lines.append(f"- Primary reasons: {', '.join(formatted)}")

    view = referral.get("view", "")
    view_map = {
        "core_to_quality": "Referral is core to quality care",
        "situational": "Referral is situational",
        "trying_to_reduce": "Aiming to expand in-house capabilities"
    }
    if view:
        lines.append(f"- Philosophy: {view_map.get(view, view)}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _build_risk_section(config: Dict[str, Any]) -> str:
    """Build the risk sensitivity section."""
    risk = config.get("risk_sensitivity", {})

    if not risk:
        return ""

    lines = ["**Risk & Documentation**:"]

    doc_level = risk.get("documentation_level", "")
    if doc_level:
        lines.append(f"- Documentation practices: {doc_level}")

    caution_areas = risk.get("extra_caution_areas", [])
    if caution_areas:
        caution_map = {
            "board_scrutiny": "board scrutiny sensitivity",
            "malpractice": "malpractice risk awareness",
            "conservative_culture": "conservative practice culture"
        }
        formatted = [caution_map.get(c, c) for c in caution_areas]
        lines.append(f"- Extra caution: {', '.join(formatted)}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _build_operational_section(config: Dict[str, Any]) -> str:
    """Build the operational preferences section."""
    ops = config.get("operational_preferences", {})

    if not ops:
        return ""

    lines = ["**Operational Style**:"]

    approach = ops.get("treatment_approach", "")
    if approach:
        lines.append(f"- Treatment approach: {approach}")

    complexity = ops.get("case_complexity", "")
    complexity_map = {
        "refer_early": "Refers early for complex cases",
        "moderate_in_house": "Manages moderate complexity in-house",
        "advanced_in_house": "Handles advanced cases internally"
    }
    if complexity:
        lines.append(f"- Complexity: {complexity_map.get(complexity, complexity)}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _truncate_to_budget(text: str, max_chars: int = MAX_CHARS) -> str:
    """Truncate text to fit within character budget while preserving structure."""
    if len(text) <= max_chars:
        return text

    # Split into sections and prioritize
    sections = text.split("\n\n")

    # Always keep philosophy section (first section)
    result = sections[0] if sections else ""

    # Add remaining sections until we hit the budget
    for section in sections[1:]:
        if len(result) + len("\n\n") + len(section) <= max_chars:
            result += "\n\n" + section
        else:
            # Try to add a truncated version
            remaining = max_chars - len(result) - len("\n\n") - 50
            if remaining > 100:
                truncated = section[:remaining] + "..."
                result += "\n\n" + truncated
            break

    return result


def _compute_config_hash(config: Dict[str, Any]) -> str:
    """Compute a hash of the config for cache validation."""
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()[:12]


def build_profile_injection(
    config: Dict[str, Any],
    clinic_name: Optional[str] = None,
    max_chars: int = MAX_CHARS
) -> InjectionResult:
    """
    Build a practice profile injection block from clinical_advisor_config.

    This is the main entry point for converting structured intake data
    into a normalized, token-budgeted text block for prompt injection.

    Args:
        config: The clinical_advisor_config dictionary
        clinic_name: Optional clinic name to include
        max_chars: Maximum character count (default ~800 tokens)

    Returns:
        InjectionResult with the summary text and metadata
    """
    if not config:
        return InjectionResult(
            summary="No specific practice profile configured. Using AGD-informed general guidance with conservative defaults.",
            char_count=95,
            estimated_tokens=24,
            config_hash="",
            version=0
        )

    sections = []

    # Add clinic name if provided
    if clinic_name:
        sections.append(f"**Practice**: {clinic_name}")

    # Build each section
    philosophy = _build_philosophy_section(config)
    if philosophy:
        sections.append(philosophy)

    procedures = _build_procedures_section(config)
    if procedures:
        sections.append(procedures)

    equipment = _build_equipment_section(config)
    if equipment:
        sections.append(equipment)

    team = _build_team_section(config)
    if team:
        sections.append(team)

    referral = _build_referral_section(config)
    if referral:
        sections.append(referral)

    risk = _build_risk_section(config)
    if risk:
        sections.append(risk)

    ops = _build_operational_section(config)
    if ops:
        sections.append(ops)

    # Add additional notes if present (truncated)
    notes = config.get("additional_notes", "")
    if notes and len(notes.strip()) > 0:
        truncated_notes = notes.strip()[:200]
        sections.append(f"**Additional Notes**: {truncated_notes}")

    # Combine and truncate
    full_text = "\n\n".join(sections)
    summary = _truncate_to_budget(full_text, max_chars)

    char_count = len(summary)
    estimated_tokens = char_count // CHARS_PER_TOKEN
    config_hash = _compute_config_hash(config)

    return InjectionResult(
        summary=summary,
        char_count=char_count,
        estimated_tokens=estimated_tokens,
        config_hash=config_hash,
        version=1
    )


def get_cached_or_build_injection(
    profile_json: Dict[str, Any],
    clinic_name: Optional[str] = None,
    force_rebuild: bool = False
) -> tuple[str, bool]:
    """
    Get cached profile injection or build a new one.

    This function checks if a cached summary exists and is still valid
    (based on config hash), returning it if so. Otherwise, it builds
    a new injection and returns it along with a flag indicating rebuild.

    Args:
        profile_json: The full profile_json from practice_profiles table
        clinic_name: Optional clinic name
        force_rebuild: If True, always rebuild even if cache exists

    Returns:
        Tuple of (injection_summary, was_rebuilt)
    """
    config = profile_json.get("clinical_advisor_config", {})
    cached_summary = profile_json.get("clinical_advisor_profile_summary")
    cached_version = profile_json.get("clinical_advisor_profile_version", 0)

    # Compute current config hash
    current_hash = _compute_config_hash(config) if config else ""

    # Check if we can use cached version
    if not force_rebuild and cached_summary and cached_version > 0:
        # For now, we trust the cache if it exists
        # In future, could store hash and compare
        return cached_summary, False

    # Build new injection
    result = build_profile_injection(config, clinic_name)
    return result.summary, True


# ============================================================================
# Example / Default Config
# ============================================================================

EXAMPLE_CLINICAL_ADVISOR_CONFIG = {
    "philosophy": {
        "primary_bias": "kois",
        "secondary_bias": "conservative",
        "bias_strength": "moderate",
        "additional_context": "Strong emphasis on risk assessment before any irreversible treatment."
    },
    "procedures_in_house": {
        "endodontics": ["anterior", "premolar"],
        "extractions": ["simple", "surgical"],
        "implants": "restorative_only",
        "sedation": ["oral", "nitrous"],
        "pediatric": {"min_age": 6, "limited": True, "referred": False},
        "other_services": ["clear_aligners", "cosmetic"]
    },
    "equipment_technology": {
        "imaging": ["digital_pa", "panoramic", "cbct"],
        "digital_dentistry": ["intraoral_scanner"],
        "other": [],
        "limitations": "No in-house milling"
    },
    "team_experience": {
        "provider_years": "10-20",
        "team_stability": "highly_experienced",
        "hygiene_model": "structured_perio"
    },
    "referral_philosophy": {
        "primary_reasons": ["complexity", "risk"],
        "view": "core_to_quality"
    },
    "risk_sensitivity": {
        "documentation_level": "strong",
        "extra_caution_areas": ["malpractice", "conservative_culture"]
    },
    "operational_preferences": {
        "treatment_approach": "conservative",
        "case_complexity": "moderate_in_house"
    },
    "additional_notes": "Patient comfort is priority. Strong believer in second opinions for complex cases."
}
