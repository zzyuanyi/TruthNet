"""Validate that LLM prose only reuses numbers from locked facts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def unlocked_numbers(texts: list[str], locked_facts: str) -> set[str]:
    """Return numeric values present in output but absent from locked facts."""

    def _values(text: str) -> set[Decimal]:
        values: set[Decimal] = set()
        for token in _NUMBER_RE.findall(text or ""):
            try:
                values.add(Decimal(token.replace(",", "")))
            except InvalidOperation:
                continue
        return values

    allowed = _values(locked_facts)
    return {str(value) for text in texts for value in _values(text) if value not in allowed}
