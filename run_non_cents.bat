@echo off
echo ============================================================
echo  NON-CENTS MARKET FILTER — Daily Update
echo ============================================================

cd /d C:\non-cents

echo.
echo [1/5] Copying watchlist queue (if downloaded from app)...
if exist "C:\Users\jpadi\OneDrive\Desktop\Non-cents market filter\watchlist_queue.json" (
    echo   + Found watchlist_queue.json — copying to data folder...
    copy /Y "C:\Users\jpadi\OneDrive\Desktop\Non-cents market filter\watchlist_queue.json" C:\non-cents\data\watchlist_queue.json
) else (
    echo   (No watchlist_queue.json on Desktop — skipping)
)

echo.
echo [2/5] Fetching market data (Finnhub + yfinance)...
python scripts\fetch_data.py
if errorlevel 1 (
    echo ERROR: fetch_data.py failed. Check output above.
    pause
    exit /b 1
)

echo.
echo [3/5] Syncing with GitHub (pulling remote changes first)...
git pull --rebase origin main
if errorlevel 1 (
    echo ERROR: git pull failed. Check output above.
    pause
    exit /b 1
)

echo.
echo [4/5] Staging and committing...
git add .
git commit -m "Daily data update %date%"

echo.
echo [5/5] Pushing to GitHub...
git push
if errorlevel 1 (
    echo ERROR: git push failed. Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  DONE — Live at https://j2padill-maker.github.io/non-cents-market-filter
echo ============================================================
