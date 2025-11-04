import sys
import os
sys.path.insert(0, os.path.abspath('.')) 
from dotenv import load_dotenv
from src.models.models import Base, engine
from src.core.config import DATABASE_URL

load_dotenv()

def create_database_tables():
    """
    Connects to the PostgreSQL database using the SQLAlchemy engine
    and creates all tables defined in the Base metadata.
    """
    if not DATABASE_URL:
        print("❌ DATABASE_URL environment variable not set. Please create a .env file and set the DATABASE_URL.")
        return

    print(f"Connecting to database at: {engine.url.render_as_string(hide_password=True)}")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables (conversations, chat_logs) created successfully!")
        print("Tables should now be ready for the FastAPI application.")
    except Exception as e:
        print("❌ FAILED to create database tables.")
        print(f"Reason: {e}")
        print("HINT: Check your DATABASE_URL, ensure PostgreSQL is running, and verify the 'client_id' FK setup.")

if __name__ == "__main__":
    create_database_tables()