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

# Edit these to match what you want
WANTED_KEYWORDS = [
    "koharu",
    "takeyoshi", 
    "junya"
]

# ============================================

PAGE_URL = "https://m.thehipstore.co.uk/mens/brand/district-vision/"

# Store seen products permanently
SEEN_FILE = "seen_products.json"
seen_products = set()

def load_seen_products():
    """Load previously seen products from file"""
    global seen_products
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, 'r') as f:
                seen_products = set(json.load(f))
            print(f"Loaded {len(seen_products)} previously seen products")
    except:
        seen_products = set()

def save_seen_products():
    """Save seen products to file so we remember across restarts"""
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump(list(seen_products), f)
    except:
        pass

def send_notification(title, message, url=""):
    """Send ONE notification to your iPhone"""
    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PUSHOVER_TOKEN,
            "user": PUSHOVER_USER,
            "title": title,
            "message": message,
            "url": url,
            "priority": 1,  # High priority
            "sound": "pushover"  # Standard notification sound
        })
        if response.status_code == 200:
            print(f"✅ Notification sent: {title}")
        else:
            print(f"❌ Notification failed: {response.text}")
    except Exception as e:
        print(f"Notification error: {e}")

def check_page():
    """Check page for NEW products only"""
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
        
        # Find all links on page
        links = driver.find_elements(By.TAG_NAME, "a")
        
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                combined = (text + " " + href).lower()
                
                # Check if it matches wanted keywords AND is a product link
                for keyword in WANTED_KEYWORDS:
                    if keyword in combined and href not in seen_products:
                        
                        # Only care about actual product links
                        if "/product/" in href.lower() or "/products/" in href.lower():
                            
                            # NEW PRODUCT FOUND!
                            seen_products.add(href)
                            save_seen_products()
                            new_found += 1
                            
                            product_name = text or "District Vision Product"
                            
                            print(f"🆕 NEW PRODUCT: {product_name}")
                            print(f"   URL: {href}")
                            print(f"   Time: {timestamp}")
                            
                            # Send ONE notification
                            send_notification(
                                "🆕 New District Vision Product!",
                                f"{product_name}\n\nJust appeared on Hip Store\nTap to view",
                                href
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

def monitor():
    """Main loop"""
    load_seen_products()
    
    print("=" * 50)
    print("🆕 NEW PRODUCT MONITOR")
    print("=" * 50)
    print(f"📱 Only alerts for NEW products")
    print(f"🔍 Keywords: {', '.join(WANTED_KEYWORDS)}")
    print(f"📦 Previously seen: {len(seen_products)} products")
    print(f"⚡ Checking every 15 seconds")
    print("=" * 50)
    
    while True:
        try:
            check_page()
            time.sleep(15)
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(30)

@app.route('/')
def dashboard():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="15">
    <title>New Product Monitor</title>
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
        li {{ padding: 6px 0; font-size: 16px; }}
        .time {{ color: #666; font-size: 12px; }}
    </style>
    </head>
    <body>
    <h1>🆕 New Product Alerts</h1>
    <p class="status">● Monitoring - 15s intervals</p>
    
    <div class="card">
    <h3>Watching For New</h3>
    <ul>
        {"".join(f"<li>🔍 {k.title()}</li>" for k in WANTED_KEYWORDS)}
    </ul>
    </div>
    
    <div class="card">
    <h3>Total Products Seen</h3>
    <p class="big-number">{len(seen_products)}</p>
    <p class="time">These won't trigger alerts again</p>
    </div>
    
    <div class="card">
    <h3>Alert Mode</h3>
    <p style="font-size: 16px;">🔕 Only NEW products trigger notifications</p>
    </div>
    
    <p class="info">Last check: {datetime.now().strftime('%H:%M:%S')}<br>Page refreshes every 15 seconds</p>
    </body>
    </html>
    """

@app.route('/reset')
def reset():
    """Reset seen products (use if you want fresh alerts)"""
    global seen_products
    seen_products = set()
    save_seen_products()
    return "✅ Reset complete. All products will be treated as new."

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
