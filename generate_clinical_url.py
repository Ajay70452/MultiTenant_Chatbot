#!/usr/bin/env python3
"""
Generate a one-time access URL for the Clinical Advisor UI.
This script creates a secure one-time token and outputs a URL you can use to access the clinical interface.
"""

import sys
from uuid import UUID
from src.core.db import get_db
from src.models.models import Client
from src.api.dependencies import generate_one_time_url_token

def main():
    # Get clinic name from command line or default to first client
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
        else:
            # Get all clients and let user choose
            clients = db.query(Client).all()

            if not clients:
                print("ERROR: No clients found in database.")
                print("Please create a client first.")
                sys.exit(1)

            print("\nAvailable clients:")
            for i, c in enumerate(clients, 1):
                print(f"  {i}. {c.clinic_name} (ID: {c.client_id})")

            choice = input("\nSelect client number (or press Enter for first): ").strip()

            if choice:
                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(clients):
                        print("Invalid selection")
                        sys.exit(1)
                    client = clients[idx]
                except ValueError:
                    print("Invalid selection")
                    sys.exit(1)
            else:
                client = clients[0]

        # Generate one-time token
        one_time_token = generate_one_time_url_token(client.client_id)

        # Print the URL
        print(f"\n{'='*80}")
        print(f"SUCCESS: Clinical Advisor Access URL Generated")
        print(f"{'='*80}")
        print(f"Clinic: {client.clinic_name}")
        print(f"Client ID: {client.client_id}")
        print(f"\nAccess URL (valid for 5 minutes):")
        print(f"\nhttp://localhost:8000/frontends/clinical-ui/index.html?token={one_time_token}")
        print(f"\n{'='*80}")
        print(f"Note: This token can only be used ONCE and expires in 5 minutes.")
        print(f"{'='*80}\n")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
