"""
Clinical Advisor Prompt (Door 2)

This prompt defines the personality and behavior for the doctor-facing
Clinical Advisor assistant. It prioritizes patient safety and references
the doctor's practice philosophy.

The prompt is assembled from three parts (per guidance docs):
1. Global Clinical Advisor System Prompt (rules) - versioned template
2. Global Policy Blocks - citations, standards authority, red flags, bias governance
3. Practice Profile Injection - generated from clinical_advisor_config
"""

from typing import Optional
from src.core.prompts.injection_builder import build_profile_injection, get_cached_or_build_injection


CLINICAL_SYSTEM_PROMPT = """
You are an AI assistant for dental practitioners. You help doctors with BOTH clinical questions AND practice-related questions.

## YOUR ROLE

You are a comprehensive assistant that helps with:

**Clinical Support:**
- Evidence-based clinical guidance and considerations
- Differential diagnoses and treatment planning
- Case analysis and clinical decision support
- Research and best practices references

**Practice Operations Support:**
- Insurance and payment policies
- Services offered by the practice
- FAQs and patient inquiries
- Practice policies and procedures
- Website content and general practice information

When a doctor asks "A patient called and asked about X", provide the answer they can give to the patient based on the knowledge base context below.

## PRACTICE PHILOSOPHY

The following represents this doctor's clinical philosophy and preferences. Reference these when providing guidance:

{practice_profile}

## KNOWLEDGE BASE CONTEXT

The following information has been retrieved from the practice's knowledge base. USE THIS INFORMATION to answer questions about insurance, services, FAQs, policies, and any practice-related topics:

{rag_context}

## SAFETY PRINCIPLES (ALWAYS PRIORITIZE)

1. **Patient Safety First**: Always prioritize patient safety in any recommendation
2. **Scope of Practice**: Remind the doctor of referral needs when cases exceed general dentistry scope
3. **Medical History Considerations**: Flag potential contraindications or drug interactions
4. **Emergency Recognition**: Clearly identify any signs suggesting immediate intervention
5. **Defensive Documentation**: Suggest documentation practices when relevant

## CLINICAL COMMUNICATION STYLE

- Be concise and professional - doctors are busy
- Use proper dental/medical terminology
- Structure complex responses with clear headings
- Provide confidence levels when appropriate (e.g., "highly likely", "consider ruling out")
- Cite guidelines or research when available (e.g., "Per ADA guidelines...")
- Ask clarifying questions if critical information is missing

## IMAGE ANALYSIS (When X-rays/Photos Provided)

**IMPORTANT: You have vision capabilities and CAN analyze clinical images.** When an image is provided, you MUST actually analyze it - do NOT say you cannot see or analyze images.

When analyzing clinical images:
1. **Describe what you observe**: Identify anatomical structures, any visible pathology, radiolucencies, radiopacities, bone levels, restorations, etc.
2. **Provide clinical interpretation**: What do the findings suggest? What conditions should be considered?
3. **Note areas of concern**: Highlight any abnormalities, potential issues, or areas requiring attention
4. **Suggest next steps**: Additional views, tests, or treatments to consider based on findings
5. **Provide differential considerations**: List possible diagnoses based on the visual findings

**End with disclaimer**: "This AI analysis is for reference only. Clinical correlation and professional judgment are required."

Remember: You are an AI assistant WITH vision capabilities helping a licensed dentist. Provide actual clinical observations and guidance based on what you see in the image.

## RESPONSE STRUCTURE

For clinical questions, structure your response as:

**Assessment**: Brief summary of the clinical situation
**Considerations**: Key factors to evaluate
**Options**: Treatment or diagnostic options to consider
**Recommendations**: Your suggested approach (aligned with practice philosophy)
**Caveats**: Any warnings, contraindications, or when to refer

For simple questions, respond conversationally without rigid structure.

## LIMITATIONS

Be transparent about your limitations:
- You cannot examine patients directly
- You cannot make definitive diagnoses - always recommend clinical correlation
- You cannot replace clinical judgment
- You may not have the latest research (knowledge cutoff applies)
- Image quality may affect analysis accuracy - note if image quality is suboptimal

**Note**: You DO have vision capabilities. When images are provided, analyze them and provide your clinical observations.

## CONVERSATION CONTEXT

This is a stateless conversation. The doctor may provide conversation history for context.
{history_context}

Now, how can I assist you with your clinical question?
"""


def _format_practice_profile(profile_json: Optional[dict], clinic_name: Optional[str] = None) -> str:
    """
    Convert the practice profile JSON into a readable text block.

    This function now checks for clinical_advisor_config and uses the
    injection builder for token-budgeted output. Falls back to legacy
    formatting for profiles without clinical_advisor_config.

    Args:
        profile_json: The practice profile dictionary from the database
        clinic_name: The name of the clinic/practice

    Returns:
        A formatted string describing the doctor's philosophy (300-800 tokens)
    """
    if not profile_json:
        return "No specific practice philosophy configured. Using AGD-informed general guidance with conservative defaults."

    # Check if clinical_advisor_config exists (new format)
    if "clinical_advisor_config" in profile_json:
        # Use the new injection builder with caching support
        injection_summary, was_rebuilt = get_cached_or_build_injection(
            profile_json=profile_json,
            clinic_name=clinic_name
        )
        return injection_summary

    # Legacy format: fall back to old formatting logic
    return _format_legacy_profile(profile_json, clinic_name)


def _format_legacy_profile(profile_json: dict, clinic_name: Optional[str] = None) -> str:
    """
    Legacy profile formatting for profiles without clinical_advisor_config.

    This preserves backward compatibility with existing profile structures.

    Args:
        profile_json: The practice profile dictionary (legacy format)
        clinic_name: The name of the clinic/practice

    Returns:
        A formatted string describing the doctor's philosophy
    """
    sections = []

    # Add clinic name at the beginning if provided
    if clinic_name:
        sections.append(f"**Practice Name**: {clinic_name}")

    # Map of profile keys to human-readable section names
    section_mapping = {
        "treatment_philosophy": "Treatment Philosophy",
        "preferred_materials": "Preferred Materials & Brands",
        "conservative_vs_aggressive": "Treatment Approach",
        "specialties": "Areas of Focus/Specialization",
        "referral_preferences": "Referral Preferences",
        "patient_communication_style": "Patient Communication Style",
        "insurance_considerations": "Insurance & Financial Considerations",
        "technology_preferences": "Technology & Equipment Preferences",
        "continuing_education": "Recent CE & Special Training",
        "clinical_protocols": "Clinical Protocols",
        "emergency_protocols": "Emergency Protocols",
        "medication_preferences": "Medication Preferences",
        "anesthesia_protocols": "Anesthesia Protocols",
        "notes": "Additional Notes",
    }

    # Skip internal fields when formatting
    skip_keys = {
        "clinical_advisor_config",
        "clinical_advisor_profile_version",
        "clinical_advisor_profile_summary"
    }

    for key, value in profile_json.items():
        if key in skip_keys:
            continue

        section_name = section_mapping.get(key, key.replace("_", " ").title())

        if isinstance(value, list):
            # Format list items
            items = "\n".join(f"  - {item}" for item in value)
            sections.append(f"**{section_name}**:\n{items}")
        elif isinstance(value, dict):
            # Format nested dict
            items = "\n".join(f"  - {k}: {v}" for k, v in value.items())
            sections.append(f"**{section_name}**:\n{items}")
        else:
            sections.append(f"**{section_name}**: {value}")

    return "\n\n".join(sections) if sections else "No specific practice philosophy configured."


def _format_history_context(conversation_history: Optional[list]) -> str:
    """
    Format the conversation history for context injection.

    Args:
        conversation_history: List of previous messages

    Returns:
        Formatted history string
    """
    if not conversation_history:
        return "This is the start of a new conversation."

    history_text = "Previous messages in this conversation:\n"
    for msg in conversation_history[-10:]:  # Limit to last 10 messages
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        history_text += f"\n{role}: {content}"

    return history_text


def _format_rag_context(rag_context: Optional[str]) -> str:
    """
    Format the RAG context for injection into the prompt.

    Args:
        rag_context: The retrieved context from Pinecone

    Returns:
        Formatted RAG context string
    """
    if not rag_context or not rag_context.strip():
        return "No specific context retrieved from the knowledge base for this query."

    return rag_context.strip()


def build_clinical_prompt(
    practice_profile: Optional[dict] = None,
    conversation_history: Optional[list] = None,
    rag_context: Optional[str] = None,
    clinic_name: Optional[str] = None
) -> str:
    """
    Build the clinical advisor system prompt with injected practice philosophy and RAG context.

    Args:
        practice_profile: The doctor's practice profile JSON from the database
        conversation_history: List of previous messages for context
        rag_context: Retrieved context from Pinecone RAG
        clinic_name: The name of the clinic/practice

    Returns:
        The formatted system prompt string
    """
    formatted_profile = _format_practice_profile(practice_profile, clinic_name)
    formatted_history = _format_history_context(conversation_history)
    formatted_rag = _format_rag_context(rag_context)

    return CLINICAL_SYSTEM_PROMPT.format(
        practice_profile=formatted_profile,
        history_context=formatted_history,
        rag_context=formatted_rag
    )


# Example practice profile structure for reference
EXAMPLE_PRACTICE_PROFILE = {
    "treatment_philosophy": "Conservative, minimally invasive approach. Prefer to monitor and prevent rather than intervene early.",
    "preferred_materials": [
        "Composite: 3M Filtek Supreme",
        "Cement: RelyX Universal",
        "Impression: Digital scanning (iTero) preferred"
    ],
    "conservative_vs_aggressive": "Conservative - prefer watchful waiting for early lesions",
    "specialties": ["Cosmetic dentistry", "Implant restoration", "TMJ/TMD"],
    "referral_preferences": {
        "oral_surgery": "Dr. Smith at Oral Surgery Associates",
        "endo": "In-house for anterior, refer molar RCT",
        "perio": "Refer Stage 3+ periodontitis",
        "ortho": "ABC Orthodontics"
    },
    "medication_preferences": {
        "antibiotic_first_line": "Amoxicillin 500mg TID x 7 days",
        "penicillin_allergy": "Clindamycin 300mg QID x 7 days",
        "pain_management": "Ibuprofen 600mg + Acetaminophen 500mg alternating"
    },
    "clinical_protocols": {
        "prophy_frequency": "6 months standard, 3-4 months for perio maintenance",
        "radiograph_frequency": "BWX annually, Pano every 3-5 years"
    },
    "notes": "Patient comfort is priority. Always offer nitrous for anxious patients."
}
