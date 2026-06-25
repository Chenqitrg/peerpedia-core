# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Unicode pseudo-font typography for terminal academic rendering.

Maps ASCII → Mathematical Alphanumeric Symbols for six visual roles.
Every function returns the styled string and a plain fallback.

Block reference
---------------
- Math Bold (title):       U+1D400  𝐀–𝐙  U+1D41A  𝐚–𝐳   U+1D7CE  𝟎–𝟗
- Math Italic (quote):     U+1D434  𝐴–𝑍  U+1D44E  𝑎–𝑧
- Math Script (author):    U+1D49C  𝒜–𝒵  U+1D4B6  𝒶–𝓏  (has gaps!)
- Math Fraktur (venue):    U+1D504  𝔄–𝔷  (has gaps!)
- Math Sans Bold (status): U+1D5D4  𝗔–𝗭  U+1D5EE  𝗮–𝘇  U+1D7E2  𝟬–𝟵
- Math Monospace (date/commit): U+1D670  𝙰–𝚉  U+1D68A  𝚊–𝚣
  Digits: U+1D7F6  𝟶–𝟿
- Double-Struck (score):   U+1D7D8  𝟘–𝟡

Design constraints:
- No more than 3 pseudo-font families on screen at once
- Body text and code NEVER get styled — only labels/metadata
- Every function returns {display, plain} for search/copy/export
"""

from __future__ import annotations

# ── Character mapping tables ─────────────────────────────────────────────

# Math Bold Serif: title
_BOLD_UPPER = {chr(i): chr(0x1D400 + i - ord('A')) for i in range(ord('A'), ord('Z') + 1)}
_BOLD_LOWER = {chr(i): chr(0x1D41A + i - ord('a')) for i in range(ord('a'), ord('z') + 1)}
_BOLD_DIGITS = {str(d): chr(0x1D7CE + d) for d in range(10)}

# Math Italic: subtitle / quote (U+1D455 is a gap — 'h' stays plain ASCII)
_ITALIC_UPPER = {chr(i): chr(0x1D434 + i - ord('A')) for i in range(ord('A'), ord('Z') + 1)}
_ITALIC_LOWER = {chr(i): chr(0x1D44E + i - ord('a')) for i in range(ord('a'), ord('z') + 1)}
# Remove entries that fall on Unicode gaps (they produce wrong glyphs).
for _gap_char in ('h',):
    _ITALIC_LOWER.pop(_gap_char, None)

# Math Script: author (has gaps — use lookup, not offset)
_SCRIPT_MAP = {
    **{chr(i): chr(0x1D49C + i - ord('A')) for i in range(ord('A'), ord('Z') + 1)},
    **{chr(i): chr(0x1D4B6 + i - ord('a')) for i in range(ord('a'), ord('z') + 1)},
}
# Fix known gaps in Script
_SCRIPT_MAP['B'] = 'ℬ'   # ℬ SCRIPT CAPITAL B
_SCRIPT_MAP['E'] = 'ℰ'   # ℰ SCRIPT CAPITAL E
_SCRIPT_MAP['F'] = 'ℱ'   # ℱ SCRIPT CAPITAL F
_SCRIPT_MAP['H'] = 'ℋ'   # ℋ SCRIPT CAPITAL H
_SCRIPT_MAP['I'] = 'ℐ'   # ℐ SCRIPT CAPITAL I
_SCRIPT_MAP['L'] = 'ℒ'   # ℒ SCRIPT CAPITAL L
_SCRIPT_MAP['M'] = 'ℳ'   # ℳ SCRIPT CAPITAL M
_SCRIPT_MAP['R'] = 'ℛ'   # ℛ SCRIPT CAPITAL R
_SCRIPT_MAP['e'] = 'ℯ'   # ℯ SCRIPT SMALL E
_SCRIPT_MAP['g'] = 'ℊ'   # ℊ SCRIPT SMALL G
_SCRIPT_MAP['o'] = 'ℴ'   # ℴ SCRIPT SMALL O

# Math Fraktur: venue (has gaps)
_FRAKTUR_MAP = {
    **{chr(i): chr(0x1D504 + i - ord('A')) for i in range(ord('A'), ord('Z') + 1)},
    **{chr(i): chr(0x1D51E + i - ord('a')) for i in range(ord('a'), ord('z') + 1)},
}
_FRAKTUR_MAP['C'] = 'ℭ'   # ℭ BLACK-LETTER CAPITAL C
_FRAKTUR_MAP['H'] = 'ℌ'   # ℌ BLACK-LETTER CAPITAL H
_FRAKTUR_MAP['I'] = 'ℑ'   # ℑ BLACK-LETTER CAPITAL I
_FRAKTUR_MAP['R'] = 'ℜ'   # ℜ BLACK-LETTER CAPITAL R
_FRAKTUR_MAP['Z'] = 'ℨ'   # ℨ BLACK-LETTER CAPITAL Z

# Math Sans Bold: status labels
_SANS_BOLD_UPPER = {chr(i): chr(0x1D5D4 + i - ord('A')) for i in range(ord('A'), ord('Z') + 1)}
_SANS_BOLD_LOWER = {chr(i): chr(0x1D5EE + i - ord('a')) for i in range(ord('a'), ord('z') + 1)}
_SANS_BOLD_DIGITS = {str(d): chr(0x1D7E2 + d) for d in range(10)}

# Math Monospace: date / commit
_MONO_UPPER = {chr(i): chr(0x1D670 + i - ord('A')) for i in range(ord('A'), ord('Z') + 1)}
_MONO_LOWER = {chr(i): chr(0x1D68A + i - ord('a')) for i in range(ord('a'), ord('z') + 1)}
_MONO_DIGITS = {str(d): chr(0x1D7F6 + d) for d in range(10)}

# Double-Struck digits: scores
_DOUBLE_DIGITS = {str(d): chr(0x1D7D8 + d) for d in range(10)}


# ── Render functions ─────────────────────────────────────────────────────

def _apply(ch: str, upper: dict, lower: dict, digits: dict | None = None) -> str:
    """Map a single character through the style tables."""
    if ch in upper:
        return upper[ch]
    if ch in lower:
        return lower[ch]
    if digits and ch in digits:
        return digits[ch]
    return ch


def _apply_dict(ch: str, mapping: dict) -> str:
    """Map a single character through a unified dict (for Script/Fraktur)."""
    return mapping.get(ch, ch)


def title(s: str) -> str:
    """Math Bold Serif — paper titles."""
    return ''.join(_apply(c, _BOLD_UPPER, _BOLD_LOWER, _BOLD_DIGITS) for c in s)


def italic(s: str) -> str:
    """Math Italic — quotes, abstract opening."""
    return ''.join(_apply(c, _ITALIC_UPPER, _ITALIC_LOWER) for c in s)


def author(s: str) -> str:
    """Math Script — author names (short names only, ≤ 2-3 authors)."""
    return ''.join(_apply_dict(c, _SCRIPT_MAP) for c in s)


def venue(s: str) -> str:
    """Math Fraktur — journal/institution badge (short names only)."""
    return ''.join(_apply_dict(c, _FRAKTUR_MAP) for c in s)


def status(s: str) -> str:
    """Math Sans Bold — DRAFT, ACCEPTED, PUBLISHED labels."""
    return ''.join(_apply(c, _SANS_BOLD_UPPER, _SANS_BOLD_LOWER, _SANS_BOLD_DIGITS) for c in s)


def mono(s: str) -> str:
    """Math Monospace — dates, commit hashes, DOIs."""
    return ''.join(_apply(c, _MONO_UPPER, _MONO_LOWER, _MONO_DIGITS) for c in s)


def score(s: str) -> str:
    """Double-Struck digits — ratings and scores."""
    return ''.join(_apply(c, {}, {}, _DOUBLE_DIGITS) for c in s)


# ── Rich markup wrappers ─────────────────────────────────────────────────

def styled_title(s: str, color: str = "bold") -> str:
    """Return a Rich-markup-safe styled title."""
    return f"[{color}]{title(s)}[/]"


def styled_author(s: str, color: str = "accent") -> str:
    """Return a Rich-markup-safe styled author name."""
    return f"[{color}]{author(s)}[/]"


def styled_status(s: str, color: str = "muted") -> str:
    """Return a Rich-markup-safe styled status badge."""
    return f"[{color}]{status(s.upper())}[/]"


def styled_date(s: str) -> str:
    """Return a Rich-markup-safe styled date string."""
    return f"[muted]{mono(s)}[/]"


def styled_score_val(n: float, color: str = "accent") -> str:
    """Return a Rich-markup-safe styled numeric score."""
    return f"[{color}]{score(f'{n:.1f}')}[/]"
