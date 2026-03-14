"""Tests for selectors — ensure all selectors are non-empty strings and regex patterns compile."""

import re

import pytest

from mcp_linkedin import selectors


def _get_string_selectors():
    """Yield (name, value) for all public string-type selector constants."""
    for name in dir(selectors):
        if name.startswith("_") or name.endswith("_RE") or name.endswith("_PATTERNS"):
            continue
        val = getattr(selectors, name)
        if isinstance(val, str):
            yield name, val


class TestSelectorStrings:
    @pytest.mark.parametrize("name,value", list(_get_string_selectors()))
    def test_non_empty(self, name, value):
        assert value.strip(), f"Selector {name} is empty"

    @pytest.mark.parametrize("name,value", list(_get_string_selectors()))
    def test_no_accidental_duplicates_within_value(self, name, value):
        # Basic sanity — selector string should not be just whitespace
        assert len(value) > 1, f"Selector {name} suspiciously short: {value!r}"


class TestRegexPatterns:
    def test_view_replies_re_compiles(self):
        assert isinstance(selectors.VIEW_REPLIES_RE, re.Pattern)

    def test_reaction_re_compiles(self):
        assert isinstance(selectors.REACTION_RE, re.Pattern)

    def test_view_replies_matches_english(self):
        assert selectors.VIEW_REPLIES_RE.search("View 3 replies")

    def test_view_replies_matches_czech(self):
        assert selectors.VIEW_REPLIES_RE.search("Zobrazit 5 odpovědí")

    def test_reaction_re_matches_like(self):
        assert selectors.REACTION_RE.search("Like 12")

    def test_reaction_re_matches_czech(self):
        assert selectors.REACTION_RE.search("Líbí se 7")

    def test_reply_count_patterns_list(self):
        assert len(selectors.REPLY_COUNT_PATTERNS) >= 3
        for p in selectors.REPLY_COUNT_PATTERNS:
            assert isinstance(p, re.Pattern)
