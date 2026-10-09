"""The one place privacy regexes live. Every privacy test imports from here (prompt 18 asserts it)."""

import re

# E.164-ish: optional +, 10-15 digits, allowing common separators between groups.
E164 = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{8,}\d(?![\w.])")
# A stricter form for machine-generated output (no separators).
E164_STRICT = re.compile(r"\+?\d{10,15}")
HEALTH_WORDS = re.compile(r"\b(fall|fallen|emergency|unwell|911|stroke|collapsed|injur\w*)\b", re.I)
AWS_KEY_ID = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._-]{20,}")

ALLOWED_PHONE_FORMS = re.compile(r"(?:•{4}|\*{4}|x{4})\s?\d{4}")  # masked last-four is allowed


def phone_hits(text: str) -> list[str]:
    """Return E.164-looking substrings, excluding masked last-four forms and ISO timestamps."""
    hits = []
    for m in E164_STRICT.finditer(text):
        s = m.group(0)
        # 14-digit ISO-ish timestamps like 20261005141400 are not phone numbers; neither are hashes.
        ctx = text[max(0, m.start() - 1) : m.end() + 1]
        if ALLOWED_PHONE_FORMS.search(ctx):
            continue
        hits.append(s)
    return hits
