@echo off
setlocal

REM So this bat file can be called from a different working directory.
cd /d "%~dp0"

REM Prefer bundled Python if present.
if exist ".\python\python.exe" (
    set "PATH=.\python;%PATH%"
    .\python\python.exe -I .\server.py
    goto :done
)

REM Fallback to Windows Python launcher.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 -I .\server.py
    goto :done
)

REM Final fallback to python on PATH.
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python -I .\server.py
    goto :done
)

echo Error: Could not find Python.
echo Install Python 3 and ensure "py" or "python" is on PATH.

:done
echo Press any key to quit...
pause >nul