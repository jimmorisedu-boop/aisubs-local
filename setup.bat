@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   AISubs - первичная установка
echo ============================================
echo.
echo Будет скачано:
echo   - Python и ffmpeg           ~600 МБ
echo   - библиотеки CUDA           ~550 МБ (только если есть видеокарта NVIDIA)
echo   - модель распознавания      ~3 ГБ  (можно отказаться и скачать позже)
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
echo [3/6] Устанавливаю библиотеки Python...
"%PY%" -m pip install --no-warn-script-location -r requirements.txt
if errorlevel 1 goto :fail

if exist "%~dp0ffmpeg\ffmpeg.exe" (
    echo [4/6] ffmpeg уже установлен - пропускаю.
    goto :cuda
)

echo [4/6] Скачиваю ffmpeg...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "New-Item -ItemType Directory -Force -Path 'scratch' | Out-Null;" ^
  "Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'scratch\ffmpeg.zip';" ^
  "Expand-Archive -Path 'scratch\ffmpeg.zip' -DestinationPath 'scratch\ffmpeg' -Force;" ^
  "New-Item -ItemType Directory -Force -Path 'ffmpeg' | Out-Null;" ^
  "Get-ChildItem 'scratch\ffmpeg' -Recurse -Include ffmpeg.exe,ffprobe.exe | ForEach-Object { Copy-Item $_.FullName 'ffmpeg\' -Force };" ^
  "Remove-Item 'scratch\ffmpeg' -Recurse -Force; Remove-Item 'scratch\ffmpeg.zip' -Force"
if errorlevel 1 goto :fail

:cuda
rem cuBLAS is loaded by name at runtime and is NOT part of the NVIDIA driver -
rem without it the GPU path fails and everything silently runs on the CPU.
where nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo [5/6] Видеокарта NVIDIA не найдена - пропускаю библиотеки CUDA.
    echo       Распознавание будет работать на процессоре.
    goto :model
)

"%PY%" -c "import nvidia.cublas, os; print(os.path.dirname(nvidia.cublas.__file__))" >nul 2>&1
if not errorlevel 1 (
    echo [5/6] Библиотеки CUDA уже установлены - пропускаю.
    goto :model
)

echo [5/6] Видеокарта NVIDIA найдена. Скачиваю библиотеки CUDA (~550 МБ)...
"%PY%" -m pip install --no-warn-script-location nvidia-cublas-cu12
if errorlevel 1 (
    echo       Не получилось. Распознавание будет работать на процессоре,
    echo       установку можно повторить позже, запустив setup.bat снова.
)

:model
echo.
echo [6/6] Модель распознавания речи.
echo.
echo   1. large-v3          ~3 ГБ    максимальное качество
echo   2. distil-large-v3   ~1.5 ГБ  быстрее, почти так же точно
echo   3. small             ~500 МБ  быстро, качество ниже
echo   4. пропустить - скачается сама при первой обработке видео
echo.
set "MODELCHOICE="
set /p MODELCHOICE="Что скачать? [1]: "
if "%MODELCHOICE%"=="" set "MODELCHOICE=1"

if "%MODELCHOICE%"=="4" (
    echo Пропускаю. Модель скачается при первой обработке видео.
    goto :done
)
set "MODELNAME=large-v3"
if "%MODELCHOICE%"=="2" set "MODELNAME=distil-large-v3"
if "%MODELCHOICE%"=="3" set "MODELNAME=small"

"%PY%" download_model.py %MODELNAME%
if errorlevel 1 (
    echo Модель не скачалась - ничего страшного, она загрузится
    echo автоматически при первой обработке видео.
)

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
