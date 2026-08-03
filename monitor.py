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
import hashlib

app = Flask(__name__)

# ============================================
# YOUR SETTINGS
# ============================================

PUSHOVER_USER = "uv4ar371e2hh22m23ozycabbp71mbe"
PUSHOVER_TOKEN = "ai2ub9o9ey9jaj4hfozp6vtgom167z"

CHECK_FREQUENCY = 30
REPEAT_INTERVAL = 30
MAX_REPEATS = 100
PUSHOVER_PRIORITY = 2

# ============================================
# MONITOR SALE PAGE ONLY (sorted by latest)
# ============================================

PAGES_TO_WATCH = [
    "https://m.thehipstore.co.uk/sale/?sort=latest",
]

WANTED_KEYWORDS = [
    "district",
    "vision",
    "koharu",
    "takeyoshi",
    "junya",
    "nagata",
    "keiichi",
    "sunglasses",
    "eyewear",
]

# ============================================

STATE_FILE = "page_state.json"
FOUND_FILE = "pending_alerts.json"
page_hashes = {}
pending_alerts = {}

def load_state():
    global page_hashes, pending_alerts
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                page_hashes = json.load(f)
    except:
        page_hashes = {}
    try:
        if os.path.exists(FOUND_FILE):
            with open(FOUND_FILE, 'r') as f:
                pending_alerts = json.load(f)
    except:
        pending_alerts = {}

def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(page_hashes, f)
    except:
        pass

def save_pending():
    try:
        with open(FOUND_FILE, 'w') as f:
            json.dump(pending_alerts, f)
    except:
        pass

def send_notification(title, message, url=""):
    try:
        data = {
            "token": PUSHOVER_TOKEN,
            "user": PUSHOVER_USER,
            "title": title,
            "message": message,
            "url": url,
            "priority": PUSHOVER_PRIORITY,
            "sound": "persistent"
        }
        if PUSHOVER_PRIORITY == 2:
            data["retry"] = REPEAT_INTERVAL
            data["expire"] = REPEAT_INTERVAL * MAX_REPEATS
        
        response = requests.post("https://api.pushover.net/1/messages.json", data=data)
        if response.status_code == 200:
            print(f"✅ Notification sent: {title}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except:
        return False

def get_page_content(driver, url):
    try:
        driver.get(url)
        time.sleep(2)
        
        content_parts = []
        
        # Get all product links
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if text and len(text) > 2:
                    content_parts.append(f"{text}|{href}")
            except:
                pass
        
        # Get prices
        try:
            prices = driver.find_elements(By.CSS_SELECTOR, "[class*='price'], [class*='Price'], .money")
            for p in prices:
                text = p.text.strip()
                if text:
                    content_parts.append(text)
        except:
            pass
        
        combined = "|".join(sorted(content_parts))
        return hashlib.md5(combined.encode()).hexdigest()
    except:
        return None

def check_page():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)')
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(10)
    
    try:
        for url in PAGES_TO_WATCH:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            current_hash = get_page_content(driver, url)
            if current_hash is None:
                continue
            
            previous_hash = page_hashes.get(url)
            
            if previous_hash is None:
                page_hashes[url] = current_hash
                save_state()
                
                driver.get(url)
                time.sleep(1)
                links = driver.find_elements(By.TAG_NAME, "a")
                product_count = sum(1 for l in links if "product" in (l.get_attribute("href") or "").lower())
                print(f"[{timestamp}] 📌 Tracking sale page ({product_count} products)")
                
            elif current_hash != previous_hash:
                page_hashes[url] = current_hash
                save_state()
                
                driver.get(url)
                time.sleep(1)
                links = driver.find_elements(By.TAG_NAME, "a")
                
                product_links = []
                district_links = []
                
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        if "product" in href.lower() and text:
                            product_links.append({"name": text, "url": href})
                            
                            # Check for District Vision
                            for keyword in WANTED_KEYWORDS:
                                if keyword.lower() in (text + href).lower():
                                    district_links.append({"name": text, "url": href})
                                    break
                    except:
                        pass
                
                change_id = f"{url}_{current_hash}"
                
                if change_id not in pending_alerts:
                    pending_alerts[change_id] = {
                        "page": "💰 Sale - Latest",
                        "url": url,
                        "products": product_links[:10],
                        "time": timestamp,
                        "repeats": 0
                    }
                    save_pending()
                    
                    if district_links:
                        product_list = "\n".join([f"• {p['name'][:60]}" for p in district_links[:5]])
                        message = f"🚨 DISTRICT VISION IN SALE!\n\n{product_list}"
                        title = "🚨 DISTRICT VISION SALE!"
                    else:
                        new_count = len(product_links)
                        message = f"💰 {new_count} products in sale\n\nNewest items added!"
                        title = f"💰 Sale Updated - {new_count} items"
                    
                    print(f"[{timestamp}] 🚨 SALE PAGE CHANGED!")
                    send_notification(title, message, url)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

def send_repeat_alerts():
    for change_id, info in list(pending_alerts.items()):
        repeats = info.get("repeats", 0)
        
        if repeats < MAX_REPEATS:
            pending_alerts[change_id]["repeats"] = repeats + 1
            save_pending()
            
            send_notification(
                f"⏰ Reminder {repeats + 1}/{MAX_REPEATS}",
                f"💰 Sale page was updated!\n\nTap to view latest items",
                info['url']
            )
        else:
            del pending_alerts[change_id]
            save_pending()

def monitor():
    load_state()
    
    print("=" * 50)
    print("💰 HIP STORE SALE MONITOR")
    print("=" * 50)
    print(f"⏱️  Every {CHECK_FREQUENCY}s")
    print(f"📍 https://m.thehipstore.co.uk/sale/?sort=latest")
    print("=" * 50)
    
    send_notification("💰 Sale Monitor Active", "Watching sale page (latest first)", "")
    
    last_repeat = time.time()
    
    while True:
        try:
            check_page()
            
            if time.time() - last_repeat >= REPEAT_INTERVAL:
                send_repeat_alerts()
                last_repeat = time.time()
            
            time.sleep(CHECK_FREQUENCY)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

@app.route('/')
def dashboard():
    alerts_html = ""
    if pending_alerts:
        for change_id, info in pending_alerts.items():
            products = info.get("products", [])
            product_list = "<br>".join([f"• {p['name'][:60]}" for p in products[:5]])
            alerts_html += f"""
            <li style="background:#330000;padding:10px;border-radius:8px;margin:5px 0;">
                🚨 {info['page']}<br>
                <small>{product_list}</small><br>
                <small>Repeats: {info.get('repeats', 0)}/{MAX_REPEATS}</small><br>
                <a href="{info['url']}" style="color:#ff4444;">View sale →</a>
            </li>"""
    else:
        alerts_html = "<li>No pending alerts</li>"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="5">
    <title>Sale Monitor</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, sans-serif; padding: 20px; background: #000; color: #fff; }}
        h1 {{ font-size: 22px; }}
        .status {{ color: #00ff00; font-size: 16px; }}
        .card {{ background: #1a1a1a; padding: 18px; border-radius: 12px; margin: 12px 0; }}
        .card h3 {{ color: #888; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }}
        .warning {{ color: #ff4444; }}
        ul {{ list-style: none; }}
        li {{ padding: 4px 0; font-size: 14px; }}
    </style>
    </head>
    <body>
    <h1>💰 Sale Monitor</h1>
    <p class="status">● Checking every {CHECK_FREQUENCY}s</p>
    
    <div class="card">
    <h3>Watching</h3>
    <p>📍 Sale page (sorted by latest)</p>
    <p>🔍 District Vision keywords active</p>
    </div>
    
    <div class="card">
    <h3>Alerts ({len(pending_alerts)})</h3>
    <ul>{alerts_html}</ul>
    </div>
    
    <p style="color: #666; margin-top: 15px;">Last check: {datetime.now().strftime('%H:%M:%S')}</p>
    </body>
    </html>
    """

@app.route('/acknowledge')
def acknowledge():
    global pending_alerts
    count = len(pending_alerts)
    pending_alerts = {}
    save_pending()
    return f"✅ Stopped {count} alerts"

@app.route('/reset')
def reset():
    global page_hashes, pending_alerts
    page_hashes = {}
    pending_alerts = {}
    save_state()
    save_pending()
    return "✅ Reset complete"

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
