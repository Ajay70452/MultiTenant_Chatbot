import os
import json
from dotenv import load_dotenv

# LangChain and Pinecone imports
from langchain_openai import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
# Renamed to avoid confusion with the base pinecone library
from langchain_pinecone import Pinecone as LangchainPinecone
import pinecone

# --- CONFIGURATION ---

# Load environment variables (.env file)
load_dotenv()

# --- Pinecone Configuration ---
try:
    # NOTE: The LangChain integration primarily uses the API key.
    # The environment is often not needed for the new client but is good to have.
    PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
    PINECONE_ENVIRONMENT = os.environ["PINECONE_ENVIRONMENT"]
    INDEX_NAME = "robeck-dental-v2"
except KeyError as e:
    print(f"❌ ERROR: Missing environment variable: {e}. Please set it in your .env file.")
    exit()

# --- OpenAI Configuration ---
try:
    os.environ["OPENAI_API_KEY"]
except KeyError:
    print("❌ ERROR: OPENAI_API_KEY not found. Please set it in your .env file.")
    exit()

# --- File Paths ---
INPUT_FILE = "cleaned_data.json"

# --- SCRIPT LOGIC ---

def load_cleaned_data(filepath: str) -> list:
    """Loads the JSON data from the cleaning process."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: Input file not found at {filepath}")
        return []
    except json.JSONDecodeError:
        print(f"❌ ERROR: Could not decode JSON from {filepath}. The file might be empty or corrupt.")
        return []

def prepare_and_embed_data(data: list):
    """
    Processes each document, chunks it semantically, and uploads to Pinecone.
    """
    if not data:
        print("No data to process.")
        return

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # <<< THE FIX IS HERE >>>
    # This line has been removed. The newer versions of the Pinecone client
    # are handled automatically by the LangChain integration below.
    # pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    
    client_id = data[0].get("client_id")
    if not client_id:
        print("❌ ERROR: 'client_id' not found in the data. Cannot proceed.")
        return
        
    print(f"✅ Initialized connections. Processing for client_id: {client_id}")
    print(f"🎯 Target Pinecone index: '{INDEX_NAME}', Namespace: '{client_id}'")

    text_splitter = SemanticChunker(embeddings)
    all_chunks_with_metadata = []

    for i, item in enumerate(data):
        print(f"🔄 Chunking content for URL {i+1}/{len(data)}: {item['url']}")
        
        cleaned_content = item.get("cleaned_content", "")
        if not cleaned_content:
            print("   - ⚠️ Skipping URL due to empty cleaned_content.")
            continue
            
        chunks = text_splitter.create_documents([cleaned_content])
        
        for chunk in chunks:
            chunk.metadata = {
                "client_id": client_id,
                "source": item.get("url", "Unknown"),
                "title": item.get("title", "Untitled")
            }
        
        all_chunks_with_metadata.extend(chunks)
        print(f"   - ✅ Created {len(chunks)} semantic chunks.")

    if not all_chunks_with_metadata:
        print("No chunks were created. Halting before upload.")
        return

    print(f"\nTotal of {len(all_chunks_with_metadata)} chunks created. Starting upload to Pinecone...")
    
    try:
        # Using the renamed import for clarity
        LangchainPinecone.from_documents(
            documents=all_chunks_with_metadata,
            embedding=embeddings,
            index_name=INDEX_NAME,
            namespace=client_id
        )
        print(f"🎉 Success! All chunks have been embedded and uploaded to the '{client_id}' namespace in Pinecone.")
    except Exception as e:
        print(f"❌ An error occurred during the Pinecone upload: {e}")


if __name__ == "__main__":
    cleaned_data = load_cleaned_data(INPUT_FILE)
    if cleaned_data:
        prepare_and_embed_data(cleaned_data)