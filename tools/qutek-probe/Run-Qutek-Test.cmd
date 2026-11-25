@echo off
cd /d "%~dp0"
where node.exe >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 22 or newer from https://nodejs.org/ before running the test.
  goto done
)
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 22 ? 0 : 1)"
if errorlevel 1 (
  echo Node.js 22 or newer is required.
  goto done
)
call npm.cmd ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 goto done
node probe.mjs
:done
pause
