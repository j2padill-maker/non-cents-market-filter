@echo off
rem Non-Cents catch-up: runs an update only if the scheduled one was missed.
rem Log: C:\non-cents\logs\catchup.log
cd /d C:\non-cents
set "PYTHONIOENCODING=utf-8"
python scripts\catchup_update.py
