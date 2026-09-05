@echo off
REM Local CMS launcher for ddsverified.ir
REM Double-click this file to start the CMS in a new window.
REM Browser opens to http://127.0.0.1:8765/ automatically.
REM Close this window (or Ctrl+C) to stop the CMS.

start "DDSVerified CMS" cmd /k "python cms.py & timeout /t 2 /nobreak >nul & start http://127.0.0.1:8765/"