"""Unit tests for ANSI SGR parsing used by the split launch-log panels."""

from __future__ import annotations

from lappa.ansi import parse_ansi_segments, strip_ansi


def test_strip_ansi_removes_color_codes():
    raw = "\x1b[32m[INFO]\x1b[0m starting node"
    assert strip_ansi(raw) == "[INFO] starting node"


def test_plain_text_is_a_single_uncolored_segment():
    segments = parse_ansi_segments("no escapes here")
    assert len(segments) == 1
    assert segments[0].text == "no escapes here"
    assert segments[0].color is None
    assert segments[0].bold is False


def test_color_applies_only_until_reset():
    segments = parse_ansi_segments("\x1b[31mERROR\x1b[0m: disk full")
    texts = [(s.text, s.color) for s in segments]
    assert texts == [("ERROR", "#f87171"), (": disk full", None)]


def test_bold_and_color_combine_from_a_single_sgr_sequence():
    segments = parse_ansi_segments("\x1b[1;33mWARN\x1b[0m low battery")
    assert segments[0].text == "WARN"
    assert segments[0].color == "#fbbf24"
    assert segments[0].bold is True
    assert segments[1].bold is False


def test_bright_variant_maps_to_a_lighter_color_than_base():
    dim = parse_ansi_segments("\x1b[32mok\x1b[0m")[0].color
    bright = parse_ansi_segments("\x1b[92mok\x1b[0m")[0].color
    assert dim != bright


def test_unknown_sgr_code_is_ignored_not_fatal():
    segments = parse_ansi_segments("\x1b[4;99munderline-ish\x1b[0m")
    assert segments[0].text == "underline-ish"
    assert segments[0].color is None


def test_empty_string_yields_one_empty_segment():
    segments = parse_ansi_segments("")
    assert segments == [type(segments[0])("", None, False)]


def test_color_persists_across_multiple_plain_chunks_in_one_call():
    segments = parse_ansi_segments("\x1b[34mfirst")
    assert segments[0].text == "first"
    assert segments[0].color == "#60a5fa"
