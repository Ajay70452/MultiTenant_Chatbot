# scripts/seed_robeck_prod.py
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import uuid
from src.models.models import SessionLocal, PracticeProfile

# !!! REPLACE THIS WITH THE REAL UUID FROM STEP 3.1 !!!
ROBECK_ID_STR = "443f5716-27d3-463a-9377-33a666f5ad88" 

def seed_robeck_brain():
    db = SessionLocal()
    try:
        robeck_uuid = uuid.UUID(ROBECK_ID_STR)
        
        # This is the "Brain" configuration
        # You can edit these values based on what you know about the client
        profile_data = {
            "philosophy": "Evidence-based, conservative dentistry. we provide advanced, comprehensive dental care for every stage of life.",
            "implants": "We offer implants for single tooth replacement. For complex full-arch cases, we refer to Dr. Smith (Oral Surgeon).",
            "referral_policy": "Refer: Complex Endodontics (molars), Impacted Wisdom Teeth, Pediatric patients under 5. Treat: Simple anterior Endo, Simple extractions.",
            "materials": "Posterior teeth: Zirconia crowns. Anterior teeth: E-max/Porcelain. Fillings: Composite only (no Amalgam).",
            "tone": "Professional, educational, and supportive. Speak like a knowledgeable colleague, not a robot."
        }

        # Check if profile exists
        profile = db.query(PracticeProfile).filter(PracticeProfile.practice_id == robeck_uuid).first()
        
        if profile:
            print(f"Updating existing profile for {ROBECK_ID_STR}...")
            profile.profile_json = profile_data
        else:
            print(f"Creating NEW profile for {ROBECK_ID_STR}...")
            new_profile = PracticeProfile(
                practice_id=robeck_uuid,
                profile_json=profile_data
            )
            db.add(new_profile)
        
        db.commit()
        print("✅ Robeck Dental 'Practice Brain' successfully injected.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_robeck_brain()