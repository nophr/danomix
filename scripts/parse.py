"""Flex XML → structured dict. Deliberately drops the accountId attribute."""

from __future__ import annotations

import xml.etree.ElementTree as ET

# IBKR's CashTransaction `type` values that represent external cashflows
# (account in/out moves, not internal P&L). These must be subtracted from
# NAV change when computing time-weighted return.
EXTERNAL_CASHFLOW_TYPES = {
    "Deposits/Withdrawals",
    "Deposits",
    "Withdrawals",
    "Internal Transfers",
}


def parse_flex_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)

    positions = []
    for p in root.iter("OpenPosition"):
        positions.append({
            "symbol":         p.attrib["symbol"],
            "asset_category": p.attrib["assetCategory"],
            "position":       float(p.attrib["position"]),
            "position_value": float(p.attrib["positionValue"]),
            "currency":       p.attrib.get("currency", "USD"),
        })

    nav = []
    for row in root.iter("EquitySummaryByReportDateInBase"):
        nav.append({
            "date":        row.attrib["reportDate"],
            "total":       float(row.attrib["total"]),
            "total_long":  float(row.attrib["totalLong"]),
            "total_short": float(row.attrib["totalShort"]),
        })
    nav.sort(key=lambda r: r["date"])

    cashflows = []
    for row in root.iter("CashTransaction"):
        ttype = row.attrib.get("type", "")
        if ttype not in EXTERNAL_CASHFLOW_TYPES:
            continue
        # IBKR uses either reportDate or dateTime; settleDate is also possible
        date = row.attrib.get("reportDate") or row.attrib.get("dateTime", "")[:10] \
            or row.attrib.get("settleDate", "")
        if not date:
            continue
        cashflows.append({
            "date":   date,
            "amount": float(row.attrib["amount"]),  # positive = deposit, negative = withdrawal
            "type":   ttype,
        })
    cashflows.sort(key=lambda r: r["date"])

    return {"positions": positions, "nav": nav, "cashflows": cashflows}
