"""Pull Daniel's data from the Garmin Connect Personal API into data/*.json.

Needs the environment variable GARMIN_PERSONAL_API_KEY.
Run:  python sync/sync.py          (then compute.py builds the dashboard data)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = os.environ.get("GARMIN_PERSONAL_API_BASE_URL", "https://personal.connectapi.garmin.com")
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
DATA = Path(__file__).resolve().parent.parent / "data"
BACKFILL_START = date(2026, 6, 1)   # first run pulls everything since this date
RECENT_DAYS = 21                    # later runs re-check this many days (catches edits / late syncs)
WELLNESS_DAYS = 90
CHUNK = 28                          # days per wellness request

# Only these activity fields are kept. No GPS / location data is stored.
KEEP = [
    "activityId", "activityName", "startTimeLocal", "distance", "duration", "movingDuration",
    "elapsedDuration", "averageSpeed", "maxSpeed", "averageHR", "maxHR", "elevationGain",
    "calories", "averageRunningCadenceInStepsPerMinute", "aerobicTrainingEffect",
    "anaerobicTrainingEffect", "trainingEffectLabel", "activityTrainingLoad", "vO2MaxValue",
    "avgStrideLength", "lapCount", "description",
]


class Garmin:
    def __init__(self, api_key: str):
        r = requests.post(BASE + TOKEN_PATH, headers={"Authorization": f"ApiKey {api_key}"}, timeout=30)
        if not r.ok:
            sys.exit(f"Token request failed ({r.status_code}): {r.text[:300]}")
        token = r.text.strip()
        if token.startswith("{"):  # tolerate a JSON-wrapped token
            j = r.json()
            token = j.get("access_token") or j.get("accessToken") or j.get("token")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    def get(self, path, params=None):
        for attempt in range(3):
            r = self.s.get(BASE + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            if not r.ok:
                raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
            return r.json() if r.content else None
        raise RuntimeError(f"GET {path} rate-limited")


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=1, sort_keys=True))


def slim(a: dict) -> dict:
    out = {k: a.get(k) for k in KEEP if a.get(k) is not None}
    t = a.get("activityType") or {}
    out["type"] = t.get("typeKey") if isinstance(t, dict) else str(t)
    out["parentType"] = (t.get("parentTypeId") if isinstance(t, dict) else None)
    return out


def fetch_activities(g: Garmin, since: date, until: date) -> list[dict]:
    got, start = [], 0
    while True:
        page = g.get("/activitylist-service/activities/search/activities",
                     {"start": start, "limit": 100, "startDate": since.isoformat(), "endDate": until.isoformat()})
        if isinstance(page, dict):  # tolerate wrapped responses
            page = page.get("activityList") or page.get("activities") or []
        page = page or []
        got += page
        if len(page) < 100:
            return got
        start += 100


def date_chunks(start: date, end: date, n=CHUNK):
    s = start
    while s <= end:
        e = min(s + timedelta(days=n - 1), end)
        yield s, e
        s = e + timedelta(days=1)


def find_by_date(obj, keys, out, current_date=None):
    """Walk any JSON shape; collect {calendarDate: value} for the first matching key found."""
    if isinstance(obj, dict):
        d = (obj.get("calendarDate") or obj.get("date") or obj.get("summaryDate")
             or obj.get("calendarDateString") or current_date)
        for k in keys:
            v = obj
            for part in k.split("."):  # dotted paths like "sleepScores.overall.value"
                v = v.get(part) if isinstance(v, dict) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool) and d:
                out.setdefault(str(d)[:10], v)
                break
        for v in obj.values():
            find_by_date(v, keys, out, d)
    elif isinstance(obj, list):
        for v in obj:
            find_by_date(v, keys, out, current_date)
    return out


def shape(obj, depth=0):
    """Key structure only (no values) - used to debug field names without storing data."""
    if depth > 4:
        return "..."
    if isinstance(obj, dict):
        return {k: shape(v, depth + 1) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return [shape(obj[0], depth + 1)] if obj else []
    return type(obj).__name__


def fetch_resting_hr_daily(g: Garmin, have: dict, today: date, days=60, cap=20) -> dict:
    """Fallback: per-day heart-rate endpoint, filling in missing recent days (max `cap` calls per run)."""
    out, calls = {}, 0
    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        if d in have or calls >= cap:
            continue
        calls += 1
        try:
            r = g.get("/wellness-service/wellness/dailyHeartRate", {"date": d})
            v = (r or {}).get("restingHeartRate") if isinstance(r, dict) else None
            if v:
                out[d] = v
        except Exception:
            break
    return out


def fetch_wellness(g: Garmin, start: date, end: date) -> dict:
    series = {"resting_hr": {}, "hrv": {}, "sleep_hours": {}, "sleep_score": {}, "vo2max": {}, "body_battery": {}}
    errors, shapes = [], {}
    for s, e in date_chunks(start, end):
        jobs = [
            ("resting_hr", "/usersummary-service/v2/dailysummaries", {"startDate": s, "endDate": e},
             ["heartRate.restingValue", "restingHeartRate", "restingHeartRateValue"]),
            ("hrv", f"/hrv-service/hrv/daily/{s}/{e}", None, ["lastNightAvg", "lastNight"]),
            ("sleep_hours", "/sleep-service/sleep/dailySleepSummariesByDate", {"startDate": s, "endDate": e},
             ["sleepTimeSeconds", "totalSleepSeconds"]),
            ("sleep_score", "/sleep-service/sleep/dailySleepSummariesByDate", {"startDate": s, "endDate": e},
             ["overallSleepScore", "sleepScores.overall.value", "sleepScore"]),
            ("vo2max", f"/metrics-service/metrics/maxmet/daily/{s}/{e}", {"sport": ["RUNNING"]},
             ["vo2MaxPreciseValue", "vo2MaxValue"]),
        ]
        cache = {}
        for key, path, params, fields in jobs:
            try:
                ck = (path, json.dumps(params, default=str))
                if ck not in cache:
                    p = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in (params or {}).items()}
                    cache[ck] = g.get(path, p or None)
                shapes.setdefault(key, shape(cache[ck]))
                vals = find_by_date(cache[ck], fields, {})
                if key == "sleep_hours":
                    vals = {d: round(v / 3600, 2) for d, v in vals.items() if v}
                series[key].update(vals)
            except Exception as ex:  # one bad endpoint shouldn't stop the sync
                errors.append(f"{key}: {ex}")
    return {"series": series, "errors": errors[:10], "shapes": shapes}


def main():
    key = os.environ.get("GARMIN_PERSONAL_API_KEY")
    if not key:
        sys.exit("Set GARMIN_PERSONAL_API_KEY")
    g = Garmin(key)
    today = date.today()

    store = {str(a["activityId"]): a for a in load("activities.json", [])}
    since = BACKFILL_START if not store else today - timedelta(days=RECENT_DAYS)
    fresh = fetch_activities(g, since, today)
    for a in fresh:
        if a.get("activityId"):
            store[str(a["activityId"])] = slim(a)
    acts = sorted(store.values(), key=lambda a: a.get("startTimeLocal", ""))
    save("activities.json", acts)

    wstart = BACKFILL_START if not (DATA / "wellness.json").exists() else today - timedelta(days=WELLNESS_DAYS)
    old = load("wellness.json", {"series": {}})
    new = fetch_wellness(g, wstart, today)
    for k, v in new["series"].items():
        old["series"].setdefault(k, {}).update(v)
    old.pop("demo", None)
    old["errors"] = new["errors"]
    rhr = old["series"].setdefault("resting_hr", {})
    rhr.update(fetch_resting_hr_daily(g, rhr, today))
    save("wellness.json", old)
    save("debug_shapes.json", new["shapes"])  # field names only, no values

    print(f"Synced {len(fresh)} activities from {since} (total stored: {len(acts)}).")
    if new["errors"]:
        print("Wellness warnings:", *new["errors"], sep="\n  ")


if __name__ == "__main__":
    main()
