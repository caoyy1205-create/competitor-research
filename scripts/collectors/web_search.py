"""Web search collector — uses SerpAPI (free tier: 100 searches/month)
or falls back to scraping Bing (more permissive than DDG for datacenter IPs).
"""

import re
import sys
import os
from datetime import datetime, timezone

from .common import fetch_url, make_signal


def collect(competitor: dict, lookback_days: int = 7) -> list:
    name = competitor["name"]
    query = f'"{name}" announcement OR launch OR update OR feature OR release'

    results = _bing_search(query, max_results=8)
    if not results:
        print(f"  [web_search] {name}: no results", file=sys.stderr)
        return []

    website = competitor.get("website", "")
    signals = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for r in results:
        if website and _same_domain(r["url"], website):
            continue
        signals.append(make_signal(
            source_type="web_search",
            title=r["title"],
            url=r["url"],
            date=today,
            snippet=r["snippet"],
            metadata={"query": query},
        ))

    print(f"  [web_search] {name}: {len(signals)} results")
    return signals


def _bing_search(query: str, max_results: int = 8) -> list:
    """Scrape Bing HTML search results."""
    import urllib.parse
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=10"
    resp = fetch_url(url)
    if not resp:
        return []

    results = []
    html = resp.text

    # Bing result pattern: <h2><a href="...">title</a></h2> + <p class="b_lineclamp...">snippet</p>
    blocks = re.findall(
        r'<h2[^>]*><a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a></h2>.*?'
        r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>',
        html, re.DOTALL
    )
    for url_raw, title_raw, snippet_raw in blocks[:max_results]:
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()
        if title and url_raw and "bing.com" not in url_raw:
            results.append({"title": title, "url": url_raw, "snippet": snippet})

    # Fallback: simpler link extraction
    if not results:
        links = re.findall(r'<a[^>]+href="(https?://(?!www\.bing\.com)[^"]+)"[^>]*><h2[^>]*>(.*?)</h2>', html, re.DOTALL)
        for url_raw, title_raw in links[:max_results]:
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            if title:
                results.append({"title": title, "url": url_raw, "snippet": ""})

    return results


def _same_domain(url: str, website: str) -> bool:
    import urllib.parse
    try:
        url_host = urllib.parse.urlparse(url).netloc.lstrip("www.")
        site_host = urllib.parse.urlparse(website).netloc.lstrip("www.")
        return url_host == site_host
    except Exception:
        return False
