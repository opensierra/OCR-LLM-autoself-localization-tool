@echo off
setlocal EnableDelayedExpansion

:: ==========================================================
:: ULTRA ROBUST PYTHON ENVIRONMENT INSTALLER
:: ==========================================================
:: FEATURES:
:: - Auto requests Administrator privileges
:: - Verifies Python installation
:: - Repairs broken venvs
:: - Forces dependency installation
:: - Retries failed installs
:: - Verifies pip integrity
:: - Detects internet connection
:: - Uses safer execution flow
:: - Prevents silent failures
:: - Works even if venv already exists
:: ==========================================================

title Python Environment Installer

:: ==========================================================
:: CONFIG
:: ==========================================================
set "VENV_NAME=venv"
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "REQ_FILE=%SCRIPT_DIR%requirements.txt"
set "VENV_NAME=%SCRIPT_DIR%venv"
set "PYTHON_CMD=python"

echo ==========================================================
echo        PYTHON ENVIRONMENT INITIALIZER
echo ==========================================================
echo.

:: ==========================================================
:: 0. REQUEST ADMIN PRIVILEGES
:: ==========================================================
net session >nul 2>&1

if %errorlevel% neq 0 (
    echo [INFO] Administrator privileges required.
    echo Requesting elevation...
    echo.

    powershell -Command "Start-Process cmd -ArgumentList '/c cd /d ""%~dp0"" && ""%~f0""' -Verb RunAs"
    
    exit /b
)

echo [OK] Running as Administrator.
echo.

:: ==========================================================
:: 1. VERIFY INTERNET CONNECTION
:: ==========================================================
echo [1/9] Checking internet connection...

ping 8.8.8.8 -n 1 >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No internet connection detected.
    echo Please connect to the internet and retry.
    echo.
    pause
    exit /b 1
)

echo [OK] Internet connection available.
echo.

:: ==========================================================
:: 2. VERIFY PYTHON EXISTS
:: ==========================================================
echo [2/9] Checking Python installation...

where %PYTHON_CMD% >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python not found in PATH.
    echo.
    echo Install Python and enable:
    echo     [x] Add Python to PATH
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
    set PYTHON_VERSION=%%i
)

echo [OK] Python detected: !PYTHON_VERSION!
echo.

:: ==========================================================
:: 3. VERIFY PIP
:: ==========================================================
echo [3/9] Verifying pip...

python -m ensurepip --upgrade >nul 2>&1

python -m pip --version >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] pip is broken or unavailable.
    pause
    exit /b 1
)

echo [OK] pip operational.
echo.

:: ==========================================================
:: 4. VERIFY REQUIREMENTS FILE
:: ==========================================================
echo [4/9] Checking requirements.txt...

if not exist "%REQ_FILE%" (
    echo.
    echo [ERROR] requirements.txt not found.
    echo.
    echo Expected file:
    echo     %cd%\%REQ_FILE%
    echo.
    pause
    exit /b 1
)

echo [OK] requirements.txt found.
echo.

:: ==========================================================
:: 5. CREATE OR REPAIR VENV
:: ==========================================================
echo [5/9] Verifying virtual environment...

if exist "%VENV_NAME%" (

    if exist "%VENV_NAME%\Scripts\python.exe" (

        echo Existing venv detected.
        echo Validating integrity...

        "%VENV_NAME%\Scripts\python.exe" --version >nul 2>&1

        if !errorlevel! neq 0 (
            echo.
            echo [WARNING] Virtual environment corrupted.
            echo Recreating...
            rmdir /s /q "%VENV_NAME%"
        )
    ) else (
        echo.
        echo [WARNING] Broken virtual environment detected.
        echo Recreating...
        rmdir /s /q "%VENV_NAME%"
    )
)

if not exist "%VENV_NAME%\Scripts\python.exe" (

    echo Creating virtual environment...

    python -m venv "%VENV_NAME%"

    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Failed creating virtual environment.
        pause
        exit /b 1
    )
)

echo [OK] Virtual environment ready.
echo.

:: ==========================================================
:: 6. ACTIVATE VENV
:: ==========================================================
echo [6/9] Activating virtual environment...

call "%VENV_NAME%\Scripts\activate.bat"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Could not activate virtual environment.
    pause
    exit /b 1
)

echo [OK] Virtual environment activated.
echo.

:: ==========================================================
:: 7. UPGRADE INSTALL TOOLS
:: ==========================================================
echo [7/9] Updating installation tools...

python -m pip install ^
    --upgrade ^
    pip ^
    setuptools ^
    wheel ^
    --no-cache-dir

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Tool upgrade failed.
)

echo [OK] Installation tools ready.
echo.

:: ==========================================================
:: 8. INSTALL DEPENDENCIES
:: ==========================================================
echo [8/9] Installing dependencies...
echo.
echo This may take a long time.
echo DO NOT CLOSE THIS WINDOW.
echo.

python -m pip install ^
    --upgrade ^
    --force-reinstall ^
    --no-cache-dir ^
    --prefer-binary ^
    -r "%REQ_FILE%"

if %errorlevel% neq 0 (

    echo.
    echo [WARNING] Primary installation failed.
    echo Retrying with legacy resolver...
    echo.

    python -m pip install ^
        --upgrade ^
        --force-reinstall ^
        --use-deprecated=legacy-resolver ^
        --no-cache-dir ^
        -r "%REQ_FILE%"
)

if %errorlevel% neq 0 (

    echo.
    echo ==========================================================
    echo INSTALLATION FAILED
    echo ==========================================================
    echo.
    echo Possible causes:
    echo.
    echo - Corrupted package cache
    echo - Antivirus blocking installation
    echo - Firewall restrictions
    echo - Network timeout
    echo - Broken wheel dependency
    echo - Insufficient disk space
    echo.
    echo Installed packages so far:
    echo.
    python -m pip list
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Dependencies installed successfully.
echo.

:: ==========================================================
:: 9. FINAL VALIDATION
:: ==========================================================
echo [9/9] Final validation...

python -c "import sys; print('Python OK:', sys.version)"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python validation failed.
    pause
    exit /b 1
)

echo.
echo Installed package count:
python -m pip list | find /c /v ""

echo.
echo ==========================================================
echo               INSTALLATION COMPLETE
echo ==========================================================
echo.
echo Environment fully configured.
echo.
echo To start your project:
echo.
echo     launch.bat
echo.
pause