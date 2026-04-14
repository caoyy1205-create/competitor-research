"""GitHub collector — tracks releases, new repos, and activity for a GitHub org."""

import sys
from datetime import datetime, timezone, timedelta

from .common import fetch_url, make_signal

GITHUB_API = "https://api.github.com"


def collect(competitor: dict, lookback_days: int = 7) -> list:
    org = competitor.get("github_org")
    if not org:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    signals = []

    signals.extend(_get_releases(org, cutoff, competitor["name"]))
    signals.extend(_get_new_repos(org, cutoff, competitor["name"]))

    print(f"  [github] {competitor['name']}: {len(signals)} signals")
    return signals


def _api_get(path: str) -> list | dict | None:
    resp = fetch_url(f"{GITHUB_API}{path}")
    if not resp:
        return None
    try:
        return resp.json()
    except Exception:
        return None


def _parse_gh_date(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_releases(org: str, cutoff: datetime, name: str) -> list:
    signals = []
    repos = _api_get(f"/orgs/{org}/repos?sort=updated&per_page=10")
    if not repos or not isinstance(repos, list):
        return []

    for repo in repos[:5]:
        repo_name = repo.get("name", "")
        releases = _api_get(f"/repos/{org}/{repo_name}/releases?per_page=5")
        if not releases or not isinstance(releases, list):
            continue
        for rel in releases:
            published = _parse_gh_date(rel.get("published_at", ""))
            if not published or published < cutoff:
                continue
            tag = rel.get("tag_name", "")
            title = rel.get("name") or tag or "New Release"
            body = rel.get("body", "") or ""
            signals.append(make_signal(
                source_type="github",
                title=f"{name} — {repo_name} {title}",
                url=rel.get("html_url", ""),
                date=published.strftime("%Y-%m-%d"),
                snippet=body[:300],
                metadata={"repo": repo_name, "tag": tag, "type": "release"},
            ))
    return signals


def _get_new_repos(org: str, cutoff: datetime, name: str) -> list:
    signals = []
    repos = _api_get(f"/orgs/{org}/repos?sort=created&direction=desc&per_page=10")
    if not repos or not isinstance(repos, list):
        return []

    for repo in repos:
        created = _parse_gh_date(repo.get("created_at", ""))
        if not created or created < cutoff:
            continue
        if repo.get("fork"):
            continue
        signals.append(make_signal(
            source_type="github",
            title=f"{name} — new repo: {repo['name']}",
            url=repo.get("html_url", ""),
            date=created.strftime("%Y-%m-%d"),
            snippet=repo.get("description", "") or "",
            metadata={"repo": repo["name"], "stars": repo.get("stargazers_count", 0), "type": "new_repo"},
        ))
    return signals
