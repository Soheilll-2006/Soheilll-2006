#!/usr/bin/env python3
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from html import escape

USERNAME = os.environ.get("PROFILE_USERNAME", "Soheilll-2006")
TOKEN = os.environ["GITHUB_TOKEN"]
README = Path("README.md")

today = datetime.now(timezone.utc).date()
year_start = date(today.year, 1, 1)
lookback_start = today - timedelta(days=364)

query = """
query($login: String!, $ytdFrom: DateTime!, $lookbackFrom: DateTime!, $to: DateTime!) {
  user(login: $login) {
    ytd: contributionsCollection(from: $ytdFrom, to: $to) {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
    lookback: contributionsCollection(from: $lookbackFrom, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

payload = json.dumps({
    "query": query,
    "variables": {
        "login": USERNAME,
        "ytdFrom": year_start.isoformat() + "T00:00:00Z",
        "lookbackFrom": lookback_start.isoformat() + "T00:00:00Z",
        "to": today.isoformat() + "T23:59:59Z",
    },
}).encode()

req = urllib.request.Request(
    "https://api.github.com/graphql",
    data=payload,
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "profile-metrics-action",
    },
)

with urllib.request.urlopen(req, timeout=30) as response:
    result = json.load(response)

if result.get("errors"):
    raise RuntimeError(result["errors"])

user = result["data"]["user"]
ytd = user["ytd"]
lookback = user["lookback"]

days = []
for week in lookback["contributionCalendar"]["weeks"]:
    for d in week["contributionDays"]:
        dt = date.fromisoformat(d["date"])
        if lookback_start <= dt <= today:
            days.append((dt, int(d["contributionCount"])))
days.sort()
day_map = {d: count for d, count in days}
active_days = sum(1 for _, count in days if count > 0)

def streak_ending(anchor):
    streak = 0
    d = anchor
    while d >= lookback_start and day_map.get(d, 0) > 0:
        streak += 1
        d -= timedelta(days=1)
    return streak

current_streak = streak_ending(today)
if current_streak == 0:
    current_streak = streak_ending(today - timedelta(days=1))

longest = 0
running = 0
for _, count in days:
    if count > 0:
        running += 1
        longest = max(longest, running)
    else:
        running = 0

contribs_ytd = int(ytd["contributionCalendar"]["totalContributions"])
public_commits_ytd = int(ytd["totalCommitContributions"])

profile_url = f"https://github.com/{USERNAME}?tab=overview"
commit_search = "https://github.com/search?" + urllib.parse.urlencode({
    "q": f"author:{USERNAME}",
    "type": "commits",
})

block = f"""<!-- activity:start -->
<div align="center">

## Activity

<sub>Live GitHub data · refreshed {today.isoformat()}</sub>

<table>
<tr>
<td align="center" width="25%">
<a href="{profile_url}" title="{contribs_ytd:,} contributions year to date">
<strong>{contribs_ytd:,}</strong><br/>
<sub>Contributions YTD</sub>
</a>
</td>
<td align="center" width="25%">
<a href="{commit_search}" title="{public_commits_ytd:,} public commits year to date">
<strong>{public_commits_ytd:,}</strong><br/>
<sub>Public Commits YTD</sub>
</a>
</td>
<td align="center" width="25%">
<a href="{profile_url}" title="Current streak: {current_streak} days · longest in last 365 days: {longest} days">
<strong>{current_streak} days</strong><br/>
<sub>Current Streak</sub>
</a>
</td>
<td align="center" width="25%">
<a href="{profile_url}" title="{active_days} active contribution days in the last 365 days">
<strong>{active_days}</strong><br/>
<sub>Active Days · 365d</sub>
</a>
</td>
</tr>
</table>

<a href="{profile_url}" title="Open GitHub's native interactive contribution calendar">
<strong>↗ Open interactive contribution graph</strong>
</a>

</div>
<!-- activity:end -->"""

text = README.read_text(encoding="utf-8")
pattern = r"<!-- activity:start -->.*?<!-- activity:end -->"
new_text, count = re.subn(pattern, block, text, flags=re.S)
if count != 1:
    raise RuntimeError(f"Expected exactly one activity block, found {count}")

README.write_text(new_text, encoding="utf-8")
print(
    f"Updated README: {contribs_ytd:,} contributions, "
    f"{public_commits_ytd:,} public commits, "
    f"{current_streak}d streak, {active_days} active days"
)
