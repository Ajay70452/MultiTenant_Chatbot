# scripts/retrieve_robeck_token.py

import uuid
from src.models.models import SessionLocal, Client # Assuming Client model is available

def retrieve_token():
    db = SessionLocal()
    try:
        # Find the client by their name (using LIKE is safer than an exact match)
        client = db.query(Client).filter(Client.clinic_name.ilike('%robeck%')).first()
        
        if client:
            print("==================================================")
            print("✅ ROBECK DENTAL PRODUCTION CREDENTIALS FOUND")
            print("==================================================")
            print(f"CLIENT ID (UUID):   {client.client_id}")
            print(f"ACCESS TOKEN:       {client.access_token}")
            print("==================================================")
            print("Use these values for the Ahsuite URL.")
        else:
            print("ERROR: Could not find 'Robeck' client in the database.")
            
    except Exception as e:
        print(f"An error occurred during retrieval: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    retrieve_token()