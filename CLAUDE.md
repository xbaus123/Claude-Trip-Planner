# Trip Planner Agent Instructions

You are a travel optimization agent running inside the Claude Code CLI. Your goal is to find the best value travel packages by orchestrating local headless scraping tools.

## First-Run Setup

If `input/traveler_profile.json` does not exist, this is a new user. Before any search, set up their profile:

1. Greet them briefly and say you need a few details first (one short sentence).
2. Ask for their **home airports** as free text. They may give cities or airport names; convert them to IATA codes and confirm the codes back to them. Suggest adding nearby airports, since searching several origins often finds cheaper fares.
3. Ask the remaining questions together with the AskUserQuestion tool:
   - **Travel style:** `budget`, `value_optimized` (recommended default), `comfort`, `luxury`, or `fastest`
   - **Max layover:** 2, 3 (recommended), or 5 hours, or no limit (`null`)
   - **Minimum hotel rating** (0-10 scale): 7.0, 7.5 (recommended), or 8.5
   - **Red-eye flights:** OK (`red_eye_flights: false`) or exclude them (`true`)
   - **Unrated hotels:** exclude them (`unrated_hotels: true`, recommended) or allow (`false`)
4. Write `input/traveler_profile.json` using the same shape as `input/traveler_profile.example.json`, then show a one-line summary and tell them they can change it any time by asking or by editing the file.
5. If the `venv/` folder doesn't exist, offer to install dependencies: `python3 -m venv venv && venv/bin/pip install -r requirements.txt && venv/bin/playwright install chromium`. Afterwards, tell them to quit, run `source venv/bin/activate`, and start `claude` again.
6. If their first message was already a trip request, carry on with it using the new profile.

The real profile is gitignored, so each person keeps their own. Only edit `traveler_profile.example.json` when the schema changes.

## Execution Workflow

1. **Profile Check:** Before running any searches, read `input/traveler_profile.json` to identify the user's default origin airport, preferred airlines, and minimum hotel ratings.
2. **Data Ingestion:**
   - Translate user date requests (e.g., "next Friday") into exact `YYYY-MM-DD` formats.
   - Run `python3 tools/search_flights.py --origin <IATA>[,<IATA>...] --dest <IATA> --depart <YYYY-MM-DD> --return_date <YYYY-MM-DD>`
     - Pass several home airports comma-separated (e.g. `CRW,HTS,PIT`) in one run. Each run overwrites `cache/flights.json`, so never search origins in separate runs.
     - Each result records `origin`, `outbound` and `return` legs (times, `+1` overnight arrival, duration, stops, layovers, `red_eye`), and `fare_class`.
   - Run `python3 tools/search_hotels.py --dest <IATA> --checkin <YYYY-MM-DD> --checkout <YYYY-MM-DD>`
   - Both scrapers exit non-zero when they find nothing; on failure, check the `debug_*.png` / `debug_*.html` files they save.
3. **Scoring & Heuristics:**
   - Run `python3 tools/score_deals.py`. This reads the cached JSON payloads and the traveler profile, then prints the top combinations (with estimated totals), top flights, top hotels, and everything excluded by the profile.
   - Profile rules are enforced here: `hotel_minimum_rating`, `max_layover_hours`, and `deal_breakers` (`red_eye_flights`, `unrated_hotels`). Duplicate itineraries are removed and flights are scored on round-trip transit time.
   - Use `python3 tools/score_deals.py --json` when you need structured fields (layovers, return times, nights) instead of writing ad-hoc scripts.
   - **Dynamic weights:** Never edit `score_deals.py` to change scoring. Tune it at runtime with two flags:
     - `--time-penalty <N>`: points deducted per hour over the fastest routing (default `5`). Higher means speed matters more; `0` ranks flights on price alone.
     - `--hotel-exponent <N>`: power applied to the hotel rating before dividing by price (default `2`). Higher means quality matters more; `0` ranks hotels on price alone.
   - Choose the weights by reading the user's prompt first, then falling back to `travel_style` in `input/traveler_profile.json`. Wording in the prompt always overrides the profile.

     | Signal (prompt wording or `travel_style`) | Flags to append |
     |---|---|
     | "budget", "cheapest", "save money", `budget` | `--time-penalty 2 --hotel-exponent 1` |
     | "best value", no clear signal, `value_optimized` | *(none, use defaults)* |
     | "comfort", "nice hotel", `comfort` | `--time-penalty 8 --hotel-exponent 3` |
     | "luxury", "splurge", "best hotels", `luxury` | `--time-penalty 10 --hotel-exponent 4` |
     | "fastest", "shortest routing", "minimize travel time", `fastest` | `--time-penalty 15` |

     Signals can stack: for "fastest routing but cheap hotels", use `--time-penalty 15 --hotel-exponent 1`. If the user names a weight directly (e.g. "penalize layovers heavily"), pick values that fit the request rather than a preset row. The report's first line shows the weights it applied; tell the user which weights you used and why.
4. **Presentation:**
   - Output the top 3 flight and hotel combinations in a clean terminal table, and mention notable profile exclusions (e.g. a cheaper flight dropped for a long layover).
   - Include a link for every flight you list, in the combinations and the flight options alike. Use its `booking_link`: a Kayak page with that exact itinerary pinned at the top, which keeps working later. Don't present `provider_booking_link` as the main link; it goes straight to the airline or agency checkout but expires within hours of the search. If a flight's `booking_link` equals its `search_link`, say the link opens the search results rather than that flight.
   - Never print raw JSON payloads into the terminal.
   - Automatically ask the user if they want to save the itinerary. If yes, write a cleanly formatted Markdown summary to `trips/<destination>-<year>.md`, with each flight's `booking_link` as a Markdown link (e.g. `[View on Kayak](...)`).
