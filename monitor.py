from flask import Flask
import threading
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime

app = Flask(__name__)

# ============================================
# ONLY THESE 2 THINGS TO SET UP
# ============================================

# 1. Get these from pushover.net (free trial, then $5 one-time)
PUSHOVER_USER = "uv4ar371e2hh22m23ozycabbp71mbe"
PUSHOVER_TOKEN = "ai2ub9o9ey9jaj4hfozp6vtgom167z"

# 2. The products you want
WANTED = [
    "nagata",
    "keiichi", 
    "junya"
]

# ============================================

PAGE_URL = "https://m.thehipstore.co.uk/mens/brand/district-vision/"
found_cache = set()
cart_added = False

def send_notification(title, message, url=""):
    """Send alert to your iPhone"""
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PUSHOVER_TOKEN,
            "user": PUSHOVER_USER,
            "title": title,
            "message": message,
            "url": url,
            "priority": 2,
            "retry": 30,
            "expire": 300,
            "sound": "persistent"
        })
        print(f"✅ Notification sent: {title}")
    except Exception as e:
        print(f"Notification error: {e}")

def check_and_buy():
    """Check the page and auto-buy if found"""
    global cart_added
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking...")
        driver.get(PAGE_URL)
        time.sleep(3)
        
        # Find all links
        links = driver.find_elements(By.TAG_NAME, "a")
        
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip().lower()
                combined = (text + " " + href).lower()
                
                for keyword in WANTED:
                    if keyword in combined and "product" in href.lower():
                        
                        if href not in found_cache:
                            found_cache.add(href)
                            product_name = link.text.strip() or "District Vision Product"
                            
                            print(f"🎯 FOUND: {product_name}")
                            print(f"   URL: {href}")
                            
                            # Go to product page
                            driver.get(href)
                            time.sleep(2)
                            
                            # Look for add to cart button
                            page_text = driver.page_source.lower()
                            
                            if "add to basket" in page_text or "add to cart" in page_text:
                                print("   ✅ IN STOCK!")
                                
                                # Click add to cart
                                for btn_text in ["Add to Basket", "Add to Cart", "Add to Bag"]:
                                    try:
                                        btn = driver.find_element(By.XPATH, f"//*[contains(text(), '{btn_text}')]")
                                        btn.click()
                                        print(f"   🛒 Added to cart!")
                                        cart_added = True
                                        time.sleep(2)
                                        break
                                    except:
                                        continue
                                
                                if cart_added:
                                    # Go to checkout
                                    driver.get("https://m.thehipstore.co.uk/basket/")
                                    time.sleep(2)
                                    
                                    try:
                                        checkout_btn = driver.find_element(By.XPATH, "//a[contains(@href, 'checkout')]")
                                        checkout_url = checkout_btn.get_attribute("href")
                                        driver.get(checkout_url)
                                        time.sleep(2)
                                        final_url = driver.current_url
                                        
                                        send_notification(
                                            "🚨 READY TO BUY!",
                                            f"{product_name}\nIn cart & checkout ready!\n\nTAP HERE TO PAY NOW",
                                            final_url
                                        )
                                        
                                        print("   🎉 CHECKOUT READY - Notification sent!")
                                        return True
                                    except:
                                        send_notification(
                                            "🛒 IN CART!",
                                            f"{product_name}\nAdded to basket!\n\nTAP HERE TO CHECKOUT",
                                            "https://m.thehipstore.co.uk/basket/"
                                        )
                                        return True
                            else:
                                print("   ❌ Out of stock")
            except:
                continue
        
        print("   No new products found")
        return False
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        driver.quit()

def monitor():
    """Main loop - checks continuously"""
    print("=" * 50)
    print("🤖 HIP STORE AUTO-BUY BOT")
    print("=" * 50)
    print(f"📱 Monitoring: District Vision")
    print(f"🔍 Products: {', '.join(WANTED)}")
    print(f"⚡ Speed: Every 10 seconds")
    print("=" * 50)
    
    # Send startup notification
    send_notification("✅ Monitor Started", "Now watching for District Vision products")
    
    while True:
        try:
            check_and_buy()
            
            if cart_added:
                print("⏸️  Item found! Pausing for 5 minutes...")
                time.sleep(300)
                cart_added = False
            else:
                time.sleep(10)
                
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
    <meta http-equiv="refresh" content="10">
    <title>Auto-Buy Monitor</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 20px; background: #000; color: #fff; }}
        h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .status {{ color: #00ff00; font-weight: bold; font-size: 18px; margin-bottom: 20px; }}
        .card {{ background: #1a1a1a; padding: 20px; border-radius: 12px; margin-bottom: 15px; }}
        .card h3 {{ margin-bottom: 10px; color: #888; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
        .found {{ color: #ff4444; font-size: 28px; font-weight: bold; }}
        ul {{ list-style: none; }}
        li {{ padding: 8px 0; font-size: 18px; }}
        .time {{ color: #666; font-size: 13px; margin-top: 20px; }}
    </style>
    </head>
    <body>
    <h1>🤖 District Vision Bot</h1>
    <p class="status">● ACTIVE - Checking every 10 seconds</p>
    
    <div class="card">
    <h3>Watching For</h3>
    <ul>
        {"".join(f"<li>🔍 {w.title()}</li>" for w in WANTED)}
    </ul>
    </div>
    
    <div class="card">
    <h3>Products Found</h3>
    <p class="found">{len(found_cache)}</p>
    </div>
    
    <div class="card">
    <h3>Cart Status</h3>
    <p style="font-size: 20px;">{"🛒 Items Ready!" if cart_added else "⏳ Waiting for stock..."}</p>
    </div>
    
    <p class="time">Last check: {datetime.now().strftime('%H:%M:%S')}</p>
    <p class="time">You'll get a push notification when products are found</p>
    </body>
    </html>
    """

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
