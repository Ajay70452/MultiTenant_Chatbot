import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration - construct URL from components if DATABASE_URL contains unresolved variables
_raw_database_url = os.getenv("DATABASE_URL", "")
if "${" in _raw_database_url or not _raw_database_url:
    # Construct DATABASE_URL from individual components
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "dental_chatbot")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = _raw_database_url

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "robeck-dental-v2")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,https://dental-chatbot-coral.vercel.app")