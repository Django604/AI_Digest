@echo off
setlocal

cd /d "%~dp0"
set "PYTHONUTF8=1"
title AI Digest Dashboard Server

echo [AI_Digest] Starting dashboard server...
echo [AI_Digest] Press Ctrl+C to stop.
echo.

if exist "%~dp0.venv\Scripts\python.exe" goto use_dot_venv
if exist "%~dp0venv\Scripts\python.exe" goto use_venv

where python >nul 2>nul
if not errorlevel 1 goto use_python

set "PYTHON_EXE="
for /d %%D in ("%LocalAppData%\Programs\Python\Python*") do if not defined PYTHON_EXE if exist "%%~fD\python.exe" set "PYTHON_EXE=%%~fD\python.exe"
if defined PYTHON_EXE goto use_detected

set "PYTHON_EXE="
for /d %%D in ("%ProgramFiles%\Python*") do if not defined PYTHON_EXE if exist "%%~fD\python.exe" set "PYTHON_EXE=%%~fD\python.exe"
if defined PYTHON_EXE goto use_detected

if defined ProgramFiles(x86) (
  set "PYTHON_EXE="
  for /d %%D in ("%ProgramFiles(x86)%\Python*") do if not defined PYTHON_EXE if exist "%%~fD\python.exe" set "PYTHON_EXE=%%~fD\python.exe"
  if defined PYTHON_EXE goto use_detected
)

where py >nul 2>nul
if not errorlevel 1 goto use_py

echo [AI_Digest] Python was not found. Please install Python or add it to PATH.
pause
exit /b 1

:use_dot_venv
call "%~dp0.venv\Scripts\python.exe" -X utf8 scripts\serve_dashboard.py %*
goto finish

:use_venv
call "%~dp0venv\Scripts\python.exe" -X utf8 scripts\serve_dashboard.py %*
goto finish

:use_python
call python -X utf8 scripts\serve_dashboard.py %*
goto finish

:use_detected
call "%PYTHON_EXE%" -X utf8 scripts\serve_dashboard.py %*
goto finish

:use_py
call py -3 -X utf8 scripts\serve_dashboard.py %*

:finish
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [AI_Digest] Dashboard server exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
