from flask import Flask
import threading
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import json
import os

app = Flask(__name__)

# ============================================
# YOUR SETTINGS
# ============================================

PUSHOVER_USER = "uv4ar371e2hh22m23ozycabbp71mbe"
PUSHOVER_TOKEN = "ai2ub9o9ey9jaj4hfozp6vtgom167z"

# How often to check for new products (seconds)
CHECK_FREQUENCY = 15

# NOTIFICATION SETTINGS
NOTIFICATION_REPEAT = True
REPEAT_INTERVAL = 120
MAX_REPEATS = 10

# Keywords that catch ALL District Vision products
WANTED_KEYWORDS = [
    "district-vision",
]

# Products to NEVER alert about
BLOCKED_PRODUCTS = [
    "outdoor-track-pants",
]

# ============================================

PAGE_URL = "https://m.thehipstore.co.uk/mens/brand/district-vision/"

SEEN_FILE = "seen_products.json"
FOUND_FILE = "pending_alerts.json"
seen_products = set()
pending_alerts = {}

def load_seen_products():
    global seen_products, pending_alerts
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, 'r') as f:
                seen_products = set(json.load(f))
            print(f"Loaded {len(seen_products)} previously seen products")
    except:
        seen_products = set()
    
    try:
        if os.path.exists(FOUND_FILE):
            with open(FOUND_FILE, 'r') as f:
                pending_alerts = json.load(f)
            print(f"Loaded {len(pending_alerts)} pending alerts")
    except:
        pending_alerts = {}

def save_seen_products():
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump(list(seen_products), f)
    except:
        pass

def save_pending_alerts():
    try:
        with open(FOUND_FILE, 'w') as f:
            json.dump(pending_alerts, f)
    except:
        pass

def send_notification(title, message, url="", priority=2):
    try:
        data = {
            "token": PUSHOVER_TOKEN,
            "user": PUSHOVER_USER,
            "title": title,
            "message": message,
            "url": url,
            "priority": priority,
            "sound": "persistent"
        }
        
        if priority == 2:
            data["retry"] = REPEAT_INTERVAL
            data["expire"] = REPEAT_INTERVAL * MAX_REPEATS
        
        response = requests.post("https://api.pushover.net/1/messages.json", data=data)
        if response.status_code == 200:
            print(f"✅ Notification sent: {title}")
            return True
        else:
            print(f"❌ Notification failed: {response.text}")
            return False
    except Exception as e:
        print(f"Notification error: {e}")
        return False

def is_blocked(href, text):
    """Check if product should be ignored"""
    combined = (text + " " + href).lower()
    for blocked in BLOCKED_PRODUCTS:
        if blocked.lower() in combined:
            return True
    return False

def check_page():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15')
    
    driver = webdriver.Chrome(options=options)
    new_found = 0
    
    try:
        timestamp = datetime.now().strftime('%H:%M:%S')
        driver.get(PAGE_URL)
        time.sleep(3)
        
        links = driver.find_elements(By.TAG_NAME, "a")
        
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                combined = (text + " " + href).lower()
                
                # Skip blocked products
                if is_blocked(href, text):
                    continue
                
                # Check if it has "product" in the URL
                has_product = "/product/" in href.lower() or "/products/" in href.lower()
                
                for keyword in WANTED_KEYWORDS:
                    if keyword in combined and href not in seen_products and has_product:
                        
                        seen_products.add(href)
                        save_seen_products()
                        new_found += 1
                        
                        product_name = text or "District Vision Product"
                        
                        print(f"🆕 NEW PRODUCT: {product_name}")
                        print(f"   URL: {href}")
                        print(f"   Time: {timestamp}")
                        
                        pending_alerts[href] = {
                            "name": product_name,
                            "url": href,
                            "found_at": datetime.now().isoformat(),
                            "repeats_sent": 0
                        }
                        save_pending_alerts()
                        
                        send_notification(
                            "🚨 NEW DISTRICT VISION!",
                            f"{product_name}\n\nTap to view and purchase!",
                            href,
                            priority=2
                        )
            except:
                continue
        
        if new_found > 0:
            print(f"   → {new_found} new product(s) found and notified")
        else:
            print(f"[{timestamp}] No new products - {len(seen_products)} total seen before")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

def send_pending_alerts():
    if not NOTIFICATION_REPEAT:
        return
    
    for url, info in list(pending_alerts.items()):
        repeats = info.get("repeats_sent", 0)
        
        if repeats < MAX_REPEATS:
            pending_alerts[url]["repeats_sent"] = repeats + 1
            save_pending_alerts()
            
            print(f"🔁 Repeat alert {repeats + 1}/{MAX_REPEATS}: {info['name']}")
            
            send_notification(
                f"⏰ REMINDER: Still Available!",
                f"{info['name']}\n\nAlert {repeats + 1} of {MAX_REPEATS}\nTap to buy!",
                url,
                priority=2
            )
        else:
            del pending_alerts[url]
            save_pending_alerts()
            print(f"⏹️  Stopped alerts for: {info['name']}")

def monitor():
    load_seen_products()
    
    print("=" * 50)
    print("🚨 DISTRICT VISION MONITOR")
    print("=" * 50)
    print(f"📱 Emergency notifications (bypasses silent mode)")
    print(f"🔁 Repeats: Every {REPEAT_INTERVAL}s up to {MAX_REPEATS} times")
    print(f"🔍 Catching ALL District Vision products")
    print(f"🚫 Blocked: {', '.join(BLOCKED_PRODUCTS)}")
    print(f"📦 Previously seen: {len(seen_products)} products")
    print(f"⏱️  Checking every {CHECK_FREQUENCY} seconds")
    print("=" * 50)
    
    last_alert_check = time.time()
    
    while True:
        try:
            check_page()
            
            if time.time() - last_alert_check >= REPEAT_INTERVAL:
                send_pending_alerts()
                last_alert_check = time.time()
            
            time.sleep(CHECK_FREQUENCY)
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(30)

@app.route('/')
def dashboard():
    pending_html = ""
    if pending_alerts:
        for url, info in pending_alerts.items():
            pending_html += f"""
            <li style="background:#330000;padding:10px;border-radius:8px;margin:5px 0;">
                🚨 {info['name']}<br>
                <small>Repeats: {info.get('repeats_sent', 0)}/{MAX_REPEATS}</small><br>
                <a href="{url}" style="color:#ff4444;">Tap to buy →</a>
            </li>"""
    else:
        pending_html = "<li>No pending alerts</li>"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="{CHECK_FREQUENCY}">
    <title>District Vision Monitor</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, sans-serif; padding: 20px; background: #000; color: #fff; }}
        h1 {{ font-size: 22px; margin-bottom: 5px; }}
        .status {{ color: #00ff00; font-size: 16px; margin-bottom: 20px; }}
        .card {{ background: #1a1a1a; padding: 18px; border-radius: 12px; margin-bottom: 12px; }}
        .card h3 {{ color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
        .big-number {{ font-size: 36px; font-weight: bold; color: #ff4444; }}
        .info {{ color: #aaa; font-size: 13px; margin-top: 15px; }}
        ul {{ list-style: none; }}
        li {{ padding: 6px 0; font-size: 14px; }}
        .time {{ color: #666; font-size: 12px; }}
        a {{ color: #ff4444; text-decoration: none; }}
    </style>
    </head>
    <body>
    <h1>🥽 District Vision Monitor</h1>
    <p class="status">● Active - Every {CHECK_FREQUENCY}s</p>
    
    <div class="card">
    <h3>Alert Mode</h3>
    <p>🔁 Repeats every {REPEAT_INTERVAL}s</p>
    <p>🔢 Max {MAX_REPEATS} repeats</p>
    <p>📱 Emergency priority (bypasses silent)</p>
    </div>
    
    <div class="card">
    <h3>🔴 Pending Alerts ({len(pending_alerts)})</h3>
    <ul>{pending_html}</ul>
    </div>
    
    <div class="card">
    <h3>Monitoring</h3>
    <p>🔍 ALL District Vision products</p>
    </div>
    
    <div class="card">
    <h3>Blocked</h3>
    <ul>
        {"".join(f"<li>🚫 {b.replace('-', ' ').title()}</li>" for b in BLOCKED_PRODUCTS)}
    </ul>
    </div>
    
    <div class="card">
    <h3>Total Products Seen</h3>
    <p class="big-number">{len(seen_products)}</p>
    </div>
    
    <p class="info">Last check: {datetime.now().strftime('%H:%M:%S')}<br>Auto-refreshes every {CHECK_FREQUENCY} seconds</p>
    </body>
    </html>
    """

@app.route('/acknowledge')
def acknowledge():
    global pending_alerts
    count = len(pending_alerts)
    pending_alerts = {}
    save_pending_alerts()
    return f"✅ Stopped alerts for {count} product(s)."

@app.route('/reset')
def reset():
    global seen_products, pending_alerts
    seen_products = set()
    pending_alerts = {}
    save_seen_products()
    save_pending_alerts()
    return "✅ Full reset complete."

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
