import hashlib
import json
import sqlite3
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# Reuse same embedding model as rag_service
from rag_service import embedding_model, get_db

DB_PATH = "rag_cache.db"


def ensure_youtube_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS youtube_chunks (
            hash        TEXT PRIMARY KEY,
            video_id    TEXT NOT NULL,
            text        TEXT NOT NULL,
            start_time  REAL NOT NULL,
            end_time    REAL NOT NULL,
            ts_label    TEXT NOT NULL,
            embedding   TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vid ON youtube_chunks(video_id)")
    conn.commit()
    conn.close()


def chunk_hash(video_id: str, start_time: float) -> str:
    return hashlib.sha256(f"{video_id}:{start_time}".encode()).hexdigest()


def store_youtube_chunks(video_id: str, chunks: list[dict]) -> list[dict]:
    """Store timed chunks with embeddings, using hash cache."""
    ensure_youtube_table()
    conn = get_db()
    results = []
    
    if video_id:
        row = conn.execute(
            "SELECT * FROM youtube_chunks WHERE video_id = ?", (video_id,)
        ).fetchone()
        
        if row: 
            print(f"[YT-RAG] Video found")
            return []
        
    for chunk in chunks:
        h = chunk_hash(video_id, chunk["start_time"])

        row = conn.execute(
            "SELECT embedding FROM youtube_chunks WHERE hash = ?", (h,)
        ).fetchone()

        if row:
            embedding = json.loads(row[0])
            print(f"[YT-RAG] Cache HIT  | {chunk['timestamp_label']}")
        else:
            embedding = embedding_model.encode(
                chunk["text"], normalize_embeddings=True
            ).tolist()
            conn.execute("""
                INSERT INTO youtube_chunks
                  (hash, video_id, text, start_time, end_time, ts_label, embedding)
                VALUES (?,?,?,?,?,?,?)
            """, (
                h, video_id,
                chunk["text"], chunk["start_time"], chunk["end_time"],
                chunk["timestamp_label"], json.dumps(embedding)
            ))
            conn.commit()
            print(f"[YT-RAG] Cache MISS | {chunk['timestamp_label']} stored")

        results.append({**chunk, "embedding": embedding})

    conn.close()
    return results


def query_youtube(video_id: str, query: str, top_k: int = 3) -> list[dict]:
    """
    Get top_k most relevant chunks for a query.
    Returns list of {text, start_time, end_time, ts_label, score}
    """
    ensure_youtube_table()
    conn = get_db()

    rows = conn.execute(
        "SELECT text, start_time, end_time, ts_label, embedding FROM youtube_chunks WHERE video_id = ?",
        (video_id,)
    ).fetchall()
    conn.close()

    if not rows:
        return []

    query_emb = embedding_model.encode(query, normalize_embeddings=True).reshape(1, -1)
    embeddings = np.array([json.loads(r[4]) for r in rows])
    scores     = cosine_similarity(query_emb, embeddings)[0]
    top_idx    = np.argsort(scores)[::-1][:top_k]

    results = []
    for i in top_idx:
        r = rows[i]
        results.append({
            "text":       r[0],
            "start_time": r[1],
            "end_time":   r[2],
            "ts_label":   r[3],
            "score":      round(float(scores[i]), 3),
        })

    return results