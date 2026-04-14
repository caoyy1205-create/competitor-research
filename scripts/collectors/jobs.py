"""Jobs collector — scrapes Greenhouse/Lever job boards for new postings."""

import re
import sys
from datetime import datetime, timezone

from .common import fetch_url, make_signal


def collect(competitor: dict, lookback_days: int = 7) -> list:
    job_board = competitor.get("job_board", "")
    name = competitor["name"]
    signals = []

    if not job_board:
        return []

    if "ashbyhq.com" in job_board:
        signals = _scrape_ashby(job_board, name)
    elif "greenhouse.io" in job_board:
        signals = _scrape_greenhouse(job_board, name)
    elif "lever.co" in job_board:
        signals = _scrape_lever(job_board, name)
    else:
        signals = _scrape_generic(job_board, name)

    print(f"  [jobs] {name}: {len(signals)} postings")
    return signals


def _scrape_ashby(url: str, name: str) -> list:
    # Ashby JSON API: https://jobs.ashbyhq.com/{company}/api/jobs
    company = url.rstrip("/").split("/")[-1]
    api_url = f"https://jobs.ashbyhq.com/{company}/api/jobs"
    resp = fetch_url(api_url)
    if not resp:
        return []
    try:
        data = resp.json()
    except Exception:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = []
    for job in (data.get("jobs") or data.get("jobPostings") or [])[:20]:
        title = job.get("title") or job.get("jobTitle", "")
        job_url = job.get("jobUrl") or job.get("applyUrl") or url
        dept = (job.get("department") or {}).get("name", "") if isinstance(job.get("department"), dict) else job.get("department", "")
        if title:
            signals.append(make_signal(
                source_type="jobs",
                title=f"{name} hiring: {title}",
                url=job_url,
                date=today,
                snippet=f"Department: {dept}" if dept else title,
                metadata={"department": dept, "company": name},
            ))
    return signals


def _scrape_greenhouse(url: str, name: str) -> list:
    # Greenhouse JSON API
    company = url.rstrip("/").split("/")[-1]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    resp = fetch_url(api_url)
    if not resp:
        return []
    try:
        data = resp.json()
    except Exception:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = []
    for job in data.get("jobs", [])[:20]:
        title = job.get("title", "")
        job_url = job.get("absolute_url", "")
        dept = job.get("departments", [{}])[0].get("name", "") if job.get("departments") else ""
        signals.append(make_signal(
            source_type="jobs",
            title=f"{name} hiring: {title}",
            url=job_url,
            date=today,
            snippet=f"Department: {dept}" if dept else title,
            metadata={"department": dept, "company": name},
        ))
    return signals


def _scrape_lever(url: str, name: str) -> list:
    # Lever JSON API
    company = url.rstrip("/").split("/")[-1]
    api_url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    resp = fetch_url(api_url)
    if not resp:
        return []
    try:
        jobs = resp.json()
    except Exception:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = []
    for job in jobs[:20]:
        title = job.get("text", "")
        job_url = job.get("hostedUrl", "")
        team = job.get("categories", {}).get("team", "")
        signals.append(make_signal(
            source_type="jobs",
            title=f"{name} hiring: {title}",
            url=job_url,
            date=today,
            snippet=f"Team: {team}" if team else title,
            metadata={"team": team, "company": name},
        ))
    return signals


def _scrape_generic(url: str, name: str) -> list:
    resp = fetch_url(url)
    if not resp:
        return []
    # Best-effort: extract job titles from page
    titles = re.findall(r'<h\d[^>]*>\s*([^<]{10,80})\s*</h\d>', resp.text)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = []
    for title in titles[:10]:
        title = title.strip()
        if any(kw in title.lower() for kw in ["engineer", "manager", "designer", "scientist", "analyst", "lead", "director"]):
            signals.append(make_signal(
                source_type="jobs",
                title=f"{name} hiring: {title}",
                url=url,
                date=today,
                snippet=title,
                metadata={"company": name},
            ))
    return signals
