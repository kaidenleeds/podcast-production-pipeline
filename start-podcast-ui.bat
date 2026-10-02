@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup. This may take a minute.
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 goto :failed
  ".venv\Scripts\python.exe" -m pip install -e .
  if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -m podcast_pipeline ui
goto :eof

:failed
echo.
echo Setup failed. Make sure Python 3.10 or newer is installed.
pause
exit /b 1
