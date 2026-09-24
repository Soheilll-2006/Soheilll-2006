#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("PROFILE_USERNAME", "Soheilll-2006")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets/activity-metrics.svg")

today = datetime.now(timezone.utc).date()
year_start = date(today.year, 1, 1)
lookback_start = today - timedelta(days=364)

query = """
query($login: String!, $ytdFrom: DateTime!, $lookbackFrom: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    ytd: contributionsCollection(from: $ytdFrom, to: $to) {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
    lookback: contributionsCollection(from: $lookbackFrom, to: $to) {
      contributionCalendar {
        totalContributions
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
calendar = lookback["contributionCalendar"]

days = []
for week in calendar["weeks"]:
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
public_repos = int(user["repositories"]["totalCount"])

# 52-week Monday-aligned heatmap.
heat_start = today - timedelta(days=363)
heat_start -= timedelta(days=heat_start.weekday())
weeks = []
cursor = heat_start
while cursor <= today:
    weeks.append(cursor)
    cursor += timedelta(days=7)
weeks = weeks[-52:]

visible_counts = []
for monday in weeks:
    for dow in range(7):
        d = monday + timedelta(days=dow)
        if d <= today:
            visible_counts.append(day_map.get(d, 0))
max_count = max(visible_counts or [0])

def heat_color(n):
    if n <= 0:
        return "#132238"
    ratio = n / max_count if max_count else 0
    if ratio <= .20:
        return "#0E4D64"
    if ratio <= .45:
        return "#087E8B"
    if ratio <= .70:
        return "#20BFC6"
    return "#5AE8E8"

W, H = 1200, 390
cards = [
    ("CONTRIBUTIONS", f"{contribs_ytd:,}", "year to date", "#58A6FF"),
    ("PUBLIC COMMITS", f"{public_commits_ytd:,}", "year to date", "#2DE2E6"),
    ("CURRENT STREAK", f"{current_streak}d", f"longest {longest}d · last 365d", "#7EE787"),
    ("ACTIVE DAYS", f"{active_days}", f"last 365d · {public_repos} public repos", "#F2CC60"),
]

parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
    <stop stop-color="#07111F"/>
    <stop offset="1" stop-color="#0A1C31"/>
  </linearGradient>
  <linearGradient id="rail" x1="52" y1="0" x2="1148" y2="0" gradientUnits="userSpaceOnUse">
    <stop stop-color="#58A6FF"/>
    <stop offset=".5" stop-color="#2DE2E6"/>
    <stop offset="1" stop-color="#7EE787"/>
  </linearGradient>
  <pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="1" fill="#7890AB" fill-opacity=".09"/>
  </pattern>
</defs>
<rect width="{W}" height="{H}" rx="28" fill="url(#bg)"/>
<rect width="{W}" height="{H}" rx="28" fill="url(#dots)"/>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="27" stroke="#25415F" stroke-opacity=".85"/>
<text x="52" y="48" fill="#FFFFFF" font-size="24" font-weight="750" font-family="Inter,Segoe UI,Arial,sans-serif">ACTIVITY PULSE</text>
<text x="52" y="72" fill="#6F86A1" font-size="13" font-family="Consolas,monospace">live GitHub contribution data · refreshed {escape(today.isoformat())}</text>
<rect x="52" y="85" width="170" height="3" rx="2" fill="url(#rail)"/>
''']

card_x = [52, 330, 608, 886]
for i, (label, value, sub, color) in enumerate(cards):
    x = card_x[i]
    parts.append(f'''<g transform="translate({x} 112)">
  <rect width="262" height="108" rx="19" fill="#0C1C31" stroke="#284664"/>
  <circle cx="25" cy="25" r="5" fill="{color}"/>
  <text x="42" y="29" fill="#839AB5" font-size="12" font-weight="700" font-family="Consolas,monospace" letter-spacing=".8">{escape(label)}</text>
  <text x="22" y="72" fill="#FFFFFF" font-size="33" font-weight="800" font-family="Inter,Segoe UI,Arial,sans-serif">{escape(value)}</text>
  <text x="22" y="94" fill="#6F86A1" font-size="12" font-family="Inter,Segoe UI,Arial,sans-serif">{escape(sub)}</text>
</g>''')

parts.append('''<text x="52" y="264" fill="#FFFFFF" font-size="16" font-weight="700" font-family="Inter,Segoe UI,Arial,sans-serif">LAST 52 WEEKS</text>
<text x="1148" y="264" text-anchor="end" fill="#607894" font-size="11" font-family="Consolas,monospace">contribution intensity</text>''')

cell = 13
gap = 7
x0 = 52
y0 = 282
for wi, monday in enumerate(weeks):
    for dow in range(7):
        d = monday + timedelta(days=dow)
        if d > today:
            continue
        n = day_map.get(d, 0)
        x = x0 + wi * (cell + gap)
        y = y0 + dow * (cell + 2)
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{heat_color(n)}"/>')

parts.append('''</svg>''')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"Wrote {OUT}")
