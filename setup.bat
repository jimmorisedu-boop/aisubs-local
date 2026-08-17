@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   AISubs - первичная установка
echo ============================================
echo.
echo Будет скачано около 600 МБ (Python и ffmpeg).
echo Модель распознавания речи скачается позже,
echo при первом запуске.
echo.

set "PYTHONNOUSERSITE=1"
set "PY=%~dp0python\python.exe"

if exist "%PY%" (
    echo [1/4] Python уже установлен - пропускаю.
    goto :deps
)

echo [1/4] Скачиваю портативный Python 3.11...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "New-Item -ItemType Directory -Force -Path 'scratch' | Out-Null;" ^
  "Invoke-WebRequest 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'scratch\python.zip';" ^
  "Expand-Archive -Path 'scratch\python.zip' -DestinationPath 'python' -Force;" ^
  "Remove-Item 'scratch\python.zip';" ^
  "(Get-Content 'python\python311._pth') -replace '^#import site','import site' | Set-Content 'python\python311._pth' -Encoding ascii"
if errorlevel 1 goto :fail

echo [2/4] Устанавливаю pip...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'scratch\get-pip.py'"
if errorlevel 1 goto :fail
"%PY%" "scratch\get-pip.py" --no-warn-script-location
if errorlevel 1 goto :fail
del /q "scratch\get-pip.py" 2>nul

:deps
echo [3/4] Устанавливаю библиотеки Python...
"%PY%" -m pip install --no-warn-script-location -r requirements.txt
if errorlevel 1 goto :fail

if exist "%~dp0ffmpeg\ffmpeg.exe" (
    echo [4/4] ffmpeg уже установлен - пропускаю.
    goto :done
)

echo [4/4] Скачиваю ffmpeg...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "New-Item -ItemType Directory -Force -Path 'scratch' | Out-Null;" ^
  "Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'scratch\ffmpeg.zip';" ^
  "Expand-Archive -Path 'scratch\ffmpeg.zip' -DestinationPath 'scratch\ffmpeg' -Force;" ^
  "New-Item -ItemType Directory -Force -Path 'ffmpeg' | Out-Null;" ^
  "Get-ChildItem 'scratch\ffmpeg' -Recurse -Include ffmpeg.exe,ffprobe.exe | ForEach-Object { Copy-Item $_.FullName 'ffmpeg\' -Force };" ^
  "Remove-Item 'scratch\ffmpeg' -Recurse -Force; Remove-Item 'scratch\ffmpeg.zip' -Force"
if errorlevel 1 goto :fail

:done
echo.
echo ============================================
echo   Готово. Запускайте run.bat
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo ============================================
echo   Установка прервалась.
echo   Проверьте интернет и запустите setup.bat снова -
echo   уже скачанное повторно качаться не будет.
echo ============================================
echo.
pause
exit /b 1
