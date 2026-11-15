# Road to Miami — Marathon Dashboard (sub-3:45)

Tabs: Home (countdown) · Week Ahead (+ fueling) · Progress (+ badges) · Road to Miami · Recovery · Runs · Plan · Gators Hoops.
Install it like an app: open the site on your phone → Share → **Add to Home Screen**.

Gators basketball scores, schedule, season averages and news come from ESPN's public API (`sync/gators.py`) on every sync.

This is a personal training dashboard. Every 15 minutes it pulls your runs, heart rate, sleep and VO2max from Garmin Connect, compares them with your plan, and republishes the site.

```
Garmin watch ─► Garmin Connect ─► (Personal API, every 15 min) ─► GitHub Actions
                                                                     │
                     plan/build_plan.py (your 11-week plan) ─────────┤
                                                                     ▼
                                  sync.py → compute.py → data/dashboard.json
                                                                     │
                                                            GitHub Pages website
```

## One-time setup (~15 min)

1. **Create a repository.** On GitHub, click **New repository** and name it `marathon-dashboard`.
   - Make it **Public**. GitHub Pages and unlimited Actions minutes are free for public repos.
   - Leave "Add a README" unchecked.
2. **Upload these files.** On the new repo page, click **uploading an existing file**. Drag in *everything* in this folder, including the hidden `.github` folder, then commit.
   - On a Mac, press **Cmd + Shift + .** in Finder to show hidden folders.
3. **Add your Garmin key.** Go to repo **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `GARMIN_PERSONAL_API_KEY`
   - Value: your Personal API key
4. **Turn on Pages.** Go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
5. **Run the first sync.** Go to the **Actions** tab, choose **Sync Garmin & update dashboard**, click **Run workflow**, and wait about 1 minute.
   - The first run backfills everything since June 1.
6. **Open your site** at `https://<your-username>.github.io/marathon-dashboard/`.

After setup, it updates on its own. To force an update right after a run, sync your watch to Garmin Connect, then press **Run workflow** again.

## Changing the plan

Edit the `WEEKS` table in `plan/build_plan.py`, for example to move a long run or swap a workout. Commit the change and the site rebuilds within a minute or two.

## Files

| Path | What it does |
|---|---|
| `plan/build_plan.py` | The 11-week plan (runs, cross-training, lifts, paces). Writes `plan.json` and a calendar file |
| `sync/sync.py` | Pulls activities and wellness data from the Garmin Personal API. Stores no GPS/location data |
| `sync/compute.py` | Builds the dashboard numbers: plan vs actual, projection, efficiency, recovery |
| `sync/demo_data.py` | Fake data for previewing the site without Garmin |
| `site/index.html` | The website |
| `.github/workflows/sync.yml` | The 15-minute schedule, data commit and deploy |

## How the projected finish works

1. It starts from your **July half (1:42:30)**.
2. It moves that up or down with your **Garmin VO2max trend** since July. Raw Garmin VO2max predictions run fast for the marathon, so only the change since July is used.
3. A real race effort, like racing the Gainesville Half, replaces steps 1–2.
4. It adds **~45 seconds per mile your longest run in the last 6 weeks falls short of 18 mi**. Fitness says what you could run; long runs decide whether you can hold it for 26.2.

## Preview locally with fake data

```bash
python plan/build_plan.py
python sync/demo_data.py --through 2026-12-20
DASH_TODAY=2026-12-21 python sync/compute.py
cp data/dashboard.json site/ && cd site && python -m http.server 8000   # open http://localhost:8000
```

Delete `data/*.json` before going live. Demo data is labeled on the page.

## Privacy note

The website and a public repo are visible to anyone who has the link. They show run summaries (distance, pace, heart rate), resting HR, HRV and sleep. No GPS routes or locations are stored.
