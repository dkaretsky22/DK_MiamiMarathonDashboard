"""Builds plan/plan.json (and a calendar file) for the Miami Marathon block.

Edit the WEEKS table below, then run:  python plan/build_plan.py
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GOAL = {
    "race": "Miami Marathon",
    "race_date": "2027-01-31",
    "goal_time": "3:45:00",
    "goal_pace": "8:35",
    "tuneup": {"race": "Gainesville Half Marathon", "date": "2027-01-16"},
    "reference_result": {"race": "Half marathon (July 2026)", "distance_mi": 13.1, "time": "1:42:30"},
}

PACES = {
    "easy": "10:00–10:45",
    "recovery": "10:30+",
    "mp": "8:35",
    "tempo": "7:55–8:05",
    "interval": "7:30–7:40",
}

# Lift labels
CB, SA, LEGS, BB, CTS = "Chest & Back", "Shoulders & Arms", "Legs", "Back & Bis", "Chest, Tris & Shoulders"


def run(kind, miles, title, details=""):
    return {"type": kind, "miles": miles, "title": title, "details": details}


def easy(m, extra=""):
    return run("easy", m, f"Easy {m} mi" + (f" + {extra}" if extra else ""), f"Conversational, {PACES['easy']}/mi.")


def rec(m):
    return run("recovery", m, f"Recovery {m} mi", f"Very easy, {PACES['recovery']}/mi. Shake out the long run.")


def long_(m, details="Easy, steady effort. Practice fueling (gel every ~45 min once over 10 mi)."):
    return run("long", m, f"Long run {m} mi", details)


def wo(m, title, details):
    return run("workout", m, title, details)


def bike(minutes=30):
    return {"type": "bike", "minutes": minutes, "title": f"Easy bike {minutes} min", "details": "Conversational / nose-breathing effort."}


def incline(minutes=30):
    return {"type": "incline_walk", "minutes": minutes, "title": f"Incline walk {minutes} min",
            "details": "10–12% incline, 3.0–3.5 mph, no rails. Swap for bike if legs are sore."}


def lift(focus, note=""):
    return {"focus": focus, "details": note}


REST = None

# Each week: (label, location, {weekday_index: (run, cross, lift, note)}) — Monday = 0
WEEKS = [
    ("Return", "Gainesville", {
        0: (easy(3), None, lift(CB, "~70% volume, 2–3 reps in reserve"), ""),
        1: (None, bike(30), lift(LEGS, "Light — ~70% volume"), ""),
        2: (easy(3), None, lift(SA, "~70% volume"), ""),
        3: (None, incline(30), lift(BB, "~70% volume"), "Full rest instead if you feel run-down."),
        4: (long_(6, "Easy the whole way. No lifting."), None, None, ""),
        5: (easy(3, "4 strides"), None, lift(CTS, "~70% volume"), "Strides only if you feel good."),
        6: (None, None, None, "Travel to NY — full rest."),
    }),
    ("Rebuild", "New York (Thanksgiving)", {
        0: (easy(3), None, lift(CB), ""),
        1: (run("easy", 5, "Easy 5 mi + 6 strides", "Easy pace, then 6 × 20 sec quick & relaxed."), None, lift(LEGS), ""),
        2: (None, bike(35), lift(SA), ""),
        3: (easy(4), None, None, "Thanksgiving — Turkey Trot is fine at steady effort, not a race."),
        4: (long_(8), None, None, ""),
        5: (rec(3), None, lift(BB), ""),
        6: (None, None, lift(CTS), "Travel back to Gainesville."),
    }),
    ("Build 1", "Gainesville", {
        0: (easy(4), None, lift(CB), ""),
        1: (wo(6, "Tempo: 3 × 1 mi", f"1.5 mi warm-up · 3 × 1 mi @ {PACES['tempo']} w/ 90 sec jog · 1.5 mi cool-down"), None, lift(LEGS), "Run AM, lift PM."),
        2: (None, bike(40), lift(SA), ""),
        3: (easy(4), None, lift(BB), ""),
        4: (long_(10), None, None, ""),
        5: (rec(3), None, lift(CTS), ""),
        6: (None, None, None, "Full rest."),
    }),
    ("Build 2", "Gainesville", {
        0: (easy(4), None, lift(CB), ""),
        1: (wo(6, "Tempo: 2 × 2 mi", f"1 mi warm-up · 2 × 2 mi @ {PACES['tempo']} w/ 2 min jog · 1 mi cool-down"), None, lift(LEGS), "Run AM, lift PM."),
        2: (None, incline(35), lift(SA), ""),
        3: (easy(5), None, lift(BB), ""),
        4: (long_(13, f"10 easy, last 3 @ marathon pace ({PACES['mp']})."), None, None, "First marathon-pace miles."),
        5: (rec(3), None, lift(CTS), ""),
        6: (None, None, None, "Full rest."),
    }),
    ("Cutback + travel", "Gainesville → New York", {
        0: (wo(5, "MP run: 3 mi @ 8:35", f"1 mi warm-up · 3 mi @ {PACES['mp']} · 1 mi cool-down"), None, lift(LEGS), "Before travel."),
        1: (None, None, None, "Travel to NY (approx.) — rest."),
        2: (easy(4), None, lift(CB), ""),
        3: (easy(4), None, lift(BB), ""),
        4: (None, bike(40), lift(SA), ""),
        5: (long_(11), None, None, "Cutback week."),
        6: (rec(3), None, lift(CTS), ""),
    }),
    ("Build 3", "New York", {
        0: (easy(5), None, lift(CB), ""),
        1: (wo(7, "MP run: 5 mi @ 8:35", f"1 mi warm-up · 5 mi @ {PACES['mp']} · 1 mi cool-down"), None, lift(LEGS), "Treadmill at 1% if icy."),
        2: (None, bike(40), lift(SA), ""),
        3: (easy(5), None, lift(BB), ""),
        4: (None, None, None, "Christmas — rest (optional easy bike)."),
        5: (long_(15), None, None, ""),
        6: (rec(3), None, lift(CTS), ""),
    }),
    ("Peak", "New York", {
        0: (easy(4), None, lift(CB), ""),
        1: (wo(8, "Tempo: 3 × 1.5 mi", f"1.5 mi warm-up · 3 × 1.5 mi @ {PACES['tempo']} w/ 2 min jog · 1 mi cool-down"), None, lift(LEGS, "Last heavy leg day — maintenance from here"), ""),
        2: (None, bike(40), lift(SA), ""),
        3: (easy(5), None, lift(BB), ""),
        4: (None, None, None, "New Year's Day — rest before the long run."),
        5: (long_(18, f"Peak long run. Easy; gel every 45 min; last 2 mi can drift toward {PACES['mp']}."), None, None, "Biggest run of the block."),
        6: (rec(3), None, lift(CTS), ""),
    }),
    ("Sharpen", "New York → Gainesville", {
        0: (easy(4), None, lift(CB), ""),
        1: (wo(7, "Tempo: 2 × 2.5 mi", f"1 mi warm-up · 2 × 2.5 mi @ {PACES['tempo']} w/ 2 min jog · 1 mi cool-down"), None, lift(LEGS, "Maintenance: lighter, fewer sets"), ""),
        2: (easy(5), None, lift(SA), ""),
        3: (easy(3), None, lift(BB), ""),
        4: (None, None, None, "Travel back to Gainesville — rest."),
        5: (long_(15, f"7 easy, then 8 @ marathon pace ({PACES['mp']}). Race-day fueling and shoes."), None, None, "Dress rehearsal for race pace."),
        6: (None, None, lift(CTS), "Rest from running."),
    }),
    ("Tune-up race", "Gainesville", {
        0: (easy(4), None, lift(CB), ""),
        1: (wo(6, "MP run: 4 mi @ 8:35", f"1 mi warm-up · 4 mi @ {PACES['mp']} · 1 mi cool-down"), None, lift(LEGS, "Light maintenance"), ""),
        2: (None, bike(30), lift(SA), ""),
        3: (easy(4), None, lift(BB), ""),
        4: (run("shakeout", 2, "Shakeout 2 mi + 4 strides", "Very easy."), None, None, ""),
        5: (run("race", 14, "Gainesville Half Marathon", f"1 mi warm-up · first 10 mi @ {PACES['mp']} · last 5K ~8:00. Controlled — NOT all-out."), None, None, "Race-day rehearsal: breakfast, gels, shoes."),
        6: (None, None, lift(CTS, "Light"), "Rest from running."),
    }),
    ("Taper", "Gainesville", {
        0: (rec(3), None, lift(CB, "Light"), ""),
        1: (wo(6, "Intervals: 4 × 1 mi", f"1 mi warm-up · 4 × 1 mi @ {PACES['tempo']} w/ 90 sec jog · 1 mi cool-down"), None, lift(LEGS, "Light — last leg session"), ""),
        2: (None, bike(30), lift(SA, "Light"), ""),
        3: (easy(5), None, lift(BB, "Light"), ""),
        4: (long_(10, "Easy. Last long run."), None, None, ""),
        5: (easy(3), None, lift(CTS, "Light"), ""),
        6: (None, None, None, "Full rest."),
    }),
    ("Race week", "Gainesville → Miami", {
        0: (easy(4), None, lift(CB, "Very light, upper only"), ""),
        1: (wo(5, "MP tune: 2 mi @ 8:35", f"1.5 mi warm-up · 2 mi @ {PACES['mp']} · 1.5 mi cool-down"), None, None, "No leg lifting this week."),
        2: (easy(3), None, lift(SA, "Very light"), ""),
        3: (easy(3, "4 strides"), None, None, "Start carb-loading Friday."),
        4: (None, None, None, "Rest. Travel to Miami; pick up bib."),
        5: (run("shakeout", 2, "Shakeout 2 mi", "15–20 min very easy + 3 strides."), None, None, "Lay out gear tonight."),
        6: (run("race", 26.2, "MIAMI MARATHON", f"Goal 3:45 → {PACES['mp']}/mi. First 3 mi at 8:40–8:45, settle into 8:35, push only after mile 20."), None, None, "Race day."),
    }),
]

START = date(2026, 11, 16)


def build():
    days = []
    weeks = []
    for wi, (label, location, sched) in enumerate(WEEKS):
        wk_start = START + timedelta(weeks=wi)
        wk_miles = 0.0
        for d in range(7):
            run_, cross, lift_, note = sched.get(d, (None, None, None, ""))
            day = wk_start + timedelta(days=d)
            miles = run_["miles"] if run_ else 0
            wk_miles += miles
            days.append({
                "date": day.isoformat(),
                "week": wi + 1,
                "location": location,
                "run": run_,
                "cross": cross,
                "lift": lift_,
                "note": note,
            })
        weeks.append({
            "week": wi + 1,
            "label": label,
            "location": location,
            "start": wk_start.isoformat(),
            "end": (wk_start + timedelta(days=6)).isoformat(),
            "planned_miles": round(wk_miles, 1),
        })
    plan = {"goal": GOAL, "paces": PACES, "weeks": weeks, "days": days}
    (ROOT / "plan.json").write_text(json.dumps(plan, indent=2))
    return plan


# ---------- calendar export (.ics) ----------
TIMES = {  # local start time + duration (minutes)
    "run_weekday": ("08:00", 45), "run_long": ("08:00", None), "run_weekend": ("09:00", 45),
    "cross": ("07:30", 45), "lift_weekday": ("16:30", 75), "lift_weekend": ("11:00", 75),
}


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _vevent(uid, day: date, hhmm: str, minutes: int, summary: str, desc: str) -> str:
    h, m = map(int, hhmm.split(":"))
    start = datetime(day.year, day.month, day.day, h, m)
    end = start + timedelta(minutes=minutes)
    f = "%Y%m%dT%H%M%S"
    return "\r\n".join([
        "BEGIN:VEVENT", f"UID:{uid}@miami-marathon-plan", f"DTSTAMP:{datetime.now(UTC).strftime(f)}Z",
        f"DTSTART;TZID=America/New_York:{start.strftime(f)}", f"DTEND;TZID=America/New_York:{end.strftime(f)}",
        f"SUMMARY:{_esc(summary)}", f"DESCRIPTION:{_esc(desc)}", "END:VEVENT",
    ])


def build_ics(plan, from_week=1, path=None):
    evs = []
    for d in plan["days"]:
        if d["week"] < from_week:
            continue
        day = date.fromisoformat(d["date"])
        weekend = day.weekday() >= 5
        r, c, l = d["run"], d["cross"], d["lift"]
        if r:
            if r["type"] in ("long", "race"):
                hhmm, mins = ("07:00" if r["type"] == "race" else "08:00"), int(r["miles"] * 11) + 15
                icon = "🏁" if r["type"] == "race" else "🏃"
                summ = f"{icon} {r['title'].upper() if r['type'] == 'long' else r['title']}"
            else:
                hhmm, mins = TIMES["run_weekend" if weekend else "run_weekday"]
                mins = max(mins, int(r["miles"] * 11) + 10)
                summ = f"🏃 {r['title']}"
            evs.append(_vevent(f"{d['date']}-run", day, hhmm, mins, summ, "\n".join(x for x in [r["details"], d["note"]] if x)))
        if c:
            icon = "🚴" if c["type"] == "bike" else "🚶"
            evs.append(_vevent(f"{d['date']}-cross", day, TIMES["cross"][0], c["minutes"] + 15, f"{icon} {c['title']}", c["details"]))
        if l:
            hhmm, mins = TIMES["lift_weekend" if weekend else "lift_weekday"]
            evs.append(_vevent(f"{d['date']}-lift", day, hhmm, mins, f"🏋️ Lift – {l['focus']}", l["details"] or ""))
    tz = "\r\n".join([
        "BEGIN:VTIMEZONE", "TZID:America/New_York",
        "BEGIN:STANDARD", "DTSTART:19701101T020000", "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
        "TZOFFSETFROM:-0400", "TZOFFSETTO:-0500", "TZNAME:EST", "END:STANDARD",
        "BEGIN:DAYLIGHT", "DTSTART:19700308T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
        "TZOFFSETFROM:-0500", "TZOFFSETTO:-0400", "TZNAME:EDT", "END:DAYLIGHT", "END:VTIMEZONE",
    ])
    ics = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Miami Marathon Plan//EN",
                       "X-WR-CALNAME:Miami Marathon Training", tz, *evs, "END:VCALENDAR"]) + "\r\n"
    (path or ROOT / "plan.ics").write_text(ics)
    return len(evs)


if __name__ == "__main__":
    p = build()
    for w in p["weeks"]:
        print(f"Week {w['week']:>2} {w['start']}  {w['planned_miles']:>5} mi  {w['label']} ({w['location']})")
