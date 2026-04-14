"""Shared utilities for all collectors."""

import html as html_module
import re
import time

import requests

FETCH_TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CompetitorResearch-Bot/1.0)"}


def fetch_url(url, retries=2):
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=FETCH_TIMEOUT, headers=HEADERS)
            if resp.status_code == 429:
                if attempt == 0:
                    time.sleep(5)
                    continue
                return None
            resp.raise_for_status()
            return resp
        except Exception:
            return None
    return None


def extract_article_text(html):
    for tag in ("script", "style", "nav", "header", "footer", "aside", "figure"):
        html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", html,
                      flags=re.DOTALL | re.IGNORECASE)
    candidates = [
        r'<article[^>]*>(.*?)</article>',
        r'<main[^>]*>(.*?)</main>',
        r'<div[^>]+class="[^"]*\b(?:post-content|entry-content|article-body|article-content|post-body)\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]+class="[^"]*\b(?:post|entry|article|content|body)\b[^"]*"[^>]*>(.*?)</div>',
    ]
    best = ""
    for pattern in candidates:
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if m:
            block = m.group(1) if m.lastindex else m.group(0)
            text = clean_text(re.sub(r"<[^>]+>", " ", block))
            if len(text) > len(best):
                best = text
    if not best:
        best = clean_text(re.sub(r"<[^>]+>", " ", html))
    return best


def clean_text(text):
    text = html_module.unescape(text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r'([.!?]) ([A-Z\u4e00-\u9fa5])', r'\1\n\n\2', text)
    return text.strip()


def make_signal(source_type, title, url, date, snippet, raw="", metadata=None):
    return {
        "source_type": source_type,
        "title": title,
        "url": url,
        "date": date,
        "snippet": snippet[:500],
        "raw": raw,
        "metadata": metadata or {},
    }
