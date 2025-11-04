import pinecone
from langchain_openai import OpenAIEmbeddings
from src.core.config import PINECONE_API_KEY, OPENAI_API_KEY, PINECONE_INDEX_NAME

pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)

embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

import logging

def get_relevant_context(query: str, client_id: str):
    index = pc.Index(PINECONE_INDEX_NAME)

    query_vector = embeddings.embed_query(query)
    
    results = index.query(
        vector=query_vector,
        top_k=3,
        namespace=client_id,
        include_metadata=True
    )
    
    context = ""
    if hasattr(results, 'matches'):
        matches = results.matches
    else:
        matches = results.get('matches', {})
    
    for match in matches:
        if hasattr(match, 'metadata'):
            metadata = match.metadata
        else:
            metadata = match.get('metadata', {})
        
        text = metadata.get('text', '')
        if text:
            context += text + "\n\n"
        
    return context