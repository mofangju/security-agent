"""Seed the Pet Shop database with sample data."""

from __future__ import annotations

from security_agent.petshop.models import get_connection, init_db


PRODUCTS = [
    {
        "name": "Golden Retriever Puppy",
        "species": "Dog",
        "breed": "Golden Retriever",
        "price": 1200.00,
        "description": "Friendly and intelligent golden retriever puppy, 8 weeks old. "
        "Great with families and children.",
        "image_url": "/static/img/golden.jpg",
    },
    {
        "name": "Persian Kitten",
        "species": "Cat",
        "breed": "Persian",
        "price": 800.00,
        "description": "Beautiful long-haired Persian kitten with blue eyes. "
        "Calm temperament, perfect indoor companion.",
        "image_url": "/static/img/persian.jpg",
    },
    {
        "name": "German Shepherd Puppy",
        "species": "Dog",
        "breed": "German Shepherd",
        "price": 1500.00,
        "description": "Loyal and protective German Shepherd puppy. "
        "Excellent guard dog potential with proper training.",
        "image_url": "/static/img/shepherd.jpg",
    },
    {
        "name": "Siamese Kitten",
        "species": "Cat",
        "breed": "Siamese",
        "price": 600.00,
        "description": "Vocal and affectionate Siamese kitten. "
        "Known for striking blue eyes and social personality.",
        "image_url": "/static/img/siamese.jpg",
    },
    {
        "name": "Holland Lop Rabbit",
        "species": "Rabbit",
        "breed": "Holland Lop",
        "price": 150.00,
        "description": "Adorable floppy-eared Holland Lop rabbit. "
        "Gentle and easy to care for.",
        "image_url": "/static/img/rabbit.jpg",
    },
    {
        "name": "Cockatiel",
        "species": "Bird",
        "breed": "Cockatiel",
        "price": 250.00,
        "description": "Friendly hand-tamed cockatiel that loves to whistle. "
        "Easy to train and great first bird.",
        "image_url": "/static/img/cockatiel.jpg",
    },
    {
        "name": "Labrador Retriever Puppy",
        "species": "Dog",
        "breed": "Labrador Retriever",
        "price": 1100.00,
        "description": "Energetic and playful Lab puppy. "
        "America's most popular breed. Great family dog.",
        "image_url": "/static/img/labrador.jpg",
    },
    {
        "name": "Maine Coon Kitten",
        "species": "Cat",
        "breed": "Maine Coon",
        "price": 950.00,
        "description": "Majestic Maine Coon kitten — the gentle giant. "
        "Extremely friendly and dog-like personality.",
        "image_url": "/static/img/mainecoon.jpg",
    },
]

USERS = [
    {"username": "admin", "password": "admin123", "email": "admin@petshop.com", "role": "admin"},
    {"username": "alice", "password": "password1", "email": "alice@example.com", "role": "customer"},
    {"username": "bob", "password": "password2", "email": "bob@example.com", "role": "customer"},
]

REVIEWS = [
    {"product_id": 1, "author": "Alice", "content": "Absolutely adorable puppy! Very healthy and playful.", "rating": 5},
    {"product_id": 1, "author": "Charlie", "content": "Great breeder, puppy came with all vaccinations.", "rating": 4},
    {"product_id": 2, "author": "Bob", "content": "Beautiful kitten. Very calm and cuddly.", "rating": 5},
    {"product_id": 3, "author": "Diana", "content": "Smart and eager to learn. Already responding to commands.", "rating": 5},
    {"product_id": 5, "author": "Eve", "content": "Cutest little bunny! My kids love her.", "rating": 5},
]


def seed_database() -> None:
    """Populate the database with sample data."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] > 0:
        print("Database already seeded, skipping.")
        conn.close()
        return

    # Insert products
    for product in PRODUCTS:
        cursor.execute(
            "INSERT INTO products (name, species, breed, price, description, image_url) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                product["name"],
                product["species"],
                product["breed"],
                product["price"],
                product["description"],
                product["image_url"],
            ),
        )

    # Insert users
    for user in USERS:
        cursor.execute(
            "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
            (user["username"], user["password"], user["email"], user["role"]),
        )

    # Insert reviews
    for review in REVIEWS:
        cursor.execute(
            "INSERT INTO reviews (product_id, author, content, rating) VALUES (?, ?, ?, ?)",
            (review["product_id"], review["author"], review["content"], review["rating"]),
        )

    conn.commit()
    conn.close()
    print(f"Seeded database: {len(PRODUCTS)} products, {len(USERS)} users, {len(REVIEWS)} reviews")


if __name__ == "__main__":
    seed_database()
