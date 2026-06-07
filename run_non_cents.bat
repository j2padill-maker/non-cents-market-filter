@echo off
echo =======================================
echo  Non-Cents Market Filter - Daily Run
echo =======================================
echo.

cd C:\non-cents

echo [1/5] Syncing with GitHub...
git pull --rebase origin main
echo.

echo [2/5] Copying latest files from Desktop...
copy /Y "C:\Users\jpadi\OneDrive\Desktop\Non-cents market filter\index.html" C:\non-cents\index.html 2>nul && echo   index.html copied || echo   index.html not found in Desktop folder (skipping)
copy /Y "C:\Users\jpadi\OneDrive\Desktop\Non-cents market filter\fetch_data.py" C:\non-cents\scripts\fetch_data.py 2>nul && echo   fetch_data.py copied || echo   fetch_data.py not found in Desktop folder (skipping)
echo.

echo [3/5] Fetching fresh market data (15-20 mins)...
python scripts\fetch_data.py
echo.

echo [4/5] Staging all changes...
git add .
echo.

echo [5/5] Committing and pushing to GitHub...
git commit -m "Daily data refresh %date%"
git push
echo.

echo =======================================
echo  Done! App is live at:
echo  https://j2padill-maker.github.io/non-cents-market-filter/
echo =======================================
pause
