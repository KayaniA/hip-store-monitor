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

PUSHOVER_USER = "YOUR_USER_KEY"
PUSHOVER_TOKEN = "YOUR_APP_TOKEN"

# How often to check (seconds)
CHECK_FREQUENCY = 30  # 30 seconds for whole-site monitoring

# Notification repeat settings
NOTIFICATION_REPEAT = True
REPEAT_INTERVAL = 120
MAX_REPEATS = 10
PUSHOVER_PRIORITY = 2

# ============================================
# PAGES TO MONITOR FOR ANY CHANGES
# ============================================

PAGES_TO_WATCH = [
    # Main District Vision page
    "https://m.thehipstore.co.uk/mens/brand/district-vision/",
    
    # New Arrivals (often updated first)
    "https://m.thehipstore.co.uk/mens/new-arrivals/",
    
    # All mens brands
    "https://m.thehipstore.co.uk/mens/",
    
    # Add any other pages you want:
    # "https://m.thehipstore.co.uk/mens/brand/nike/",
    "https://m.thehipstore.co.uk/sale/",
]

# ============================================
# DON'T EDIT BELOW
# ============================================

STATE_FILE = "page_state.json"
FOUND_FILE = "pending_alerts.json"
page_hashes = {}  # Stores hash of each page
pending_alerts = {}

def load_state():
    global page_hashes, pending_alerts
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                page_hashes = json.load(f)
            print(f"Loaded state for {len(page_hashes)} pages")
    except:
        page_hashes = {}
    
    try:
        if os.path.exists(FOUND_FILE):
            with open(FOUND_FILE, 'r') as f:
                pending_alerts = json.load(f)
            print(f"Loaded {len(pending_alerts)} pending alerts")
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

def send_notification(title, message, url="", priority=None):
    if priority is None:
        priority = PUSHOVER_PRIORITY
    
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
    
    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data=data)
        if response.status_code == 200:
            print(f"✅ Notification sent: {title}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def get_page_hash(driver, url):
    """Get a hash of the page content to detect ANY changes"""
    try:
        driver.get(url)
        time.sleep(3)
        
        # Get all product-related content
        content_parts = []
        
        # Get page title
        content_parts.append(driver.title)
        
        # Get all product links and text
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if text and ("product" in href.lower() or "brand" in href.lower()):
                    content_parts.append(f"{text}|{href}")
            except:
                pass
        
        # Get all product images
        images = driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            try:
                src = img.get_attribute("src") or ""
                alt = img.get_attribute("alt") or ""
                if src and ("product" in src.lower() or "brand" in src.lower()):
                    content_parts.append(f"{alt}|{src}")
            except:
                pass
        
        # Get all product prices
        try:
            price_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='price'], [class*='Price']")
            for el in price_elements:
                content_parts.append(el.text.strip())
        except:
            pass
        
        # Create hash of all content
        combined = "|".join(sorted(content_parts))
        return hashlib.md5(combined.encode()).hexdigest()
        
    except Exception as e:
        print(f"Hash error for {url}: {e}")
        return None

def check_all_pages():
    """Check all pages for any changes"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15')
    
    driver = webdriver.Chrome(options=options)
    changes_found = []
    
    try:
        for url in PAGES_TO_WATCH:
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # Get current page hash
            current_hash = get_page_hash(driver, url)
            
            if current_hash is None:
                print(f"[{timestamp}] ❌ Failed: {url}")
                continue
            
            # Get previous hash
            previous_hash = page_hashes.get(url)
            
            if previous_hash is None:
                # First time seeing this page
                page_hashes[url] = current_hash
                save_state()
                
                # Count products for initial baseline
                links = driver.find_elements(By.TAG_NAME, "a")
                product_count = sum(1 for l in links if "product" in (l.get_attribute("href") or "").lower())
                
                print(f"[{timestamp}] 📌 New page tracked: {url}")
                print(f"   Products found: {product_count}")
                
            elif current_hash != previous_hash:
                # CHANGE DETECTED!
                page_hashes[url] = current_hash
                save_state()
                
                # Extract what's on the page now
                driver.get(url)
                time.sleep(2)
                links = driver.find_elements(By.TAG_NAME, "a")
                
                product_links = []
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.text.strip()
                    if "product" in href.lower() and text:
                        product_links.append({"name": text, "url": href})
                
                page_name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
                page_name = page_name.replace("-", " ").title()
                
                change_id = f"{url}_{current_hash}"
                
                if change_id not in pending_alerts:
                    pending_alerts[change_id] = {
                        "page": page_name,
                        "url": url,
                        "products": product_links[:5],  # First 5 products
                        "time": timestamp,
                        "repeats": 0
                    }
                    save_pending()
                    
                    changes_found.append({"page": page_name, "url": url, "products": product_links[:5]})
                    
                    # Build notification message
                    if product_links:
                        product_list = "\n".join([f"• {p['name'][:50]}" for p in product_links[:3]])
                        message = f"📄 {page_name}\n\nNew products:\n{product_list}"
                        if len(product_links) > 3:
                            message += f"\n+ {len(product_links) - 3} more"
                    else:
                        message = f"📄 {page_name}\n\nPage updated - check now!"
                    
                    print(f"[{timestamp}] 🚨 CHANGE DETECTED: {page_name}")
                    print(f"   Products now visible: {len(product_links)}")
                    
                    send_notification(
                        f"🚨 HIP STORE UPDATE!",
                        message,
                        url,
                        priority=2
                    )
            else:
                print(f"[{timestamp}] ✓ No change: {url.split('/')[-2]}")
        
        return changes_found
        
    except Exception as e:
        print(f"Error: {e}")
        return []
    finally:
        driver.quit()

def send_repeat_alerts():
    """Re-send alerts for pending changes"""
    if not NOTIFICATION_REPEAT:
        return
    
    for change_id, info in list(pending_alerts.items()):
        repeats = info.get("repeats", 0)
        
        if repeats < MAX_REPEATS:
            pending_alerts[change_id]["repeats"] = repeats + 1
            save_pending()
            
            product_list = "\n".join([f"• {p['name'][:50]}" for p in info.get("products", [])[:3]])
            message = f"⏰ REMINDER {repeats + 1}/{MAX_REPEATS}\n\n{info['page']} was updated!\n\n{product_list}"
            
            send_notification(
                f"⏰ Still Available!",
                message,
                info['url'],
                priority=2
            )
        else:
            del pending_alerts[change_id]
            save_pending()

def monitor():
    """Main monitoring loop"""
    load_state()
    
    print("=" * 60)
    print("🔍 HIP STORE - FULL SITE CHANGE MONITOR")
    print("=" * 60)
    print(f"📄 Watching {len(PAGES_TO_WATCH)} pages for ANY changes")
    print(f"⏱️  Checking every {CHECK_FREQUENCY} seconds")
    print(f"🔁 Alerts repeat every {REPEAT_INTERVAL}s ({MAX_REPEATS}x max)")
    print("=" * 60)
    for url in PAGES_TO_WATCH:
        print(f"📍 {url}")
    print("=" * 60)
    
    # Send startup notification
    send_notification(
        "✅ Monitor Active",
        f"Watching {len(PAGES_TO_WATCH)} Hip Store pages for changes",
        priority=1
    )
    
    last_repeat = time.time()
    
    while True:
        try:
            changes = check_all_pages()
            
            if changes:
                print(f"\n🚨 {len(changes)} page(s) changed!")
                for change in changes:
                    print(f"   📄 {change['page']}: {len(change['products'])} products")
            
            # Send repeats
            if time.time() - last_repeat >= REPEAT_INTERVAL:
                send_repeat_alerts()
                last_repeat = time.time()
            
            time.sleep(CHECK_FREQUENCY)
            
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(60)

@app.route('/')
def dashboard():
    pages_html = ""
    for url in PAGES_TO_WATCH:
        name = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        name = name.replace("-", " ").title()
        status = "✅ Tracked" if url in page_hashes else "🆕 New"
        pages_html += f"<li>{status} {name}</li>"
    
    alerts_html = ""
    if pending_alerts:
        for change_id, info in pending_alerts.items():
            products = info.get("products", [])
            product_list = "<br>".join([f"• {p['name'][:60]}" for p in products[:3]])
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
    <meta http-equiv="refresh" content="{CHECK_FREQUENCY}">
    <title>Hip Store Monitor</title>
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
    <h1>🔍 Hip Store Monitor</h1>
    <p class="status">● Active - Every {CHECK_FREQUENCY}s</p>
    
    <div class="card">
    <h3>📄 Pages Watched ({len(PAGES_TO_WATCH)})</h3>
    <ul>{pages_html}</ul>
    </div>
    
    <div class="card">
    <h3>🚨 Recent Changes ({len(pending_alerts)})</h3>
    <ul>{alerts_html}</ul>
    </div>
    
    <div class="card">
    <h3>Detection Method</h3>
    <p>🔍 Monitors product listings, prices, images</p>
    <p>⚡ Alerts on ANY page change</p>
    <p>🔁 Repeats until acknowledged</p>
    </div>
    
    <p class="info">Last check: {datetime.now().strftime('%H:%M:%S')}<br>All times UTC</p>
    </body>
    </html>
    """

@app.route('/acknowledge')
def acknowledge():
    global pending_alerts
    count = len(pending_alerts)
    pending_alerts = {}
    save_pending()
    return f"✅ Stopped alerts for {count} change(s)"

@app.route('/reset')
def reset():
    global page_hashes, pending_alerts
    page_hashes = {}
    pending_alerts = {}
    save_state()
    save_pending()
    return "✅ Reset complete. Next scan will establish new baseline."

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
