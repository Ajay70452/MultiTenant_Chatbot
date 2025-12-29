import argparse
import secrets
import sys
import uuid
from pathlib import Path

# Add project root to path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.models.models import SessionLocal, Client
from sqlalchemy.exc import IntegrityError

def generate_and_assign_token(client_id_str: str):
    """
    Generates a secure, unique access token and assigns it to a specific client.
    """
    db = SessionLocal()
    try:
        # 1. Validate Input
        client_id = uuid.UUID(client_id_str)
        
        # 2. Find the client
        client = db.query(Client).filter(Client.client_id == client_id).first()
        
        if not client:
            print(f"❌ Error: Client with ID '{client_id_str}' not found in the database.")
            return

        # 3. Generate Token: Use secrets.token_hex for a cryptographically secure, random 64-char string
        new_token = secrets.token_hex(32) 
        
        # 4. Assign and Commit
        client.access_token = new_token
        db.commit()
        
        print("\n=============================================")
        print("✅ TOKEN GENERATION SUCCESSFUL (PROD DEPLOY)")
        print(f"Client: {client.clinic_name}")
        print(f"Client ID: {client.client_id}")
        print(f"ACCESS TOKEN: {new_token}")
        print("=============================================\n")
        print("⚠️ ACTION REQUIRED: Save this token and remove the IP firewall rule in AWS.")

    except ValueError:
        print(f"❌ Error: '{client_id_str}' is not a valid UUID format.")
    except IntegrityError:
        db.rollback()
        print(f"❌ Error: A token already exists for client {client_id_str}. Rolling back.")
    except Exception as e:
        db.rollback()
        print(f"❌ An unexpected database error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and assign a secure access token to a client.")
    parser.add_argument("client_id", type=str, help="The UUID of the client to assign the token to.")
    
    args = parser.parse_args()
    
    generate_and_assign_token(args.client_id)