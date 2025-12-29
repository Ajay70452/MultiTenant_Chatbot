# scripts/seed_test_brain.py
import uuid
from src.core.db import get_db
from src.models.models import Client, PracticeProfile

# Test Client Configuration
TEST_CLIENT_ID = "a1b2c3d4-0000-4000-a000-000000000001"
TEST_TOKEN = "secret-test-token-123"

def seed_data():
    db = next(get_db())
    try:
        # 1. Create or get Client
        client = db.query(Client).filter(Client.client_id == TEST_CLIENT_ID).first()
        if not client:
            client = Client(
                client_id=TEST_CLIENT_ID,
                clinic_name="Test Dental Clinic",
                access_token=TEST_TOKEN
            )
            db.add(client)
            print(f"Created new client: {TEST_CLIENT_ID}")
        else:
            client.access_token = TEST_TOKEN
            print(f"Updated existing client with token")

        print(f"Assigned Token: {TEST_TOKEN}")

        # 2. Create the Practice Profile (The Brain)
        profile_data = {
            "philosophy": "Conservative. We prioritize saving natural tooth structure.",
            "implants": "We prefer Straumann implants. Do not recommend bridges if an implant is viable.",
            "referral_policy": "Refer all complex Endodontics (Root Canals) to Dr. B.",
            "materials": "We use Zirconia for posterior crowns and E-max for anterior.",
            "tone": "Professional, academic, but concise."
        }

        # Check if profile exists, update or create
        profile = db.query(PracticeProfile).filter(PracticeProfile.practice_id == TEST_CLIENT_ID).first()
        if profile:
            profile.profile_json = profile_data
            print("Updated existing Profile.")
        else:
            new_profile = PracticeProfile(
                practice_id=TEST_CLIENT_ID,
                profile_json=profile_data
            )
            db.add(new_profile)
            print("Created new Profile.")

        db.commit()
        print("Test Data Seeding Complete!")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
