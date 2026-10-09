"""The output filter (doc 11 §8.3): defence in depth on every HTML fragment and SSE frame.

The UI never reads a number (it uses the mock's `ref`s and the services' redacted views), so this should never
fire. It masks the privacy regex (`\\+?\\d{10,15}`, the same as `ref_client.transcript.E164`) and the grouped
North-American shapes (`+1 613 555 0101`, `(613) 555-0101`, `613.555.0101`) the strict regex would miss.
"""

from __future__ import annotations

import re

from ref_client.transcript import E164, REDACTED

GROUPED = re.compile(r"(?:\+?\d{1,3}[\s.-])?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")


def mask(text: str) -> str:
    return str(E164.sub(REDACTED, GROUPED.sub(REDACTED, text)))
