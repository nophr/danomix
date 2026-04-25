"""Thin client for the IBKR Flex Web Service (two-call protocol)."""

from __future__ import annotations

import time
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
SEND = BASE + "/SendRequest"
GET = BASE + "/GetStatement"
VERSION = "3"

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 60


class FlexError(RuntimeError):
    pass


def _urlopen(url: str, timeout: int = 30):
    return urllib.request.urlopen(url, timeout=timeout)


def request_statement(*, token: str, query_id: str) -> str:
    url = f"{SEND}?t={token}&q={query_id}&v={VERSION}"
    with _urlopen(url, timeout=30) as resp:
        body = resp.read()
    root = ET.fromstring(body)
    status = (root.findtext("Status") or "").strip()
    if status != "Success":
        code = root.findtext("ErrorCode") or "?"
        msg = root.findtext("ErrorMessage") or "(no message)"
        raise FlexError(f"Flex SendRequest failed {code}: {msg}")
    ref = root.findtext("ReferenceCode")
    if not ref:
        raise FlexError("Flex SendRequest success but no ReferenceCode")
    return ref.strip()


def fetch_statement(*, token: str, ref_code: str) -> bytes:
    url = f"{GET}?t={token}&q={ref_code}&v={VERSION}"
    deadline = time.time() + POLL_TIMEOUT_S
    while True:
        with _urlopen(url, timeout=30) as resp:
            body = resp.read()
        stripped = body.lstrip()
        # skip optional XML declaration
        if stripped.startswith(b"<?"):
            stripped = stripped[stripped.index(b"?>") + 2:].lstrip()
        if stripped.startswith(b"<FlexQueryResponse"):
            return body
        # otherwise it's an error/in-progress envelope
        try:
            root = ET.fromstring(body)
            code = root.findtext("ErrorCode") or ""
            msg = root.findtext("ErrorMessage") or ""
        except ET.ParseError:
            code, msg = "parse", "could not parse response"
        if code == "1019" or "in progress" in msg.lower():
            if time.time() > deadline:
                raise FlexError(f"Flex statement still generating after {POLL_TIMEOUT_S}s")
            time.sleep(POLL_INTERVAL_S)
            continue
        raise FlexError(f"Flex GetStatement failed {code}: {msg}")
