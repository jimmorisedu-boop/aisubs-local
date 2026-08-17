@echo off
setlocal
cd /d "%~dp0"

set "PYTHONNOUSERSITE=1"
set "PATH=%~dp0python;%~dp0ffmpeg;%PATH%"

if "%~1"=="" (
    "%~dp0python\python.exe" "%~dp0app.py"
) else (
    "%~dp0python\python.exe" "%~dp0pipeline.py" %*
)

endlocal
