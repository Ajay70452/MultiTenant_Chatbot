#!/usr/bin/env python3
"""Quick script to check client tokens in the database."""

from src.core.db import get_db
from src.models.models import Client

def main():
    db = next(get_db())
    try:
        clients = db.query(Client).all()

        print(f"\nFound {len(clients)} clients:")
        print("-" * 80)

        for client in clients:
            print(f"Client ID: {client.client_id}")
            print(f"Clinic Name: {client.clinic_name}")
            print(f"Access Token: {client.access_token}")
            print("-" * 80)

    finally:
        db.close()

if __name__ == "__main__":
    main()
