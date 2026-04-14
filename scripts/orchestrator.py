#!/usr/bin/env python3
"""
Competitor Research Orchestrator.
Loads competitors.yaml, runs all collectors, calls synthesizer, writes JSON.
Usage: python scripts/orchestrator.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from collectors import blog, web_search, github, jobs, pricing
import synthesizer

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

LOOKBACK_DAYS = 30

COLLECTOR_MAP = {
    "blog": blog,
    "web_search": web_search,
    "github": github,
    "jobs": jobs,
    "pricing": pricing,
}


def load_config():
    config_path = ROOT / "competitors.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def deduplicate(signals: list) -> list:
    seen_urls = set()
    result = []
    for s in signals:
        url = s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            result.append(s)
        elif not url:
            result.append(s)
    return result


def run_competitor(competitor: dict) -> dict:
    name = competitor["name"]
    print(f"\n→ {name}")

    signals = []
    for source in competitor.get("sources", []):
        collector = COLLECTOR_MAP.get(source)
        if not collector:
            print(f"  [warn] unknown source: {source}", file=sys.stderr)
            continue
        try:
            new_signals = collector.collect(competitor, LOOKBACK_DAYS)
            signals.extend(new_signals)
        except Exception as e:
            print(f"  [{source}] error: {e}", file=sys.stderr)

    signals = deduplicate(signals)
    print(f"  Total signals: {len(signals)}")

    print(f"  Synthesizing with Qwen...")
    result = synthesizer.synthesize(competitor, signals)
    result["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    result["total_signals"] = len(signals)
    return result


def update_index(competitors: list, date: str):
    index_path = DATA_DIR / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
    else:
        index = {"competitors": [], "dates": []}

    # Update competitors list
    index["competitors"] = [
        {"id": c["id"], "name": c["name"]} for c in competitors
    ]

    # Update dates list
    if date not in index.get("dates", []):
        index.setdefault("dates", []).insert(0, date)
        index["dates"].sort(reverse=True)

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"\nUpdated index.json")


def main():
    print("=== Competitor Research Orchestrator ===")
    config = load_config()
    competitors = config["competitors"]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    date_dir = DATA_DIR / date
    date_dir.mkdir(exist_ok=True)

    for competitor in competitors:
        out_path = date_dir / f"{competitor['id']}.json"
        if out_path.exists():
            print(f"  [skip] {competitor['name']} — already generated today")
            continue

        result = run_competitor(competitor)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"  Written: {out_path.relative_to(ROOT)}")

    update_index(competitors, date)
    print("\nDone.")


if __name__ == "__main__":
    main()
