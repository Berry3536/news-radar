"""Unit tests for the pure helpers in aggregate.py (no external network)."""

import json
import socket
import threading
import time
from datetime import UTC, datetime, timedelta, timezone

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


def test_parse_date_survives_overflowing_raw_string():
    # A huge offset makes email.utils raise OverflowError; one such item must not fail the feed (RULE4).
    raw = "2026 Nov 21 11:51:51 +99999999999999999999"
    assert aggregate.parse_date({"published": raw}) is None
    st = (2026, 11, 21, 2, 0, 0, 0, 0, 0)
    assert aggregate.parse_date({"published": raw, "published_parsed": st}) == datetime(
        2026, 11, 21, 2, 0, 0, tzinfo=UTC
    )


# --- feed tz: parse_tz / lacks_tz / parse_date(entry, tz) / collect_feed / build_category ---

KST = timezone(timedelta(hours=9))
KST_0251_UTC = datetime(2026, 11, 21, 2, 51, 51, tzinfo=UTC)  # 2026-11-21 11:51:51 KST
ST_0251 = (2026, 11, 21, 2, 51, 51, 5, 325, 0)
ST_1151 = (2026, 11, 21, 11, 51, 51, 5, 325, 0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, UTC),
        ("+09:00", KST),
        ("-05:30", timezone(-timedelta(hours=5, minutes=30))),
        ("+00:00", UTC),
    ],
)
def test_parse_tz_accepts_fixed_offsets(value, expected):
    assert aggregate.parse_tz(value) == expected


@pytest.mark.parametrize("value", ["KST", "Asia/Seoul", "+9", "+0900", "09:00", "+24:00", "+09:60", "", 9])
def test_parse_tz_rejects_anything_else(value):
    with pytest.raises(ValueError, match="tz"):
        aggregate.parse_tz(value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-11-21 11:51:51", True),
        ("2026-11-21T11:51:51", True),
        ("2026-11-21", True),
        ("Sat, 21 Nov 2026 11:51:51", True),
        ("2026-11-21T11:51:51+09:00", False),
        ("2026-11-21T11:51:51Z", False),
        ("Sat, 21 Nov 2026 11:51:51 +0900", False),
        ("Sat, 21 Nov 2026 11:51:51 GMT", False),
        ("Sat, 21 Nov 2026 11:51:51 -0000", False),  # RFC 2822: UTC (parsedate_to_datetime gives naive)
        ("Sat, 21 Nov 2026 11:51:51 KST", False),  # a zone is written, even if unknown
        ("garbage", False),
        ("", False),
        (None, False),
    ],
)
def test_lacks_tz(raw, expected):
    assert aggregate.lacks_tz(raw) is expected


@pytest.mark.parametrize("key", ["published", "updated"])
def test_parse_date_reads_naive_string_in_feed_tz(key):
    entry = {key: "2026-11-21 11:51:51", f"{key}_parsed": ST_1151}  # feedparser read it as UTC
    assert aggregate.parse_date(entry, KST).isoformat() == "2026-11-21T02:51:51+00:00"
    assert aggregate.parse_date(entry) == datetime(2026, 11, 21, 11, 51, 51, tzinfo=UTC)  # no feed tz: UTC


@pytest.mark.parametrize(
    ("raw", "st"),
    [
        ("Sat, 21 Nov 2026 11:51:51 +0900", ST_0251),
        ("Sat, 21 Nov 2026 02:51:51 GMT", ST_0251),
        ("Sat, 21 Nov 2026 02:51:51 -0000", ST_0251),
        ("2026-11-21T11:51:51+09:00", ST_0251),
    ],
)
def test_parse_date_keeps_explicit_zone_with_feed_tz(raw, st):
    assert aggregate.parse_date({"published": raw, "published_parsed": st}, KST) == KST_0251_UTC


def test_parse_date_string_fallback_uses_feed_tz_only_without_zone():
    assert aggregate.parse_date({"updated": "Sat, 21 Nov 2026 11:51:51"}, KST) == KST_0251_UTC
    assert aggregate.parse_date({"updated": "Sat, 21 Nov 2026 02:51:51 -0000"}, KST) == KST_0251_UTC


RSS_NAIVE_PUBDATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title><link>https://example.com/</link><description>d</description>
<item><title>naive</title><link>https://example.com/1</link><pubDate>2026-11-21 11:51:51</pubDate></item>
<item><title>explicit</title><link>https://example.com/2</link><pubDate>Sat, 21 Nov 2026 11:51:51 +0900</pubDate></item>
</channel></rss>
"""


def test_collect_feed_reads_naive_pubdate_in_feed_tz():
    # feedparser.parse() takes the XML document itself in place of a URL: no network.
    with_tz = {it["title"]: it["dt"] for it in aggregate.collect_feed("T", RSS_NAIVE_PUBDATE, KST)}
    assert with_tz == {"naive": KST_0251_UTC, "explicit": KST_0251_UTC}

    without_tz = {it["title"]: it["dt"] for it in aggregate.collect_feed("T", RSS_NAIVE_PUBDATE)}
    assert without_tz == {"naive": datetime(2026, 11, 21, 11, 51, 51, tzinfo=UTC), "explicit": KST_0251_UTC}


def test_build_category_skips_only_the_feed_with_invalid_tz(monkeypatch, capsys):
    now = datetime.now(UTC)
    received_tz = {}

    def fake_collect(name, url, tz=UTC):
        received_tz[name] = tz
        return [{"title": f"{name} news", "link": f"https://{name}/1", "source": name, "summary": "", "dt": now}]

    monkeypatch.setattr(aggregate, "collect_feed", fake_collect)
    cat = {
        "key": "robot",
        "label": "로봇",
        "feeds": [
            {"name": "A", "url": "https://A", "tz": "KST"},  # invalid: fails before any request
            {"name": "B", "url": "https://B", "tz": "+09:00"},
            {"name": "C", "url": "https://C"},
        ],
    }

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    assert {i["title"] for i in out["items"]} == {"B news", "C news"}
    assert received_tz == {"B": KST, "C": UTC}
    err = capsys.readouterr().err
    assert "[FAIL] robot / A: " in err and "'KST'" in err


# --- link scheme: safe_link / collect_feed / build_category (RULE11) ---------------------


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("http://example.com/a?idxno=1", "http://example.com/a?idxno=1"),
        ("https://example.com/b", "https://example.com/b"),
        ("  HTTPS://Example.com/c \n", "HTTPS://Example.com/c"),  # scheme case-insensitive, outer whitespace stripped
        ("javascript:alert(1)", ""),
        (" JaVaScRiPt:alert(1) ", ""),
        ("java\tscript:alert(1)", ""),  # browsers drop the tab too
        ("ht\ttps://example.com/t", ""),  # urlsplit drops the tab; the dashboard would not link it
        ("\x00https://example.com/z", ""),  # leading control char: same, matches isWebLink
        ("vbscript:msgbox(1)", ""),
        ("data:text/html,<script>alert(1)</script>", ""),
        ("ftp://example.com/f", ""),
        ("mailto:a@example.com", ""),
        ("/news/1", ""),
        ("//example.com/news/2", ""),
        ("https:example.com", ""),  # no "://"
        ("https:///x", ""),  # "://" but no host
        ("http://?q=1", ""),  # "://" but no host
        ("http://[::1/a", ""),  # urlsplit raises ValueError
        ("", ""),
        ("   ", ""),
    ],
)
def test_safe_link(link, expected):
    assert aggregate.safe_link(link) == expected


RSS_LINK_SCHEMES = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title><link>https://example.com/</link><description>d</description>
<item><title>js</title><link>javascript:alert(1)</link></item>
<item><title>js-mixed-case</title><link> JaVaScRiPt:alert(document.cookie) </link></item>
<item><title>vbs</title><link>vbscript:msgbox(1)</link></item>
<item><title>data</title><link>data:text/html,&lt;script&gt;alert(1)&lt;/script&gt;</link></item>
<item><title>relative</title><link>/news/1</link></item>
<item><title>scheme-relative</title><link>//cdn.example.com/news/2</link></item>
<item><title>http</title><link>http://example.com/a?idxno=1</link></item>
<item><title>https</title><link>https://example.com/b</link></item>
</channel></rss>
"""


def test_collect_feed_keeps_only_http_links():
    # Passed as a document, the feed has no base URL: feedparser leaves relative links relative, so they are dropped.
    links = {it["title"]: it["link"] for it in aggregate.collect_feed("T", RSS_LINK_SCHEMES)}
    assert links == {
        "js": "",
        "js-mixed-case": "",
        "vbs": "",
        "data": "",
        "relative": "",
        "scheme-relative": "",
        "http": "http://example.com/a?idxno=1",
        "https": "https://example.com/b",
    }


def test_collect_feed_keeps_relative_links_that_feedparser_resolves():
    # Fetched over HTTP, feedparser resolves relative links against the feed URL; xml:base stands in for it here.
    rss = RSS_LINK_SCHEMES.replace(
        '<rss version="2.0">', '<rss version="2.0" xml:base="https://feeds.example.org/rss/">'
    )
    links = {it["title"]: it["link"] for it in aggregate.collect_feed("T", rss)}
    assert links["relative"] == "https://feeds.example.org/news/1"
    assert links["scheme-relative"] == "https://cdn.example.com/news/2"
    assert links["js"] == links["js-mixed-case"] == links["vbs"] == links["data"] == ""  # a base does not rescue them


def test_build_category_dedups_items_with_dropped_links_by_title():
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title><link>https://example.com/</link><description>d</description>
<item><title>Same title</title><link>javascript:alert(1)</link></item>
<item><title>SAME TITLE</title><link>data:text/html,x</link></item>
<item><title>Other title</title><link>javascript:alert(1)</link></item>
</channel></rss>
"""
    cat = {"key": "k", "label": "L", "feeds": [{"name": "T", "url": rss}]}  # real collect_feed, document as url

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    # Empty link → the key is the lowercased title (RULE7): same title collapses, same unsafe link does not.
    assert [(i["title"], i["link"]) for i in out["items"]] == [("Same title", ""), ("Other title", "")]


# --- feed timeout: collect_feed / build_category / main (DEFECT4, fake server on 127.0.0.1) ---

FEED_TIMEOUT = 0.5  # seconds; stands in for feeds.json feed_timeout_seconds
TIME_BOUND = 5  # a timed-out feed must give up well within this many seconds
SILENT_HOLD = 10  # the fake server drops a connection after this, so a missing timeout fails instead of hanging

RSS_UNDATED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title><link>https://example.com/</link><description>d</description>
<item><title>still here</title><link>https://example.com/ok</link></item>
</channel></rss>
"""


@pytest.fixture
def restore_socket_timeout():
    saved = socket.getdefaulttimeout()
    yield
    socket.setdefaulttimeout(saved)


@pytest.fixture
def silent_server():
    """host:port of a server on 127.0.0.1 that accepts connections and never answers."""
    server = socket.create_server(("127.0.0.1", 0))
    server.settimeout(0.05)
    stop = threading.Event()

    def serve():
        held = []
        while not stop.is_set():
            try:
                held.append((time.monotonic() + SILENT_HOLD, server.accept()[0]))
            except TimeoutError:
                pass
            for drop_at, conn in held:
                if time.monotonic() > drop_at:
                    conn.close()
        for _, conn in held:
            conn.close()
        server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield f"127.0.0.1:{server.getsockname()[1]}"
    stop.set()
    thread.join()


@pytest.mark.usefixtures("restore_socket_timeout")
@pytest.mark.parametrize("scheme", ["http", "https"])  # http: waiting for the response; https: the TLS handshake
def test_collect_feed_times_out_on_silent_server(silent_server, scheme):
    socket.setdefaulttimeout(FEED_TIMEOUT)
    start = time.monotonic()
    # http raises TimeoutError; https comes back from feedparser as bozo with no entries (RuntimeError).
    with pytest.raises((TimeoutError, RuntimeError), match="timed out"):
        aggregate.collect_feed("silent", f"{scheme}://{silent_server}/feed")
    assert time.monotonic() - start < TIME_BOUND


@pytest.mark.usefixtures("restore_socket_timeout")
def test_build_category_skips_a_feed_that_never_answers(silent_server, capsys):
    socket.setdefaulttimeout(FEED_TIMEOUT)
    cat = {
        "key": "robot",
        "label": "로봇",
        "feeds": [
            {"name": "silent", "url": f"http://{silent_server}/feed"},
            {"name": "ok", "url": RSS_UNDATED},  # feedparser takes the document itself: no network
        ],
    }

    start = time.monotonic()
    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    assert time.monotonic() - start < TIME_BOUND
    assert [i["title"] for i in out["items"]] == ["still here"]
    err = capsys.readouterr().err
    assert "[FAIL] robot / silent: timed out" in err and "[OK]   robot / ok: 1 entries" in err


def _run_main(tmp_path, monkeypatch, config):
    (tmp_path / "feeds.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(aggregate, "CONFIG_PATH", str(tmp_path / "feeds.json"))
    monkeypatch.setattr(aggregate, "OUTPUT_PATH", str(tmp_path / "data.json"))
    return aggregate.main()


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_applies_feed_timeout_seconds(tmp_path, monkeypatch, silent_server, capsys):
    feeds = [{"name": "silent", "url": f"http://{silent_server}/feed"}, {"name": "ok", "url": RSS_UNDATED}]
    config = {"feed_timeout_seconds": FEED_TIMEOUT, "categories": [{"key": "ai", "label": "AI", "feeds": feeds}]}

    start = time.monotonic()
    assert _run_main(tmp_path, monkeypatch, config) == 0

    assert time.monotonic() - start < TIME_BOUND
    assert socket.getdefaulttimeout() == FEED_TIMEOUT
    data = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    assert [i["title"] for i in data["categories"][0]["items"]] == ["still here"]
    assert "[FAIL] ai / silent: timed out" in capsys.readouterr().err


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_defaults_feed_timeout_to_30_seconds(tmp_path, monkeypatch):
    _run_main(tmp_path, monkeypatch, {"categories": []})
    assert socket.getdefaulttimeout() == 30


@pytest.mark.usefixtures("restore_socket_timeout")
@pytest.mark.parametrize("value", [0, -1])
def test_main_rejects_non_positive_feed_timeout(tmp_path, monkeypatch, capsys, value):
    # 0 would make every socket non-blocking and fail every feed, not disable the timeout.
    before = socket.getdefaulttimeout()
    assert _run_main(tmp_path, monkeypatch, {"feed_timeout_seconds": value, "categories": []}) == 1
    assert socket.getdefaulttimeout() == before
    assert not (tmp_path / "data.json").exists()
    assert "[ERROR] feed_timeout_seconds" in capsys.readouterr().err


# --- clean_text / dedup_key -------------------------------------------------------------


def test_clean_text_unescapes_and_collapses_whitespace():
    assert aggregate.clean_text("  EV &amp; battery\n\n news  ") == "EV & battery news"
    assert aggregate.clean_text("") == ""


def test_dedup_key_strips_tracking_params_and_trailing_slash():
    assert aggregate.dedup_key("https://x.com/a/?utm_source=rss", "T") == "https://x.com/a"
    assert aggregate.dedup_key("https://x.com/a/", "T") == aggregate.dedup_key("https://x.com/a", "T")
    assert (
        aggregate.dedup_key("https://x.com/a?id=3&UTM_Medium=rss&fbclid=abc&gclid=z", "T")
        == "https://x.com/a?id=3"
    )


def test_dedup_key_keeps_article_identifying_query():
    first = "https://www.aitimes.com/news/articleView.html?idxno=217644"
    second = "https://www.aitimes.com/news/articleView.html?idxno=217647"
    assert aggregate.dedup_key(first, "T") == first
    assert aggregate.dedup_key(first, "T") != aggregate.dedup_key(second, "T")
    assert aggregate.dedup_key(first + "&utm_source=rss", "T") == aggregate.dedup_key(first, "T")


def test_dedup_key_does_not_raise_on_malformed_link():
    assert aggregate.dedup_key(" http://[::1/a?x=1 ", "T") == "http://[::1/a?x=1"


def test_dedup_key_uses_lowercased_title_without_link():
    assert aggregate.dedup_key("", "  Hello World ") == "hello world"
    assert aggregate.dedup_key("   ", "  Hello World ") == "hello world"


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
            _item("Battery news 1", "https://a/1?utm_source=x", now - timedelta(days=1)),
            _item("Battery news 1 dup", "https://a/1", now - timedelta(days=2)),  # same link → dropped
            _item("Motor news", "https://a/2", now),  # fails include filter
            _item("Old battery", "https://a/3", now - timedelta(days=30)),  # older than max_age
            _item("Battery undated", "https://a/4", None),  # kept, sorted last
        ],
        "B": RuntimeError("dead feed"),  # isolated, does not abort the category
        "C": [_item("Battery news 2", "https://c/1", now - timedelta(hours=1))],
    }

    def fake_collect(name, url, tz=UTC):
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


def test_build_category_keeps_articles_that_differ_only_in_query(monkeypatch):
    now = datetime.now(UTC)
    base = "https://www.irobotnews.com/news/articleView.html?idxno="
    entries = [
        _item("Robot 1", base + "1", now - timedelta(hours=1)),
        _item("Robot 2", base + "2", now - timedelta(hours=2)),
        _item("Robot 1 again", base + "1&utm_source=rss", now - timedelta(hours=3)),  # same article
    ]
    monkeypatch.setattr(aggregate, "collect_feed", lambda name, url, tz=UTC: entries)
    cat = {"key": "robot", "label": "로봇", "feeds": [{"name": "로봇신문", "url": "https://r"}]}

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    assert [i["title"] for i in out["items"]] == ["Robot 1", "Robot 2"]
