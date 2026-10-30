"""Logging helpers so DOM-parsing failures in the scrapers are loud, not silent.

When Kayak changes its markup, a scraper can fail three ways:
  1. The card selector matches nothing        -> log_no_cards()
  2. A card raises while being parsed         -> log_card_error()
  3. A card parses but key fields are missing -> log_card_skipped()
Each one logs to stderr and saves the HTML involved to a debug_*.html file
(gitignored) so you can see which selector broke.
"""
import logging
import re
import sys

SNIPPET_CHARS = 600

logger = logging.getLogger("trip_planner.scraper")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _safe(label):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", label)


def _snippet(html):
    flat = " ".join(html.split())
    return flat if len(flat) <= SNIPPET_CHARS else flat[:SNIPPET_CHARS] + " …[truncated]"


def _dump(path, html):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path
    except OSError as e:
        logger.warning("Could not write %s: %s", path, e)
        return None


def log_card_error(label, idx, card):
    """Call from inside an `except` block: logs the traceback plus the failing card's HTML."""
    html = str(card)
    path = _dump(f"debug_{_safe(label)}_card{idx}.html", html)
    logger.exception(
        "[%s] Failed to parse result card #%d (full HTML saved to %s)\nCard HTML: %s",
        label, idx, path, _snippet(html),
    )


def log_card_skipped(label, idx, card, missing):
    """Logs a card that parsed without errors but was dropped because fields were missing."""
    html = str(card)
    path = _dump(f"debug_{_safe(label)}_skipped{idx}.html", html)
    logger.warning(
        "[%s] Skipped result card #%d: could not find %s (selector may be stale; HTML saved to %s)\nCard HTML: %s",
        label, idx, ", ".join(missing), path, _snippet(html),
    )


def log_no_cards(label, selector, page_html):
    """Logs when the card selector matches nothing, saving the whole page."""
    path = _dump(f"debug_{_safe(label)}_page.html", page_html)
    logger.error(
        "[%s] Card selector matched 0 elements: %r. Kayak's markup has probably changed; full page saved to %s",
        label, selector, path,
    )


def log_parse_summary(label, total, parsed):
    level = logging.INFO if parsed else logging.ERROR
    logger.log(level, "[%s] Parsed %d of %d result cards", label, parsed, total)
