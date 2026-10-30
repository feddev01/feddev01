"""Fetch GitHub stats for the profile card into stats.json.

Usage: STATS_TOKEN=<token> python3 scripts/stats.py

STATS_TOKEN needs access to your repositories (private ones too, to count
private work). Only totals are saved: no repository or organisation names.
If the token is missing, expired or GitHub fails, stats.json records the error
and the card shows a 404 joke instead of numbers.
Run scripts/build.py afterwards to put the numbers on the card.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = "feddev01"

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    pullRequests { totalCount }
    merged: pullRequests(states: MERGED) { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, PULL_REQUEST_REVIEW, ISSUE, REPOSITORY]) {
      totalCount
    }
    repositories(ownerAffiliations: OWNER) { totalCount }
  }
}
"""


class StatsError(Exception):
    pass


def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        raise StatsError("401 · token expired" if e.code == 401 else f"{e.code} · GitHub said no") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise StatsError("503 · GitHub unreachable") from e
    if "errors" in body:
        raise StatsError("500 · GitHub API error")
    return body["data"]["user"]


def created_at_public():
    """Account creation date from the public API, so uptime works without a token."""
    with urllib.request.urlopen(f"https://api.github.com/users/{LOGIN}", timeout=30) as resp:
        return json.load(resp)["created_at"]


def age(since, today):
    months = (today.year - since.year) * 12 + today.month - since.month - (today.day < since.day)
    years, months = divmod(months, 12)
    parts = [f"{years} year{'s' * (years != 1)}"] if years else []
    if months:
        parts.append(f"{months} month{'s' * (months != 1)}")
    return ", ".join(parts) or "less than a month"


def main():
    if "--help" in sys.argv[1:]:
        print(__doc__.strip())
        return
    today = date.today()
    token = os.environ.get("STATS_TOKEN")
    try:
        if not token:
            raise StatsError("404 · token not found")
        user = fetch(token)
        stats = {
            "prs": user["pullRequests"]["totalCount"],
            "merged": user["merged"]["totalCount"],
            "contributed": user["repositoriesContributedTo"]["totalCount"],
            "owned": user["repositories"]["totalCount"],
        }
        created = user["createdAt"]
    except StatsError as e:
        print(f"stats unavailable: {e}", file=sys.stderr)
        stats = {"error": str(e)}
        created = created_at_public()
    stats["uptime"] = age(datetime.fromisoformat(created.replace("Z", "+00:00")).date(), today)
    stats["updated"] = today.isoformat()
    (ROOT / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
