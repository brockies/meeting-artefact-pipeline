"""
Deterministic redaction helpers for meeting transcripts.

This module tokenizes likely sensitive text before it is sent to the LLM or
saved in meeting history. It intentionally keeps the replacement scheme simple
and stable so references remain readable across the rest of the pipeline.
"""

from __future__ import annotations

import re


TOKEN_LABELS = ("PERSON", "ORG", "EMAIL", "PHONE", "URL", "IP", "TERM")


def parse_sensitive_terms(raw_terms: str | None) -> list[str]:
    """Parse comma/newline/semicolon separated custom sensitive terms."""
    if not raw_terms:
        return []

    terms: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[\n,;]+", raw_terms):
        term = chunk.strip()
        key = term.casefold()
        if not term or key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms


def _next_token(label: str, original: str, mappings: dict[str, dict[str, str]], counters: dict[str, int]) -> str:
    bucket = mappings.setdefault(label, {})
    if original not in bucket:
        counters[label] = counters.get(label, 0) + 1
        bucket[original] = f"[{label}_{counters[label]}]"
    return bucket[original]


def _replace_matches(
    text: str,
    pattern: str,
    label: str,
    mappings: dict[str, dict[str, str]],
    counters: dict[str, int],
    flags: int = 0,
) -> str:
    regex = re.compile(pattern, flags)

    def repl(match: re.Match) -> str:
        original = match.group(0)
        return _next_token(label, original, mappings, counters)

    return regex.sub(repl, text)


def tokenize_sensitive_text(text: str, custom_terms: list[str] | None = None) -> tuple[str, dict]:
    """
    Tokenize likely sensitive text using deterministic local rules.

    Returns:
        (tokenized_text, summary_dict)
    """
    custom_terms = custom_terms or []
    mappings: dict[str, dict[str, str]] = {}
    counters: dict[str, int] = {}
    tokenized = text

    # Speaker labels are the cleanest signal for personal names in transcripts.
    speaker_pattern = re.compile(
        r"(?m)^(?P<name>[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2})(?=\s*:)"
    )
    speaker_names = [m.group("name") for m in speaker_pattern.finditer(tokenized)]
    tokenized = speaker_pattern.sub(
        lambda m: _next_token("PERSON", m.group("name"), mappings, counters),
        tokenized,
    )

    # Replace later mentions of the same speaker names consistently.
    for name in sorted(set(speaker_names), key=len, reverse=True):
        token = _next_token("PERSON", name, mappings, counters)
        tokenized = re.sub(rf"\b{re.escape(name)}\b", token, tokenized)

    tokenized = _replace_matches(
        tokenized,
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "EMAIL",
        mappings,
        counters,
        flags=re.IGNORECASE,
    )
    tokenized = _replace_matches(
        tokenized,
        r"\b(?:https?://|www\.)\S+\b",
        "URL",
        mappings,
        counters,
        flags=re.IGNORECASE,
    )
    tokenized = _replace_matches(
        tokenized,
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "IP",
        mappings,
        counters,
    )
    tokenized = _replace_matches(
        tokenized,
        r"(?:(?<=\s)|^)(?:\+?\d[\d\s().-]{7,}\d)(?=\s|$)",
        "PHONE",
        mappings,
        counters,
    )

    # Simple company-name heuristic plus custom term support for project/client names.
    tokenized = _replace_matches(
        tokenized,
        r"\b[A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*)*\s+(?:Ltd|Limited|Inc|Corp|Corporation|LLC|PLC|Group|Company)\b",
        "ORG",
        mappings,
        counters,
    )

    for term in sorted(custom_terms, key=len, reverse=True):
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        tokenized = pattern.sub(
            lambda _: _next_token("TERM", term, mappings, counters),
            tokenized,
        )

    counts = {label: len(mappings.get(label, {})) for label in TOKEN_LABELS if mappings.get(label)}
    summary = {
        "mode": "tokenize",
        "counts": counts,
        "custom_term_count": len(custom_terms),
    }
    return tokenized, summary
