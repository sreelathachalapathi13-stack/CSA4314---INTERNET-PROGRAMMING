from flask import Flask, request, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_db_connection
from services.fetcher import get_live_prices
from services.alerter import check_all_price_alerts

app = Flask(__name__)
CORS(app)

# Background scheduler checks alerts every 30 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_all_price_alerts, trigger="interval", minutes=30)
scheduler.start()

@app.route("/api/compare", methods=["GET"])
def compare_product():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Search query is required"}), 400

    result = get_live_prices(query)
    amazon = result["amazon"]
    flipkart = result["flipkart"]
    rec = result["recommendation"]

    # Save search and price history in MySQL
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        title = (amazon["title"] if amazon["price"] else flipkart["title"]) or query
        best_platform = rec["best_platform"] if rec else None
        lowest_price = rec["lowest_price"] if rec else None

        cursor.execute(
            """INSERT INTO products 
               (search_query, title, amazon_price, amazon_url, flipkart_price, flipkart_url, lowest_platform, lowest_price)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                query,
                title[:490],
                amazon["price"],
                amazon["url"],
                flipkart["price"],
                flipkart["url"],
                best_platform,
                lowest_price
            )
        )
        product_id = cursor.lastrowid

        if amazon["price"]:
            cursor.execute(
                "INSERT INTO price_history (product_id, platform, price) VALUES (%s, %s, %s)",
                (product_id, "Amazon", amazon["price"])
            )
        if flipkart["price"]:
            cursor.execute(
                "INSERT INTO price_history (product_id, platform, price) VALUES (%s, %s, %s)",
                (product_id, "Flipkart", flipkart["price"])
            )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[MySQL Logging Error]: {e}")

    return jsonify(result)

@app.route("/api/history", methods=["GET"])
def price_history():
    query = request.args.get("q", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT p.search_query, ph.platform, ph.price, ph.recorded_at
           FROM price_history ph
           JOIN products p ON ph.product_id = p.id
           WHERE p.search_query LIKE %s
           ORDER BY ph.recorded_at ASC LIMIT 30""",
        (f"%{query}%",)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/alerts", methods=["POST"])
def create_alert():
    data = request.get_json()
    email = data.get("email", "").strip()
    product_query = data.get("product_query", "").strip()
    target_price = data.get("target_price")

    if not email or not product_query or not target_price:
        return jsonify({"error": "Email, product name, and target price are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO price_alerts (user_email, product_query, target_price) VALUES (%s, %s, %s)",
        (email, product_query, float(target_price))
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": f"Alert set! We will notify {email} when '{product_query}' drops to ₹{target_price}."})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
