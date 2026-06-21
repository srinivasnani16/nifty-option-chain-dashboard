# ============================================================
#   NIFTY OPTION CHAIN DATA COLLECTOR
#   PHASE 1 UPDATE: All credentials moved to .env file
#   No hardcoded secrets in this file
# ============================================================

from SmartApi import SmartConnect
import sqlite3
import schedule
import time
import requests
import os
import pyotp
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# ============================================================
# LOAD CREDENTIALS FROM .env FILE
# ============================================================

load_dotenv("/home/ubuntu/.env")

API_KEY      = os.getenv("API_KEY")
CLIENT_ID    = os.getenv("CLIENT_ID")
PASSWORD     = os.getenv("ANGEL_PASSWORD")
TOTP_SECRET  = os.getenv("TOTP_SECRET")
BOT_TOKEN    = os.getenv("BOT_TOKEN")
CHAT_ID      = os.getenv("CHAT_ID")
DB_FILE      = os.getenv("DB_FILE", "/home/ubuntu/nifty_option_chain.db")

# ============================================================
# SETTINGS
# ============================================================

STRIKES_RANGE    = 5
LOT_SIZE         = 65
previous_oi      = {}
morning_msg_sent = False

# ============================================================
# MARKET HOLIDAY LIST
# ============================================================

NSE_HOLIDAYS = [
    "2026-01-26",
    "2026-03-25",
    "2026-04-02",
    "2026-04-14",
    "2026-04-17",
    "2026-05-01",
    "2026-08-15",
    "2026-10-02",
    "2026-10-24",
    "2026-11-14",
    "2026-11-27",
    "2026-12-25",
]

def is_trading_day():
    today = date.today()
    if today.weekday() >= 5:
        return False
    if today.strftime("%Y-%m-%d") in NSE_HOLIDAYS:
        return False
    return True

# ============================================================
# TELEGRAM FUNCTIONS
# ============================================================

def send_telegram(text):
    try:
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_telegram_file(filepath, caption):
    try:
        url   = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        files = {"document": open(filepath, "rb")}
        data  = {"chat_id": CHAT_ID, "caption": caption}
        requests.post(url, files=files, data=data, timeout=30)
        print(f"File sent to Telegram!")
    except Exception as e:
        print(f"Telegram file error: {e}")

# ============================================================
# DATABASE SETUP
# ============================================================

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS option_chain (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tag       TEXT,
            ce_oi     INTEGER,
            ce_coi    INTEGER,
            ce_volume INTEGER,
            ce_ltp    REAL,
            strike    INTEGER,
            pe_ltp    REAL,
            pe_volume INTEGER,
            pe_coi    INTEGER,
            pe_oi     INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    print("Database ready!")

def save_to_db(rows):
    try:
        conn = sqlite3.connect(DB_FILE)
        c    = conn.cursor()
        for row in rows:
            c.execute('''
                INSERT INTO option_chain
                (timestamp, tag, ce_oi, ce_coi, ce_volume, ce_ltp,
                 strike, pe_ltp, pe_volume, pe_coi, pe_oi)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                row["timestamp"], row["tag"],
                row["ce_oi"],     row["ce_coi"],
                row["ce_volume"], row["ce_ltp"],
                row["strike"],    row["pe_ltp"],
                row["pe_volume"], row["pe_coi"],
                row["pe_oi"]
            ))
        conn.commit()
        conn.close()
        print(f"Data saved to database!")
    except Exception as e:
        print(f"Database error: {e}")

# ============================================================
# LOGIN
# ============================================================

def login():
    try:
        obj  = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = obj.generateSession(CLIENT_ID, PASSWORD, totp)
        if data["status"] == True:
            print(f"Login OK at {datetime.now().strftime('%H:%M:%S')}")
            return obj
        else:
            print(f"Login Failed: {data}")
            return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

# ============================================================
# DOWNLOAD INSTRUMENTS
# ============================================================

def download_instruments():
    try:
        url      = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = requests.get(url)
        instruments = response.json()
        print(f"Instruments downloaded: {len(instruments)} found")
        return instruments
    except Exception as e:
        print(f"Error: {e}")
        return []

# ============================================================
# GET NEAREST EXPIRY
# ============================================================

def get_nearest_expiry(instruments):
    try:
        today       = date.today()
        nifty_items = [x for x in instruments
                       if x.get("name") == "NIFTY"
                       and x.get("exch_seg") == "NFO"
                       and x.get("instrumenttype") == "OPTIDX"]
        expiry_dates = []
        for item in nifty_items:
            try:
                exp_date = datetime.strptime(item["expiry"], "%d%b%Y").date()
                expiry_dates.append(exp_date)
            except:
                continue
        future_expiries = sorted(set([e for e in expiry_dates if e >= today]))
        if not future_expiries:
            return None
        expiry_str = future_expiries[0].strftime("%d%b%Y").upper()
        print(f"Nearest Expiry: {expiry_str}")
        return expiry_str
    except Exception as e:
        print(f"Expiry error: {e}")
        return None

# ============================================================
# GET TOKEN
# ============================================================

def get_token(instruments, strike, option_type, expiry):
    strike_str = f"{int(strike * 100)}.000000"
    for item in instruments:
        if (item.get("name") == "NIFTY" and
            item.get("expiry") == expiry and
            item.get("strike") == strike_str and
            item.get("symbol", "").endswith(option_type) and
            item.get("exch_seg") == "NFO"):
            return item["token"]
    return None

# ============================================================
# GET SPOT PRICE
# ============================================================

def get_atm_strike(obj):
    try:
        quote      = obj.ltpData("NSE", "Nifty 50", "99926000")
        spot_price = quote["data"]["ltp"]
        atm_strike = round(spot_price / 50) * 50
        print(f"Spot: {spot_price} | ATM: {atm_strike}")
        return atm_strike, spot_price
    except Exception as e:
        print(f"Spot price error: {e}")
        return None, None

# ============================================================
# FETCH MARKET DATA
# ============================================================

def fetch_full_data(obj, token):
    try:
        response = obj.getMarketData("FULL", {"NFO": [token]})
        if response and response.get("status") == True:
            fetched = response["data"].get("fetched", [])
            if fetched:
                d = fetched[0]
                return {
                    "ltp"    : d.get("ltp", 0) or 0,
                    "oi"     : round((d.get("opnInterest", 0) or 0) / LOT_SIZE),
                    "volume" : round((d.get("tradeVolume", 0) or 0) / LOT_SIZE),
                }
        return {"ltp": 0, "oi": 0, "volume": 0}
    except:
        return {"ltp": 0, "oi": 0, "volume": 0}

# ============================================================
# CALCULATE COI
# ============================================================

def calculate_coi(key, current_oi):
    global previous_oi
    coi = current_oi - previous_oi.get(key, current_oi)
    previous_oi[key] = current_oi
    return coi

# ============================================================
# ANALYSE AND SEND ALERTS
# ============================================================

def analyse_and_alert(rows, timestamp, spot_price):
    try:
        alerts  = []
        all_oi  = []
        all_vol = []

        for r in rows:
            if r["ce_oi"] > 0:     all_oi.append((r["ce_oi"], r["strike"], "CE"))
            if r["pe_oi"] > 0:     all_oi.append((r["pe_oi"], r["strike"], "PE"))
            if r["ce_volume"] > 0: all_vol.append((r["ce_volume"], r["strike"], "CE"))
            if r["pe_volume"] > 0: all_vol.append((r["pe_volume"], r["strike"], "PE"))

        if all_oi:
            max_oi = max(all_oi, key=lambda x: x[0])
            min_oi = min(all_oi, key=lambda x: x[0])
            alerts.append(f"🟢 Highest OI: {max_oi[0]:,} at {max_oi[2]} Strike {max_oi[1]}")
            alerts.append(f"🔴 Lowest OI: {min_oi[0]:,} at {min_oi[2]} Strike {min_oi[1]}")

        if all_vol:
            max_vol = max(all_vol, key=lambda x: x[0])
            alerts.append(f"🔵 Highest Volume: {max_vol[0]:,} at {max_vol[2]} Strike {max_vol[1]}")

        for row in rows:
            for side in ["CE", "PE"]:
                key = f"{row['strike']}_{side}_prev"
                coi = row["ce_coi"] if side == "CE" else row["pe_coi"]
                if key in previous_oi and previous_oi[key] > 0:
                    change_pct = abs(coi) / previous_oi[key] * 100
                    if change_pct > 20:
                        alerts.append(f"🟡 Drastic {side} OI Change at {row['strike']}: {coi:+,} ({change_pct:.1f}%)")

        if alerts:
            message = (
                f"<b>🚨 NIFTY OPTION CHAIN ALERT</b>\n"
                f"<b>🕐 Time: {timestamp}</b>\n"
                f"<b>📈 Spot: {spot_price}</b>\n\n"
                + "\n".join(alerts)
            )
            send_telegram(message)
            print("Alert sent!")
    except Exception as e:
        print(f"Alert error: {e}")

# ============================================================
# FETCH OPTION CHAIN
# ============================================================

def fetch_option_chain(obj, instruments, atm_strike, expiry):
    try:
        rows      = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for i in range(-STRIKES_RANGE, STRIKES_RANGE + 1):
            strike = atm_strike + (i * 50)
            tag    = "ATM" if i == 0 else (f"ATM+{i}" if i > 0 else f"ATM{i}")

            ce_ltp = ce_oi = ce_coi = ce_volume = 0
            pe_ltp = pe_oi = pe_coi = pe_volume = 0

            ce_token = get_token(instruments, strike, "CE", expiry)
            if ce_token:
                ce        = fetch_full_data(obj, ce_token)
                ce_ltp    = ce["ltp"]
                ce_oi     = ce["oi"]
                ce_volume = ce["volume"]
                ce_coi    = calculate_coi(f"{strike}_CE", ce_oi)
                time.sleep(0.3)

            pe_token = get_token(instruments, strike, "PE", expiry)
            if pe_token:
                pe        = fetch_full_data(obj, pe_token)
                pe_ltp    = pe["ltp"]
                pe_oi     = pe["oi"]
                pe_volume = pe["volume"]
                pe_coi    = calculate_coi(f"{strike}_PE", pe_oi)
                time.sleep(0.3)

            rows.append({
                "timestamp": timestamp, "tag": tag,
                "ce_oi": ce_oi, "ce_coi": ce_coi,
                "ce_volume": ce_volume, "ce_ltp": ce_ltp,
                "strike": strike,
                "pe_ltp": pe_ltp, "pe_volume": pe_volume,
                "pe_coi": pe_coi, "pe_oi": pe_oi,
            })
            print(f"{tag:6} | {strike} | CE OI:{ce_oi:>8,} | PE OI:{pe_oi:>8,}")

        return rows, timestamp
    except Exception as e:
        print(f"Error: {e}")
        return [], ""

# ============================================================
# END OF DAY
# ============================================================

def end_of_day():
    if not is_trading_day():
        return
    print("Market Closed! Sending end of day summary...")
    send_telegram(
        f"<b>📊 NIFTY OPTION CHAIN — END OF DAY</b>\n"
        f"<b>📅 Date: {date.today().strftime('%d %b %Y')}</b>\n\n"
        f"Market session completed!\n"
        f"Complete SQLite database file attached below."
    )
    if os.path.exists(DB_FILE):
        send_telegram_file(DB_FILE, f"Nifty Option Chain — {date.today().strftime('%d %b %Y')}")

# ============================================================
# MORNING MESSAGE
# ============================================================

def morning_check():
    global morning_msg_sent
    if morning_msg_sent:
        return
    morning_msg_sent = True

    if not is_trading_day():
        today    = date.today()
        day_name = today.strftime("%A")
        date_str = today.strftime("%d %b %Y")
        reason   = "Saturday — Weekend" if today.weekday() == 5 else \
                   "Sunday — Weekend"   if today.weekday() == 6 else \
                   "Public Holiday"
        send_telegram(
            f"<b>🔴 MARKET CLOSED TODAY</b>\n"
            f"<b>📅 {day_name}, {date_str}</b>\n\n"
            f"Reason: {reason}\n"
            f"Bot resumes next trading day automatically."
        )
        print(f"Market closed — {reason}")
    else:
        send_telegram(
            f"<b>🟢 MARKET OPEN TODAY</b>\n"
            f"<b>📅 {date.today().strftime('%d %b %Y')}</b>\n\n"
            f"Data collection starts at 9:15 AM\n"
            f"Alerts will be sent for high OI activity."
        )
        print("Market open — collection starts at 9:15 AM")

# ============================================================
# MAIN JOB
# ============================================================

def job():
    if not is_trading_day():
        return
    now          = datetime.now().time()
    market_start = datetime.strptime("09:15", "%H:%M").time()
    market_end   = datetime.strptime("15:30", "%H:%M").time()
    if not (market_start <= now <= market_end):
        return

    print(f"\n{'='*60}")
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    obj = login()
    if obj is None: return

    instruments = download_instruments()
    if not instruments: return

    expiry = get_nearest_expiry(instruments)
    if expiry is None: return

    atm_strike, spot_price = get_atm_strike(obj)
    if atm_strike is None: return

    rows, timestamp = fetch_option_chain(obj, instruments, atm_strike, expiry)
    save_to_db(rows)
    analyse_and_alert(rows, timestamp, spot_price)
    print("Done! Next run in 5 minutes.")

# ============================================================
# RESET MORNING FLAG
# ============================================================

def reset_morning_flag():
    global morning_msg_sent
    morning_msg_sent = False
    print("Morning flag reset for new day")

# ============================================================
# SCHEDULER
# ============================================================

def run_scheduler():
    print("Nifty Option Chain Collector Started!")
    print(f"Lot Size: {LOT_SIZE} | DB: {DB_FILE}")

    schedule.every().day.at("08:00").do(morning_check)
    schedule.every(5).minutes.do(job)
    schedule.every().day.at("15:31").do(end_of_day)
    schedule.every().day.at("00:01").do(reset_morning_flag)

    morning_check()

    while True:
        schedule.run_pending()
        time.sleep(30)

# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    setup_database()
    run_scheduler()
