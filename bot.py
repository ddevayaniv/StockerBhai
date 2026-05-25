
import os, json, hashlib, requests, traceback
from datetime import datetime, timezone
from telegram import Bot

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = str(os.environ["CHAT_ID"])

STATE_FILE = "state.json"
STATUS_FILE = "status.json"

NSE_BASE = "https://www.nseindia.com"
NSE_API = "https://www.nseindia.com/api/corporate-announcements?index=equities"

WATCHLIST = sorted(set([
    "BSE","MCX","ANGELONE","MOTILALOFS","ANANDRATHI","NUVAMA",
    "360ONE","PRUDENT","CAMS","KFINTECH","CDSL","NSDL",
    "HDFCAMC","NAM-INDIA","ABSLAMC","UTIAMC","JMFINANCIL",
    "CRISIL","INDIGO","SPICEJET","TEXRAIL","TITAGARH",
    "RVNL","RAILTEL","RITES","JWL","IRCTC","GESHIP","SCI",
    "ZEEL","PVRINOX","SUNTV","DBCORP","TIPSMUSIC",
    "NETWORK18","SAREGAMA","PAGEIND","VTL","KPRMILL",
    "WELSPUNLIV","VMART","ARVIND","RAYMOND","ICIL",
    "GOKEX","LUXIND","ARVINDFASN","TRIDENT","PGIL",
    "ABFRL","NITINSPIN","SAISILK","GANECOS"
]))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

bot = Bot(token=TOKEN)

def now():
    return datetime.now(timezone.utc).isoformat()

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

state = load_json(STATE_FILE, {
    "seen": [],
    "last_update_id": 0,
    "heartbeat_counter": 0
})

status = load_json(STATUS_FILE, {
    "last_run": None,
    "last_success": None,
    "last_error": None,
    "nse_ok": False
})

def send(text):
    bot.send_message(
        chat_id=CHAT_ID,
        text=text[:4000],
        disable_web_page_preview=False
    )

def handle_commands():
    try:
        updates = bot.get_updates(offset=state["last_update_id"] + 1, timeout=1)

        for upd in updates:
            state["last_update_id"] = upd.update_id

            if not upd.message or not upd.message.text:
                continue

            if str(upd.message.chat_id) != CHAT_ID:
                continue

            cmd = upd.message.text.strip().lower()

            if cmd == "/ping":
                send("StockerBhai is alive.")

            elif cmd == "/status":
                send(
                    f"Last successful NSE fetch:\n{status.get('last_success')}\n\n"
                    f"NSE reachable: {status.get('nse_ok')}\n\n"
                    f"Last error:\n{status.get('last_error')}"
                )

            elif cmd == "/watchlist":
                send("Watching:\n\n" + "\n".join(WATCHLIST[:150]))

            elif cmd == "/help":
                send(
                    "/ping\n"
                    "/status\n"
                    "/watchlist\n"
                    "/help"
                )

    except Exception as e:
        print("Command handling failed:", e)

def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)

    home = s.get(NSE_BASE, timeout=20)

    if home.status_code != 200:
        raise Exception(f"NSE homepage failed: {home.status_code}")

    return s

def fetch_announcements():
    s = get_session()

    r = s.get(NSE_API, timeout=30)

    ct = r.headers.get("content-type", "")

    if r.status_code != 200:
        raise Exception(f"NSE status code: {r.status_code}")

    if "json" not in ct.lower():
        raise Exception("NSE likely blocked request (non JSON response)")

    payload = r.json()

    data = payload.get("data", [])

    if not isinstance(data, list):
        raise Exception("Unexpected NSE response structure")

    status["nse_ok"] = True
    status["last_success"] = now()

    out = []

    for item in data:
        symbol = str(item.get("symbol", "")).upper().strip()

        if symbol not in WATCHLIST:
            continue

        subject = item.get("subject", "")
        pdf = item.get("attchmntFile", "")
        dt = item.get("an_dt", "")
        company = item.get("companyName", symbol)

        uid = hashlib.sha256(
            f"{symbol}|{subject}|{pdf}".encode()
        ).hexdigest()

        out.append({
            "id": uid,
            "symbol": symbol,
            "subject": subject,
            "pdf": pdf,
            "dt": dt,
            "company": company
        })

    return out

def main():
    status["last_run"] = now()

    handle_commands()

    try:
        announcements = fetch_announcements()

        sent = 0

        for item in announcements:

            if item["id"] in state["seen"]:
                continue

            state["seen"].append(item["id"])

            msg = (
                f"{item['symbol']}\n\n"
                f"{item['subject']}\n\n"
                f"Time: {item['dt']}\n\n"
                f"PDF:\n{item['pdf']}"
            )

            send(msg)
            sent += 1

        state["seen"] = state["seen"][-5000:]

        state["heartbeat_counter"] += 1

        # every ~1 hour on 15m schedule
        if state["heartbeat_counter"] >= 4:
            send(
                "Heartbeat\n\n"
                f"Bot running normally\n"
                f"NSE reachable: {status.get('nse_ok')}\n"
                f"Last fetch: {status.get('last_success')}"
            )
            state["heartbeat_counter"] = 0

        print(f"Completed successfully. Alerts sent: {sent}")

    except Exception as e:
        status["nse_ok"] = False
        status["last_error"] = str(e)

        err = traceback.format_exc()
        print(err)

        try:
            send(
                "ERROR\n\n"
                f"{str(e)}\n\n"
                "Possible reasons:\n"
                "- NSE blocked request\n"
                "- GitHub transient network issue\n"
                "- Invalid Telegram config"
            )
        except Exception as inner:
            print(inner)

    save_json(STATE_FILE, state)
    save_json(STATUS_FILE, status)

if __name__ == "__main__":
    import requests
    import os

    TOKEN = os.environ["TELEGRAM_TOKEN"]
    CHAT_ID = os.environ["CHAT_ID"]

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": "DIRECT TELEGRAM TEST"
    }

    r = requests.post(url, json=payload)

    print(r.text)
