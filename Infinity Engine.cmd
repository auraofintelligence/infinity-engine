@echo off
rem Double-click this to open the Infinity Engine control panel in your
rem browser. Leave the black window open while you use it; close it to stop.
cd /d "%~dp0"
python -m engine gui
if errorlevel 1 (
  echo.
  echo Could not start. Make sure Python is installed, then try again.
  pause
)
