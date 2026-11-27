import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from db import get_db_connection
from services.fetcher import get_live_prices

load_dotenv()

def send_email_alert(to_email, product_query, current_price, platform, buy_url):
    sender = os.getenv("SMTP_EMAIL")
    password = os.getenv("SMTP_PASSWORD")
    if not sender or not password or "your_email" in sender:
        print(f"[Alert Simulated] Email to {to_email}: {product_query} dropped to INR {current_price} on {platform} -> {buy_url}")
        return

    subject = f"Price Drop Alert: {product_query} is now ₹{current_price}!"
    body = (
        f"Good news!\n\n"
        f"Your tracked item '{product_query}' has reached ₹{current_price} on {platform}.\n"
        f"Buy directly here: {buy_url}\n\n"
        f"- Smart E-Commerce Price Comparison Platform"
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"[Email Sent] Alert delivered to {to_email}")
    except Exception as e:
        print(f"[Email Error]: {e}")

def check_all_price_alerts():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM price_alerts WHERE is_triggered = FALSE")
    alerts = cursor.fetchall()

    for alert in alerts:
        data = get_live_prices(alert["product_query"])
        rec = data.get("recommendation")
        if rec and rec["lowest_price"] <= float(alert["target_price"]):
            send_email_alert(
                alert["user_email"],
                alert["product_query"],
                rec["lowest_price"],
                rec["best_platform"],
                rec["buy_url"]
            )
            cursor.execute("UPDATE price_alerts SET is_triggered = TRUE WHERE id = %s", (alert["id"],))
            conn.commit()

    cursor.close()
    conn.close()
