#!/usr/bin/env python3
"""SessionStart hook: shows a welcome banner and quick-start instructions
when `claude` is launched in this project. Stdlib only, so it runs with any
python3 (no venv needed)."""
import json
import os
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))

# Profile summary
profile_path = root / "input" / "traveler_profile.json"
first_run = not profile_path.exists()
profile = ""
if not first_run:
    try:
        p = json.loads(profile_path.read_text())
        airports = ", ".join(p.get("home_airports", [])) or "not set"
        style = p.get("travel_style", "value_optimized").replace("_", " ")
        profile = (f"Home airports: {airports}  |  Style: {style}  |  "
                   f"Max layover: {p.get('max_layover_hours', '?')}h  |  "
                   f"Min hotel rating: {p.get('hotel_minimum_rating', '?')}")
    except Exception:
        profile = "Profile file is unreadable. Ask me to fix input/traveler_profile.json."

trips = sorted(x.stem for x in (root / "trips").glob("*.md")) if (root / "trips").is_dir() else []

venv_tip = ""
if not (root / "venv").is_dir():
    venv_tip = ("\n\n  Heads up: Python packages aren't installed yet (no venv/ folder).\n"
                "  Follow the Setup steps in README.md, or ask me to do it for you.")
elif not os.environ.get("VIRTUAL_ENV"):
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
    • Time Penalty: Deducts points per extra travel hour (Default: 5). Use "budget" to drop it to 2, or "fastest" to raise it to 15.
    • Hotel Exponent: Amplifies the value of high ratings (Default: 2). Use "comfort" for 3, "luxury" for 4, or "budget" to lower it to 1.

  Saved trips: {", ".join(trips) if trips else "none yet"}{venv_tip}
"""

if first_run:
    msg = f"""
  ✈  Welcome to Trip Planner

  I find the best-value flight + hotel combos by scraping live fares,
  scoring them against your traveler profile, and showing the top 3.

  Looks like you're new here: there's no traveler profile yet.
  Say hi (or anything) and I'll ask a few quick questions to set it up:
    • Your home airports
    • How you like to travel (budget, best value, comfort, luxury, fastest)
    • Longest layover you'll put up with
    • Minimum hotel rating
    • Red-eye flights and unrated hotels: OK or not{venv_tip}
"""
    out = {
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "FIRST RUN: input/traveler_profile.json does not exist. Before doing anything "
                "else, whatever the user's first message is, follow the 'First-Run Setup' "
                "section of CLAUDE.md to interview the user and create the profile. If their "
                "first message was a trip request, finish setup and then continue with it."
            ),
        },
    }
else:
    out = {"systemMessage": msg}

print(json.dumps(out))
