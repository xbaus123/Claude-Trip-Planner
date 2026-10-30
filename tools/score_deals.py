import json
import os
import re

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

def score_hotels(hotels_json):
    scored_hotels = []
    for hotel in hotels_json:
        price = float(hotel['price_per_night'].replace('$', '').replace(',', ''))
        
        if hotel.get('rating') in ['Unrated', '', None]:
            continue
            
        rating = float(hotel['rating'])
        
        # Hard floor for bad hotels
        if rating < 7.0:
            continue
            
        # The Squared-Rating Heuristic
        raw_score = (rating ** 2) / price
        
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

def score_flights(flights_json):
    if not flights_json:
        return []
        
    scored_flights = []
    for flight in flights_json:
        price = float(flight['price'].replace('$', '').replace(',', ''))
        duration_mins = parse_duration(flight.get('duration', '0h 0m'))
        scored_flights.append({
            **flight, 
            "numeric_price": price,
            "duration_mins": duration_mins
        })
        
    # The cheapest flight sets the 100-point baseline
    lowest_price = min(f['numeric_price'] for f in scored_flights)
    fastest_flight = min(f['duration_mins'] for f in scored_flights if f['duration_mins'] > 0)
    
    for flight in scored_flights:
        # Base score out of 100 based strictly on price
        base_score = (lowest_price / flight['numeric_price']) * 100
        
        # Deduct 5 points for every hour over the fastest available routing
        extra_hours = (flight['duration_mins'] - fastest_flight) / 60
        time_penalty = max(0, extra_hours * 5)
        
        flight['value_score'] = round(base_score - time_penalty, 1)
        
    return sorted(scored_flights, key=lambda x: x['value_score'], reverse=True)

def main():
    if not os.path.exists("cache/hotels.json") or not os.path.exists("cache/flights.json"):
        print("Error: Cache files missing. Run the flight and hotel scrapers first.")
        return

    with open("cache/hotels.json", "r") as f:
        hotels = json.load(f)
    with open("cache/flights.json", "r") as f:
        flights = json.load(f)

    top_hotels = score_hotels(hotels)
    top_flights = score_flights(flights)

    print("\n✈️  --- TOP VALUE FLIGHTS ---")
    for f in top_flights[:3]:
        duration_str = f.get('duration', 'N/A')
        print(f"[{f['value_score']}/100] {f['airline']} - {f['price']} ({duration_str})")

    print("\n🏨 --- TOP VALUE HOTELS ---")
    for h in top_hotels[:3]:
        print(f"[{h['value_score']}/100] {h['name']} - {h['price_per_night']} ({h['rating']}★)")

if __name__ == "__main__":
    main()