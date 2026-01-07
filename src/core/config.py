import os
from pathlib import Path
from dotenv import load_dotenv

# Get the project root directory (2 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Load environment variables from .env file
load_dotenv(dotenv_path=ENV_PATH)

# Database configuration - construct URL from components if DATABASE_URL contains unresolved variables
_raw_database_url = os.getenv("DATABASE_URL", "")
if "${" in _raw_database_url or not _raw_database_url:
    # Construct DATABASE_URL from individual components
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "M3thodPr0")
    DB_HOST = os.getenv("DB_HOST", "dental-chatbot-prod-db-instance-1.cp2qgaicgsce.us-west-2.rds.amazonaws.com")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "chatbot_db")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = _raw_database_url

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "robeck-dental-v2")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", 
                            "http://localhost:3000," \
                            "https://api.methodpro.com," \
                            "https://dental-chatbot-coral.vercel.app," \
                            "https://dental-chatbot-widget-prod.s3.us-west-2.amazonaws.com," \
                            "http://dental-chatbot-widget-prod.s3-website-us-west-2.amazonaws.com," \
                            "https://dm4ym7twaensu.cloudfront.net," \
                            "http://dm4ym7twaensu.cloudfront.net")