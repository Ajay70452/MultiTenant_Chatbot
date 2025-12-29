"""
Database Migration and Test Client Seeding Script

This script:
1. Creates all base tables if they don't exist (for fresh databases)
2. Applies pending Alembic migrations
3. Inserts a test client with access_token initially set to NULL

Usage:
    # First, copy .env.local to .env (or set environment variables)
    copy .env.local .env

    # Then run:
    python scripts/apply_migration_and_seed.py
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.core.config import DATABASE_URL
from src.models.models import Base, Client, PracticeProfile


def create_base_tables():
    """Create all base tables if they don't exist (for fresh databases)."""
    print("=" * 50)
    print("Creating base tables if needed...")
    print("=" * 50)

    engine = create_engine(DATABASE_URL)

    # Create all tables defined in models
    Base.metadata.create_all(bind=engine)

    print("[OK] Base tables created/verified!")
    print()


def stamp_alembic_head():
    """Stamp the database with the current alembic head (for fresh databases)."""
    print("=" * 50)
    print("Stamping Alembic revision...")
    print("=" * 50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(project_root, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    # Stamp the database as being at the head revision
    # This is needed for fresh databases where we created tables directly
    command.stamp(alembic_cfg, "head")

    print("[OK] Alembic stamped at head!")
    print()


def apply_migrations():
    """Apply all pending Alembic migrations."""
    print("=" * 50)
    print("Applying Alembic migrations...")
    print("=" * 50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(project_root, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    # Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    print("[OK] Migrations applied successfully!")
    print()


def seed_test_client():
    """Insert a test client with access_token set to NULL."""
    print("=" * 50)
    print("Seeding test client...")
    print("=" * 50)

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        # Check if test client already exists
        existing_client = db.query(Client).filter(
            Client.clinic_name == "Test Dental Practice"
        ).first()

        if existing_client:
            print(f"[!] Test client already exists with ID: {existing_client.client_id}")
            print(f"    Clinic Name: {existing_client.clinic_name}")
            print(f"    Access Token: {existing_client.access_token}")
            return existing_client

        # Create new test client
        test_client = Client(
            clinic_name="Test Dental Practice",
            lead_webhook_url=None,
            access_token=None  # Initially NULL as per instructions
        )

        db.add(test_client)
        db.commit()
        db.refresh(test_client)

        print(f"[OK] Test client created successfully!")
        print(f"    Client ID: {test_client.client_id}")
        print(f"    Clinic Name: {test_client.clinic_name}")
        print(f"    Access Token: {test_client.access_token} (NULL)")
        print(f"    Created At: {test_client.created_at}")

        return test_client

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error creating test client: {e}")
        raise
    finally:
        db.close()


def seed_test_practice_profile(client_id):
    """Create a test practice profile for the test client."""
    print("=" * 50)
    print("Seeding test practice profile...")
    print("=" * 50)

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        # Check if profile already exists
        existing_profile = db.query(PracticeProfile).filter(
            PracticeProfile.practice_id == client_id
        ).first()

        if existing_profile:
            print(f"[!] Practice profile already exists for client: {client_id}")
            return existing_profile

        # Create test practice profile
        test_profile = PracticeProfile(
            practice_id=client_id,
            profile_json={
                "treatment_philosophy": "Conservative, minimally invasive approach. We prefer to monitor and prevent rather than intervene early.",
                "preferred_materials": [
                    "Composite: 3M Filtek Supreme",
                    "Cement: RelyX Universal",
                    "Impression: Digital scanning preferred"
                ],
                "conservative_vs_aggressive": "Conservative - prefer watchful waiting for early lesions",
                "specialties": ["General Dentistry", "Preventive Care"],
                "referral_preferences": {
                    "oral_surgery": "Refer complex extractions",
                    "endo": "In-house for anterior, refer molar RCT",
                    "perio": "Refer Stage 3+ periodontitis"
                },
                "medication_preferences": {
                    "antibiotic_first_line": "Amoxicillin 500mg TID x 7 days",
                    "penicillin_allergy": "Azithromycin Z-pack",
                    "pain_management": "Ibuprofen 600mg + Acetaminophen 500mg alternating"
                },
                "notes": "Patient comfort is priority. Always offer nitrous for anxious patients."
            }
        )

        db.add(test_profile)
        db.commit()
        db.refresh(test_profile)

        print(f"[OK] Practice profile created successfully!")
        print(f"    Practice ID: {test_profile.practice_id}")
        print(f"    Profile Keys: {list(test_profile.profile_json.keys())}")

        return test_profile

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error creating practice profile: {e}")
        raise
    finally:
        db.close()


def update_client_token(client_id, token):
    """Update the access token for a client."""
    print("=" * 50)
    print("Setting access token for test client...")
    print("=" * 50)

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client:
            client.access_token = token
            db.commit()
            print(f"[OK] Access token set: {token}")
            return True
        else:
            print(f"[ERROR] Client not found: {client_id}")
            return False
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error updating token: {e}")
        raise
    finally:
        db.close()


def main():
    print()
    print("*" * 50)
    print("  DATABASE MIGRATION & SEEDING SCRIPT")
    print("*" * 50)
    print()

    # Mask password in output
    display_url = DATABASE_URL
    if "@" in DATABASE_URL:
        parts = DATABASE_URL.split("@")
        prefix = parts[0].rsplit(":", 1)[0]  # Remove password
        display_url = f"{prefix}:****@{parts[1]}"
    print(f"Database URL: {display_url}")
    print()

    try:
        # Step 1: Create base tables (for fresh databases)
        create_base_tables()

        # Step 2: Stamp alembic (marks DB as current with migrations)
        stamp_alembic_head()

        # Step 3: Apply any pending migrations
        apply_migrations()

        # Step 4: Seed test client
        test_client = seed_test_client()

        # Step 5: Set a test access token
        test_token = "test-token-12345"
        update_client_token(test_client.client_id, test_token)

        # Step 6: Seed practice profile
        seed_test_practice_profile(test_client.client_id)

        print()
        print("=" * 50)
        print("[OK] All operations completed successfully!")
        print("=" * 50)
        print()
        print("TEST CREDENTIALS:")
        print(f"  Client ID: {test_client.client_id}")
        print(f"  Access Token: {test_token}")
        print()
        print("To test the Clinical Advisor UI, open:")
        print(f"  http://localhost:8000/frontends/clinical-ui/?token={test_token}")
        print()

    except Exception as e:
        print()
        print("=" * 50)
        print(f"[ERROR] Script failed: {e}")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
