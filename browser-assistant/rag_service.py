import hashlib
import json
import sqlite3
import numpy as np
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

DB_PATH = "rag_cache.db"

# Load embedding model once at startup (runs locally, no API key needed)
print("[RAG] Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("[RAG] Embedding model ready.")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ".", " ", ""]
)


# ── Database Setup ──────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            hash        TEXT PRIMARY KEY,
            content     TEXT NOT NULL,
            embedding   TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# ── Core Functions ──────────────────────────────────────────────────────────

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


def embed_text(text: str) -> list[float]:
    return embedding_model.encode(text, normalize_embeddings=True).tolist()


def split_text(content: str) -> list[str]:
    return text_splitter.split_text(content)


def store_chunks(chunks: list[str], conn: sqlite3.Connection) -> list[dict]:
    """
    For each chunk:
      - Compute hash
      - If hash exists in DB → fetch embedding
      - If not → compute embedding, store in DB
    Returns list of {hash, content, embedding}
    """
    results = []

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        chunk_hash = compute_hash(chunk)

        # Check if already cached
        row = conn.execute(
            "SELECT content, embedding FROM chunks WHERE hash = ?",
            (chunk_hash,)
        ).fetchone()

        if row:
            # Cache HIT - reuse stored embedding
            embedding = json.loads(row[1])
            print(f"[RAG] Cache HIT  | hash={chunk_hash[:8]}...")
        else:
            # Cache MISS - compute and store
            embedding = embed_text(chunk)
            conn.execute(
                "INSERT INTO chunks (hash, content, embedding) VALUES (?, ?, ?)",
                (chunk_hash, chunk, json.dumps(embedding))
            )
            conn.commit()
            print(f"[RAG] Cache MISS | hash={chunk_hash[:8]}... | stored")

        results.append({
            "hash": chunk_hash,
            "content": chunk,
            "embedding": embedding
        })

    return results


def get_top_chunks(query: str, chunks: list[dict], top_k: int = 3) -> list[str]:
    """
    Embed the query, compute cosine similarity with all chunk embeddings,
    return top_k most relevant chunk contents.
    """
    if not chunks:
        return []

    query_embedding = np.array(embed_text(query)).reshape(1, -1)
    chunk_embeddings = np.array([c["embedding"] for c in chunks])

    scores = cosine_similarity(query_embedding, chunk_embeddings)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]

    print(f"[RAG] Top scores: {[round(scores[i], 3) for i in top_indices]}")

    return [chunks[i]["content"] for i in top_indices]


# ── Main Entry Point ────────────────────────────────────────────────────────

def process_page_and_query(page_content: str, query: str, top_k: int = 3) -> str:
    """
    Full RAG pipeline:
    1. Split page into chunks
    2. Hash check → embed + store or retrieve
    3. Find top_k chunks relevant to query
    4. Return joined context string
    """
    conn = get_db()

    chunks = split_text(page_content)
    print(f"[RAG] Page split into {len(chunks)} chunks")

    stored = store_chunks(chunks, conn)
    conn.close()

    top_contents = get_top_chunks(query, stored, top_k=top_k)

    context = "\n\n---\n\n".join(top_contents)
    return context