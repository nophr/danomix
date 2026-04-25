"""Pytest fixtures shared across all test modules."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
