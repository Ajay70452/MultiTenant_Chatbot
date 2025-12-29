"""
Script to fetch access token for a client from the database
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.models import Client
from src.core.config import DATABASE_URL

# Create engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Query for Robeck Dental client
    client = session.query(Client).filter(
        Client.clinic_name.ilike('%robeck%')
    ).first()
    
    if client:
        print(f"\n{'='*60}")
        print(f"Client Found!")
        print(f"{'='*60}")
        print(f"Clinic Name: {client.clinic_name}")
        print(f"Client ID: {client.client_id}")
        print(f"Access Token: {client.access_token}")
        print(f"Created At: {client.created_at}")
        print(f"Lead Webhook URL: {client.lead_webhook_url}")
        print(f"{'='*60}\n")
    else:
        print("\n❌ No client found with 'robeck' in the name.")
        print("\nLet me list all clients in the database:\n")
        all_clients = session.query(Client).all()
        if all_clients:
            for c in all_clients:
                print(f"  - {c.clinic_name} (ID: {c.client_id})")
                print(f"    Access Token: {c.access_token}")
        else:
            print("  No clients found in database.")
            
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    session.close()
