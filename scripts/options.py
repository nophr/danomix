"""OCC-style option symbol parser.

Format: 21 characters — 6-char left-padded root, YYMMDD, C/P, 8-digit strike×1000.
Example: "LUMN  270115C00010000" → LUMN Jan 15 2027 $10 call.
"""

from __future__ import annotations

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_option_symbol(symbol: str) -> dict:
    if len(symbol) != 21 or symbol[12] not in ("C", "P"):
        raise ValueError(f"Not an OCC option symbol: {symbol!r}")

    root = symbol[0:6].strip()
    yy, mm, dd = symbol[6:8], symbol[8:10], symbol[10:12]
    kind = "call" if symbol[12] == "C" else "put"
    strike_raw = int(symbol[13:21])
    strike = strike_raw // 1000 if strike_raw % 1000 == 0 else strike_raw / 1000

    return {
        "underlying": root,
        "expiry": f"20{yy}-{mm}-{dd}",
        "type": kind,
        "strike": strike,
    }


def format_option_display(parsed: dict) -> str:
    yy, mm, _dd = parsed["expiry"][2:4], parsed["expiry"][5:7], parsed["expiry"][8:10]
    month = _MONTHS[int(mm) - 1]
    letter = "C" if parsed["type"] == "call" else "P"
    strike = parsed["strike"]
    strike_str = f"{strike:g}"  # drop trailing zeros: 10.0 → "10"
    return f"{parsed['underlying']} {month}'{yy} ${strike_str}{letter}"
