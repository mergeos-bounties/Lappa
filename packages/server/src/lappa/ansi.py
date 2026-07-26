"""ANSI SGR escape-code parsing for terminal-style log rendering.

ROS2/colcon/docker log output is frequently colorized with ANSI SGR
sequences (``\\x1b[32mINFO\\x1b[0m``). Rendered verbatim in a plain-text
widget these show up as garbled escape bytes instead of color. This module
turns a line of text into color/weight-tagged segments so a UI layer (Qt or
otherwise) can render it faithfully, and offers a plain-text fallback for
places that must not show escape bytes at all (e.g. redaction tests).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# Standard 8 foreground colors (30-37) tuned to stay legible on the IDE's
# dark (#080d18) log background; bright variants (90-97) are lighter.
_BASE_COLORS = {
    30: "#64748b",
    31: "#f87171",
    32: "#4ade80",
    33: "#fbbf24",
    34: "#60a5fa",
    35: "#f472b6",
    36: "#22d3ee",
    37: "#e2e8f0",
}
_BRIGHT_COLORS = {
    90: "#94a3b8",
    91: "#fca5a5",
    92: "#86efac",
    93: "#fde047",
    94: "#93c5fd",
    95: "#f9a8d4",
    96: "#67e8f9",
    97: "#f8fafc",
}


@dataclass(frozen=True)
class AnsiSegment:
    """A run of text sharing the same resolved SGR style."""

    text: str
    color: str | None = None
    bold: bool = False


def strip_ansi(text: str) -> str:
    """Return *text* with all SGR escape sequences removed."""
    return _SGR_RE.sub("", text)


def parse_ansi_segments(text: str) -> list[AnsiSegment]:
    """Split *text* into style-tagged segments, resolving SGR state as it goes.

    Unsupported/unknown SGR codes (e.g. background colors, underline) are
    accepted and ignored rather than raising: real log producers emit a wide
    range of codes, and a code Lappa doesn't render should degrade to the
    current color, not crash the log panel.
    """
    segments: list[AnsiSegment] = []
    color: str | None = None
    bold = False
    pos = 0
    for match in _SGR_RE.finditer(text):
        chunk = text[pos : match.start()]
        if chunk:
            segments.append(AnsiSegment(chunk, color, bold))
        codes_raw = match.group(1)
        codes = [int(part) for part in codes_raw.split(";") if part] if codes_raw else [0]
        for code in codes:
            if code == 0:
                color, bold = None, False
            elif code == 1:
                bold = True
            elif code == 22:
                bold = False
            elif code == 39:
                color = None
            elif code in _BASE_COLORS:
                color = _BASE_COLORS[code]
            elif code in _BRIGHT_COLORS:
                color = _BRIGHT_COLORS[code]
        pos = match.end()
    tail = text[pos:]
    if tail or not segments:
        segments.append(AnsiSegment(tail, color, bold))
    return segments
