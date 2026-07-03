import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("collect_updates", Path("tools/collect_updates.py"))
collector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)

RECENT = collector.TODAY
ARTICLE_URL = "https://example-media.test/articles/depot-branding-case"
FEED_URL = "https://example-media.test/feed.xml"
ARTICLE_HTML = f"""
<html><head>
<meta property="og:title" content="Depot показал кейс про брендинг упаковки" />
<meta name="description" content="Материал о маркетинге, айдентике и упаковке конкурента Serenity." />
<meta property="article:published_time" content="{RECENT}T10:00:00+03:00" />
</head><body><h1>Depot показал кейс про брендинг упаковки</h1><p>Depot развивает маркетинг и айдентику.</p></body></html>
"""
FEED_XML = f"""<?xml version="1.0" encoding="utf-8"?>
<rss><channel><item><title>Depot показал кейс про брендинг упаковки</title><link>{ARTICLE_URL}</link><pubDate>{RECENT}</pubDate><description>Маркетинг и брендинг</description></item></channel></rss>
"""


def fake_fetch(url):
    if url == FEED_URL:
        return FEED_XML, None
    if url == ARTICLE_URL:
        return ARTICLE_HTML, None
    return "", "unexpected url"


def test_direct_media_collects_competitor_article_and_not_client_brand(monkeypatch):
    monkeypatch.setattr(collector, "fetch", fake_fetch)
    monkeypatch.setattr(collector.time, "sleep", lambda _seconds: None)
    media_sources = [{"name": "Example Media", "domain": "example-media.test", "enabled": True, "feed_url": FEED_URL, "search_url": "", "section_url": "https://example-media.test/articles/", "notes": "mock"}]
    competitors = [{"rank": 1, "name": "Depot", "site": "https://depotwpf.ru"}]
    status = {"notes": []}
    findings = []
    collector.collect_media_direct(media_sources, competitors, status, findings, set(), [10])

    assert len(findings) == 1
    assert findings[0]["source_type"] == "СМИ"
    assert findings[0]["channel"] == "СМИ"
    assert findings[0]["media_source"] == "Example Media"
    assert findings[0]["competitor"] == "Depot"
    assert findings[0]["monitor_scope"] == "competitor"
    assert all(item.get("monitor_scope") != "client_brand" for item in findings)
    assert "client_brands" not in collector.Path("tools/collect_updates.py").read_text(encoding="utf-8")
