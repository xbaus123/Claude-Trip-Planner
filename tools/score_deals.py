import argparse
import json
import os
import re
from datetime import date

PROFILE_DEFAULTS = {
    "hotel_minimum_rating": 7.0,
    "max_layover_hours": None,
    "deal_breakers": {"red_eye_flights": False, "unrated_hotels": True},
}

def parse_duration(duration_str):
    """Converts a string like '16h 12m' into total minutes."""
    hours = 0
    minutes = 0
    h_match = re.search(r'(\d+)h', duration_str)
    m_match = re.search(r'(\d+)m', duration_str)
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    return (hours * 60) + minutes

def parse_price(price_str):
    """Converts '$1,234' into 1234.0, or None if it isn't a price."""
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except ValueError:
        return None

def load_profile(profile_path="input/traveler_profile.json"):
    """Reads the traveler profile, filling in defaults for anything missing."""
    profile = {**PROFILE_DEFAULTS, "deal_breakers": dict(PROFILE_DEFAULTS["deal_breakers"])}
    try:
        with open(profile_path, "r") as f:
            loaded = json.load(f)
    except (OSError, ValueError):
        return profile
    profile.update({k: v for k, v in loaded.items() if k != "deal_breakers"})
    profile["deal_breakers"].update(loaded.get("deal_breakers", {}))
    return profile

def score_hotels(hotels_json, profile, excluded, hotel_exponent=2.0):
    min_rating = float(profile["hotel_minimum_rating"])
    scored_hotels = []
    for hotel in hotels_json:
        price = parse_price(hotel['price_per_night'])
        if not price:
            continue

        if hotel.get('rating') in ['Unrated', '', None]:
            if profile["deal_breakers"]["unrated_hotels"]:
                excluded.append(f"{hotel['name']}: unrated")
                continue
            # Unrated is allowed, so give it the benefit of the minimum rating
            rating = min_rating
        else:
            rating = float(hotel['rating'])

        # Hard floor from the traveler profile
        if rating < min_rating:
            excluded.append(f"{hotel['name']}: rated {rating}, below the {min_rating} minimum")
            continue

        # Rating raised to a tunable power: higher exponents favor quality over price
        raw_score = (rating ** hotel_exponent) / price

        scored_hotels.append({
            **hotel,
            "numeric_price": price,
            "raw_score": raw_score
        })

    if not scored_hotels:
        return []

    # Normalize to a 0-100 scale based on the best performer
    max_score = max(h['raw_score'] for h in scored_hotels)
    for hotel in scored_hotels:
        hotel['value_score'] = round((hotel['raw_score'] / max_score) * 100, 1)

    return sorted(scored_hotels, key=lambda x: x['value_score'], reverse=True)

def flight_label(flight):
    origin = f" [{flight['origin']}]" if flight.get('origin') else ""
    out_times = flight.get('outbound', {}).get('times') or flight.get('times')
    return_times = flight.get('return', {}).get('times')
    legs = [f"out {out_times}" if out_times else "", f"return {return_times}" if return_times else ""]
    schedule = f" ({', '.join(l for l in legs if l)})" if any(legs) else ""
    return f"{flight['airline']}{origin} {flight['price']}{schedule}"

def score_flights(flights_json, profile, excluded, time_penalty_per_hour=5.0):
    max_layover_hours = profile.get("max_layover_hours")
    seen = set()
    scored_flights = []
    for flight in flights_json:
        price = parse_price(flight['price'])
        if not price:
            continue

        # Kayak often repeats the same itinerary with different fare bundles
        key = (flight.get('origin'), flight['airline'], flight['price'], flight.get('times'),
               flight.get('return', {}).get('times'))
        if key in seen:
            continue
        seen.add(key)

        legs = [leg for leg in (flight.get('outbound'), flight.get('return')) if leg]

        layovers = [leg['max_layover_mins'] for leg in legs if leg.get('max_layover_mins')]
        if max_layover_hours and layovers and max(layovers) > max_layover_hours * 60:
            longest = max(layovers)
            excluded.append(f"{flight_label(flight)}: {longest // 60}h {longest % 60:02d}m layover, over the {max_layover_hours}h limit")
            continue

        if profile["deal_breakers"]["red_eye_flights"] and any(leg.get('red_eye') for leg in legs):
            excluded.append(f"{flight_label(flight)}: red-eye")
            continue

        # Score on total time in transit for both legs when the scraper captured them
        if legs:
            duration_mins = sum(parse_duration(leg.get('duration', '')) for leg in legs)
        else:
            duration_mins = parse_duration(flight.get('duration', '0h 0m'))

        scored_flights.append({
            **flight,
            "numeric_price": price,
            "duration_mins": duration_mins
        })

    if not scored_flights:
        return []

    # The cheapest flight sets the 100-point baseline
    lowest_price = min(f['numeric_price'] for f in scored_flights)
    known_durations = [f['duration_mins'] for f in scored_flights if f['duration_mins'] > 0]
    fastest_flight = min(known_durations) if known_durations else 0

    for flight in scored_flights:
        # Base score out of 100 based strictly on price
        base_score = (lowest_price / flight['numeric_price']) * 100

        # Deduct points for every hour over the fastest available routing
        extra_hours = (flight['duration_mins'] - fastest_flight) / 60 if flight['duration_mins'] else 0
        time_penalty = max(0, extra_hours * time_penalty_per_hour)

        flight['value_score'] = round(base_score - time_penalty, 1)

    return sorted(scored_flights, key=lambda x: x['value_score'], reverse=True)

def stay_nights(hotel, flight):
    if hotel.get('nights'):
        return hotel['nights']
    if flight.get('depart_date') and flight.get('return_date'):
        return (date.fromisoformat(flight['return_date']) - date.fromisoformat(flight['depart_date'])).days
    return None

def build_combos(top_flights, top_hotels, limit=3):
    """Pairs the best flights and hotels, ranked by their average value score."""
    combos = []
    for flight in top_flights[:limit]:
        for hotel in top_hotels[:limit]:
            nights = stay_nights(hotel, flight)
            hotel_total = hotel['numeric_price'] * nights if nights else None
            combos.append({
                "flight": flight,
                "hotel": hotel,
                "nights": nights,
                "hotel_total": hotel_total,
                "estimated_total": flight['numeric_price'] + hotel_total if hotel_total else None,
                "combo_score": round((flight['value_score'] + hotel['value_score']) / 2, 1),
            })
    combos.sort(key=lambda c: (-c['combo_score'], c['estimated_total'] or 0))
    return combos[:limit]

def print_report(top_flights, top_hotels, combos, excluded, weights):
    print(f"\n⚖️  Weights: time penalty {weights['time_penalty']:g} pts/hour, "
          f"hotel rating exponent {weights['hotel_exponent']:g}")
    print("\n🧳 --- TOP COMBINATIONS ---")
    for i, c in enumerate(combos, 1):
        total = f"~${c['estimated_total']:,.0f}" if c['estimated_total'] else "total unknown"
        print(f"{i}. [{c['combo_score']}/100] {flight_label(c['flight'])} + {c['hotel']['name']} "
              f"{c['hotel']['price_per_night']}/night x {c['nights']} = {total}")

    print("\n✈️  --- TOP VALUE FLIGHTS ---")
    for f in top_flights[:3]:
        hours, mins = divmod(f['duration_mins'], 60)
        print(f"[{f['value_score']}/100] {flight_label(f)} | {f.get('stops', 'N/A')} "
              f"| {hours}h {mins:02d}m round-trip transit")

    print("\n🏨 --- TOP VALUE HOTELS ---")
    for h in top_hotels[:3]:
        print(f"[{h['value_score']}/100] {h['name']} - {h['price_per_night']} ({h['rating']}★)")

    if excluded:
        print("\n🚫 --- EXCLUDED BY PROFILE ---")
        for reason in excluded:
            print(f"- {reason}")

def main():
    parser = argparse.ArgumentParser(description="Score cached flight and hotel deals.")
    parser.add_argument("--json", action="store_true", help="Print structured results instead of the text report")
    parser.add_argument("--time-penalty", type=float, default=5.0,
                        help="Points deducted per hour over the fastest routing (default: 5)")
    parser.add_argument("--hotel-exponent", type=float, default=2.0,
                        help="Power applied to hotel ratings before dividing by price (default: 2)")
    args = parser.parse_args()
    if args.time_penalty < 0 or args.hotel_exponent < 0:
        parser.error("--time-penalty and --hotel-exponent must be non-negative")
    weights = {"time_penalty": args.time_penalty, "hotel_exponent": args.hotel_exponent}

    if not os.path.exists("cache/hotels.json") or not os.path.exists("cache/flights.json"):
        print("Error: Cache files missing. Run the flight and hotel scrapers first.")
        return

    with open("cache/hotels.json", "r") as f:
        hotels = json.load(f)
    with open("cache/flights.json", "r") as f:
        flights = json.load(f)

    profile = load_profile()
    excluded = []
    top_hotels = score_hotels(hotels, profile, excluded, args.hotel_exponent)
    top_flights = score_flights(flights, profile, excluded, args.time_penalty)
    combos = build_combos(top_flights, top_hotels)

    if args.json:
        print(json.dumps({"weights": weights, "combos": combos, "flights": top_flights,
                          "hotels": top_hotels, "excluded": excluded}, indent=2))
    else:
        print_report(top_flights, top_hotels, combos, excluded, weights)

if __name__ == "__main__":
    main()
