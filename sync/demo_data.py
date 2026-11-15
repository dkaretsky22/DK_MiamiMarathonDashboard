"""Generate realistic FAKE data so the dashboard can be previewed before Garmin is connected.

python sync/demo_data.py                    # history up to today
python sync/demo_data.py --through 2026-12-20   # also simulate following the plan until a date
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
M = 1609.344
random.seed(7)
_id = [20000000000]


def act(d: date, kind, mi=0.0, pace=None, hr=None, minutes=None, name=None, hour=7):
    _id[0] += 1
    a = {"activityId": _id[0], "startTimeLocal": f"{d} {hour:02d}:{random.randint(0,59):02d}:00", "type": kind}
    if kind == "running":
        dur = mi * pace
        a.update(activityName=name or "Gainesville Running", distance=round(mi * M, 1), duration=round(dur),
                 movingDuration=round(dur * 0.98), averageSpeed=round(M / pace, 3), averageHR=hr,
                 maxHR=hr + random.randint(12, 22), elevationGain=round(mi * random.uniform(3, 8), 1),
                 averageRunningCadenceInStepsPerMinute=random.randint(164, 174),
                 aerobicTrainingEffect=round(min(5, 2.2 + mi / 6 + (165 - pace / 6) / 40), 1))
    else:
        a.update(activityName=name or kind.replace("_", " ").title(), duration=(minutes or 60) * 60,
                 averageHR=hr or random.randint(100, 125))
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--through", default=None)
    args = ap.parse_args()
    today = date.today()
    acts, rhr, hrv, sleep, score, vo2 = [], {}, {}, {}, {}, {}
    lift_days = {0: "Chest & Back", 1: "Legs", 2: "Shoulders & Arms", 3: "Back & Bis", 5: "Chest, Tris & Shoulders"}

    # --- history: Jul 20 → Oct 24 training, then sick ---
    d = date(2026, 7, 20)
    fitness = 0.0
    while d <= today:
        sick = date(2026, 10, 25) <= d <= date(2026, 11, 14)
        wd = d.weekday()
        if d == date(2026, 7, 25):
            acts.append(act(d, "running", 13.1, 6150 / 13.1, 172, name="Half Marathon Race"))
        elif not sick and d < date(2026, 10, 25):
            plan = {1: 5, 3: 5, 5: 4, 6: min(12, 7 + (d - date(2026, 8, 1)).days // 14)}
            if wd in plan:
                mi = plan[wd] + random.choice([0, 0, 0.3, -0.2])
                pace = random.uniform(585, 615) - fitness * 8
                hr = int(random.uniform(146, 154) - fitness * 2.5)
                acts.append(act(d, "running", mi, pace, hr))
            fitness = min(3, fitness + 0.012)
        if not sick and wd in lift_days and d < today:
            acts.append(act(d, "strength_training", minutes=65, name=lift_days[wd], hour=17))
        # wellness
        base_rhr = 52 - fitness
        bump = 9 if date(2026, 10, 25) <= d <= date(2026, 11, 3) else (4 if sick else 0)
        rhr[str(d)] = round(base_rhr + bump + random.uniform(-1.5, 1.5))
        hrv[str(d)] = round(68 + fitness * 2 - bump * 2.2 + random.uniform(-6, 6))
        sleep[str(d)] = round(random.uniform(6.3, 8.4), 2)
        score[str(d)] = random.randint(62, 90) - bump * 2
        if not sick and wd in (1, 3, 6):
            vo2[str(d)] = round(47 + fitness * 0.6 + random.uniform(-0.3, 0.3), 1)
        elif sick and wd == 3:
            vo2[str(d)] = round(46.2 + random.uniform(-0.3, 0.3), 1)
        d += timedelta(days=1)

    # --- optional: simulate following the plan ---
    if args.through:
        plan = json.loads((ROOT / "plan" / "plan.json").read_text())
        end = date.fromisoformat(args.through)
        fit = 0.0
        for day in plan["days"]:
            dd = date.fromisoformat(day["date"])
            if dd > end:
                break
            r = day["run"]
            if r and random.random() > 0.08:  # ~8% of runs missed
                mp = {"easy": 615, "recovery": 640, "long": 610, "workout": 545, "race": 515, "shakeout": 630}[r["type"]]
                pace = mp - fit * 10 + random.uniform(-10, 10)
                hr = int({"easy": 148, "recovery": 140, "long": 150, "workout": 163, "race": 170, "shakeout": 138}[r["type"]] - fit * 2)
                acts.append(act(dd, "running", r["miles"] * random.uniform(0.97, 1.03), pace, hr,
                                name="Gainesville Half Marathon" if r["type"] == "race" and r["miles"] < 20 else None))
            if day["lift"] and random.random() > 0.1:
                acts.append(act(dd, "strength_training", minutes=60, name=day["lift"]["focus"], hour=17))
            if day["cross"]:
                acts.append(act(dd, "indoor_cycling", minutes=day["cross"]["minutes"], hour=7))
            fit = min(3, fit + 0.04)
            rhr[str(dd)] = round(51 - fit + random.uniform(-1.5, 1.5))
            hrv[str(dd)] = round(66 + fit * 3 + random.uniform(-6, 6))
            sleep[str(dd)] = round(random.uniform(6.3, 8.4), 2)
            score[str(dd)] = random.randint(64, 90)
            if r and dd.weekday() in (1, 5):
                vo2[str(dd)] = round(46.3 + fit * 0.7 + random.uniform(-0.3, 0.3), 1)

    DATA.mkdir(exist_ok=True)
    (DATA / "activities.json").write_text(json.dumps(sorted(acts, key=lambda a: a["startTimeLocal"]), indent=1))
    (DATA / "wellness.json").write_text(json.dumps({"demo": True, "series": {
        "resting_hr": rhr, "hrv": hrv, "sleep_hours": sleep, "sleep_score": score, "vo2max": vo2}, "errors": []}, indent=1))
    print(f"Demo data: {len(acts)} activities")


if __name__ == "__main__":
    main()
