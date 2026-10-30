"""Currency-aware price parsing shared by the scrapers and the scorer.

Kayak localizes prices by market, so a card can read "$1,234", "€1.234", "1 234 kr",
"CHF 1'234.50", "R$ 2.345,67" or "¥123,456". parse_price_text() finds the first amount
that carries a currency marker and returns it as a float plus a currency code, so a deal
in another currency is kept instead of being recorded as "Unknown" and dropped.
"""
import re

# Symbols and local abbreviations -> ISO 4217 code. Ambiguous markers ("kr" is used by
# SEK, NOK, DKK and ISK) keep the marker itself as the code, which is still enough to
# tell whether two prices can be compared.
SYMBOLS = {
    "US$": "USD", "$": "USD",  # Kayak.com's bare "$" is US dollars
    "CA$": "CAD", "C$": "CAD", "AU$": "AUD", "A$": "AUD", "NZ$": "NZD",
    "HK$": "HKD", "S$": "SGD", "MX$": "MXN", "R$": "BRL", "NT$": "TWD",
    "€": "EUR", "£": "GBP", "¥": "JPY", "JP¥": "JPY", "CN¥": "CNY", "元": "CNY",
    "₹": "INR", "₩": "KRW", "₺": "TRY", "₪": "ILS", "฿": "THB", "₱": "PHP",
    "₫": "VND", "₦": "NGN", "₴": "UAH", "₽": "RUB", "zł": "PLN", "Kč": "CZK",
    "Ft": "HUF", "lei": "RON", "Rp": "IDR", "RM": "MYR", "kr": "kr", "Fr.": "CHF",
}

# Display symbol for each code when printing totals; anything else prints as "1,234 XYZ"
DISPLAY = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹", "KRW": "₩",
           "CAD": "CA$", "AUD": "A$", "BRL": "R$", "MXN": "MX$"}

# Longest first so "US$" wins over "$"; any 3-letter uppercase ISO code also counts
_CUR = "|".join(re.escape(s) for s in sorted(SYMBOLS, key=len, reverse=True)) + r"|\b[A-Z]{3}\b"
# Digits with optional thousands groups (",", ".", spaces, apostrophes) and up to 2 decimals
_NUM = r"\d+(?:[.,\s\u00a0\u202f'’]\d{3})*(?:[.,]\d{1,2})?(?!\d)"
PRICE_RE = re.compile(
    rf"(?:(?P<pre>{_CUR})[\s\u00a0\u202f]*)?(?P<num>{_NUM})(?:[\s\u00a0\u202f]*(?P<post>{_CUR})(?![\s\u00a0\u202f]*\d))?"
)


def _to_float(num):
    """Normalizes '1.234,56', '1,234.56', '1 234', "1'234" or '12,50' to a float."""
    num = re.sub(r"[\s\u00a0\u202f'’]", "", num)
    if "," in num and "." in num:
        # Whichever separator comes last is the decimal point
        decimal = "," if num.rfind(",") > num.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        return float(num.replace(thousands, "").replace(decimal, "."))
    for sep in (",", "."):
        if sep in num:
            parts = num.split(sep)
            # Repeated, or followed by exactly 3 digits -> thousands separator ("1.234" is 1234)
            if len(parts) > 2 or len(parts[-1]) == 3:
                return float(num.replace(sep, ""))
            return float(num.replace(sep, "."))
    return float(num)


def parse_price_text(text):
    """Returns (display_text, amount, currency_code) for the first priced amount, or None.

    An amount only counts when a currency marker sits right before or after it, so stray
    numbers on a card (ratings, review counts) are never mistaken for prices.
    """
    if not text:
        return None
    for m in PRICE_RE.finditer(str(text)):
        marker = m.group("pre") or m.group("post")
        if not marker:
            continue
        try:
            amount = _to_float(m.group("num"))
        except ValueError:
            continue
        return m.group(0).strip(), amount, SYMBOLS.get(marker, marker)
    return None


def format_money(amount, currency):
    """Formats an amount for the report, e.g. ('USD', 1234) -> '$1,234', ('SEK', 50) -> '50 SEK'."""
    symbol = DISPLAY.get(currency)
    return f"{symbol}{amount:,.0f}" if symbol else f"{amount:,.0f} {currency}"
