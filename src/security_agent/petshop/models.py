"""Pet Shop database models — SQLite with intentional vulnerabilities.

WARNING: This code contains INTENTIONAL security vulnerabilities for demo purposes.
DO NOT use these patterns in production code.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_db_path() -> str:
    """Get the database file path."""
    return str(Path(__file__).parent / "petshop.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            species TEXT NOT NULL,
            breed TEXT,
            price REAL NOT NULL,
            description TEXT,
            image_url TEXT,
            in_stock INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'customer'
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
    """)

    conn.commit()
    conn.close()


# ─── VULNERABLE query functions (intentional for demo) ───


def search_products_vulnerable(query: str) -> list[dict]:
    """VULNERABLE: SQL injection via string interpolation.

    This is intentionally insecure for the PoC demo.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # ⚠️ VULNERABLE: direct string interpolation
    sql = f"SELECT * FROM products WHERE name LIKE '%{query}%' OR description LIKE '%{query}%'"
    try:
        cursor.execute(sql)
        results = [dict(row) for row in cursor.fetchall()]
    except Exception:
        results = []
    conn.close()
    return results


def login_vulnerable(username: str, password: str) -> dict | None:
    """VULNERABLE: SQL injection in login.

    This is intentionally insecure for the PoC demo.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # ⚠️ VULNERABLE: direct string interpolation
    sql = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    try:
        cursor.execute(sql)
        row = cursor.fetchone()
        result = dict(row) if row else None
    except Exception:
        result = None
    conn.close()
    return result


# ─── Safe query functions ───


def get_all_products() -> list[dict]:
    """Get all products (safe query)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE in_stock = 1")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_product_by_id(product_id: int) -> dict | None:
    """Get a single product by ID (safe query)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    result = dict(row) if row else None
    conn.close()
    return result


def get_reviews_for_product(product_id: int) -> list[dict]:
    """Get reviews for a product (safe query)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,),
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def add_review(product_id: int, author: str, content: str, rating: int = 5) -> None:
    """Add a review — content is stored unsanitized (for stored XSS demo)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (product_id, author, content, rating) VALUES (?, ?, ?, ?)",
        (product_id, author, content, rating),
    )
    conn.commit()
    conn.close()
