
import os
import sqlite3
import hashlib
import requests
from telegram import Bot

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

DB_FILE = "seen.db"

NSE_BASE = "https://www.nseindia.com"
NSE_API = "https://www.nseindia.com/api/corporate-announcements?index=equities"

WATCHLIST = [
    "TCS",
    "INFY",
    "RELIANCE",
    "HDFCBANK"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def already_seen(x):
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute("SELECT 1 FROM seen WHERE id=?", (x,)).fetchone()
    conn.close()
    return row is not None

def save_seen(x):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO seen(id) VALUES (?)", (x,))
    conn.commit()
    conn.close()

def fetch_announcements():
    s = requests.Session()

    s.get(NSE_BASE, headers=HEADERS, timeout=20)

    r = s.get(NSE_API, headers=HEADERS, timeout=20)

    data = r.json().get("data", [])

    out = []

    for item in data:
        symbol = str(item.get("symbol", "")).upper()
        company = item.get("companyName", "")
        subject = item.get("subject", "Corporate announcement")
        pdf = item.get("attchmntFile", "")
        dt = item.get("an_dt", "")

        if symbol not in WATCHLIST:
            continue

        uid = hashlib.sha256(
            f"{symbol}{subject}{pdf}".encode()
        ).hexdigest()

        out.append({
            "id": uid,
            "symbol": symbol,
            "company": company,
            "subject": subject,
            "pdf": pdf,
            "dt": dt
        })

    return out

def send_message(text):
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(
        chat_id=CHAT_ID,
        text=text,
        disable_web_page_preview=False
    )

def main():
    init_db()

    try:
        announcements = fetch_announcements()
    except Exception as e:
        print("Fetch failed:", e)
        return

    for item in announcements:

        if already_seen(item["id"]):
            continue

        save_seen(item["id"])

        msg = (
            f"Company name: {item['company']}\n\n"
            f"Gist of update: {item['subject']}\n\n"
            f"Time/date: {item['dt']}\n\n"
            f"PDF:\n{item['pdf']}"
        )

        try:
            send_message(msg)
            print("Sent:", item["symbol"])
        except Exception as e:
            print("Telegram failed:", e)

if __name__ == "__main__":
    main()
