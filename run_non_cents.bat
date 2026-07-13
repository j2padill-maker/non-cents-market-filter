@echo off
cd /d C:\non-cents
set "PYTHONIOENCODING=utf-8"

set "LOGDIR=C:\non-cents\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\update_%date:~-4%-%date:~4,2%-%date:~7,2%.log"

echo ============================================================ >> "%LOGFILE%"
echo Run started: %date% %time% >> "%LOGFILE%"

git commit -am "Pre-sync auto-commit %date% %time%" >> "%LOGFILE%" 2>&1

python fetch_data.py >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo FETCH FAILED - skipping commit/push this run. >> "%LOGFILE%"
    goto :end
)

git add fetch_data.py data\cache.json >> "%LOGFILE%" 2>&1
git commit -m "Daily data update %date%" >> "%LOGFILE%" 2>&1

git pull --rebase origin main >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo PULL/REBASE CONFLICT - resolve manually, then push. >> "%LOGFILE%"
    goto :end
)
git push origin main >> "%LOGFILE%" 2>&1

:end
echo Run finished: %date% %time% >> "%LOGFILE%"
echo. >> "%LOGFILE%"
