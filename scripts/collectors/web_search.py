"""Web search collector — DuckDuckGo HTML search, no API key needed."""

import re
import sys
from datetime import datetime, timezone

from .common import fetch_url, make_signal


def collect(competitor: dict, lookback_days: int = 7) -> list:
    name = competitor["name"]
    website = competitor.get("website", "")
    query = competitor.get("job_search_query", name)

    # Build search query focused on recent news/announcements
    search_query = f'"{name}" announcement OR launch OR update OR release OR feature'

    results = _ddg_search(search_query, max_results=8)
    if not results:
        print(f"  [web_search] {name}: no results", file=sys.stderr)
        return []

    signals = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for r in results:
        # Skip results from the competitor's own domain (covered by blog collector)
        if website and _same_domain(r["url"], website):
            continue
        signals.append(make_signal(
            source_type="web_search",
            title=r["title"],
            url=r["url"],
            date=today,
            snippet=r["snippet"],
            metadata={"query": search_query},
        ))

    print(f"  [web_search] {name}: {len(signals)} results")
    return signals


def _ddg_search(query: str, max_results: int = 8) -> list:
    """Scrape DuckDuckGo HTML results (no API key needed)."""
    import urllib.parse
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    resp = fetch_url(url)
    if not resp:
        return []

    results = []
    # Parse result blocks
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        resp.text, re.DOTALL
    )
    for url_raw, title_raw, snippet_raw in blocks[:max_results]:
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()
        # DuckDuckGo wraps URLs — extract actual URL
        url = _extract_ddg_url(url_raw)
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})

    return results


def _extract_ddg_url(raw: str) -> str:
    """DDG uses redirect URLs like //duckduckgo.com/l/?uddg=https%3A%2F%2F..."""
    import urllib.parse
    if raw.startswith("//duckduckgo.com/l/"):
        parsed = urllib.parse.urlparse("https:" + raw)
        params = urllib.parse.parse_qs(parsed.query)
        return urllib.parse.unquote(params.get("uddg", [raw])[0])
    return raw


def _same_domain(url: str, website: str) -> bool:
    import urllib.parse
    try:
        url_host = urllib.parse.urlparse(url).netloc.lstrip("www.")
        site_host = urllib.parse.urlparse(website).netloc.lstrip("www.")
        return url_host == site_host
    except Exception:
        return False
