import os
import argparse
import uuid
from typing import List

from dotenv import load_dotenv

from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker


DEFAULT_CLIENT_ID = "443f5716-27d3-463a-9377-33a666f5ad88"
DEFAULT_INDEX = "robeck-dental-v2"

def read_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    if ext == ".docx":
        try:
            import importlib
            docx_mod = importlib.import_module("docx")
            Document = getattr(docx_mod, "Document")
        except Exception:
            raise RuntimeError("python-docx not installed. Run: pip install python-docx")
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
    raise ValueError("Unsupported file type. Use .docx or .txt")


def parse_qa_blocks(text: str):
    """
    Parse Q&A blocks separated by blank lines. First line ending with '?' is question; remainder is answer.
    Returns a list of {"question","answer"} dicts or None if it doesn't look like Q&A.
    """
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(blocks) < 1:
        return None
    looks_like_qa = any(block.splitlines()[0].strip().endswith("?") for block in blocks)
    if not looks_like_qa:
        return None
    qa_list = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        q_idx = next((i for i, ln in enumerate(lines) if ln.endswith("?")), None)
        if q_idx is None:
            qa_list.append({"question": "", "answer": "\n".join(lines)})
            continue
        question = lines[q_idx]
        answer = "\n".join(lines[q_idx + 1:]).strip()
        qa_list.append({"question": question, "answer": answer})
    if not any(item["question"] or item["answer"] for item in qa_list):
        return None
    return qa_list


def chunk_with_semantics(text: str) -> List[str]:
    """Use SemanticChunker for higher-quality chunks."""
    # Use a small, fast embedding model consistent with the rest of the project
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    splitter = SemanticChunker(embeddings)
    docs = splitter.create_documents([text])
    return [d.page_content for d in docs]


def build_chunks_from_qa(qa_list) -> List[str]:
    chunks: List[str] = []
    for qa in qa_list:
        q = qa.get("question", "").strip()
        a = qa.get("answer", "").strip()
        if q or a:
            chunks.append(f"Q: {q}\nA: {a}".strip())
    return chunks


def embed_chunks(chunks: List[str]) -> List[List[float]]:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    # embed_documents returns a list of vectors (List[List[float]])
    return embeddings.embed_documents(chunks)


def upsert_to_pinecone(
    embeddings: List[List[float]],
    chunks: List[str],
    client_id: str,
    index_name: str,
    source: str,
    qa_list=None,
):
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])  # raises KeyError if missing
    index = pc.Index(index_name)

    doc_id = str(uuid.uuid4())
    vectors = []
    for i, (emb, chunk) in enumerate(zip(embeddings, chunks)):
        meta = {
            # IMPORTANT: rag_engine expects metadata['text']
            "text": chunk,
            "client_id": client_id,
            "source": source,
            "doc_id": doc_id,
            "type": "faq",
        }
        if qa_list and i < len(qa_list):
            meta["question"] = qa_list[i].get("question", "")
            meta["answer"] = qa_list[i].get("answer", "")
        vectors.append({
            "id": f"{doc_id}-{i}",
            "values": emb,
            "metadata": meta,
        })

    # Upsert into namespace scoped by client_id (multi-tenant)
    index.upsert(vectors=vectors, namespace=client_id)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Embed and upsert a single FAQ doc to Pinecone.")
    parser.add_argument("--file", required=True, help="Path to .docx or .txt file")
    parser.add_argument("--index", default=DEFAULT_INDEX, help=f"Pinecone index name (default: {DEFAULT_INDEX})")
    parser.add_argument(
        "--client-id",
        default=DEFAULT_CLIENT_ID,
        help=f"Client namespace (default: {DEFAULT_CLIENT_ID})",
    )
    args = parser.parse_args()

    # Validate env
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")
    if not os.getenv("PINECONE_API_KEY"):
        raise RuntimeError("PINECONE_API_KEY is not set.")

    text = read_text(args.file)
    if not text.strip():
        raise RuntimeError("Document appears to be empty.")

    print(f"📄 Loading: {os.path.basename(args.file)}")

    qa_list = parse_qa_blocks(text)
    if qa_list:
        chunks = build_chunks_from_qa(qa_list)
        print(f"🔹 Detected Q&A format. Prepared {len(chunks)} Q&A chunks")
    else:
        chunks = chunk_with_semantics(text)
        qa_list = None
        print(f"🔹 No Q&A structure detected. Created {len(chunks)} semantic chunks")

    vectors = embed_chunks(chunks)
    print(f"🧠 Generated {len(vectors)} embeddings")

    upsert_to_pinecone(vectors, chunks, args.client_id, args.index, source=os.path.basename(args.file), qa_list=qa_list)
    print(f"✅ Upsert complete to index '{args.index}' in namespace '{args.client_id}'")


if __name__ == "__main__":
    main()
