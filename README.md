# Trip Planner

A travel deal finder that runs inside [Claude Code](https://claude.com/claude-code). Tell it where and when you want to go in plain English. It scrapes live flight and hotel prices from Kayak, scores every flight + hotel combination against your personal traveler profile, and shows you the top 3.

Example (illustrative output):

```
> Cheapest trip to Denver next weekend

  #  Flight                          Hotel                       Est. total
  1  United  CRW→DEN  $312  1 stop   Hotel Teatro (8.9)  $498    $810
  2  ...
```

## How it works

1. **Profile:** your home airports, travel style and deal-breakers live in `input/traveler_profile.json`.
2. **Search:** Claude runs headless-browser scrapers (`tools/search_flights.py`, `tools/search_hotels.py`) for your dates, searching all of your home airports at once.
3. **Score:** `tools/score_deals.py` filters out anything that breaks your profile (long layovers, red-eyes, low-rated hotels), removes duplicates, and ranks what's left.
4. **Present:** Claude shows the top 3 combos, explains anything notable that got excluded, and offers to save the itinerary to `trips/`.

## Requirements

- Python 3.10+ (developed on 3.13)
- [Claude Code](https://claude.com/claude-code) (`claude` CLI)
- macOS or Linux (Windows should work with the activation command changed)

## Setup

```bash
git clone <repo-url> claude-trip-planner
cd claude-trip-planner

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium       # downloads the browser the scrapers drive

claude
```

Activate the venv **before** starting `claude` each time, so the scrapers can find their packages. The welcome screen warns you if you forget.

### First run

The first time you start `claude` you won't have a traveler profile yet. The welcome screen says so. Type anything (even "hi") and Claude will ask you a few quick questions:

- Your home airports (cities are fine, it'll convert them to airport codes)
- Travel style: budget, best value, comfort, luxury or fastest
- Longest layover you'll accept
- Minimum hotel rating
- Whether red-eye flights and unrated hotels are OK

It saves your answers to `input/traveler_profile.json`. That file is gitignored, so your profile stays on your machine. To change it later, ask Claude ("add IAD to my home airports") or edit the file directly. See `input/traveler_profile.example.json` for the format.

## Using it

Just describe the trip:

- "Find me a trip to Cancun March 12-19"
- "Cheapest dirtbag trip to Denver next weekend"
- "Luxury hotel in Chicago Dec 4-7, money is no object"
- "Fastest routing to MIA over Thanksgiving"

Relative dates like "next weekend" are converted to exact dates for you.

### Scoring weights

Claude reads the wording of your request and tunes two knobs on the scoring engine. If your request gives no signal, it falls back to the `travel_style` in your profile.

| You say | Time penalty (points per extra travel hour) | Hotel exponent (how much rating matters) |
|---|---|---|
| "budget", "cheapest" | 2 | 1 |
| "best value" / nothing specific | 5 (default) | 2 (default) |
| "comfort", "nice hotel" | 8 | 3 |
| "luxury", "splurge" | 10 | 4 |
| "fastest", "shortest routing" | 15 | 2 |

Signals combine ("fastest flight but a cheap hotel" uses 15 and 1), and Claude tells you which weights it used.

You can also run the scorer yourself on the last search:

```bash
python3 tools/score_deals.py --time-penalty 15 --hotel-exponent 1
python3 tools/score_deals.py --json     # structured output
```

## Project layout

```
.claude/
  settings.json           Startup hook config
  hooks/welcome.py        Welcome screen / first-run detection
CLAUDE.md                 Instructions Claude follows in this project
input/
  traveler_profile.example.json   Profile template (your real profile is gitignored)
tools/
  browser_engine.py       Stealth Playwright browser wrapper
  search_flights.py       Kayak flight scraper  -> cache/flights.json
  search_hotels.py        Kayak hotel scraper   -> cache/hotels.json
  score_deals.py          Filtering and ranking engine
trips/                    Saved itineraries (gitignored)
cache/                    Latest raw search results (gitignored)
```

## Troubleshooting

- **A scraper exits with an error / finds nothing.** It saves `debug_*.png` and `debug_*.html` in the project folder showing what the page looked like. Kayak changes its page structure from time to time, so a selector in the scraper may need updating.
- **`ModuleNotFoundError: playwright`.** The venv isn't active. Quit Claude, run `source venv/bin/activate`, start `claude` again.
- **`Executable doesn't exist` from Playwright.** Run `playwright install chromium`.
- **No welcome screen.** Claude Code asks you to trust the project's settings the first time. Approve it so the startup hook can run.

## Disclaimer

This project scrapes Kayak for personal use. Prices are estimates at the time of the search; always confirm on the booking site before paying. Respect Kayak's terms of service and don't run searches in bulk.
