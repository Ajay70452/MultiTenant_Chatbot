"""
Prompt Factory Module

This module contains prompt builders for different agent personalities:
- Patient Concierge (appointment booking)
- Clinical Advisor (doctor-facing assistant)
"""

from src.core.prompts.patient import build_patient_prompt, PATIENT_SYSTEM_PROMPT
from src.core.prompts.clinical import build_clinical_prompt

__all__ = [
    "build_patient_prompt",
    "build_clinical_prompt",
    "PATIENT_SYSTEM_PROMPT",
]
