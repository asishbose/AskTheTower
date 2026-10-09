"""Doc 11 §8.3: the output filter masks number shapes and leaves times, ids and refs alone."""

from __future__ import annotations

import pytest
from demo_ui.redact import mask

from tests.privacy.patterns import phone_hits

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "text",
    ["+16135550101", "16135550101", "+1 613 555 0101", "(613) 555-0101", "613.555.0101", "613-555-0101"],
)
def test_number_shapes_are_masked(text: str) -> None:
    out = mask(f"call {text} now")
    assert "[redacted]" in out and phone_hits(out) == []
    assert "555" not in out


@pytest.mark.parametrize(
    "text",
    [
        "2026-10-05T14:12:00Z",
        "2026-10-05 14:12",
        "14:12:00",
        "line:3f2a9c0d1e4b5a6c",
        "SIM_SWAPPED_RECENT.sms",
        "moment-1#3",
        "1234 ms",
    ],
)
def test_ordinary_text_is_kept(text: str) -> None:
    assert mask(text) == text
