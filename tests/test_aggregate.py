"""Unit tests for the pure helpers in aggregate.py (no network)."""

from datetime import UTC, datetime, timedelta

import pytest

import aggregate

# --- parse_date -------------------------------------------------------------------------


def test_parse_date_prefers_feedparser_struct_time():
    entry = {"published_parsed": (2026, 10, 14, 9, 20, 35, 0, 0, 0), "published": "garbage"}
    assert aggregate.parse_date(entry) == datetime(2026, 10, 14, 9, 20, 35, tzinfo=UTC)


def test_parse_date_falls_back_to_rfc2822_string_and_converts_to_utc():
    entry = {"published": "Tue, 14 Oct 2026 18:00:00 +0900"}
    assert aggregate.parse_date(entry) == datetime(2026, 10, 14, 9, 0, 0, tzinfo=UTC)


def test_parse_date_treats_naive_string_as_utc():
    entry = {"updated": "Tue, 14 Oct 2026 09:00:00"}
    assert aggregate.parse_date(entry) == datetime(2026, 10, 14, 9, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize("entry", [{}, {"published": "not a date"}, {"published_parsed": ("x",)}])
def test_parse_date_returns_none_when_unparseable(entry):
    assert aggregate.parse_date(entry) is None


# --- clean_text / dedup_key -------------------------------------------------------------


def test_clean_text_unescapes_and_collapses_whitespace():
    assert aggregate.clean_text("  EV &amp; battery\n\n news  ") == "EV & battery news"
    assert aggregate.clean_text("") == ""


def test_dedup_key_strips_query_string_and_trailing_slash():
    assert aggregate.dedup_key("https://x.com/a/?utm=1", "T") == "https://x.com/a"
    assert aggregate.dedup_key("https://x.com/a/", "T") == aggregate.dedup_key("https://x.com/a", "T")


def test_dedup_key_uses_lowercased_title_without_link():
    assert aggregate.dedup_key("", "  Hello World ") == "hello world"


# --- passes_filters ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "include", "exclude", "expected"),
    [
        ("Solid-state battery breakthrough", [], [], True),
        ("Solid-state battery breakthrough", ["battery"], [], True),
        ("Solid-state battery breakthrough", ["BATTERY"], [], True),  # case-insensitive
        ("Solid-state battery breakthrough", ["motor"], [], False),
        ("Solid-state battery breakthrough", ["battery"], ["solid-state"], False),  # exclude wins
        ("Solid-state battery breakthrough", [], ["nothing"], True),
    ],
)
def test_passes_filters(text, include, exclude, expected):
    assert aggregate.passes_filters(text, include, exclude) is expected


# --- build_category (collect_feed replaced, no network) ---------------------------------


def _item(title, link, dt, source="src", summary=""):
    return {"title": title, "link": link, "source": source, "summary": summary, "dt": dt}


def test_build_category_filters_dedups_sorts_and_caps(monkeypatch):
    now = datetime.now(UTC)
    feeds = {
        "A": [
            _item("Battery news 1", "https://a/1?utm=x", now - timedelta(days=1)),
            _item("Battery news 1 dup", "https://a/1", now - timedelta(days=2)),  # same link → dropped
            _item("Motor news", "https://a/2", now),  # fails include filter
            _item("Old battery", "https://a/3", now - timedelta(days=30)),  # older than max_age
            _item("Battery undated", "https://a/4", None),  # kept, sorted last
        ],
        "B": RuntimeError("dead feed"),  # isolated, does not abort the category
        "C": [_item("Battery news 2", "https://c/1", now - timedelta(hours=1))],
    }

    def fake_collect(name, url):
        result = feeds[name]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(aggregate, "collect_feed", fake_collect)
    cat = {
        "key": "battery",
        "label": "배터리",
        "include_keywords": ["battery"],
        "exclude_keywords": [],
        "feeds": [{"name": n, "url": f"https://{n}"} for n in ("A", "B", "C")],
    }

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    assert out["key"] == "battery" and out["label"] == "배터리"
    assert [i["title"] for i in out["items"]] == ["Battery news 2", "Battery news 1", "Battery undated"]
    assert out["count"] == 3
    assert out["items"][0]["published"].endswith("+00:00") and out["items"][2]["published"] is None

    capped = aggregate.build_category(cat, max_age_days=14, max_items=1)
    assert [i["title"] for i in capped["items"]] == ["Battery news 2"]
