"""Florida Gators men's basketball: schedule, scores, season player averages and news.

Uses ESPN's public site API (no key needed). Writes data/gators.json.
If ESPN is unreachable the previous file is kept, so the tab never goes blank.
Run:  python sync/gators.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "gators.json"
TEAM_ID = "57"  # Florida
BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
HEAD = {"User-Agent": "Mozilla/5.0 (personal training dashboard)"}


def get(url, **params):
    r = requests.get(url, params=params or None, headers=HEAD, timeout=20)
    r.raise_for_status()
    return r.json()


def shape(obj, depth=0):
    if depth > 5:
        return "..."
    if isinstance(obj, dict):
        return {k: shape(v, depth + 1) for k, v in list(obj.items())[:30]}
    if isinstance(obj, list):
        return [shape(obj[0], depth + 1)] if obj else []
    return type(obj).__name__


def score_of(c):
    s = c.get("score")
    if isinstance(s, dict):
        s = s.get("displayValue") or s.get("value")
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def rank_of(c):
    r = (c.get("curatedRank") or {}).get("current")
    return r if isinstance(r, int) and 0 < r <= 25 else None


def parse_event(ev):
    comp = (ev.get("competitions") or [{}])[0]
    status = (comp.get("status") or ev.get("status") or {}).get("type", {})
    comps = comp.get("competitors") or []
    fla = next((c for c in comps if str((c.get("team") or {}).get("id")) == TEAM_ID), None)
    opp = next((c for c in comps if c is not fla), None)
    if not fla or not opp:
        return None
    ot = opp.get("team") or {}
    fs, os_ = score_of(fla), score_of(opp)
    completed = bool(status.get("completed"))
    result = None
    if completed and fs is not None and os_ is not None:
        result = "W" if fs > os_ else "L"
    bc = []
    for b in comp.get("broadcasts") or []:
        if isinstance(b, dict):
            name = (b.get("media") or {}).get("shortName") or (b.get("names") or [None])[0]
            if name:
                bc.append(name)
    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    return {
        "id": ev.get("id"),
        "date": ev.get("date"),
        "opponent": ot.get("displayName") or ot.get("shortDisplayName") or ot.get("name"),
        "opp_short": ot.get("shortDisplayName") or ot.get("location") or ot.get("displayName"),
        "opp_abbr": ot.get("abbreviation"),
        "opp_color": ot.get("color"),
        "home": fla.get("homeAway") == "home",
        "neutral": bool(comp.get("neutralSite")),
        "fla_score": fs, "opp_score": os_,
        "fla_rank": rank_of(fla), "opp_rank": rank_of(opp),
        "completed": completed,
        "state": status.get("state"),  # pre / in / post
        "detail": status.get("shortDetail") or status.get("detail"),
        "result": result,
        "tv": ", ".join(dict.fromkeys(bc)),
        "venue": venue.get("fullName"),
        "city": ", ".join(x for x in [addr.get("city"), addr.get("state")] if x),
        "conference": bool(comp.get("conferenceCompetition")),
    }


def parse_box(summary):
    """Florida players' lines from a game summary."""
    out = []
    for side in (summary.get("boxscore") or {}).get("players") or []:
        if str((side.get("team") or {}).get("id")) != TEAM_ID:
            continue
        for block in side.get("statistics") or []:
            labels = [str(x).upper() for x in (block.get("labels") or block.get("names") or [])]
            for a in block.get("athletes") or []:
                if a.get("didNotPlay"):
                    continue
                vals = dict(zip(labels, a.get("stats") or []))
                ath = a.get("athlete") or {}

                def num(k):
                    try:
                        return float(str(vals.get(k, "")).split("-")[0])
                    except ValueError:
                        return 0.0
                out.append({"name": ath.get("displayName") or ath.get("shortName"),
                            "short": ath.get("shortName") or ath.get("displayName"),
                            "pos": (ath.get("position") or {}).get("abbreviation"),
                            "jersey": ath.get("jersey"), "starter": bool(a.get("starter")),
                            "min": num("MIN"), "pts": num("PTS"), "reb": num("REB"),
                            "ast": num("AST"), "stl": num("STL"), "blk": num("BLK"),
                            "fg": vals.get("FG"), "3pt": vals.get("3PT")})
    return out


def main():
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    boxes = prev.get("boxscores", {})
    errors, shapes = [], {}
    out = {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes")}

    try:
        t = get(f"{BASE}/teams/{TEAM_ID}")
        shapes["team"] = shape(t)
        team = t.get("team") or {}
        rec = ((team.get("record") or {}).get("items") or [{}])
        overall = next((r for r in rec if r.get("type") == "total"), rec[0] if rec else {})
        out["team"] = {"name": team.get("displayName") or "Florida Gators",
                       "record": overall.get("summary"),
                       "records": {r.get("type") or r.get("description"): r.get("summary") for r in rec},
                       "rank": team.get("rank") if isinstance(team.get("rank"), int) and team.get("rank") <= 25 else None,
                       "standing": team.get("standingSummary")}
    except Exception as ex:
        errors.append(f"team: {ex}")

    games = []
    try:
        sch = get(f"{BASE}/teams/{TEAM_ID}/schedule")
        shapes["schedule"] = shape(sch)
        for ev in sch.get("events") or []:
            g = parse_event(ev)
            if g:
                games.append(g)
    except Exception as ex:
        errors.append(f"schedule: {ex}")
    games.sort(key=lambda g: g["date"] or "")

    # Box scores: fetch each finished game once (cached), plus any live game every run
    for g in games:
        if not g["id"] or g["state"] == "pre" or (g["completed"] and g["id"] in boxes):
            continue
        try:
            s = get(f"{BASE}/summary", event=g["id"])
            shapes.setdefault("summary", shape(s))
            boxes[g["id"]] = parse_box(s)
        except Exception as ex:
            errors.append(f"summary {g['id']}: {ex}")
    for g in games:
        g["box"] = boxes.get(g["id"]) if g["state"] != "pre" else None

    # Season averages from completed games
    agg = {}
    done = [g for g in games if g["completed"]]
    for g in done:
        for p in boxes.get(g["id"]) or []:
            a = agg.setdefault(p["name"], {"name": p["name"], "short": p["short"], "pos": p["pos"], "jersey": p["jersey"],
                                           "gp": 0, "min": 0, "pts": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0})
            a["gp"] += 1
            for k in ("min", "pts", "reb", "ast", "stl", "blk"):
                a[k] += p[k]
    players = []
    for a in agg.values():
        gp = a["gp"] or 1
        players.append({**{k: a[k] for k in ("name", "short", "pos", "jersey", "gp")},
                        **{f"{k}pg": round(a[k] / gp, 1) for k in ("min", "pts", "reb", "ast", "stl", "blk")}})
    players.sort(key=lambda p: -p["ptspg"])

    news = []
    try:
        n = get(f"{BASE}/news", team=TEAM_ID, limit=15)
        shapes["news"] = shape(n)
        for a in n.get("articles") or []:
            link = ((a.get("links") or {}).get("web") or {}).get("href")
            img = next((i.get("url") for i in a.get("images") or [] if i.get("url")), None)
            if a.get("headline") and link:
                news.append({"headline": a["headline"], "description": a.get("description"),
                             "published": a.get("published") or a.get("lastModified"), "url": link, "image": img})
    except Exception as ex:
        errors.append(f"news: {ex}")

    live = [g for g in games if g["state"] == "in"]
    upcoming = [g for g in games if g["state"] == "pre"]
    out.update({
        "games": [{k: v for k, v in g.items() if k != "box"} for g in games],
        "live_game": live[0] if live else None,
        "next_game": upcoming[0] if upcoming else None,
        "last_game": done[-1] if done else None,
        "players": players,
        "news": news[:12],
        "boxscores": boxes,
        "errors": errors,
        "shapes": shapes,
    })
    if not games and not news and prev:  # ESPN unreachable: keep yesterday's data
        prev["errors"] = errors
        out = prev
    if not out.get("team"):
        out["team"] = prev.get("team") or {"name": "Florida Gators"}
    # Only bump the timestamp when something actually changed (avoids a redeploy every 15 min)
    strip = lambda d: {k: v for k, v in d.items() if k not in ("updated", "shapes", "errors")}
    if prev and strip(prev) == strip(out):
        out["updated"] = prev.get("updated", out["updated"])
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"Gators: {len(games)} games, {len(players)} players, {len(news)} news. Errors: {errors or 'none'}")


if __name__ == "__main__":
    main()
