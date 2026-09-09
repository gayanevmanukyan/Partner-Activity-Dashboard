@echo off
REM ---------------------------------------------------------------
REM  Puts the GitHub Actions workflow into place.
REM  Run this once, by double-clicking it, before the first git push.
REM
REM  It exists because folders whose name starts with a dot cannot be
REM  written here remotely, so the workflow arrived as _github\ and
REM  has to be renamed to .github\.
REM ---------------------------------------------------------------
cd /d "%~dp0"
if not exist "_github\workflows\deploy.yml" (
  echo _github\workflows\deploy.yml not found - nothing to do.
  pause
  exit /b 1
)
if not exist ".github\workflows" mkdir ".github\workflows"
move /y "_github\workflows\deploy.yml" ".github\workflows\deploy.yml" >nul
rmdir /s /q "_github" 2>nul
echo Done - .github\workflows\deploy.yml is in place.
pause
