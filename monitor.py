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

# SPEED SETTINGS
CHECK_FREQUENCY = 30        # Check every 30 seconds

# ALERT SETTINGS
REPEAT_INTERVAL = 30       # Repeat every 30 seconds
MAX_REPEATS = 100          # Keep going for nearly an hour
PUSHOVER_PRIORITY = 2      # Emergency bypass

# ============================================
# PAGES TO MONITOR - SALE PAGE FIRST!
# ============================================

PAGES_TO_WATCH = [
    # Sale page sorted by latest - catches new drops FIRST
    "https://m.thehipstore.co.uk/sale/?sort=latest",
    
    # District Vision specific
    "https://m.thehipstore.co.uk/mens/brand/district-vision/",
    
    # New arrivals
    "https://m.thehipstore.co.uk/mens/new-arrivals/",
]

# Keywords that trigger instant alert
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
    "sale",
    "discount",
]

# ============================================
# DON'T EDIT BELOW
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
            print(f"❌ Notification failed: {response.text}")
            return False
    except Exception as e:
        print(f"Notification error: {e}")
        return False

def get_page_content(driver, url):
    """Get all product-related content from a page"""
    try:
        driver.get(url)
        time.sleep(1.5)
        
        content_parts = []
        
        # Get all links with text
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if text and len(text) > 2:
                    content_parts.append(f"{text}|{href}")
            except:
                pass
        
        # Get all images
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            try:
                src = img.get_attribute("src") or ""
                alt = img.get_attribute("alt") or ""
                if src:
                    content_parts.append(f"{alt}|{src}")
            except:
                pass
        
        # Get prices
        try:
            prices = driver.find_elements(By.CSS_SELECTOR, "[class*='price'], [class*='Price'], .money, .was, .now")
            for p in prices:
                text = p.text.strip()
                if text:
                    content_parts.append(text)
        except:
            pass
        
        # Create hash
        combined = "|".join(sorted(content_parts))
        return hashlib.md5(combined.encode()).hexdigest()
    except:
        return None

def check_all_pages():
    """Ultra-fast page checking"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-images')
    options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)')
    options.add_argument('--window-size=390,844')
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(8)
    driver.implicitly_wait(0.5)
    
    changes_found = []
    
    try:
        for url in PAGES_TO_WATCH:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            current_hash = get_page_content(driver, url)
            
            if current_hash is None:
                continue
            
            previous_hash = page_hashes.get(url)
            page_name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
            page_name = page_name.replace("-", " ").title()
            
            # Special label for sale page
            if "sale" in url.lower():
                page_name = "💰 SALE - Latest"
            
            if previous_hash is None:
                page_hashes[url] = current_hash
                save_state()
                
                driver.get(url)
                time.sleep(1)
                links = driver.find_elements(By.TAG_NAME, "a")
                product_count = sum(1 for l in links if "product" in (l.get_attribute("href") or "").lower())
                print(f"[{timestamp}] 📌 Tracking: {page_name} ({product_count} products)")
                
            elif current_hash != previous_hash:
                # CHANGE DETECTED!
                page_hashes[url] = current_hash
                save_state()
                
                driver.get(url)
                time.sleep(1)
                links = driver.find_elements(By.TAG_NAME, "a")
                
                product_links = []
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        text = link.text.strip()
                        if "product" in href.lower() and text:
                            product_links.append({"name": text, "url": href})
                    except:
                        pass
                
                change_id = f"{url}_{current_hash}"
                
                if change_id not in pending_alerts:
                    pending_alerts[change_id] = {
                        "page": page_name,
                        "url": url,
                        "products": product_links[:10],  # Show more products for sale page
                        "time": timestamp,
                        "repeats": 0
                    }
                    save_pending()
                    
                    # Check for wanted keywords
                    found_wanted = []
                    for p in product_links:
                        for keyword in WANTED_KEYWORDS:
                            if keyword.lower() in (p["name"] + p["url"]).lower():
                                if p["name"] not in found_wanted:
                                    found_wanted.append(p["name"])
                                break
                    
                    # Build notification
                    if found_wanted:
                        product_list = "\n".join([f"• {n[:60]}" for n in found_wanted[:5]])
                        message = f"🔥 {page_name}\n\n{product_list}"
                        if len(found_wanted) > 5:
                            message += f"\n+ {len(found_wanted) - 5} more"
                        title = "🚨 WANTED ITEM DETECTED!"
                    else:
                        product_list = "\n".join([f"• {p['name'][:60]}" for p in product_links[:5]])
                        message = f"📄 {page_name} Updated\n\n{product_list}"
                        if len(product_links) > 5:
                            message += f"\n+ {len(product_links) - 5} more products"
                        title = "🆕 New Items Added!"
                    
                    print(f"[{timestamp}] 🚨 CHANGE: {page_name} - {len(product_links)} products")
                    
                    send_notification(title, message, url)
                    changes_found.append({"page": page_name, "url": url, "products": product_links})
        
        return changes_found
        
    except Exception as e:
        print(f"Error: {e}")
        return []
    finally:
        driver.quit()

def send_repeat_alerts():
    """Keep alerting until acknowledged"""
    for change_id, info in list(pending_alerts.items()):
        repeats = info.get("repeats", 0)
        
        if repeats < MAX_REPEATS:
            pending_alerts[change_id]["repeats"] = repeats + 1
            save_pending()
            
            products = info.get("products", [])
            product_list = "\n".join([f"• {p['name'][:60]}" for p in products[:5]])
            
            send_notification(
                f"⏰ REMINDER {repeats + 1}/{MAX_REPEATS}",
                f"{info['page']}\n\n{product_list}\n\nTAP TO BUY!",
                info['url']
            )
        else:
            del pending_alerts[change_id]
            save_pending()

def monitor():
    """Main monitoring loop"""
    load_state()
    
    print("=" * 60)
    print("💰 HIP STORE - SALE + DISTRICT VISION MONITOR")
    print("=" * 60)
    print(f"⏱️  Checking every {CHECK_FREQUENCY} seconds")
    print(f"📄 Monitoring {len(PAGES_TO_WATCH)} pages:")
    for url in PAGES_TO_WATCH:
        name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        print(f"   📍 {name.replace('-', ' ').title()}")
    print(f"🔁 Alerts repeat every {REPEAT_INTERVAL}s ({MAX_REPEATS}x)")
    print("=" * 60)
    
    send_notification("💰 Monitor Active", "Watching sale page + District Vision", "")
    
    last_repeat = time.time()
    scan_count = 0
    
    while True:
        try:
            scan_count += 1
            changes = check_all_pages()
            
            if changes:
                print(f"🚨 {len(changes)} page(s) changed!")
                for change in changes:
                    print(f"   📄 {change['page']}: {len(change['products'])} products")
            
            if time.time() - last_repeat >= REPEAT_INTERVAL:
                send_repeat_alerts()
                last_repeat = time.time()
            
            if scan_count % 12 == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Scans: {scan_count} | Pending: {len(pending_alerts)}")
            
            time.sleep(CHECK_FREQUENCY)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

@app.route('/')
def dashboard():
    pages_html = ""
    for url in PAGES_TO_WATCH:
        name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        name = name.replace("-", " ").title()
        if "sale" in url.lower():
            name = "💰 " + name + " (Latest)"
        icon = "✅" if url in page_hashes else "🆕"
        pages_html += f"<li>{icon} {name}</li>"
    
    alerts_html = ""
    if pending_alerts:
        for change_id, info in pending_alerts.items():
            products = info.get("products", [])
            product_list = "<br>".join([f"• {p['name'][:60]}" for p in products[:5]])
            alerts_html += f"""
            <li style="background:#330000;padding:10px;border-radius:8px;margin:5px 0;">
                🚨 <strong>{info['page']}</strong><br>
                <small>{product_list}</small><br>
                <small>Repeats: {info.get('repeats', 0)}/{MAX_REPEATS}</small><br>
                <a href="{info['url']}" style="color:#ff4444;">View page →</a>
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
    <h1>💰 Hip Store Monitor</h1>
    <p class="status">● Checking every {CHECK_FREQUENCY}s</p>
    
    <div class="card">
    <h3>Mode</h3>
    <p class="warning">🔥 SALE PAGE + DISTRICT VISION</p>
    <p>📱 Emergency alerts (bypasses silent)</p>
    <p>🔁 Repeats every {REPEAT_INTERVAL}s</p>
    </div>
    
    <div class="card">
    <h3>Pages Watching</h3>
    <ul>{pages_html}</ul>
    </div>
    
    <div class="card">
    <h3>Pending Alerts</h3>
    <p class="warning">{len(pending_alerts)} active</p>
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
