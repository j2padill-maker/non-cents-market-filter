@echo off
cd /d C:\non-cents
set "PYTHONIOENCODING=utf-8"

set "LOGDIR=C:\non-cents\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\update_%date:~-4%-%date:~4,2%-%date:~7,2%.log"

echo ============================================================ >> "%LOGFILE%"
echo Run started: %date% %time% >> "%LOGFILE%"

REM 1. Discard any stale local changes to GENERATED files so they never enter
REM    the pull. This is the fix for the recurring cache.json rebase conflict:
REM    we regenerate these below, so a local copy is never worth keeping.
git checkout -- data\cache.json data\watchlist.json >> "%LOGFILE%" 2>&1

REM 2. Commit any real (code) changes you made before syncing.
git commit -am "Pre-sync auto-commit %date% %time%" >> "%LOGFILE%" 2>&1

REM 3. Sync with remote FIRST, while there are no local generated changes to
REM    conflict against. This is a clean fast-forward, not a merge of two caches.
git pull --rebase origin main >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo PULL/REBASE CONFLICT - resolve manually, then re-run. >> "%LOGFILE%"
    goto :end
)

REM 4. Regenerate data locally.
python scripts\fetch_data.py >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo FETCH FAILED - skipping commit/push this run. >> "%LOGFILE%"
    goto :end
)

REM 5. Commit the freshly generated data and push (clean fast-forward).
git add scripts\fetch_data.py data\cache.json data\watchlist.json >> "%LOGFILE%" 2>&1
git commit -m "Daily data update %date%" >> "%LOGFILE%" 2>&1
git push origin main >> "%LOGFILE%" 2>&1

:end
echo Run finished: %date% %time% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
