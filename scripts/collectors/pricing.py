"""Pricing collector — diffs competitor pricing page against stored snapshot."""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .common import fetch_url, extract_article_text, make_signal

SNAPSHOTS_DIR = Path(__file__).parent.parent.parent / "data" / "snapshots"


def collect(competitor: dict, lookback_days: int = 7) -> list:
    pricing_url = competitor.get("pricing_url")
    if not pricing_url:
        return []

    name = competitor["name"]
    comp_id = competitor["id"]
    snapshot_path = SNAPSHOTS_DIR / f"{comp_id}_pricing.txt"
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    resp = fetch_url(pricing_url)
    if not resp:
        print(f"  [pricing] {name}: failed to fetch {pricing_url}", file=sys.stderr)
        return []

    current_text = _extract_pricing_text(resp.text)
    if not current_text:
        return []

    signals = []
    if snapshot_path.exists():
        previous_text = snapshot_path.read_text(encoding="utf-8")
        diff_score = _diff_score(previous_text, current_text)
        if diff_score > 0.05:  # >5% change
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            signals.append(make_signal(
                source_type="pricing",
                title=f"{name} — pricing page changed",
                url=pricing_url,
                date=today,
                snippet=f"Pricing page changed significantly (~{int(diff_score*100)}% different from last snapshot).",
                metadata={"diff_score": round(diff_score, 3)},
            ))
            print(f"  [pricing] {name}: change detected ({int(diff_score*100)}%)")
        else:
            print(f"  [pricing] {name}: no significant change")
    else:
        print(f"  [pricing] {name}: first snapshot saved")

    # Always update snapshot
    snapshot_path.write_text(current_text, encoding="utf-8")
    return signals


def _extract_pricing_text(html: str) -> str:
    """Extract pricing-relevant text: numbers, plan names, feature lists."""
    # Remove scripts/styles
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ",
                  html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    # Keep only lines with pricing signals: $, numbers, plan keywords
    lines = text.split(". ")
    relevant = [l for l in lines if re.search(r'\$|€|£|per month|per year|free|pro|team|enterprise|\d+/mo', l, re.IGNORECASE)]
    return " ".join(relevant)[:5000]


def _diff_score(old: str, new: str) -> float:
    """Simple word-level diff ratio (0=identical, 1=completely different)."""
    old_words = set(old.lower().split())
    new_words = set(new.lower().split())
    if not old_words and not new_words:
        return 0.0
    union = old_words | new_words
    intersection = old_words & new_words
    return 1 - len(intersection) / len(union)
