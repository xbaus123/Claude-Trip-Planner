import json
import os

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
        scored_flights.append({**flight, "numeric_price": price})
        
    # The cheapest flight sets the 100-point baseline
    lowest_price = min(f['numeric_price'] for f in scored_flights)
    
    for flight in scored_flights:
        flight['value_score'] = round((lowest_price / flight['numeric_price']) * 100, 1)
        
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