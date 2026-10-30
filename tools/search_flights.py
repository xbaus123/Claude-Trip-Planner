import asyncio
import json
import argparse
import os
import re
import sys
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from browser_engine import StealthBrowser
from score_deals import parse_duration
from scrape_debug import log_card_error, log_card_skipped, log_no_cards, log_parse_summary

# Matches the "6:00 am – 3:37 pm +1" header that starts each leg on a result card
LEG_TIMES_RE = re.compile(r'(\d{1,2}:\d{2}\s*[ap]m)\s*[–-]\s*(\d{1,2}:\d{2}\s*[ap]m)(\s*\+\d)?')
LAYOVER_RE = re.compile(r'((?:\d{1,2}h\s*)?\d{1,2}m)\s*layover')
# Skip layover durations (e.g. "3h 38m layover") to get the leg's total duration
DURATION_RE = re.compile(r'\d{1,2}h\s*\d{1,2}m(?!\s*layover)')
FARE_RE = re.compile(r'basic economy|premium economy|economy|business|first')

def to_hour(time_str):
    """Converts '9:28 pm' into a 24-hour integer hour."""
    hour = int(time_str.split(':')[0]) % 12
    return hour + 12 if 'pm' in time_str else hour

def parse_leg(segment, match):
    """Extracts times, stops, layovers, and duration from one leg of a card."""
    depart, arrive = match.group(1), match.group(2)
    overnight = bool(match.group(3))

    if "nonstop" in segment:
        stops = "Nonstop"
    else:
        stops_match = re.search(r'\d+\s*stops?', segment)
        stops = stops_match.group(0) if stops_match else "Unknown Stops"

    layover_mins = [parse_duration(l) for l in LAYOVER_RE.findall(segment)]
    duration_match = DURATION_RE.search(segment)

    return {
        "times": f"{depart} – {arrive}{' +1' if overnight else ''}".upper(),
        "overnight": overnight,
        # In the air overnight: leaves late at night or lands before dawn the next day
        "red_eye": to_hour(depart) >= 21 or to_hour(depart) < 5 or (overnight and to_hour(arrive) < 6),
        "duration": duration_match.group(0) if duration_match else "Unknown Duration",
        "stops": stops,
        "layovers": [l.strip() for l in LAYOVER_RE.findall(segment)],
        "max_layover_mins": max(layover_mins) if layover_mins else None,
    }

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
            await page.wait_for_selector("div.nrc6-wrapper", timeout=25000)
            await page.wait_for_timeout(3000)
            html = await page.content()

        except Exception as e:
            print(f"\n⚠️ Timeout or blocking encountered: {e}")
            print(f"📸 Saving debug_{origin}.png and debug_{origin}.html to your current directory...")
            await page.screenshot(path=f"debug_{origin}.png", full_page=True)
            with open(f"debug_{origin}.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            await engine.close()
            return []

        await engine.close()

    # Parse the extracted DOM
    soup = BeautifulSoup(html, 'html.parser')

    # Target individual flight cards
    card_selector = "div.nrc6-wrapper, div.inner-row, div[class*='resultWrapper']"
    flight_results = soup.select(card_selector)
    label = f"flights_{origin}"
    if not flight_results:
        log_no_cards(label, card_selector, html)
        return []

    top_deals = []

    for idx, flight in enumerate(flight_results[:5]):
        try:
            # 1. Clean the Price using Regex
            price_element = flight.select_one("div[class*='price']")
            price_text = price_element.text.strip() if price_element else ""
            price_match = re.search(r'\$[0-9,]+', price_text)
            price = price_match.group(0) if price_match else "Unknown"

            # 2. Find the Airline
            airline = "Multiple Airlines"
            img_element = flight.select_one("img[alt]")
            if img_element and img_element.get("alt"):
                airline = img_element.get("alt")
            else:
                airline_element = flight.select_one("div[class*='airline'], div[dir='auto']")
                if airline_element and airline_element.text.strip():
                    airline = airline_element.text.strip()

            # 3. Split the flattened card text into outbound and return legs
            flight_text = ' '.join(flight.stripped_strings).lower()
            leg_matches = list(LEG_TIMES_RE.finditer(flight_text))[:2]
            legs = []
            for i, match in enumerate(leg_matches):
                end = leg_matches[i + 1].start() if i + 1 < len(leg_matches) else len(flight_text)
                legs.append(parse_leg(flight_text[match.start():end], match))

            outbound = legs[0] if legs else {}
            return_leg = legs[1] if len(legs) > 1 else {}
            fare_match = FARE_RE.search(flight_text)

            if price != "Unknown":
                top_deals.append({
                    "rank": len(top_deals) + 1,
                    "origin": origin,
                    "dest": dest,
                    "depart_date": departure_date,
                    "return_date": return_date,
                    "price": price,
                    "airline": airline,
                    "fare_class": fare_match.group(0).title() if fare_match else "Unknown",
                    # Top-level fields describe the outbound leg
                    "times": outbound.get("times", "Unknown Times"),
                    "duration": outbound.get("duration", "Unknown Duration"),
                    "stops": outbound.get("stops", "Unknown Stops"),
                    "outbound": outbound,
                    "return": return_leg,
                    "booking_link": url
                })
            else:
                log_card_skipped(label, idx, flight, ["price (div[class*='price'] with a $ amount)"])

        except Exception:
            log_card_error(label, idx, flight)

    log_parse_summary(label, min(len(flight_results), 5), len(top_deals))
    return top_deals

async def main(origins, dest, departure_date, return_date):
    """Scrapes every origin concurrently and merges the results in origin order."""
    tasks = [scrape_flights(origin, dest, departure_date, return_date) for origin in origins]
    # return_exceptions keeps one failed origin from cancelling the others
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for origin, outcome in zip(origins, outcomes):
        if isinstance(outcome, Exception):
            print(f"   {origin}: search failed ({outcome})")
            continue
        print(f"   {origin}: {len(outcome)} flights found")
        results.extend(outcome)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape flight deals.")
    parser.add_argument("--origin", required=True, help="Origin IATA, or several comma-separated (e.g., CRW,HTS,PIT)")
    parser.add_argument("--dest", required=True, help="Destination IATA")
    parser.add_argument("--depart", required=True, help="YYYY-MM-DD")
    parser.add_argument("--return_date", required=True, help="YYYY-MM-DD")

    args = parser.parse_args()

    # Search all origins at once (deduplicated, order kept) and merge into one cache file
    origins = list(dict.fromkeys(o.strip().upper() for o in args.origin.split(",") if o.strip()))
    results = asyncio.run(main(origins, args.dest, args.depart, args.return_date))

    print("\n--- TOP DEALS FOUND ---")
    for f in results:
        print(f"[{f['origin']}] {f['airline']} - {f['price']} | out {f['times']} ({f['duration']}, {f['stops']})")

    os.makedirs("cache", exist_ok=True)
    with open("cache/flights.json", "w") as f:
        json.dump(results, f, indent=2)

    if not results:
        sys.exit(1)
