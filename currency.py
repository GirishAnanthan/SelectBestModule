"""
World currency definitions for the Solar Module Comparison app.

`rate` = value of 1 unit of the currency expressed in INR (approximate, static).
Display conversion:  display_value = inr_value / rate
`div`  = scaling divisor used for the large monetary unit (Crore/Million/Billion).
`unit` = label for that scaled unit.
"""

# Approximate static exchange rates vs INR (1 foreign unit = rate INR).
WORLD_CURRENCIES = {
    "INR": {"name": "Indian Rupee",        "symbol": "Rs.",  "rate": 1.0,    "unit": "Cr", "div": 1e7},
    "USD": {"name": "US Dollar",            "symbol": "$",    "rate": 83.0,   "unit": "M",  "div": 1e6},
    "EUR": {"name": "Euro",                 "symbol": "€",    "rate": 90.0,   "unit": "M",  "div": 1e6},
    "GBP": {"name": "British Pound",        "symbol": "£",    "rate": 105.0,  "unit": "M",  "div": 1e6},
    "JPY": {"name": "Japanese Yen",         "symbol": "¥",    "rate": 0.55,   "unit": "Bn", "div": 1e9},
    "CNY": {"name": "Chinese Yuan",         "symbol": "¥",    "rate": 11.5,   "unit": "M",  "div": 1e6},
    "AED": {"name": "UAE Dirham",           "symbol": "AED",  "rate": 22.6,   "unit": "M",  "div": 1e6},
    "SAR": {"name": "Saudi Riyal",          "symbol": "SR",   "rate": 22.1,   "unit": "M",  "div": 1e6},
    "ZAR": {"name": "South African Rand",   "symbol": "R",    "rate": 4.5,    "unit": "M",  "div": 1e6},
    "AUD": {"name": "Australian Dollar",    "symbol": "A$",   "rate": 55.0,   "unit": "M",  "div": 1e6},
    "CAD": {"name": "Canadian Dollar",      "symbol": "C$",   "rate": 61.0,   "unit": "M",  "div": 1e6},
    "CHF": {"name": "Swiss Franc",          "symbol": "CHF",  "rate": 92.0,   "unit": "M",  "div": 1e6},
    "SGD": {"name": "Singapore Dollar",     "symbol": "S$",   "rate": 61.5,   "unit": "M",  "div": 1e6},
    "HKD": {"name": "Hong Kong Dollar",     "symbol": "HK$",  "rate": 10.6,   "unit": "M",  "div": 1e6},
    "THB": {"name": "Thai Baht",            "symbol": "฿",    "rate": 2.3,    "unit": "M",  "div": 1e6},
    "MYR": {"name": "Malaysian Ringgit",    "symbol": "RM",   "rate": 17.5,   "unit": "M",  "div": 1e6},
    "BRL": {"name": "Brazilian Real",       "symbol": "R$",   "rate": 16.5,   "unit": "M",  "div": 1e6},
    "MXN": {"name": "Mexican Peso",         "symbol": "$",    "rate": 4.9,    "unit": "M",  "div": 1e6},
    "RUB": {"name": "Russian Ruble",        "symbol": "₽",    "rate": 0.90,   "unit": "Bn", "div": 1e9},
    "KRW": {"name": "South Korean Won",     "symbol": "₩",    "rate": 0.063,  "unit": "Bn", "div": 1e9},
    "IDR": {"name": "Indonesian Rupiah",    "symbol": "Rp",   "rate": 0.0053, "unit": "Bn", "div": 1e9},
    "TRY": {"name": "Turkish Lira",         "symbol": "₺",    "rate": 2.6,    "unit": "Bn", "div": 1e9},
    "PHP": {"name": "Philippine Peso",      "symbol": "₱",    "rate": 1.45,   "unit": "M",  "div": 1e6},
    "VND": {"name": "Vietnamese Dong",      "symbol": "₫",    "rate": 0.0034, "unit": "Bn", "div": 1e9},
    "PLN": {"name": "Polish Zloty",         "symbol": "zł",   "rate": 21.0,   "unit": "M",  "div": 1e6},
    "SEK": {"name": "Swedish Krona",        "symbol": "kr",   "rate": 7.8,    "unit": "M",  "div": 1e6},
    "NOK": {"name": "Norwegian Krone",      "symbol": "kr",   "rate": 7.5,    "unit": "M",  "div": 1e6},
    "DKK": {"name": "Danish Krone",         "symbol": "kr",   "rate": 12.1,   "unit": "M",  "div": 1e6},
    "NZD": {"name": "New Zealand Dollar",   "symbol": "NZ$",  "rate": 50.0,   "unit": "M",  "div": 1e6},
    "ILS": {"name": "Israeli Shekel",       "symbol": "₪",    "rate": 22.5,   "unit": "M",  "div": 1e6},
    "EGP": {"name": "Egyptian Pound",       "symbol": "E£",   "rate": 1.7,    "unit": "M",  "div": 1e6},
    "PKR": {"name": "Pakistani Rupee",      "symbol": "Rs.",  "rate": 0.30,   "unit": "Bn", "div": 1e9},
    "BDT": {"name": "Bangladeshi Taka",     "symbol": "৳",    "rate": 0.75,   "unit": "Bn", "div": 1e9},
    "NGN": {"name": "Nigerian Naira",       "symbol": "₦",    "rate": 0.05,   "unit": "Bn", "div": 1e9},
}


def get_currency(code):
    return WORLD_CURRENCIES.get(code, WORLD_CURRENCIES["INR"])


def currency_options():
    """Return list of 'CODE - Name' strings for a dropdown."""
    return [f"{c} - {WORLD_CURRENCIES[c]['name']}" for c in WORLD_CURRENCIES]


def code_from_option(option):
    return option.split(" - ")[0].strip()


def make_formatter(cur):
    """Return a dict of money-formatting helpers bound to a currency dict."""
    sym = cur["symbol"]
    rate = cur["rate"]
    unit = cur["unit"]
    div = cur["div"]

    def money(v):
        try:
            return f"{sym} {float(v) / rate / div:.2f} {unit}"
        except Exception:
            return f"{sym} 0.00 {unit}"

    def money1(v):
        try:
            return f"{sym} {float(v) / rate / div:.1f} {unit}"
        except Exception:
            return f"{sym} 0.0 {unit}"

    def money_kwh(v):
        try:
            return f"{sym} {float(v) / rate:.3f}/kWh"
        except Exception:
            return "-"

    def money_wp(v):
        try:
            return f"{sym}{float(v) / rate:.1f}/Wp"
        except Exception:
            return "-"

    def money_small(v):
        try:
            return f"{sym}{float(v) / rate:.2f}"
        except Exception:
            return "-"

    return {
        "money": money,
        "money1": money1,
        "money_kwh": money_kwh,
        "money_wp": money_wp,
        "money_small": money_small,
        "symbol": sym,
        "rate": rate,
        "unit": unit,
        "div": div,
    }
