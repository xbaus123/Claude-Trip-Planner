import json

def score_hotels(hotels_json):
    scored_hotels = []
    for hotel in hotels_json:
        price = float(hotel['price_per_night'].replace('$', '').replace(',', ''))
        
        if hotel['rating'] == 'Unrated':
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
        
    # Normalize to a 0-100 scale based on the best performer
    if not scored_hotels:
        return []
        
    max_score = max(h['raw_score'] for h in scored_hotels)
    for hotel in scored_hotels:
        hotel['value_score'] = round((hotel['raw_score'] / max_score) * 100, 1)
        
    # Sort by best value
    return sorted(scored_hotels, key=lambda x: x['value_score'], reverse=True)

# Example usage for your next step
if __name__ == "__main__":
    # This will eventually read from sys.stdin or a local cache file
    pass