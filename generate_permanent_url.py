#!/usr/bin/env python3
"""
Generate permanent access URLs for the Clinical Advisor UI.
These URLs use the permanent access token and don't expire.
"""

import sys
from src.core.db import get_db
from src.models.models import Client

def main():
    # Get clinic name from command line or show all
    clinic_name = sys.argv[1] if len(sys.argv) > 1 else None

    db = next(get_db())
    try:
        if clinic_name:
            # Find client by clinic name
            client = db.query(Client).filter(
                Client.clinic_name.ilike(f'%{clinic_name}%')
            ).first()

            if not client:
                print(f"ERROR: No client found matching '{clinic_name}'")
                print("\nAvailable clients:")
                all_clients = db.query(Client).all()
                for c in all_clients:
                    print(f"  - {c.clinic_name}")
                sys.exit(1)

            print_client_url(client)
        else:
            # Show all clients
            clients = db.query(Client).all()

            if not clients:
                print("ERROR: No clients found in database.")
                sys.exit(1)

            print("\n" + "="*80)
            print("PERMANENT ACCESS URLS FOR ALL CLIENTS")
            print("="*80 + "\n")

            for client in clients:
                print_client_url(client)
                print()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def print_client_url(client):
    """Print the permanent access URL for a client."""
    if not client.access_token:
        print(f"WARNING: {client.clinic_name} has no access token configured")
        return

    print(f"Clinic: {client.clinic_name}")
    print(f"Client ID: {client.client_id}")
    print(f"Access Token: {client.access_token}")
    print(f"\nPermanent Access URL:")
    print(f"http://localhost:8000/frontends/clinical-ui/index.html?permanent_token={client.access_token}")
    print(f"\nNote: This URL never expires and can be bookmarked!")
    print("-" * 80)

if __name__ == "__main__":
    main()
