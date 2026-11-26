"""Unit tests for the pure helpers in aggregate.py (no external network)."""

import copy
import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import feedparser
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


@pytest.mark.parametrize(
    ("tz", "raw"),
    [
        ("+09:00", "0001-01-01 00:00:00"),
        ("-05:00", "9999-12-31 23:59:59"),
        ("-05:00", "Fri, 31 Dec 9999 23:59:59"),  # RFC 2822: reaches the raw-string path of parse_date
    ],
)
def test_collect_feed_keeps_the_feed_when_a_date_leaves_the_range_in_its_tz(tz, raw):
    # Moving these naive times into UTC leaves datetime's range (DEFECT7): that item is undated, the feed still works.
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>'
        f"<item><title>edge</title><link>https://example.com/e</link><pubDate>{raw}</pubDate></item>"
        "<item><title>normal</title><link>https://example.com/n</link><pubDate>2026-11-21 11:51:51</pubDate></item>"
        "</channel></rss>"
    )
    items = {it["title"]: it["dt"] for it in aggregate.collect_feed("K", rss, aggregate.parse_tz(tz))}
    assert items["edge"] is None
    assert items["normal"] is not None and items["normal"].utcoffset() == timedelta(0)


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


def test_build_category_skips_only_the_feed_with_invalid_tz_when_called_directly(monkeypatch, capsys):
    # main never gets here with a bad tz: the feeds.json check stops the run first (RULE6, RULE17,
    # test_main_stops_before_collecting_on_an_invalid_config). build_category on its own still isolates the feed.
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


# --- malformed feed: the bozo rule in collect_feed / build_category (RULE4) -------------

RSS_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title><link>https://example.com/</link><description>d</description>
"""
# Both documents are cut off (no closing tags), so neither is well-formed XML: feedparser sets bozo on both.
RSS_CUT_BEFORE_ANY_ITEM = RSS_HEAD
RSS_CUT_AFTER_ONE_ITEM = RSS_HEAD + "<item><title>kept anyway</title><link>https://example.com/1</link></item>\n"


def test_collect_feed_fails_a_malformed_feed_only_when_it_has_no_entries():
    assert feedparser.parse(RSS_CUT_BEFORE_ANY_ITEM).bozo and feedparser.parse(RSS_CUT_AFTER_ONE_ITEM).bozo

    with pytest.raises(RuntimeError, match="^bozo: "):
        aggregate.collect_feed("T", RSS_CUT_BEFORE_ANY_ITEM)

    # bozo alone is not a failure: some working feeds come back with bozo=1
    items = aggregate.collect_feed("T", RSS_CUT_AFTER_ONE_ITEM)
    assert [(i["title"], i["link"]) for i in items] == [("kept anyway", "https://example.com/1")]


def test_build_category_logs_fail_for_a_malformed_feed_without_entries(capsys):
    feeds = [{"name": "broken", "url": RSS_CUT_BEFORE_ANY_ITEM}, {"name": "partial", "url": RSS_CUT_AFTER_ONE_ITEM}]
    cat = {"key": "k", "label": "L", "feeds": feeds}  # real collect_feed, documents as urls

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    assert [(i["title"], i["source"]) for i in out["items"]] == [("kept anyway", "partial")]
    err = capsys.readouterr().err
    assert "[FAIL] k / broken: bozo: " in err and "[OK]   k / partial: 1 entries" in err


# --- feed timeout: collect_feed / build_category / main (DEFECT4, fake server on 127.0.0.1) ---

FEED_TIMEOUT = 0.5  # seconds; the socket timeout main sets from feeds.json feed_timeout_seconds
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


def _run_main(tmp_path, monkeypatch, config, argv=None):
    (tmp_path / "feeds.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(aggregate, "CONFIG_PATH", str(tmp_path / "feeds.json"))
    monkeypatch.setattr(aggregate, "OUTPUT_PATH", str(tmp_path / "data.json"))
    return aggregate.main(argv)


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_applies_feed_timeout_seconds(tmp_path, monkeypatch, silent_server, capsys):
    # feeds.json urls must be http(s) URLs (RULE17): "ok" is served from a document, "silent" goes over the network.
    real_collect = aggregate.collect_feed
    documents = {"https://ok.example/feed": RSS_UNDATED}
    monkeypatch.setattr(
        aggregate, "collect_feed", lambda name, url, tz=UTC: real_collect(name, documents.get(url, url), tz)
    )
    feeds = [{"name": "silent", "url": f"http://{silent_server}/feed"}, {"name": "ok", "url": "https://ok.example/feed"}]
    # whole seconds only (RULE17)
    config = {"feed_timeout_seconds": 1, "categories": [{"key": "ai", "label": "AI", "feeds": feeds}]}

    start = time.monotonic()
    assert _run_main(tmp_path, monkeypatch, config) == 0

    assert time.monotonic() - start < TIME_BOUND
    assert socket.getdefaulttimeout() == 1
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


# --- zero items: nothing is published (RULE16) ------------------------------------------


def _fail(name, url, tz=UTC):
    raise RuntimeError("down")


def _filtered_out(name, url, tz=UTC):
    return [{"title": "x", "link": "https://example.com/x", "source": name, "summary": "", "dt": None}]


@pytest.mark.usefixtures("restore_socket_timeout")
@pytest.mark.parametrize(
    ("collect", "categories"),
    [
        (
            _fail,
            [{"key": "ai", "label": "AI", "feeds": [{"name": "a", "url": "https://a/1"}, {"name": "b", "url": "https://b/1"}]}],
        ),
        (
            _filtered_out,
            [{"key": "ai", "label": "AI", "include_keywords": ["nomatch"], "feeds": [{"name": "a", "url": "https://a/1"}]}],
        ),
        (_fail, []),
    ],
    ids=["all-feeds-fail", "all-items-filtered", "no-categories"],
)
def test_main_publishes_nothing_when_zero_items(tmp_path, monkeypatch, capsys, collect, categories):
    monkeypatch.setattr(aggregate, "collect_feed", collect)
    (tmp_path / "data.json").write_text("previous", encoding="utf-8")  # stands in for a local leftover

    assert _run_main(tmp_path, monkeypatch, {"categories": categories}) == 1

    assert (tmp_path / "data.json").read_text(encoding="utf-8") == "previous"
    assert "[ERROR] 수집된 항목이 0건" in capsys.readouterr().err


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_writes_data_json_when_any_item_is_collected(tmp_path, monkeypatch):
    monkeypatch.setattr(aggregate, "collect_feed", _filtered_out)
    categories = [
        {"key": "ai", "label": "AI", "feeds": [{"name": "a", "url": "https://a/1"}]},
        {"key": "robot", "label": "로봇", "include_keywords": ["nomatch"], "feeds": [{"name": "b", "url": "https://b/1"}]},
    ]

    assert _run_main(tmp_path, monkeypatch, {"categories": categories}) == 0

    data = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    # one empty category does not stop the run: both are published, the empty one with count 0
    assert [(c["key"], c["count"]) for c in data["categories"]] == [("ai", 1), ("robot", 0)]


# --- feeds.json format check: validate_config / load_config / main / --check (RULE17) ---

REPO_ROOT = Path(aggregate.__file__).resolve().parent
MINIMAL_CONFIG = {"categories": [{"key": "ai", "label": "AI", "feeds": [{"name": "A", "url": "https://a.example/feed"}]}]}
MISSING = object()  # _edited: remove the key instead of setting it
CAT = ("categories", 0)
FEED = (*CAT, "feeds", 0)
CAT_AT = "categories[0](ai)"
FEED_AT = f"{CAT_AT}.feeds[0](A)"


def _edited(path, value):
    """A copy of MINIMAL_CONFIG with the value at path set (or removed with MISSING); () replaces the whole file."""
    if not path:
        return value
    config = copy.deepcopy(MINIMAL_CONFIG)
    *parents, last = path
    target = config
    for step in parents:
        target = target[step]
    if value is MISSING:
        del target[last]
    else:
        target[last] = value
    return config


def _never_called(calls):
    return lambda *args, **kwargs: calls.append(args)


@pytest.mark.parametrize(
    "config",
    [
        MINIMAL_CONFIG,
        {
            **aggregate.LIMIT_DEFAULTS,
            "categories": [
                {
                    "key": "ai",
                    "label": "AI",
                    "include_keywords": ["robot", "로봇", " ev "],
                    "exclude_keywords": [],
                    "feeds": [
                        {"name": "Same", "url": "https://a.example/feed", "tz": "+09:00"},
                        # the same name twice is allowed: both feeds share one per-feed cap (RULE8)
                        {"name": "Same", "url": "HTTP://B.example:8080/rss?x=1", "tz": "-05:30"},
                    ],
                },
                {"key": "robot", "label": "로봇", "feeds": []},
            ],
        },
        {"categories": []},  # nothing to collect is RULE16's case, not a format error
    ],
    ids=["minimal", "every-key", "no-categories"],
)
def test_validate_config_accepts_a_valid_config(config):
    assert aggregate.validate_config(config) == []


def test_validate_config_accepts_the_real_feeds_json():
    path = REPO_ROOT / "feeds.json"
    assert aggregate.validate_config(json.loads(path.read_text(encoding="utf-8"))) == []
    assert aggregate.load_config(str(path)) is not None  # also free of repeated keys


BAD_FEED_URLS = {
    "empty": "",  # was collected as "[OK] 0 entries" (GATE0 E5)
    "ftp": "ftp://a.example/feed",
    "javascript": "javascript:alert(1)",
    "no-scheme": "a.example/feed",
    "no-host": "https://",
    "no-hostname": "http://user@/feed",
    "padded": " https://a.example/feed",
    "null": None,
}
BAD_TZS = {"KST": "KST", "+9": "+9", "+0900": "+0900", "iana": "Asia/Seoul", "null": None, "number": 9}


@pytest.mark.parametrize(
    ("path", "value", "where"),
    [
        pytest.param((), ["categories"], "최상위", id="root-not-object"),
        pytest.param(("categories",), MISSING, "categories", id="categories-missing"),
        pytest.param(("categories",), {"key": "ai"}, "categories", id="categories-not-list"),
        pytest.param(("max_age_day",), 14, "max_age_day", id="top-unknown-key"),
        pytest.param(CAT, "ai", "categories[0]", id="category-not-object"),
        pytest.param((*CAT, "key"), MISSING, "categories[0].key", id="key-missing"),
        pytest.param((*CAT, "key"), "", "categories[0].key", id="key-empty"),
        pytest.param((*CAT, "key"), 1, "categories[0].key", id="key-not-string"),
        pytest.param((*CAT, "label"), MISSING, f"{CAT_AT}.label", id="label-missing"),
        pytest.param((*CAT, "label"), None, f"{CAT_AT}.label", id="label-null"),
        pytest.param((*CAT, "feeds"), MISSING, f"{CAT_AT}.feeds", id="feeds-missing"),
        pytest.param((*CAT, "feeds"), {"name": "A", "url": "https://a/1"}, f"{CAT_AT}.feeds", id="feeds-not-list"),
        pytest.param((*CAT, "include_keywords"), "robot", f"{CAT_AT}.include_keywords", id="include-string"),
        pytest.param((*CAT, "exclude_keywords"), "crypto", f"{CAT_AT}.exclude_keywords", id="exclude-string"),
        pytest.param((*CAT, "include_keywords"), None, f"{CAT_AT}.include_keywords", id="include-null"),
        pytest.param((*CAT, "include_keywords"), ["robot", 3], f"{CAT_AT}.include_keywords[1]", id="keyword-number"),
        pytest.param((*CAT, "exclude_keywords"), ["crypto", " "], f"{CAT_AT}.exclude_keywords[1]", id="keyword-blank"),
        pytest.param((*CAT, "include_keyword"), ["robot"], f"{CAT_AT}.include_keyword", id="category-unknown-key"),
        pytest.param(FEED, "https://a.example/feed", f"{CAT_AT}.feeds[0]", id="feed-not-object"),
        pytest.param((*FEED, "name"), MISSING, f"{CAT_AT}.feeds[0].name", id="name-missing"),
        pytest.param((*FEED, "name"), "  ", f"{CAT_AT}.feeds[0].name", id="name-blank"),
        pytest.param((*FEED, "url"), MISSING, f"{FEED_AT}.url", id="url-missing"),
        *[pytest.param((*FEED, "url"), v, f"{FEED_AT}.url", id=f"url-{k}") for k, v in BAD_FEED_URLS.items()],
        *[pytest.param((*FEED, "tz"), v, f"{FEED_AT}.tz", id=f"tz-{k}") for k, v in BAD_TZS.items()],
        pytest.param((*FEED, "timezone"), "+09:00", f"{FEED_AT}.timezone", id="feed-unknown-key"),
    ],
)
def test_validate_config_reports_each_error_class(path, value, where):
    errors = aggregate.validate_config(_edited(path, value))
    assert len(errors) == 1 and errors[0].startswith(f"{where}: "), errors


@pytest.mark.parametrize(
    "value",
    [0, -1, "14", "two weeks", None, 14.0, 0.5, True, [14]],
    ids=["zero", "negative", "numeric-string", "string", "null", "float-integral", "float", "bool", "list"],
)
@pytest.mark.parametrize("key", list(aggregate.LIMIT_DEFAULTS))
def test_validate_config_rejects_a_limit_that_is_not_a_positive_integer(key, value):
    errors = aggregate.validate_config({**MINIMAL_CONFIG, key: value})
    assert errors == [f"{key}: 0보다 큰 정수여야 합니다(값: {json.dumps(value)})"]


def test_validate_config_rejects_duplicate_category_keys():
    cat = MINIMAL_CONFIG["categories"][0]
    config = {"categories": [cat, {**cat, "label": "AI 2"}, {**cat, "key": "robot"}, cat]}

    assert aggregate.validate_config(config) == [
        "categories[1](ai).key: 같은 key가 앞에 있습니다(categories[0])",
        "categories[3](ai).key: 같은 key가 앞에 있습니다(categories[0])",
    ]


EVERY_LEVEL_WRONG = {
    "max_age_days": "14",
    "max_age_day": 14,
    "categories": [
        {
            "key": "ai",
            "label": "AI",
            "include_keywords": "robot",
            "feeds": [{"name": "A", "url": "", "tz": "KST"}, {"url": "https://b.example/feed", "timezone": "+09:00"}],
        },
        {"key": "ai", "label": "", "exclude_keywords": ["ev", 3], "feeds": "https://c.example/feed"},
        "robot",
    ],
}
EVERY_LEVEL_WRONG_ERRORS = [
    "max_age_day: 알 수 없는 키입니다"
    "(쓸 수 있는 키: max_age_days, max_items_per_category, max_items_per_feed, feed_timeout_seconds, categories)",
    'max_age_days: 0보다 큰 정수여야 합니다(값: "14")',
    'categories[0](ai).include_keywords: 문자열 목록이어야 합니다(값: "robot")',
    'categories[0](ai).feeds[0](A).url: http:// 또는 https://로 시작하고 호스트가 있는 URL이어야 합니다(값: "")',
    'categories[0](ai).feeds[0](A).tz: +09:00 같은 ±HH:MM 고정 오프셋이어야 합니다(값: "KST")',
    "categories[0](ai).feeds[1].timezone: 알 수 없는 키입니다(쓸 수 있는 키: name, url, tz)",
    "categories[0](ai).feeds[1].name: 필수 키가 없습니다",
    'categories[1](ai).label: 비어 있지 않은 문자열이어야 합니다(값: "")',
    "categories[1](ai).exclude_keywords[1]: 비어 있지 않은 문자열이어야 합니다(값: 3)",
    'categories[1](ai).feeds: 목록이어야 합니다(값: "https://c.example/feed")',
    "categories[1](ai).key: 같은 key가 앞에 있습니다(categories[0])",
    'categories[2]: 객체여야 합니다(값: "robot")',
]


def test_validate_config_reports_every_error_together():
    assert aggregate.validate_config(EVERY_LEVEL_WRONG) == EVERY_LEVEL_WRONG_ERRORS


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_logs_every_error_on_its_own_line(tmp_path, monkeypatch, capsys):
    assert _run_main(tmp_path, monkeypatch, EVERY_LEVEL_WRONG) == 1

    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("[ERROR]")]
    assert lines[:-1] == [f"[ERROR] {error}" for error in EVERY_LEVEL_WRONG_ERRORS]
    assert lines[-1].startswith(f"[ERROR] {tmp_path / 'feeds.json'} 형식 오류 12건: 수집하지 않고 끝냅니다")


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_keeps_each_error_on_one_line_when_names_hold_control_characters(tmp_path, monkeypatch, capsys):
    # A line break in a key, name, unknown key or value must not start a line that reads like another log entry.
    feed = {"name": "A\n[OK] fake", "url": "x [OK] fake"}
    config = {"categories": [{"key": "k\r[OK]", "label": "L", "feeds": [feed], "include\nkeywords": []}]}

    assert _run_main(tmp_path, monkeypatch, config) == 1

    lines = capsys.readouterr().err.splitlines()  # splitlines also breaks on \r and U+2028
    assert lines and all(line.startswith("[ERROR] ") for line in lines), lines
    assert any("categories[0](k\\r[OK]).feeds[0](A\\n[OK] fake).url: " in line for line in lines)
    assert any("categories[0](k\\r[OK]).include\\nkeywords: 알 수 없는 키입니다" in line for line in lines)


@pytest.mark.usefixtures("restore_socket_timeout")
@pytest.mark.parametrize(
    ("path", "value", "where"),
    [
        # RULE6: a bad tz used to skip only its feed; now the whole run stops before collecting (RULE17)
        pytest.param((*FEED, "tz"), "KST", f"{FEED_AT}.tz", id="invalid-tz"),
        pytest.param((*CAT, "include_keywords"), "robot", f"{CAT_AT}.include_keywords", id="string-keywords"),
        pytest.param(("max_age_days",), "14", "max_age_days", id="numeric-string-limit"),
        pytest.param(("categories",), MISSING, "categories", id="no-categories-key"),
    ],
)
def test_main_stops_before_collecting_on_an_invalid_config(tmp_path, monkeypatch, capsys, path, value, where):
    calls = []
    monkeypatch.setattr(aggregate, "build_category", _never_called(calls))
    monkeypatch.setattr(aggregate, "collect_feed", _never_called(calls))
    (tmp_path / "data.json").write_text("previous", encoding="utf-8")  # stands in for a local leftover
    before = socket.getdefaulttimeout()

    assert _run_main(tmp_path, monkeypatch, _edited(path, value)) == 1

    assert calls == []  # no category built, no feed requested
    assert socket.getdefaulttimeout() == before
    assert (tmp_path / "data.json").read_text(encoding="utf-8") == "previous"
    err = capsys.readouterr().err
    assert f"[ERROR] {where}: " in err and "형식 오류 1건" in err


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(None, "feeds.json", id="missing-file"),
        pytest.param(b'{"categories": [}', "Expecting value", id="json-syntax"),
        pytest.param('{"categories": [{"label": "로봇"}]}'.encode("cp949"), "codec can't decode", id="not-utf8"),
        pytest.param(
            b'{"categories": [{"key": "ai", "label": "AI", "feeds": [], "feeds": []}]}',
            '같은 키가 두 번 있습니다: "feeds"',
            id="repeated-key",
        ),
    ],
)
def test_main_reports_an_unreadable_feeds_json(tmp_path, monkeypatch, capsys, content, reason):
    if content is not None:
        (tmp_path / "feeds.json").write_bytes(content)
    monkeypatch.setattr(aggregate, "CONFIG_PATH", str(tmp_path / "feeds.json"))
    monkeypatch.setattr(aggregate, "OUTPUT_PATH", str(tmp_path / "data.json"))

    assert aggregate.main() == 1

    assert not (tmp_path / "data.json").exists()
    err = capsys.readouterr().err
    assert "[ERROR] " in err and " 로드 실패: " in err and reason in err


@pytest.mark.usefixtures("restore_socket_timeout")
def test_main_check_only_validates(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(aggregate, "build_category", _never_called(calls))
    before = socket.getdefaulttimeout()

    assert _run_main(tmp_path, monkeypatch, MINIMAL_CONFIG, ["--check"]) == 0
    assert calls == [] and socket.getdefaulttimeout() == before
    assert not (tmp_path / "data.json").exists()
    assert "[DONE] " in (err := capsys.readouterr().err) and "형식 검사 통과: 카테고리 1개, 피드 1개" in err

    assert _run_main(tmp_path, monkeypatch, _edited((*FEED, "tz"), "KST"), ["--check"]) == 1
    assert calls == [] and not (tmp_path / "data.json").exists()
    assert f"[ERROR] {FEED_AT}.tz: " in capsys.readouterr().err


@pytest.mark.parametrize("valid", [True, False], ids=["real-feeds-json", "invalid"])
def test_check_from_the_command_line(tmp_path, valid):
    # What CI runs: `python aggregate.py --check` in the directory that holds feeds.json (here a copy, so a
    # --check that went on to collect would show up as [CATEGORY] lines and a data.json in tmp_path).
    if valid:
        (tmp_path / "feeds.json").write_bytes((REPO_ROOT / "feeds.json").read_bytes())
    else:
        (tmp_path / "feeds.json").write_text(json.dumps(_edited(("max_age_days",), 0)), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "aggregate.py"), "--check"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        encoding="utf-8",
        timeout=60,
    )

    if valid:
        assert result.returncode == 0 and "[DONE] feeds.json 형식 검사 통과" in result.stderr, result.stderr
    else:
        assert result.returncode == 1 and "[ERROR] max_age_days: " in result.stderr, result.stderr
    assert "[CATEGORY]" not in result.stderr
    assert not (tmp_path / "data.json").exists()


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


# --- keyword filter: passes_filters / build_category (RULE5) ----------------------------


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


def test_build_category_matches_keywords_in_the_summary():
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title><link>https://example.com/</link><description>d</description>
<item><title>Update</title><link>https://example.com/1</link><description>A new Battery plant</description></item>
<item><title>Outlook</title><link>https://example.com/2</link><description>battery and crypto</description></item>
<item><title>Weather</title><link>https://example.com/3</link><description>sunny</description></item>
</channel></rss>
"""
    cat = {
        "key": "k",
        "label": "L",
        "include_keywords": ["battery"],
        "exclude_keywords": ["crypto"],
        "feeds": [{"name": "T", "url": rss}],  # real collect_feed: the RSS <description> becomes the summary
    }

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    # The keywords are only in the summaries: include matches the first item, exclude drops the second.
    assert [i["title"] for i in out["items"]] == ["Update"]


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


def _feeds_by_name(monkeypatch, feeds):
    monkeypatch.setattr(aggregate, "collect_feed", lambda name, url, tz=UTC: feeds[name])
    return {"key": "k", "label": "L", "feeds": [{"name": n, "url": f"https://{n}"} for n in feeds]}


@pytest.mark.parametrize("order", [("older", "newer"), ("newer", "older")])
def test_build_category_dedup_keeps_the_copy_from_the_feed_listed_first(monkeypatch, order):
    now = datetime.now(UTC)
    copies = {  # the same article in two feeds: equal dedup keys (RULE7)
        "older": [_item("Story", "https://news.example/a/", now - timedelta(hours=3), source="older")],
        "newer": [_item("Story", "https://news.example/a?utm_source=rss", now - timedelta(hours=1), source="newer")],
    }
    cat = _feeds_by_name(monkeypatch, {name: copies[name] for name in order})

    out = aggregate.build_category(cat, max_age_days=14, max_items=10)

    # the first collected copy stays, whether it is the older or the newer one
    assert [i["source"] for i in out["items"]] == [order[0]]


def test_build_category_caps_each_feed_before_the_category(monkeypatch):
    now = datetime.now(UTC)
    # "big" posts every 10 minutes, "small" every 2 days: without a per-feed cap "big" fills the category.
    big = [_item(f"big {i}", f"https://big/{i}", now - timedelta(minutes=10 * i), source="big") for i in range(12)]
    small = [_item(f"small {i}", f"https://s/{i}", now - timedelta(days=2 * i + 1), source="small") for i in range(3)]
    cat = _feeds_by_name(monkeypatch, {"big": big, "small": small})

    uncapped = aggregate.build_category(cat, max_age_days=14, max_items=10)
    assert [i["source"] for i in uncapped["items"]] == ["big"] * 10

    out = aggregate.build_category(cat, max_age_days=14, max_items=10, max_per_feed=4)
    titles = [i["title"] for i in out["items"]]
    assert titles == ["big 0", "big 1", "big 2", "big 3", "small 0", "small 1", "small 2"]  # newest first, 4 + 3

    tight = aggregate.build_category(cat, max_age_days=14, max_items=5, max_per_feed=4)
    assert [i["title"] for i in tight["items"]] == titles[:5]  # category cap applies after the per-feed cap


def test_build_category_per_feed_cap_counts_only_kept_items(monkeypatch):
    now = datetime.now(UTC)
    a = [
        _item("a dup", "https://x/1", now - timedelta(hours=1), source="a"),  # loses dedup to b's copy
        _item("a 1", "https://a/1", now - timedelta(hours=2), source="a"),
        _item("a old", "https://a/old", now - timedelta(days=30), source="a"),  # older than max_age_days
        _item("a 2", "https://a/2", now - timedelta(hours=3), source="a"),
        _item("a undated", "https://a/u", None, source="a"),
    ]
    b = [_item("b 1", "https://x/1", now, source="b")]
    cat = _feeds_by_name(monkeypatch, {"b": b, "a": a})  # b is collected first, so its copy wins

    out = aggregate.build_category(cat, max_age_days=14, max_items=10, max_per_feed=2)

    assert [i["title"] for i in out["items"]] == ["b 1", "a 1", "a 2"]  # dropped items did not use a's 2 slots


def test_build_category_per_feed_cap_applies_after_the_keyword_filter(monkeypatch):
    now = datetime.now(UTC)
    # the 10 newest posts do not match the include keyword; they must not take the feed's slots
    a = [_item(f"ev news {i}", f"https://a/n{i}", now - timedelta(minutes=i), source="a") for i in range(10)]
    a += [_item(f"robot {i}", f"https://a/r{i}", now - timedelta(days=1, minutes=i), source="a") for i in range(3)]
    cat = _feeds_by_name(monkeypatch, {"a": a})
    cat["include_keywords"] = ["robot"]

    out = aggregate.build_category(cat, max_age_days=14, max_items=10, max_per_feed=2)

    assert [i["title"] for i in out["items"]] == ["robot 0", "robot 1"]


def test_build_category_per_feed_cap_keeps_the_newest_of_an_oldest_first_feed(monkeypatch):
    now = datetime.now(UTC)
    # the feed lists its oldest post first and an undated one before everything
    a = [_item("undated", "https://a/u", None, source="a")]
    a += [_item(f"o{i}", f"https://a/{i}", now - timedelta(hours=12 - i), source="a") for i in range(12)]
    cat = _feeds_by_name(monkeypatch, {"a": a})

    out = aggregate.build_category(cat, max_age_days=14, max_items=10, max_per_feed=4)

    assert [i["title"] for i in out["items"]] == ["o11", "o10", "o9", "o8"]


def test_build_category_feeds_with_the_same_name_share_the_cap(monkeypatch):
    now = datetime.now(UTC)

    def posts(feed, offset):
        when = [now - timedelta(hours=2 * i + offset) for i in range(6)]
        return [_item(f"{feed} {i}", f"https://{feed}/{i}", dt, "Same") for i, dt in enumerate(when)]

    by_url = {"https://one": posts("one", 0), "https://two": posts("two", 1)}
    monkeypatch.setattr(aggregate, "collect_feed", lambda name, url, tz=UTC: by_url[url])
    cat = {"key": "k", "label": "L", "feeds": [{"name": "Same", "url": u} for u in by_url]}

    out = aggregate.build_category(cat, max_age_days=14, max_items=40, max_per_feed=8)

    # counted by source name, as the dashboard shows it: 8 in total, the newest 8 of both feeds
    assert [i["title"] for i in out["items"]] == [f"{f} {i}" for i in range(4) for f in ("one", "two")]


@pytest.mark.usefixtures("restore_socket_timeout")
@pytest.mark.parametrize(
    ("limits", "expected"),
    [({}, (14, 40, 8)), ({"max_age_days": 3, "max_items_per_category": 5, "max_items_per_feed": 2}, (3, 5, 2))],
    ids=["defaults", "from-feeds-json"],
)
def test_main_passes_max_items_per_feed(tmp_path, monkeypatch, limits, expected):
    # All three limits reach build_category in the right place; a missing key takes its default (RULE3, RULE8).
    seen = []

    def fake_build(cat, max_age_days, max_items, max_per_feed=None):
        seen.append((max_age_days, max_items, max_per_feed))
        return {"key": cat["key"], "label": cat["label"], "count": 1, "items": []}

    monkeypatch.setattr(aggregate, "build_category", fake_build)
    config = {**limits, "categories": [{"key": "k", "label": "L", "feeds": []}]}

    _run_main(tmp_path, monkeypatch, config)

    assert seen == [expected]
