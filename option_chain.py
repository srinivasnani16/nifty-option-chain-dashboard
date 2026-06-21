# ============================================================
#   NIFTY OPTION CHAIN DATA COLLECTOR
#   PHASE 3 UPDATE: Telegram replaced with Discord Webhooks
# ============================================================

from SmartApi import SmartConnect
import psycopg2
import schedule
import time
import requests
import os
import pyotp
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY         = os.getenv("API_KEY")
CLIENT_ID       = os.getenv("CLIENT_ID")
PASSWORD        = os.getenv("ANGEL_PASSWORD")
TOTP_SECRET     = os.getenv("TOTP_SECRET")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

STRIKES_RANGE       = 5
LOT_SIZE            = 65
previous_oi         = {}
morning_msg_sent    = False
OI_SPIKE_THRESHOLD  = 76923

NSE_HOLIDAYS = [
    "2026-01-26", "2026-03-25", "2026-04-02", "2026-04-14",
    "2026-04-17", "2026-05-01", "2026-08-15", "2026-10-02",
    "2026-10-24", "2026-11-14", "2026-11-27", "2026-12-25",
]

def is_trading_day():
    today = date.today()
    if today.weekday() >= 5:
        return False
    if today.strftime("%Y-%m-%d") in NSE_HOLIDAYS:
        return False
    return True

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "nifty_db"),
        user=os.getenv("DB_USER", "nifty"),
        password=os.getenv("DB_PASS", "Nifty@2026")
    )

def setup_database():
    retries = 10
    while retries > 0:
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS option_chain (
                    id SERIAL PRIMARY KEY, timestamp TEXT, tag TEXT,
                    ce_oi INTEGER, ce_coi INTEGER, ce_volume INTEGER, ce_ltp REAL,
                    strike INTEGER, pe_ltp REAL, pe_volume INTEGER, pe_coi INTEGER, pe_oi INTEGER
                )
            ''')
            conn.commit()
            conn.close()
            print("PostgreSQL database ready!")
            return
        except Exception as e:
            print(f"DB not ready yet, retrying... ({e})")
            retries -= 1
            time.sleep(5)
    print("Could not connect to database after retries!")

def save_to_db(rows):
    try:
        conn = get_db()
        c = conn.cursor()
        for row in rows:
            c.execute('''
                INSERT INTO option_chain
                (timestamp, tag, ce_oi, ce_coi, ce_volume, ce_ltp,
                 strike, pe_ltp, pe_volume, pe_coi, pe_oi)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ''', (
                row["timestamp"], row["tag"],
                row["ce_oi"], row["ce_coi"], row["ce_volume"], row["ce_ltp"],
                row["strike"], row["pe_ltp"], row["pe_volume"], row["pe_coi"], row["pe_oi"]
            ))
        conn.commit()
        conn.close()
        print("Data saved to PostgreSQL!")
    except Exception as e:
        print(f"Database error: {e}")

def send_discord(title, description, color, fields=None):
    if not DISCORD_WEBHOOK:
        print("Discord webhook not configured in .env")
        return
    try:
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "footer": {"text": "Nifty Option Chain Bot"},
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        if fields:
            embed["fields"] = fields
        response = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if response.status_code == 204:
            print("Discord alert sent!")
        else:
            print(f"Discord error: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"Discord exception: {e}")

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

def download_instruments():
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        response = requests.get(url)
        instruments = response.json()
        print(f"Instruments downloaded: {len(instruments)} found")
        return instruments
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_nearest_expiry(instruments):
    try:
        today = date.today()
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

def fetch_full_data(obj, token):
    try:
        response = obj.getMarketData("FULL", {"NFO": [token]})
        if response and response.get("status") == True:
            fetched = response["data"].get("fetched", [])
            if fetched:
                d = fetched[0]
                return {
                    "ltp":    d.get("ltp", 0) or 0,
                    "oi":     round((d.get("opnInterest", 0) or 0) / LOT_SIZE),
                    "volume": round((d.get("tradeVolume", 0) or 0) / LOT_SIZE),
                }
        return {"ltp": 0, "oi": 0, "volume": 0}
    except:
        return {"ltp": 0, "oi": 0, "volume": 0}

def calculate_coi(key, current_oi):
    global previous_oi
    coi = current_oi - previous_oi.get(key, current_oi)
    previous_oi[key] = current_oi
    return coi

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
                "ce_oi": ce_oi, "ce_coi": ce_coi, "ce_volume": ce_volume, "ce_ltp": ce_ltp,
                "strike": strike,
                "pe_ltp": pe_ltp, "pe_volume": pe_volume, "pe_coi": pe_coi, "pe_oi": pe_oi,
            })
            print(f"{tag:6} | {strike} | CE OI:{ce_oi:>8,} | PE OI:{pe_oi:>8,}")
        return rows, timestamp
    except Exception as e:
        print(f"Error: {e}")
        return [], ""

def analyse_and_alert(rows, timestamp, spot_price):
    try:
        total_ce_oi = 0
        total_pe_oi = 0
        max_ce_oi = max_pe_oi = max_vol = 0
        max_ce_strike = max_pe_strike = max_vol_strike = 0
        max_vol_side = ""
        oi_spike_alerts = []

        for r in rows:
            total_ce_oi += r["ce_oi"]
            total_pe_oi += r["pe_oi"]
            if r["ce_oi"] > max_ce_oi:
                max_ce_oi = r["ce_oi"]
                max_ce_strike = r["strike"]
            if r["pe_oi"] > max_pe_oi:
                max_pe_oi = r["pe_oi"]
                max_pe_strike = r["strike"]
            if r["ce_volume"] > max_vol:
                max_vol = r["ce_volume"]
                max_vol_strike = r["strike"]
                max_vol_side = "CE"
            if r["pe_volume"] > max_vol:
                max_vol = r["pe_volume"]
                max_vol_strike = r["strike"]
                max_vol_side = "PE"
            if r["ce_oi"] > OI_SPIKE_THRESHOLD:
                oi_spike_alerts.append(
                    f"CE {r['strike']} — OI: {r['ce_oi']:,} lots (~{r['ce_oi']*LOT_SIZE//100000:.0f}L)"
                )
            if r["pe_oi"] > OI_SPIKE_THRESHOLD:
                oi_spike_alerts.append(
                    f"PE {r['strike']} — OI: {r['pe_oi']:,} lots (~{r['pe_oi']*LOT_SIZE//100000:.0f}L)"
                )

        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0

        if pcr >= 1.3:
            color = 3066993
            sentiment = "🟢 Bullish"
        elif pcr <= 0.7:
            color = 15158332
            sentiment = "🔴 Bearish"
        else:
            color = 9807270
            sentiment = "⚪ Neutral"

        summary_fields = [
            {"name": "📈 Spot Price",      "value": f"**{spot_price}**",                                              "inline": True},
            {"name": "📊 PCR",             "value": f"**{pcr}**",                                                     "inline": True},
            {"name": "🎯 Sentiment",       "value": sentiment,                                                         "inline": True},
            {"name": "🔵 Total CE OI",     "value": f"{total_ce_oi:,} lots",                                          "inline": True},
            {"name": "🟣 Total PE OI",     "value": f"{total_pe_oi:,} lots",                                          "inline": True},
            {"name": "\u200b",             "value": "\u200b",                                                          "inline": True},
            {"name": "🔴 Resistance (CE)", "value": f"Strike **{max_ce_strike}** — {max_ce_oi:,} lots",              "inline": True},
            {"name": "🟢 Support (PE)",    "value": f"Strike **{max_pe_strike}** — {max_pe_oi:,} lots",              "inline": True},
            {"name": "📦 Highest Volume",  "value": f"{max_vol_side} {max_vol_strike} — {max_vol:,} lots",           "inline": True},
        ]

        send_discord(
            title="📊 Nifty Option Chain — Cycle Update",
            description=f"Snapshot at **{timestamp}**",
            color=color,
            fields=summary_fields
        )

        if pcr >= 1.3:
            send_discord(
                title="🚨 PCR ALERT — Bullish Signal",
                description=(
                    f"PCR has crossed **1.3** — strong **bullish** sentiment.\n"
                    f"PCR = `{pcr}` | Spot = **{spot_price}**\n\n"
                    f"PE writers are dominating. Watch for upside momentum."
                ),
                color=3066993
            )
        elif pcr <= 0.7:
            send_discord(
                title="🚨 PCR ALERT — Bearish Signal",
                description=(
                    f"PCR has dropped below **0.7** — strong **bearish** sentiment.\n"
                    f"PCR = `{pcr}` | Spot = **{spot_price}**\n\n"
                    f"CE writers are dominating. Watch for downside pressure."
                ),
                color=15158332
            )

        if oi_spike_alerts:
            send_discord(
                title="⚠️ OI SPIKE — High Open Interest Detected",
                description=(
                    f"Strikes crossing **50 Lakh OI** at {timestamp}:\n\n"
                    + "\n".join(f"• {a}" for a in oi_spike_alerts)
                    + f"\n\nSpot = **{spot_price}**"
                ),
                color=15105570
            )

        print("Analysis complete. Alerts sent to Discord.")
    except Exception as e:
        print(f"Alert error: {e}")

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
        send_discord(
            title="🔴 Market Closed Today",
            description=f"**{day_name}, {date_str}**\n\nReason: {reason}\nBot resumes next trading day automatically.",
            color=15158332
        )
    else:
        send_discord(
            title="🟢 Market Open Today",
            description=f"**{date.today().strftime('%d %b %Y')}**\n\nData collection starts at 9:15 AM IST.",
            color=3066993
        )

def end_of_day():
    if not is_trading_day():
        return
    send_discord(
        title="📊 End of Day — Session Complete",
        description=f"**{date.today().strftime('%d %b %Y')}**\n\nMarket session ended. All data saved to PostgreSQL.",
        color=3447003
    )

def reset_morning_flag():
    global morning_msg_sent
    morning_msg_sent = False

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

def run_scheduler():
    print("Nifty Option Chain Collector Started!")
    schedule.every().day.at("08:00").do(morning_check)
    schedule.every(5).minutes.do(job)
    schedule.every().day.at("15:31").do(end_of_day)
    schedule.every().day.at("00:01").do(reset_morning_flag)
    morning_check()
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    setup_database()
    run_scheduler()
