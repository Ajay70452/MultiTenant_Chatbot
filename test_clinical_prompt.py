#!/usr/bin/env python3
"""Test what the clinical AI sees"""

from src.core.prompts.clinical import build_clinical_prompt
from src.core import rag_engine
from src.core.db import get_db
from src.core.state_manager import get_practice_profile
from uuid import UUID

# Robeck's client ID
robeck_id = UUID('443f5716-27d3-463a-9377-33a666f5ad88')

# Get practice profile
db = next(get_db())
practice_profile = get_practice_profile(db, robeck_id)
db.close()

# Test question
test_question = "What type of implants do we use?"

# Get RAG context
rag_context = rag_engine.get_relevant_context(test_question, str(robeck_id))

# Build the full prompt
full_prompt = build_clinical_prompt(
    practice_profile=practice_profile,
    conversation_history=None,
    rag_context=rag_context
)

print("="*80)
print("ROBECK DENTAL - CLINICAL AI PROMPT TEST")
print("="*80)
print(f"\nTest Question: {test_question}")
print(f"\nPractice Profile: {practice_profile}")
print(f"\nRAG Context Length: {len(rag_context)} characters")
print(f"\nRAG Context Preview:\n{rag_context[:500]}...")
print("\n" + "="*80)
print("FULL PROMPT SENT TO AI:")
print("="*80)
print(full_prompt)
