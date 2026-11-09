@echo off
rem Double-click or run from the repo folder. Passes flags through: launch_windows.cmd -Clean
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_windows.ps1" %*
pause
