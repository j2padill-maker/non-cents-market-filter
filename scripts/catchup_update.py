"""
Non-Cents catch-up updater.

Task Scheduler runs this hourly. It does real work only when an update was
missed (for example, the laptop was off at 4:30 PM). When it runs an update,
it calls the existing run_non_cents.bat, so the update logic stays in one place.

"Missed" means all of these are true:
  - the most recent scheduled slot (SLOTS) passed more than GRACE_MIN ago,
    so the regular 4:30 PM task gets its chance first
  - the last commit on GitHub (origin/main) touching data/cache.json is
    older than that slot. Laptop runs count: this laptop or the home laptop
    (GitHub Action commits are ignored)
  - no update is running right now (today's logs\\update_*.log was
    written to in the last BUSY_MIN minutes)

Catch-up log: C:\\non-cents\\logs\\catchup.log
Full update output still goes to: C:\\non-cents\\logs\\update_YYYY-MM-DD.log
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---- Settings -----------------------------------------------------------
SLOTS = ["16:30"]   # matches the NonCentsUpdate task on this laptop
GRACE_MIN = 60      # wait this long after a slot before treating it as missed
BUSY_MIN = 40       # an update log written this recently means a run is in progress
# -------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = REPO / "logs"
LOG_FILE = LOG_DIR / "catchup.log"
RUNNER = REPO / "run_non_cents.bat"


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git_out(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def last_slot(now):
    """Most recent scheduled slot at or before `now`."""
    out = []
    for back in (0, 1):
        d = (now - timedelta(days=back)).date()
        for s in SLOTS:
            h, m = map(int, s.split(":"))
            t = datetime(d.year, d.month, d.day, h, m)
            if t <= now:
                out.append(t)
    return max(out)


def update_in_progress():
    newest = max(LOG_DIR.glob("update_*.log"), key=lambda p: p.stat().st_mtime, default=None)
    if newest is None:
        return False
    age_min = (time.time() - newest.stat().st_mtime) / 60
    return age_min < BUSY_MIN


def last_remote_update():
    git_out("fetch", "origin", "--quiet")
    # Only laptop runs count. GitHub Action data is degraded (no RSI, partial
    # universe), so it must not satisfy the "already updated" check.
    ts = git_out("log", "-1", "--format=%ct", "--author=j2padill-maker", "origin/main", "--", "data/cache.json")
    return datetime.fromtimestamp(int(ts)) if ts else datetime.min


def main():
    now = datetime.now()
    slot = last_slot(now)

    if now < slot + timedelta(minutes=GRACE_MIN):
        return 0  # still inside the regular task's window; check quietly next hour

    if update_in_progress():
        log("An update is already running (update log was written recently). Skipping.")
        return 0

    try:
        last = last_remote_update()
    except RuntimeError as e:
        log(f"Can't reach GitHub (no internet yet?). Will retry next hour. {e}")
        return 0

    if last >= slot:
        log(f"Up to date. Last data update {last:%a %m/%d %I:%M %p}. Nothing to do.")
        return 0

    log(f"MISSED UPDATE. Last data update {last:%a %m/%d %I:%M %p}, "
        f"expected by {slot:%a %m/%d %I:%M %p}. Running run_non_cents.bat ...")
    rc = subprocess.run(["cmd", "/c", str(RUNNER)], cwd=REPO).returncode

    try:
        after = last_remote_update()
    except RuntimeError:
        after = last
    if after >= slot:
        log(f"Catch-up succeeded. GitHub now shows data from {after:%a %m/%d %I:%M %p}.")
        return 0
    log(f"Catch-up did NOT reach GitHub (exit code {rc}). Check today's logs\\update_*.log. "
        f"Will try again next hour.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
