import sqlite3
import json
import re
from datetime import datetime
from urllib.parse import urlparse

DB_PATH = "prices.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT NOT NULL,
            domain      TEXT NOT NULL,
            title       TEXT,
            price       REAL NOT NULL,
            currency    TEXT DEFAULT '₹',
            image_url   TEXT,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Index for fast URL lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_url ON price_history(url)
    """)
    conn.commit()
    return conn


def normalize_url(url: str) -> str:
    """Remove tracking params, keep only product-identifying parts."""
    parsed = urlparse(url)
    # Keep only path, remove all query params (most product pages are path-based)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean.rstrip("/")


def parse_price(price_str: str) -> float | None:
    """Extract numeric price from string like '₹1,23,456' or '$12.99'"""
    if not price_str:
        return None
    # Remove currency symbols, spaces, commas
    cleaned = re.sub(r"[^\d.]", "", price_str.replace(",", ""))
    try:
        return float(cleaned)
    except:
        return None


def detect_currency(price_str: str) -> str:
    if "₹" in price_str: return "₹"
    if "$" in price_str: return "$"
    if "€" in price_str: return "€"
    if "£" in price_str: return "£"
    return "₹"


def record_price(url: str, title: str, price_str: str, image_url: str = "") -> dict:
    """Store a price record. Returns result dict."""
    price = parse_price(price_str)
    if not price:
        return {"success": False, "error": "Could not parse price"}

    currency = detect_currency(price_str)
    clean_url = normalize_url(url)
    domain = urlparse(url).netloc

    conn = get_db()

    # Avoid duplicate recording within same hour
    existing = conn.execute("""
        SELECT id FROM price_history
        WHERE url = ? AND recorded_at > datetime('now', '-1 hour')
    """, (clean_url,)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO price_history (url, domain, title, price, currency, image_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (clean_url, domain, title, price, currency, image_url))
        conn.commit()

    result = get_price_history(clean_url)
    conn.close()
    return result


def get_price_history(url: str) -> dict:
    """Get full price history and stats for a URL."""
    clean_url = normalize_url(url)
    conn = get_db()

    rows = conn.execute("""
        SELECT price, currency, title, image_url, recorded_at
        FROM price_history
        WHERE url = ?
        ORDER BY recorded_at ASC
    """, (clean_url,)).fetchall()

    conn.close()

    if not rows:
        return {"success": False, "error": "No price history found for this product."}

    prices     = [r[0] for r in rows]
    currency   = rows[-1][1]
    title      = rows[-1][2]
    image_url  = rows[-1][3]
    timestamps = [r[4] for r in rows]

    current = prices[-1]
    lowest  = min(prices)
    highest = max(prices)
    avg     = round(sum(prices) / len(prices), 2)

    # Price trend: compare last price to previous
    trend = "stable"
    if len(prices) >= 2:
        diff = prices[-1] - prices[-2]
        if diff > 0:   trend = "up"
        elif diff < 0: trend = "down"

    return {
        "success":    True,
        "title":      title,
        "image_url":  image_url,
        "currency":   currency,
        "current":    current,
        "lowest":     lowest,
        "highest":    highest,
        "average":    avg,
        "trend":      trend,
        "data_points": len(prices),
        "history": [
            {"price": p, "date": t}
            for p, t in zip(prices, timestamps)
        ]
    }