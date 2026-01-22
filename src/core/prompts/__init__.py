"""
Prompt Factory Module

This module contains prompt builders for different agent personalities:
- Patient Concierge (appointment booking)
- Clinical Advisor (doctor-facing assistant)

Includes the Practice Profile Injection Builder for converting
clinical_advisor_config into token-budgeted prompt injections.
"""

from src.core.prompts.patient import build_patient_prompt, PATIENT_SYSTEM_PROMPT
from src.core.prompts.clinical import build_clinical_prompt
from src.core.prompts.injection_builder import (
    build_profile_injection,
    get_cached_or_build_injection,
    InjectionResult,
    PhilosophyBias,
    BiasStrength,
    EXAMPLE_CLINICAL_ADVISOR_CONFIG,
)

__all__ = [
    "build_patient_prompt",
    "build_clinical_prompt",
    "PATIENT_SYSTEM_PROMPT",
    # Injection Builder exports
    "build_profile_injection",
    "get_cached_or_build_injection",
    "InjectionResult",
    "PhilosophyBias",
    "BiasStrength",
    "EXAMPLE_CLINICAL_ADVISOR_CONFIG",
]
