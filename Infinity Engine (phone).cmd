@echo off
rem Double-click to open the studio AND make it reachable from your phone or
rem other devices on the same wifi. The black window prints the phone
rem address; type it into your phone's browser. Close the window to stop.
rem Only do this on your home wifi.
cd /d "%~dp0"
python -m engine gui --lan
if errorlevel 1 (
  echo.
  echo Could not start. Make sure Python is installed, then try again.
  pause
)
