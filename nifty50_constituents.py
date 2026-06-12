"""
NIFTY 50 constituent stocks with their Dhan security IDs and exchange segment.

Security IDs sourced from Dhan's instrument list (NSE segment).
Run `dhan.fetch_security_list()` to download a fresh copy if any ID changes.
"""

# Each entry: (symbol, security_id, exchange_segment, instrument_type)
# exchange_segment: "NSE_EQ" for equities
# instrument_type: "EQUITY"

NIFTY50_CONSTITUENTS = [
    ("ADANIENT",   "25",      "NSE_EQ", "EQUITY"),
    ("ADANIPORTS",  "15083",   "NSE_EQ", "EQUITY"),
    ("APOLLOHOSP",  "157",     "NSE_EQ", "EQUITY"),
    ("ASIANPAINT",  "236",     "NSE_EQ", "EQUITY"),
    ("AXISBANK",    "5900",    "NSE_EQ", "EQUITY"),
    ("BAJAJ-AUTO",  "16669",   "NSE_EQ", "EQUITY"),
    ("BAJAJFINSV",  "16675",   "NSE_EQ", "EQUITY"),
    ("BAJFINANCE",  "317",     "NSE_EQ", "EQUITY"),
    ("BHARTIARTL",  "10604",   "NSE_EQ", "EQUITY"),
    ("BPCL",        "526",     "NSE_EQ", "EQUITY"),
    ("BRITANNIA",   "547",     "NSE_EQ", "EQUITY"),
    ("CIPLA",       "694",     "NSE_EQ", "EQUITY"),
    ("COALINDIA",   "20374",   "NSE_EQ", "EQUITY"),
    ("DIVISLAB",    "10940",   "NSE_EQ", "EQUITY"),
    ("DRREDDY",     "881",     "NSE_EQ", "EQUITY"),
    ("EICHERMOT",   "910",     "NSE_EQ", "EQUITY"),
    ("GRASIM",      "1232",    "NSE_EQ", "EQUITY"),
    ("HCLTECH",     "7229",    "NSE_EQ", "EQUITY"),
    ("HDFCBANK",    "1333",    "NSE_EQ", "EQUITY"),
    ("HDFCLIFE",    "467",     "NSE_EQ", "EQUITY"),
    ("HEROMOTOCO",  "1348",    "NSE_EQ", "EQUITY"),
    ("HINDALCO",    "1363",    "NSE_EQ", "EQUITY"),
    ("HINDUNILVR",  "1394",    "NSE_EQ", "EQUITY"),
    ("ICICIBANK",   "4963",    "NSE_EQ", "EQUITY"),
    ("INDUSINDBK",  "5258",    "NSE_EQ", "EQUITY"),
    ("INFY",        "1594",    "NSE_EQ", "EQUITY"),
    ("ITC",         "1660",    "NSE_EQ", "EQUITY"),
    ("JSWSTEEL",    "11723",   "NSE_EQ", "EQUITY"),
    ("KOTAKBANK",   "1922",    "NSE_EQ", "EQUITY"),
    ("LT",          "11483",   "NSE_EQ", "EQUITY"),
    ("M&M",         "2031",    "NSE_EQ", "EQUITY"),
    ("MARUTI",      "10999",   "NSE_EQ", "EQUITY"),
    ("NESTLEIND",   "17963",   "NSE_EQ", "EQUITY"),
    ("NTPC",        "11630",   "NSE_EQ", "EQUITY"),
    ("ONGC",        "2475",    "NSE_EQ", "EQUITY"),
    ("POWERGRID",   "14977",   "NSE_EQ", "EQUITY"),
    ("RELIANCE",    "2885",    "NSE_EQ", "EQUITY"),
    ("SBILIFE",     "21808",   "NSE_EQ", "EQUITY"),
    ("SBIN",        "3045",    "NSE_EQ", "EQUITY"),
    ("SHRIRAMFIN",  "4306",    "NSE_EQ", "EQUITY"),
    ("SUNPHARMA",   "3351",    "NSE_EQ", "EQUITY"),
    ("TATACONSUM",  "3432",    "NSE_EQ", "EQUITY"),
    ("TATAMOTORS",  "3456",    "NSE_EQ", "EQUITY"),
    ("TATASTEEL",   "3499",    "NSE_EQ", "EQUITY"),
    ("TCS",         "11536",   "NSE_EQ", "EQUITY"),
    ("TECHM",       "13538",   "NSE_EQ", "EQUITY"),
    ("TITAN",       "3506",    "NSE_EQ", "EQUITY"),
    ("ULTRACEMCO",  "11532",   "NSE_EQ", "EQUITY"),
    ("WIPRO",       "3787",    "NSE_EQ", "EQUITY"),
    ("ZOMATO",      "21296",   "NSE_EQ", "EQUITY"),
]

# NIFTY 50 Index itself (IDX segment)
NIFTY50_INDEX = ("NIFTY 50", "13", "IDX_I", "INDEX")
