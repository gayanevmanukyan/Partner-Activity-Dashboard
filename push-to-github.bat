@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Partnership Desk - push to GitHub
echo ================================================================
echo   Partnership Desk  -  publish to GitHub
echo ================================================================
echo.

REM ---------- 0. is git installed? --------------------------------
where git >nul 2>&1
if errorlevel 1 (
  echo [!] Git is not installed, or not in PATH.
  echo     Install it from https://git-scm.com/download/win and run this again.
  echo.
  pause
  exit /b 1
)

REM ---------- 1. put the workflow in its real place ----------------
if exist "_github\workflows\deploy.yml" (
  if not exist ".github\workflows" mkdir ".github\workflows"
  move /y "_github\workflows\deploy.yml" ".github\workflows\deploy.yml" >nul
  rmdir /s /q "_github" 2>nul
  echo  [ok] .github\workflows\deploy.yml is in place
) else (
  if exist ".github\workflows\deploy.yml" (
    echo  [ok] .github\workflows\deploy.yml already in place
  ) else (
    echo  [!] workflow file not found - continuing without it
  )
)

REM ---------- 2. repository -----------------------------------------
if not exist ".git" (
  git init -b main >nul 2>&1
  if errorlevel 1 (
    git init >nul 2>&1
    git checkout -b main >nul 2>&1
  )
  echo  [ok] git repository created
) else (
  echo  [ok] git repository already here
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
if "%BRANCH%"=="" set "BRANCH=main"
if "%BRANCH%"=="HEAD" set "BRANCH=main"

REM ---------- 3. identity, if it is not set globally -----------------
git config user.email >nul 2>&1
if errorlevel 1 (
  git config user.email "gayane.manukyan@galaxsys.co"
  git config user.name  "Gayane Manukyan"
  echo  [ok] commit identity set for this repository
)

REM ---------- 4. remote ---------------------------------------------
set "URL="
for /f "delims=" %%u in ('git remote get-url origin 2^>nul') do set "URL=%%u"

if defined URL (
  echo  [ok] remote origin: !URL!
  echo.
  set /p "CHANGE=      Push there? Press Enter for yes, or type a different URL: "
  if not "!CHANGE!"=="" (
    git remote set-url origin "!CHANGE!"
    set "URL=!CHANGE!"
  )
) else (
  echo.
  echo  Paste the repository URL from GitHub - the green "Code" button,
  echo  HTTPS tab. It looks like:
  echo      https://github.com/your-name/partnership-desk.git
  echo.
  set /p "URL=  URL: "
  if "!URL!"=="" (
    echo.
    echo  [!] No URL given - nothing to push to.
    pause
    exit /b 1
  )
  git remote add origin "!URL!"
  echo  [ok] remote origin added
)

REM ---------- 5. commit ---------------------------------------------
echo.
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Partnership Desk: dashboard, data and build pipeline" >nul
  echo  [ok] changes committed
) else (
  git rev-parse HEAD >nul 2>&1
  if errorlevel 1 (
    echo  [!] nothing to commit and no history - is the folder empty?
    pause
    exit /b 1
  )
  echo  [ok] nothing new to commit
)

REM ---------- 6. push -------------------------------------------------
echo.
echo  Pushing to %BRANCH% ...
echo  If a GitHub sign-in window appears, confirm it yourself - that is normal.
echo.
git push -u origin %BRANCH%
if errorlevel 1 (
  echo.
  echo  [!] The push was refused. Usually that means the repository on GitHub
  echo      already has a commit in it - a README or a licence added at creation.
  echo      Trying to merge that in and push again...
  echo.
  git pull --rebase origin %BRANCH%
  if errorlevel 1 (
    echo.
    echo  [!] Could not merge automatically. Send me what is written above
    echo      and we will sort it out.
    echo.
    pause
    exit /b 1
  )
  git push -u origin %BRANCH%
  if errorlevel 1 (
    echo.
    echo  [!] Still refused. Send me what is written above.
    echo.
    pause
    exit /b 1
  )
)

echo.
echo ================================================================
echo   Done. The code is on GitHub.
echo.
echo   Next, once only, in the repository on github.com:
echo     Settings  -^>  Pages  -^>  Source: GitHub Actions
echo.
echo   The page builds itself and appears a minute or two later at
echo     https://^<your-name^>.github.io/partnership-desk/
echo ================================================================
echo.
pause
