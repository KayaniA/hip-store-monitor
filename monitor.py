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
# PAGES TO MONITOR
# ============================================

PAGES_TO_WATCH = [
    "https://m.thehipstore.co.uk/sale/?sort=Recommended",
    "https://m.thehipstore.co.uk/sale/?sort=latest",
    "https://m.thehipstore.co.uk/mens/brand/district-vision/",
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
SEEN_FILE = "seen_products.json"
FOUND_FILE = "pending_alerts.json"
page_hashes = {}
seen_products = set()
pending_alerts = {}

def load_state():
    global page_hashes, seen_products, pending_alerts
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                page_hashes = json.load(f)
    except:
        page_hashes = {}
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, 'r') as f:
                seen_products = set(json.load(f))
    except:
        seen_products = set()
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

def save_seen():
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump(list(seen_products), f)
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
        
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if text and len(text) > 2:
                    content_parts.append(f"{text}|{href}")
            except:
                pass
        
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

def check_pages():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)')
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(10)
    
    new_products_found = False
    
    try:
        for url in PAGES_TO_WATCH:
            timestamp = datetime.now().strftime('%H:%M:%S')
            page_name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
            page_name = page_name.replace("-", " ").title()
            if "sale" in url.lower():
                page_name = "💰 Sale"
            if "search" in url.lower():
                page_name = "🔍 Search"
            if "district-vision" in url.lower() and "search" not in url.lower():
                page_name = "👓 District Vision"
            
            current_hash = get_page_content(driver, url)
            if current_hash is None:
                continue
            
            previous_hash = page_hashes.get(url)
            
            if previous_hash is None:
                # First time seeing this page - scan products but DON'T alert
                page_hashes[url] = current_hash
                save_state()
                
                driver.get(url)
                time.sleep(1)
                links = driver.find_elements(By.TAG_NAME, "a")
                
                # Record all existing products so we don't alert for them
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        if "product" in href.lower() and text:
                            seen_products.add(href)
                    except:
                        pass
                
                save_seen()
                product_count = sum(1 for l in links if "product" in (l.get_attribute("href") or "").lower())
                print(f"[{timestamp}] 📌 {page_name}: {product_count} existing products recorded (no alert)")
                
            elif current_hash != previous_hash:
                # Page changed - check for NEW products only
                page_hashes[url] = current_hash
                save_state()
                
                driver.get(url)
                time.sleep(1)
                links = driver.find_elements(By.TAG_NAME, "a")
                
                truly_new = []
                
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        if "product" in href.lower() and text:
                            # Only alert if we've NEVER seen this product before
                            if href not in seen_products:
                                seen_products.add(href)
                                truly_new.append({"name": text, "url": href})
                    except:
                        pass
                
                save_seen()
                
                if truly_new:
                    # Check for District Vision keywords
                    district_items = []
                    for p in truly_new:
                        for keyword in WANTED_KEYWORDS:
                            if keyword.lower() in (p["name"] + p["url"]).lower():
                                district_items.append(p)
                                break
                    
                    change_id = f"{url}_{datetime.now().timestamp()}"
                    
                    pending_alerts[change_id] = {
                        "page": page_name,
                        "url": url,
                        "products": truly_new,
                        "time": timestamp,
                        "repeats": 0
                    }
                    save_pending()
                    
                    if district_items:
                        product_list = "\n".join([f"• {p['name'][:60]}" for p in district_items[:5]])
                        message = f"🚨 NEW DISTRICT VISION!\n\n{page_name}\n{product_list}"
                        title = "🚨 NEW DISTRICT VISION!"
                    else:
                        product_list = "\n".join([f"• {p['name'][:60]}" for p in truly_new[:5]])
                        message = f"🆕 {len(truly_new)} NEW products\n\n{page_name}\n{product_list}"
                        title = f"🆕 New Products!"
                    
                    print(f"[{timestamp}] 🚨 {len(truly_new)} NEW products on {page_name}!")
                    send_notification(title, message, url)
                    new_products_found = True
                else:
                    print(f"[{timestamp}] 📄 {page_name} changed but no NEW products")
        
        return new_products_found
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        driver.quit()

def send_repeat_alerts():
    for change_id, info in list(pending_alerts.items()):
        repeats = info.get("repeats", 0)
        
        if repeats < MAX_REPEATS:
            pending_alerts[change_id]["repeats"] = repeats + 1
            save_pending()
            
            products = info.get("products", [])
            product_list = "\n".join([f"• {p['name'][:60]}" for p in products[:5]])
            
            send_notification(
                f"⏰ Reminder {repeats + 1}/{MAX_REPEATS}",
                f"{info['page']}\n\n{product_list}\n\nTAP TO BUY!",
                info['url']
            )
        else:
            del pending_alerts[change_id]
            save_pending()

def monitor():
    load_state()
    
    print("=" * 50)
    print("🆕 HIP STORE - NEW PRODUCTS ONLY")
    print("=" * 50)
    print(f"⏱️  Every {CHECK_FREQUENCY}s")
    print(f"📄 {len(PAGES_TO_WATCH)} pages")
    print(f"💾 {len(seen_products)} existing products recorded")
    print(f"🔔 Only alerts for TRULY NEW products")
    print("=" * 50)
    
    send_notification("🆕 Monitor Active", f"Tracking new products only\n{len(seen_products)} existing products recorded", "")
    
    last_repeat = time.time()
    
    while True:
        try:
            check_pages()
            
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
                <a href="{info['url']}" style="color:#ff4444;">View page →</a>
            </li>"""
    else:
        alerts_html = "<li>No pending alerts</li>"
    
    pages_html = ""
    for url in PAGES_TO_WATCH:
        name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        name = name.replace("-", " ").title()
        if "sale" in url.lower():
            name = "💰 Sale"
        if "search" in url.lower():
            name = "🔍 Search"
        if "district-vision" in url.lower() and "search" not in url.lower():
            name = "👓 District Vision"
        pages_html += f"<li>📍 {name}</li>"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="5">
    <title>Hip Store Monitor</title>
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
    <h1>🆕 New Products Only</h1>
    <p class="status">● Checking every {CHECK_FREQUENCY}s</p>
    
    <div class="card">
    <h3>Watching ({len(PAGES_TO_WATCH)} pages)</h3>
    <ul>{pages_html}</ul>
    </div>
    
    <div class="card">
    <h3>Existing Products Recorded</h3>
    <p class="warning">{len(seen_products)} products</p>
    <p style="font-size:12px;color:#888;">Only NEW products will trigger alerts</p>
    </div>
    
    <div class="card">
    <h3>Pending Alerts ({len(pending_alerts)})</h3>
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
    global page_hashes, seen_products, pending_alerts
    page_hashes = {}
    seen_products = set()
    pending_alerts = {}
    save_state()
    save_seen()
    save_pending()
    return "✅ Full reset complete. All products treated as new on next scan."

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
