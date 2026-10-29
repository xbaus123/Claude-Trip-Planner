import asyncio
import json
import argparse
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from browser_engine import StealthBrowser

async def scrape_flights(origin, dest, departure_date, return_date):
    print(f"✈️  Searching flights: {origin} to {dest} ({departure_date} - {return_date})")
    
    url = f"https://www.kayak.com/flights/{origin}-{dest}/{departure_date}/{return_date}?sort=price_a"
    engine = StealthBrowser(headless=True)
    
    async with async_playwright() as p:
        await engine.start(p)
        print(f"Loading {url} (this takes 10-15 seconds)...")
        
        page = await engine.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for any generic div that looks like a result container, or the price filters
            await page.wait_for_selector("div[class*='result'], div[class*='price']", timeout=25000)
            await page.wait_for_timeout(3000)
            html = await page.content()
            
        except Exception as e:
            print(f"\n⚠️ Timeout or blocking encountered: {e}")
            print("📸 Saving debug.png and debug.html to your current directory...")
            await page.screenshot(path="debug.png", full_page=True)
            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            await engine.close()
            return []
            
        await engine.close()

    # Parse the extracted DOM
    soup = BeautifulSoup(html, 'html.parser')
    
    # Target individual flight cards
    flight_results = soup.select("div.nrc6-wrapper, div.inner-row, div[class*='resultWrapper']")
    
    top_deals = []
    
    for idx, flight in enumerate(flight_results[:5]):
        try:
            # 1. Clean the Price using Regex (extracts "$442" from "10$442Basic...")
            price_element = flight.select_one("div[class*='price']")
            price_text = price_element.text.strip() if price_element else ""
            price_match = re.search(r'\$[0-9,]+', price_text)
            price = price_match.group(0) if price_match else "Unknown"
            
            # 2. Find the Airline (Kayak often hides this in the logo's 'alt' text)
            airline = "Multiple Airlines"
            img_element = flight.select_one("img[alt]")
            if img_element and img_element.get("alt"):
                airline = img_element.get("alt")
            else:
                # Fallback to text containers
                airline_element = flight.select_one("div[class*='airline'], div[dir='auto']")
                if airline_element and airline_element.text.strip():
                    airline = airline_element.text.strip()
            
            # Prevent empty duplicates from cluttering the list
            if price != "Unknown":
                top_deals.append({
                    "rank": len(top_deals) + 1,
                    "price": price,
                    "airline": airline,
                    "booking_link": url
                })
                
        except Exception:
            continue
            
    return top_deals

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape flight deals.")
    parser.add_argument("--origin", required=True, help="Origin IATA (e.g., CRW, PIT)")
    parser.add_argument("--dest", required=True, help="Destination IATA")
    parser.add_argument("--depart", required=True, help="YYYY-MM-DD")
    parser.add_argument("--return_date", required=True, help="YYYY-MM-DD")
    
    args = parser.parse_args()
    
    results = asyncio.run(scrape_flights(args.origin, args.dest, args.depart, args.return_date))
    
    print("\n--- TOP DEALS FOUND ---")
    print(json.dumps(results, indent=2))