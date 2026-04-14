"""Blog/RSS collector — fetches recent posts from a competitor's RSS feed."""

import sys
from datetime import datetime, timezone, timedelta

import feedparser
from dateutil import parser as dateparser

from .common import fetch_url, extract_article_text, make_signal


def collect(competitor: dict, lookback_days: int = 7) -> list:
    rss_url = competitor.get("blog_rss")
    if not rss_url:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    signals = []

    resp = fetch_url(rss_url)
    if not resp:
        print(f"  [blog] failed to fetch {rss_url}", file=sys.stderr)
        return []

    feed = feedparser.parse(resp.content)
    for entry in feed.entries:
        pub = _parse_date(entry)
        if pub is None or pub < cutoff:
            continue

        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if not title or not link:
            continue

        # Try to get full text
        raw = ""
        article_resp = fetch_url(link)
        if article_resp and len(article_resp.text) > 200:
            raw = extract_article_text(article_resp.text)

        snippet = _get_snippet(entry) or raw[:300]

        signals.append(make_signal(
            source_type="blog",
            title=title,
            url=link,
            date=pub.strftime("%Y-%m-%d"),
            snippet=snippet,
            raw=raw,
            metadata={"feed": feed.feed.get("title", "")},
        ))

    print(f"  [blog] {competitor['name']}: {len(signals)} posts")
    return signals


def _parse_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for attr in ("published", "updated"):
        s = getattr(entry, attr, None)
        if s:
            try:
                dt = dateparser.parse(s)
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return None


def _get_snippet(entry):
    import re, html as html_module
    text = getattr(entry, "summary", "") or ""
    if not text:
        content = getattr(entry, "content", [])
        if content:
            text = content[0].get("value", "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= 300:
        return text
    chunk = text[:300]
    last = max(chunk.rfind(". "), chunk.rfind("! "), chunk.rfind("? "))
    return chunk[:last + 1] if last > 50 else chunk
