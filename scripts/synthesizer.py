"""Synthesizer — Qwen agent that turns raw signals into structured insights."""

import json
import os
import re
import sys

from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
MODEL = "qwen-plus-latest"


def synthesize(competitor: dict, signals: list) -> dict:
    name = competitor["name"]

    if not signals:
        return {
            "competitor": name,
            "summary": "",
            "signals": [],
            "note": "No new signals found this period.",
        }

    prompt = _build_prompt(name, signals)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_response(raw, name, signals)
    except Exception as e:
        print(f"  [synthesizer] {name}: LLM error: {e}", file=sys.stderr)
        return _fallback_response(name, signals)


def _build_prompt(name: str, signals: list) -> str:
    signal_lines = []
    for i, s in enumerate(signals, 1):
        signal_lines.append(
            f"[{i}] Type: {s['source_type']} | Date: {s['date']}\n"
            f"    Title: {s['title']}\n"
            f"    Snippet: {s['snippet'][:200]}\n"
            f"    URL: {s['url']}\n"
        )

    return f"""You are a competitive intelligence analyst. Analyze the following signals about {name} and produce a structured research brief.

Signals collected this week:
{"".join(signal_lines)}

Produce a JSON object with this exact structure:
{{
  "summary": "2-3 sentence overview of the most important things happening at {name} this week",
  "signals": [
    {{
      "type": "product_update | hiring | pricing | github | news",
      "title": "concise signal title",
      "url": "source URL",
      "date": "YYYY-MM-DD",
      "insight": "one sentence explaining why this matters competitively",
      "importance": "high | medium | low"
    }}
  ]
}}

Rules:
- Include only the most meaningful signals (max 8)
- importance=high means direct competitive threat or major product move
- Output only the JSON object, no other text
"""


def _parse_response(raw: str, name: str, signals: list) -> dict:
    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()
    # Fix curly quotes
    raw = raw.replace('\u201c', '"').replace('\u201d', '"')
    raw = raw.replace('\u2018', "'").replace('\u2019', "'")
    # Fix lone backslashes
    raw = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)

    try:
        data = json.loads(raw)
        return {
            "competitor": name,
            "summary": data.get("summary", ""),
            "signals": data.get("signals", []),
            "note": "",
        }
    except json.JSONDecodeError as e:
        print(f"  [synthesizer] JSON parse error: {e}", file=sys.stderr)
        return _fallback_response(name, signals)


def _fallback_response(name: str, signals: list) -> dict:
    """Return a basic response using raw signals when LLM fails."""
    return {
        "competitor": name,
        "summary": f"{len(signals)} signals collected for {name} this period.",
        "signals": [
            {
                "type": s["source_type"],
                "title": s["title"],
                "url": s["url"],
                "date": s["date"],
                "insight": s["snippet"][:150],
                "importance": "medium",
            }
            for s in signals[:8]
        ],
        "note": "LLM synthesis unavailable — showing raw signals.",
    }
