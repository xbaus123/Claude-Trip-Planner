import asyncio
import json
import argparse
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from browser_engine import StealthBrowser

async def scrape_hotels(dest, checkin, checkout):
    print(f"🏨 Searching hotels: {dest} ({checkin} - {checkout})")
    
    url = f"https://www.kayak.com/hotels/{dest}/{checkin}/{checkout}/2adults?sort=rank_a"
    engine = StealthBrowser(headless=True)
    
    async with async_playwright() as p:
        await engine.start(p)
        print(f"Loading {url} (this takes 10-15 seconds)...")
        
        page = await engine.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            await page.wait_for_selector("div[class*='result'], div[class*='price']", timeout=25000)
            await page.wait_for_timeout(3000)
            html = await page.content()
            
        except Exception as e:
            print(f"\n⚠️ Timeout or blocking encountered: {e}")
            print("📸 Saving debug_hotels.png and debug_hotels.html...")
            await page.screenshot(path="debug_hotels.png", full_page=True)
            with open("debug_hotels.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            await engine.close()
            return []
            
        await engine.close()

    soup = BeautifulSoup(html, 'html.parser')
    hotel_results = soup.select("div[class*='hotel-card'], div[class*='resultWrapper'], div.yuAt")
    
    top_hotels = []
    
    for idx, hotel in enumerate(hotel_results[:5]):
        try:
            # 1. Extract and Clean Hotel Name
            name_element = hotel.select_one("div[class*='name'], h3, .FLMq-title")
            name = name_element.text.strip() if name_element else "Unknown Hotel"
            name = name.replace("Compare stays once the results have fully loaded.", "").strip()
            
            # 2. Extract and Clean Price
            price_element = hotel.select_one("div[class*='price']")
            price_text = price_element.text.strip() if price_element else ""
            price_match = re.search(r'\$[0-9,]+', price_text)
            price = price_match.group(0) if price_match else "Unknown"
            
            # 3. Extract Rating
            rating_element = hotel.select_one("div[class*='score'], div[class*='rating']")
            rating_text = rating_element.text.strip() if rating_element else ""
            rating_match = re.search(r'[0-9]\.[0-9]', rating_text)
            rating = rating_match.group(0) if rating_match else "Unrated"
            
            if price != "Unknown" and name != "Unknown Hotel":
                top_hotels.append({
                    "rank": len(top_hotels) + 1,
                    "name": name,
                    "price_per_night": price,
                    "rating": rating,
                    "booking_link": url
                })
                
        except Exception:
            continue
            
    return top_hotels

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape hotel deals.")
    parser.add_argument("--dest", required=True, help="Destination IATA or City (e.g., MCO, Orlando)")
    parser.add_argument("--checkin", required=True, help="YYYY-MM-DD")
    parser.add_argument("--checkout", required=True, help="YYYY-MM-DD")
    
    args = parser.parse_args()
    
    results = asyncio.run(scrape_hotels(args.dest, args.checkin, args.checkout))
    
    print("\n--- TOP HOTELS FOUND ---")
    print(json.dumps(results, indent=2))
    import os
    os.makedirs("cache", exist_ok=True)
    with open("cache/flights.json" if "flight" in __file__ else "cache/hotels.json", "w") as f:
        json.dump(results, f, indent=2)