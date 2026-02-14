"""Pet Shop Flask application — intentionally vulnerable web app.

WARNING: This application contains INTENTIONAL security vulnerabilities
for demonstration purposes. DO NOT deploy in production.

Vulnerabilities:
- SQL Injection in /search and /login
- Reflected XSS in /search
- Stored XSS in /review
- Path Traversal in /static/<path>
- Command Injection in /admin/ping
"""

from __future__ import annotations

import os
import subprocess

from flask import Flask, jsonify, render_template, request

from security_agent.petshop.models import (
    add_review,
    get_all_products,
    get_product_by_id,
    get_reviews_for_product,
    login_vulnerable,
    search_products_vulnerable,
)
from security_agent.petshop.seed_data import seed_database


def create_app() -> Flask:
    """Create and configure the Pet Shop Flask app."""
    app = Flask(__name__)
    app.secret_key = "petshop-insecure-secret-key"

    # Initialize database on first request
    with app.app_context():
        seed_database()

    # ─── Public Routes ───

    @app.route("/")
    def index():
        """Homepage — list all products."""
        products = get_all_products()
        return render_template("index.html", products=products)

    @app.route("/product/<int:product_id>")
    def product_detail(product_id: int):
        """Product detail page with reviews."""
        product = get_product_by_id(product_id)
        if not product:
            return "Product not found", 404
        reviews = get_reviews_for_product(product_id)
        return render_template("product.html", product=product, reviews=reviews)

    @app.route("/search")
    def search():
        """VULNERABLE: SQL injection + reflected XSS in search."""
        query = request.args.get("q", "")
        # ⚠️ VULNERABLE: query passed directly to SQL and rendered unescaped
        results = search_products_vulnerable(query)
        return render_template("search.html", query=query, results=results)

    @app.route("/review", methods=["POST"])
    def submit_review():
        """VULNERABLE: Stored XSS — review content stored and displayed raw."""
        product_id = request.form.get("product_id", type=int)
        author = request.form.get("author", "Anonymous")
        content = request.form.get("content", "")
        rating = request.form.get("rating", 5, type=int)

        if product_id:
            # ⚠️ VULNERABLE: content stored without sanitization
            add_review(product_id, author, content, rating)

        return jsonify({"status": "ok", "message": "Review submitted"})

    @app.route("/login", methods=["POST"])
    def login():
        """VULNERABLE: SQL injection in login."""
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # ⚠️ VULNERABLE: direct string interpolation in SQL
        user = login_vulnerable(username, password)
        if user:
            return jsonify({"status": "ok", "user": user["username"], "role": user["role"]})
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

    # ─── Admin Routes ───

    @app.route("/admin/ping", methods=["POST"])
    def admin_ping():
        """VULNERABLE: Command injection via os.system/subprocess."""
        host = request.form.get("host", "")
        if not host:
            return jsonify({"error": "host parameter required"}), 400
        try:
            # ⚠️ VULNERABLE: unsanitized input in shell command
            result = subprocess.run(
                f"ping -c 1 {host}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return jsonify({
                "status": "ok",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return jsonify({"error": "Command timed out"}), 408

    @app.route("/static/<path:filename>")
    def serve_static(filename: str):
        """VULNERABLE: Path traversal via unsanitized file path."""
        # ⚠️ VULNERABLE: no path sanitization — allows ../../etc/passwd
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        filepath = os.path.join(static_dir, filename)
        try:
            with open(filepath) as f:
                return f.read(), 200, {"Content-Type": "text/plain"}
        except FileNotFoundError:
            return "File not found", 404
        except Exception as e:
            return str(e), 500

    # ─── API Routes (for traffic generators) ───

    @app.route("/api/products")
    def api_products():
        """JSON API for products."""
        return jsonify(get_all_products())

    @app.route("/api/health")
    def health():
        """Health check endpoint."""
        return jsonify({"status": "healthy", "app": "petshop"})

    return app


def run_petshop():
    """Run the Pet Shop server."""
    from security_agent.config import config

    app = create_app()
    print(f"🐾 Pet Shop starting on http://{config.petshop.host}:{config.petshop.port}")
    app.run(
        host=config.petshop.host,
        port=config.petshop.port,
        debug=False,
    )


if __name__ == "__main__":
    run_petshop()
