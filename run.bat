@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py"
if defined PYTHON_CMD goto python_found

where python >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if defined PYTHON_CMD goto python_found

echo [ERROR] Python 3 was not found.
echo Install Python from https://www.python.org/downloads/ and enable "Add Python to PATH".
goto end

:python_found
set "RUNTIME_DIR=%~dp0.runtime"
set "PYTHONPATH=%RUNTIME_DIR%;%PYTHONPATH%"

%PYTHON_CMD% -c "from selenium import webdriver" >nul 2>nul
if errorlevel 1 (
    echo [Setup] Installing the browser automation library locally...
    %PYTHON_CMD% -m pip install -r requirements.txt --target "%RUNTIME_DIR%" --upgrade --quiet
)
if errorlevel 1 (
    echo [ERROR] Required libraries could not be installed.
    goto end
)

%PYTHON_CMD% -c "from selenium import webdriver" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Selenium was installed but could not be loaded.
    goto end
)

%PYTHON_CMD% leetcode_syncer.py

:end
echo.
pause
