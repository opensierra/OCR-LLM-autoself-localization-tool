@echo off
setlocal EnableDelayedExpansion

title Vivo DPI

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "VENV_NAME=%SCRIPT_DIR%venv"
set "PYTHON_EXE=%VENV_NAME%\Scripts\python.exe"
set "MAIN_FILE=%SCRIPT_DIR%main.py"

cls

if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment not found.
    echo Please run init.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%MAIN_FILE%" (
    echo ERROR: main.py not found.
    echo.
    pause
    exit /b 1
)

call "%VENV_NAME%\Scripts\activate.bat"

if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)

echo Environment ready.
echo Launching Flask server...
echo This may take a few seconds while dependencies initialize.
echo.

start "loader" /min cmd /c ^
"set /a t=0 & ^
:loop ^
set /a t+=1 ^
echo Server starting... !t!s ^
timeout /t 1 >nul ^
goto loop"

"%PYTHON_EXE%" "%MAIN_FILE%"

taskkill /fi "windowtitle eq loader*" /f >nul 2>&1

echo.
echo Application closed.
echo.

pause