@echo off
setlocal
cd /d "%~dp0"

if not exist "requirements.txt" (
  echo Could not find requirements.txt. Keep this file in the dmef-analysis folder.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a Python environment...
  where python >nul 2>nul
  if not errorlevel 1 (
    python -m venv .venv
  ) else (
    where py >nul 2>nul
    if errorlevel 1 (
      echo Python was not found. Install Python, then reopen this folder in VS Code.
      pause
      exit /b 1
    )
    py -3 -m venv .venv
  )
  if errorlevel 1 goto failed
)

echo Installing or updating the app dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo Starting the DMEF app. Keep this window open while using it.
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto failed
exit /b 0

:failed
echo The app did not start. Copy the error above if you need help.
pause
exit /b 1
