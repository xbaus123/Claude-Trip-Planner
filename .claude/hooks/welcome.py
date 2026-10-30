#!/usr/bin/env python3
"""SessionStart hook: shows a welcome banner and quick-start instructions
when `claude` is launched in this project. Stdlib only, so it runs with any
python3 (no venv needed)."""
import json
import os
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))

# Profile summary
try:
    p = json.loads((root / "input" / "traveler_profile.json").read_text())
    airports = ", ".join(p.get("home_airports", [])) or "not set"
    style = p.get("travel_style", "value_optimized").replace("_", " ")
    profile = (f"Home airports: {airports}  |  Style: {style}  |  "
               f"Max layover: {p.get('max_layover_hours', '?')}h  |  "
               f"Min hotel rating: {p.get('hotel_minimum_rating', '?')}")
except Exception:
    profile = "No profile found. Create input/traveler_profile.json first."

trips = sorted(x.stem for x in (root / "trips").glob("*.md")) if (root / "trips").is_dir() else []

venv_tip = ""
if not os.environ.get("VIRTUAL_ENV"):
    venv_tip = ("\n\n  Heads up: the venv isn't active, so the scrapers may fail.\n"
                "  Quit, run `source venv/bin/activate`, then start `claude` again.")

msg = f"""
  ✈  Welcome to Trip Planner

  I find the best-value flight + hotel combos by scraping live fares,
  scoring them against your traveler profile, and showing the top 3.

  Your profile
    {profile}
    (edit input/traveler_profile.json to change it)

  How to use it: tell me where, when, and how you want to travel.
    • "Find me a trip to Cancun March 12-19"
    • "Cheapest dirtbag trip to Denver next weekend"
    • "Luxury hotel in Chicago Dec 4-7, money is no object"
    • "Fastest routing to MIA over Thanksgiving"

  Dynamic Scoring Weights:
  I parse your keywords to adjust the scoring math on the fly:
    • Time Penalty: Deducts points per extra travel hour (Default: 5). Use "budget" to drop to 0, or "fastest" to increase it.
    • Hotel Exponent: Amplifies the value of high ratings (Default: 2). Use "luxury" to cube the ratings, or "budget" to lower it to 1.

  Saved trips: {", ".join(trips) if trips else "none yet"}{venv_tip}
"""

print(json.dumps({"systemMessage": msg}))
