"""Combine plan + Garmin data into data/dashboard.json for the website.

Run after sync.py (or on demo data):  python sync/compute.py
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TZ = ZoneInfo("America/New_York")
M_PER_MI = 1609.344
MARATHON_M = 42195.0
HALF_M = 21097.5

RUN_TYPES = {"running", "treadmill_running", "trail_running", "track_running", "street_running",
             "indoor_running", "virtual_run", "obstacle_run", "ultra_run"}
LIFT_TYPES = {"strength_training", "indoor_cardio_strength", "hiit"}
CROSS_TYPES = {"cycling", "indoor_cycling", "virtual_ride", "road_biking", "walking", "indoor_walking",
               "treadmill_walking", "hiking", "elliptical", "stair_climbing", "indoor_rowing", "indoor_cardio"}


# ---------- helpers ----------
def is_run(a): return (a.get("type") or "") in RUN_TYPES or "run" in (a.get("type") or "")
def a_date(a): return (a.get("startTimeLocal") or "")[:10]
def miles(a): return (a.get("distance") or 0) / M_PER_MI


def pace_s(a):
    sp = a.get("averageSpeed")
    if sp:
        return M_PER_MI / sp
    d, t = a.get("distance"), a.get("movingDuration") or a.get("duration")
    return t / (d / M_PER_MI) if d and t else None


def fmt_time(sec):
    if sec is None:
        return None
    sec = int(round(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_time(s):
    parts = [int(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


# ---------- Jack Daniels VDOT model ----------
def _vo2(v): return -4.60 + 0.182258 * v + 0.000104 * v * v
def _pct(t): return 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)
def vdot(dist_m, sec): t = sec / 60; return _vo2(dist_m / t) / _pct(t)


def time_for(vd, dist_m):
    lo, hi = dist_m / 450, dist_m / 40  # minutes
    for _ in range(80):
        mid = (lo + hi) / 2
        if vdot(dist_m, mid * 60) > vd:
            lo = mid
        else:
            hi = mid
    return mid * 60


# ---------- main ----------
def build(today: date | None = None):
    today = today or datetime.now(TZ).date()
    plan = json.loads((ROOT / "plan" / "plan.json").read_text())
    acts = json.loads((DATA / "activities.json").read_text()) if (DATA / "activities.json").exists() else []
    well = json.loads((DATA / "wellness.json").read_text()) if (DATA / "wellness.json").exists() else {"series": {}}
    goal = plan["goal"]
    race_day = date.fromisoformat(goal["race_date"])
    goal_sec = parse_time(goal["goal_time"])
    block_start = date.fromisoformat(plan["days"][0]["date"])

    by_day: dict[str, list] = {}
    for a in acts:
        by_day.setdefault(a_date(a), []).append(a)

    def actual(dstr):
        lst = by_day.get(dstr, [])
        runs = [a for a in lst if is_run(a)]
        return {
            "run_miles": round(sum(miles(a) for a in runs), 2),
            "runs": [a.get("activityId") for a in runs],
            "lift": any((a.get("type") or "") in LIFT_TYPES for a in lst),
            "cross": any((a.get("type") or "") in CROSS_TYPES for a in lst),
        }

    def status(day, act, d):
        planned = (day["run"] or {}).get("miles", 0)
        if d > today:
            return "planned"
        if planned:
            if act["run_miles"] >= 0.75 * planned:
                return "done"
            if d == today:
                return "today"
            return "partial" if act["run_miles"] > 0.3 else "missed"
        if day["cross"]:
            return "done" if act["cross"] or act["run_miles"] else ("today" if d == today else "skipped")
        return "rest" if d < today else "today"

    days_out = []
    for day in plan["days"]:
        d = date.fromisoformat(day["date"])
        act = actual(day["date"])
        days_out.append({**day, "actual": act, "status": status(day, act, d)})

    # weekly
    weeks = []
    for w in plan["weeks"]:
        wd = [x for x in days_out if x["week"] == w["week"]]
        run_list = [a for x in wd for a in by_day.get(x["date"], []) if is_run(a)]
        long_plan = max(((x["run"] or {}).get("miles", 0) for x in wd), default=0)
        weeks.append({**w,
                      "actual_miles": round(sum(miles(a) for a in run_list), 1),
                      "long_planned": long_plan,
                      "long_actual": round(max((miles(a) for a in run_list), default=0), 1),
                      "lifts": sum(1 for x in wd if x["actual"]["lift"]),
                      "is_current": w["start"] <= today.isoformat() <= w["end"],
                      "is_past": w["end"] < today.isoformat()})

    cur_week = next((w for w in weeks if w["is_current"]), weeks[0] if today < block_start else weeks[-1])

    # compliance to date
    past = [x for x in days_out if x["date"] < today.isoformat() and x["run"]]
    done = [x for x in past if x["status"] == "done"]
    planned_mi = sum(x["run"]["miles"] for x in past)
    actual_mi = sum(x["actual"]["run_miles"] for x in days_out if x["date"] < today.isoformat())

    # runs (all history)
    runs = sorted([a for a in acts if is_run(a) and a.get("distance")], key=a_date)
    block_runs = [a for a in runs if a_date(a) >= block_start.isoformat()]

    def run_row(a):
        p = pace_s(a)
        return {"id": a.get("activityId"), "date": a_date(a), "name": a.get("activityName"),
                "type": a.get("type"), "miles": round(miles(a), 2), "time": fmt_time(a.get("duration")),
                "pace": fmt_time(p), "pace_s": round(p) if p else None, "hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"), "elev_ft": round((a.get("elevationGain") or 0) * 3.281),
                "cadence": a.get("averageRunningCadenceInStepsPerMinute"),
                "te": a.get("aerobicTrainingEffect"), "label": a.get("trainingEffectLabel")}

    # aerobic efficiency on easy runs: metres/min per heartbeat (higher = fitter)
    eff = []
    for a in runs:
        p, hr = pace_s(a), a.get("averageHR")
        if p and hr and miles(a) >= 2.5 and p >= 9.25 * 60 and a_date(a) >= (today - timedelta(days=150)).isoformat():
            eff.append({"date": a_date(a), "ef": round((M_PER_MI / p * 60) / hr, 3), "pace": fmt_time(p), "hr": hr})
    for i, e in enumerate(eff):
        win = [x["ef"] for x in eff[max(0, i - 4): i + 1]]
        e["ef_avg"] = round(sum(win) / len(win), 3)

    # ---------- marathon prediction ----------
    ref = goal["reference_result"]
    ref_vd = vdot(ref["distance_mi"] * M_PER_MI, parse_time(ref["time"]))
    history = [{"date": "2026-07-25", "seconds": round(time_for(ref_vd, MARATHON_M)), "source": "July half"}]

    vo2 = well.get("series", {}).get("vo2max", {})
    if not vo2:  # fall back to per-activity VO2max values
        for a in runs:
            if a.get("vO2MaxValue"):
                vo2[a_date(a)] = a["vO2MaxValue"]
    # Garmin's raw VO2max over-predicts marathons, so we anchor it to the real July half:
    # projected VDOT = July-half VDOT + (VO2max now - VO2max around the July race).
    near = [vo2[d] for d in vo2 if "2026-07-11" <= d <= "2026-08-08"] or [vo2[d] for d in sorted(vo2)[:5]]
    anchor = statistics.median(near) if near else None

    def adj(v): return ref_vd + (v - anchor)

    for d in sorted(vo2):
        if d >= "2026-07-26":
            history.append({"date": d, "seconds": round(time_for(adj(vo2[d]), MARATHON_M)), "source": "VO2max trend"})

    # A race only counts toward the projection if it was a real effort. The Gainesville Half is planned
    # as a controlled marathon-pace rehearsal, so it only counts if run faster than ~8:10/mi.
    def is_race(a):
        if miles(a) < 12.9 or a_date(a) < block_start.isoformat():
            return False
        if a_date(a) == goal["tuneup"]["date"]:
            return (pace_s(a) or 999) < 490
        return any(k in (a.get("activityName") or "").lower() for k in ("race", "half marathon"))
    races = [a for a in runs if is_race(a)]
    race_pred = None
    if races:
        r = races[-1]
        race_pred = {"date": a_date(r), "seconds": round(time_for(vdot(r["distance"], r["duration"]), MARATHON_M)),
                     "source": f"{r.get('activityName')} ({fmt_time(r['duration'])})"}
        history.append(race_pred)
    history.sort(key=lambda h: h["date"])

    # endurance readiness: fitness says what you *could* run; long runs decide whether you hold it.
    # ~45 s added per mile your longest run (last 6 weeks) is short of 18 mi.
    def penalty(as_of: str) -> float:
        lo = (date.fromisoformat(as_of) - timedelta(days=42)).isoformat()
        longest = max((miles(a) for a in runs if lo <= a_date(a) <= as_of), default=0)
        return 0 if longest >= 17.5 else (18 - longest) * 45

    for h in history:
        h["fitness_seconds"] = h["seconds"]
        h["seconds"] = round(h["seconds"] + penalty(h["date"]))

    recent_vo2 = [vo2[d] for d in sorted(vo2)[-7:]]
    if race_pred and race_pred["date"] >= (today - timedelta(days=56)).isoformat():
        current = race_pred | {"method": "Recent race result"}
    elif recent_vo2:
        v = statistics.median(recent_vo2)
        current = {"seconds": round(time_for(adj(v), MARATHON_M)),
                   "method": f"July half, adjusted by Garmin VO2max trend ({anchor:.0f} → {v:.0f})"}
    else:
        current = {"seconds": history[0]["seconds"], "method": "July half (1:42:30) — pre-illness"}

    longest_block = max((miles(a) for a in block_runs), default=0)
    endurance_pen = penalty(today.isoformat())
    if current.get("date"):  # race-based: use the stored (un-penalized) fitness figure
        current["seconds"] = next((h["fitness_seconds"] for h in history if h is race_pred), current["seconds"])
    current["fitness_seconds"] = current["seconds"]
    current["seconds"] = round(current["seconds"] + endurance_pen)
    current["endurance_penalty"] = round(endurance_pen)
    current["time"] = fmt_time(current["seconds"])
    current["pace"] = fmt_time(current["seconds"] / 26.2188)
    current["gap"] = current["seconds"] - goal_sec
    if history and history[-1]["date"] < today.isoformat():
        history.append({"date": today.isoformat(), "seconds": current["seconds"],
                        "fitness_seconds": current["fitness_seconds"], "source": "Today"})

    # ---------- recovery ----------
    series = well.get("series", {})

    def last(name, n=30):
        s = series.get(name, {})
        return [{"date": d, "v": s[d]} for d in sorted(s) if d > (today - timedelta(days=n)).isoformat()]

    rhr = series.get("resting_hr", {})
    flags = []
    if rhr:
        ds = sorted(rhr)
        recent = [rhr[d] for d in ds[-3:]]
        base = [rhr[d] for d in ds[-33:-3]] or recent
        if recent and base and statistics.mean(recent) - statistics.median(base) >= 5:
            flags.append("Resting HR is 5+ bpm above your baseline — keep today easy or take a rest day.")
    hrv = series.get("hrv", {})
    if len(hrv) > 10:
        ds = sorted(hrv)
        if statistics.mean(hrv[d] for d in ds[-3:]) < 0.85 * statistics.median(hrv[d] for d in ds[-33:-3]):
            flags.append("HRV is well below normal — prioritize sleep and keep runs easy.")

    today_s = today.isoformat()
    tomorrow_s = (today + timedelta(days=1)).isoformat()
    out = {
        "generated_at": datetime.now(TZ).isoformat(timespec="minutes"),
        "today": today_s,
        "goal": goal | {"goal_seconds": goal_sec},
        "paces": plan["paces"],
        "countdown": {"race_days": (race_day - today).days,
                      "half_days": (date.fromisoformat(goal["tuneup"]["date"]) - today).days,
                      "week": cur_week["week"], "weeks_total": len(weeks)},
        "today_plan": next((x for x in days_out if x["date"] == today_s), None),
        "tomorrow_plan": next((x for x in days_out if x["date"] == tomorrow_s), None),
        "current_week": {**cur_week, "days": [x for x in days_out if x["week"] == cur_week["week"]]},
        "weeks": weeks,
        "days": days_out,
        "compliance": {"runs_planned": len(past), "runs_done": len(done),
                       "pct": round(100 * len(done) / len(past)) if past else None,
                       "miles_planned": round(planned_mi, 1), "miles_done": round(actual_mi, 1)},
        "totals": {"block_miles": round(sum(miles(a) for a in block_runs), 1),
                   "block_runs": len(block_runs), "longest": round(longest_block, 1)},
        "prediction": {"current": current, "history": history, "goal_seconds": goal_sec},
        "efficiency": eff,
        "recovery": {"resting_hr": last("resting_hr"), "hrv": last("hrv"), "sleep_hours": last("sleep_hours"),
                     "sleep_score": last("sleep_score"), "flags": flags},
        "recent_runs": [run_row(a) for a in runs[::-1][:12]],
        "last_activity": run_row(runs[-1]) if runs else None,
        "sync_warnings": well.get("errors", []),
        "demo": bool(well.get("demo")),
    }
    (DATA / "dashboard.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    import os
    t = os.environ.get("DASH_TODAY")
    o = build(date.fromisoformat(t) if t else None)
    c = o["prediction"]["current"]
    print(f"Dashboard built for {o['today']}: week {o['countdown']['week']}, "
          f"{o['countdown']['race_days']} days to Miami, projected {c['time']} ({c['method']}).")
