import io
import pytest
from scripts import flex


class _FakeResp:
    def __init__(self, body: bytes): self._body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self): return self._body


def test_request_statement_returns_ref_code(monkeypatch):
    body = (b'<FlexStatementResponse timestamp="20261231"><Status>Success</Status>'
            b'<ReferenceCode>123456789</ReferenceCode>'
            b'<Url>https://ndcdyn.interactivebrokers.com/.../GetStatement</Url>'
            b'</FlexStatementResponse>')
    monkeypatch.setattr(flex, "_urlopen", lambda url, timeout=30: _FakeResp(body))
    ref = flex.request_statement(token="TOK", query_id="Q")
    assert ref == "123456789"


def test_request_statement_raises_on_error(monkeypatch):
    body = (b'<FlexStatementResponse><Status>Fail</Status>'
            b'<ErrorCode>1012</ErrorCode><ErrorMessage>Token invalid</ErrorMessage>'
            b'</FlexStatementResponse>')
    monkeypatch.setattr(flex, "_urlopen", lambda url, timeout=30: _FakeResp(body))
    with pytest.raises(flex.FlexError, match="1012"):
        flex.request_statement(token="TOK", query_id="Q")


def test_fetch_statement_returns_final_xml(monkeypatch):
    final = b'<?xml version="1.0"?><FlexQueryResponse><dummy/></FlexQueryResponse>'
    monkeypatch.setattr(flex, "_urlopen", lambda url, timeout=30: _FakeResp(final))
    monkeypatch.setattr(flex.time, "sleep", lambda _s: None)
    xml = flex.fetch_statement(token="TOK", ref_code="123")
    assert b"<FlexQueryResponse>" in xml


def test_fetch_statement_polls_on_in_progress(monkeypatch):
    calls = {"n": 0}
    in_progress = (b'<FlexStatementResponse><Status>Warn</Status>'
                   b'<ErrorCode>1019</ErrorCode>'
                   b'<ErrorMessage>Statement generation in progress</ErrorMessage>'
                   b'</FlexStatementResponse>')
    final = b'<FlexQueryResponse><ok/></FlexQueryResponse>'

    def fake(url, timeout=30):
        calls["n"] += 1
        return _FakeResp(in_progress if calls["n"] < 3 else final)

    monkeypatch.setattr(flex, "_urlopen", fake)
    monkeypatch.setattr(flex.time, "sleep", lambda _s: None)
    xml = flex.fetch_statement(token="TOK", ref_code="123")
    assert calls["n"] == 3
    assert b"<ok/>" in xml
