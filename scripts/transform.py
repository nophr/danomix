"""Build public holdings list and leverage from parsed Flex data.

Percentages are relative to gross long value (sum of positionValue). Dollars are never
written to the output — only percentages, display strings, and structured option metadata.
"""

from __future__ import annotations

from scripts.options import parse_option_symbol, format_option_display


def build_holdings(positions: list[dict]) -> list[dict]:
    gross_long = sum(p["position_value"] for p in positions)
    if gross_long == 0:
        return []

    out = []
    for p in positions:
        percent = round(p["position_value"] / gross_long * 100, 2)
        shares = p.get("position") or 0
        price = round(p["position_value"] / shares, 4) if shares else None
        row = {
            "symbol":      p["symbol"],
            "display":     p["symbol"],
            "asset_class": p["asset_category"],
            "percent":     percent,
            "price":       price,
        }
        if p["asset_category"] == "OPT":
            parsed_opt = parse_option_symbol(p["symbol"])
            row["option"] = parsed_opt
            row["display"] = format_option_display(parsed_opt)
            # stable synthetic key for options across runs (used for moves diffing)
            strike = parsed_opt["strike"]
            letter = "C" if parsed_opt["type"] == "call" else "P"
            yymmdd = parsed_opt["expiry"][2:].replace("-", "")
            row["symbol"] = f"{parsed_opt['underlying']}_{yymmdd}{letter}{strike:g}"
        out.append(row)

    out.sort(key=lambda h: h["percent"], reverse=True)
    return out


def compute_leverage(latest_nav: dict) -> float:
    """Gross leverage: (long_exposure + short_exposure_magnitude) / equity.

    total_short is stored as a negative number, so subtracting it adds the
    magnitude. This is the more honest framing of total risk than long-only
    leverage, since short positions also consume buying power and contribute
    to portfolio P&L.
    """
    gross_exposure = latest_nav["total_long"] - latest_nav["total_short"]
    return round(gross_exposure / latest_nav["total"], 2)
