<#
    AISubs installer.

    The logic lives here rather than in setup.bat because cmd.exe reads .bat
    files in the OEM code page: Russian text saved as UTF-8 turns into garbage
    and, worse, the multi-byte characters break the parsing of multi-line
    commands, so the script fell apart into "not recognized" errors.
#>
param(
    # large-v3 | distil-large-v3 | small | skip | ask
    [string]$Model = "ask",

    # Print the header and exit without touching anything - used by the tests
    # and handy for checking that the launcher runs at all.
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Double-clicking gives no -Model, and that run should end with a pause so the
# window does not vanish. An explicit -Model means automation: no pause.
$Interactive = ($Model -eq "ask")

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONNOUSERSITE = "1"
$Py = Join-Path $Root "python\python.exe"
$Scratch = Join-Path $Root "scratch"

function Say([string]$text, [string]$color = "Gray") {
    Write-Host $text -ForegroundColor $color
}

function Fail([string]$text) {
    Say ""
    Say "============================================" "Red"
    Say "  $text" "Red"
    Say "  Проверьте интернет и запустите setup.bat снова —" "Red"
    Say "  уже скачанное повторно качаться не будет." "Red"
    Say "============================================" "Red"
    Say ""
    if ($Interactive) { Read-Host "Нажмите Enter, чтобы закрыть" }
    exit 1
}

Say "============================================" "Cyan"
Say "  AISubs — установка" "Cyan"
Say "============================================" "Cyan"
Say ""
Say "Будет скачано:"
Say "  • Python и ffmpeg          ~600 МБ"
Say "  • библиотеки CUDA          ~550 МБ (только при видеокарте NVIDIA)"
Say "  • модель распознавания     0.5–3 ГБ (можно выбрать или пропустить)"
Say ""

if ($DryRun) {
    Say "Проверка запуска: установщик читается и выполняется." "Green"
    exit 0
}

New-Item -ItemType Directory -Force -Path $Scratch | Out-Null

# ---------------------------------------------------------------- Python ----
if (Test-Path $Py) {
    Say "[1/6] Python уже установлен — пропускаю." "DarkGray"
} else {
    Say "[1/6] Скачиваю портативный Python 3.11..." "White"
    try {
        $zip = Join-Path $Scratch "python.zip"
        Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath (Join-Path $Root "python") -Force
        Remove-Item $zip -Force
        # the embeddable build ignores site-packages until this line is enabled
        $pth = Join-Path $Root "python\python311._pth"
        (Get-Content $pth) -replace '^#import site', 'import site' | Set-Content $pth -Encoding ascii
    } catch { Fail "Не удалось скачать Python: $_" }

    Say "[2/6] Устанавливаю pip..." "White"
    try {
        $getpip = Join-Path $Scratch "get-pip.py"
        Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
        & $Py $getpip --no-warn-script-location
        if ($LASTEXITCODE -ne 0) { throw "pip installer exited with $LASTEXITCODE" }
        Remove-Item $getpip -Force
    } catch { Fail "Не удалось установить pip: $_" }
}

# ---------------------------------------------------------- Python deps ----
Say "[3/6] Устанавливаю библиотеки Python..." "White"
& $Py -m pip install --no-warn-script-location -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "Не удалось установить библиотеки." }

# ---------------------------------------------------------------- ffmpeg ----
if (Test-Path (Join-Path $Root "ffmpeg\ffmpeg.exe")) {
    Say "[4/6] ffmpeg уже установлен — пропускаю." "DarkGray"
} else {
    Say "[4/6] Скачиваю ffmpeg..." "White"
    try {
        $zip = Join-Path $Scratch "ffmpeg.zip"
        $tmp = Join-Path $Scratch "ffmpeg_unpack"
        Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
        New-Item -ItemType Directory -Force -Path (Join-Path $Root "ffmpeg") | Out-Null
        Get-ChildItem $tmp -Recurse -Include ffmpeg.exe, ffprobe.exe |
            ForEach-Object { Copy-Item $_.FullName (Join-Path $Root "ffmpeg") -Force }
        Remove-Item $tmp -Recurse -Force
        Remove-Item $zip -Force
    } catch { Fail "Не удалось скачать ffmpeg: $_" }
}

# ------------------------------------------------------------------ CUDA ----
# cuBLAS is loaded by name at runtime and is NOT part of the NVIDIA driver;
# without it everything silently falls back to the CPU.
$hasGpu = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if (-not $hasGpu) {
    Say "[5/6] Видеокарта NVIDIA не найдена — пропускаю библиотеки CUDA." "DarkGray"
    Say "      Распознавание будет работать на процессоре." "DarkGray"
} else {
    & $Py -c "import nvidia.cublas" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Say "[5/6] Библиотеки CUDA уже установлены — пропускаю." "DarkGray"
    } else {
        Say "[5/6] Видеокарта NVIDIA найдена. Скачиваю библиотеки CUDA (~550 МБ)..." "White"
        & $Py -m pip install --no-warn-script-location nvidia-cublas-cu12
        if ($LASTEXITCODE -ne 0) {
            Say "      Не получилось. Распознавание пойдёт на процессоре;" "Yellow"
            Say "      установку можно повторить, запустив setup.bat снова." "Yellow"
        }
    }
}

# ----------------------------------------------------------------- model ----
Say ""
Say "[6/6] Модель распознавания речи." "White"

if ($Model -eq "ask") {
    Say ""
    Say "  1. large-v3          ~3 ГБ    максимальное качество"
    Say "  2. distil-large-v3   ~1.5 ГБ  быстрее, почти так же точно"
    Say "  3. small             ~500 МБ  быстро, качество ниже"
    Say "  4. пропустить — скачается сама при первой обработке видео"
    Say ""
    $choice = Read-Host "Что скачать? [1]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }
    switch ($choice.Trim()) {
        "2" { $Model = "distil-large-v3" }
        "3" { $Model = "small" }
        "4" { $Model = "skip" }
        default { $Model = "large-v3" }
    }
}

if ($Model -eq "skip") {
    Say "Пропускаю. Модель скачается при первой обработке видео." "DarkGray"
} else {
    & $Py (Join-Path $Root "download_model.py") $Model
    if ($LASTEXITCODE -ne 0) {
        Say "Модель не скачалась — ничего страшного, она загрузится" "Yellow"
        Say "автоматически при первой обработке видео." "Yellow"
    }
}

Say ""
Say "============================================" "Green"
Say "  Готово. Запускайте run.bat" "Green"
Say "============================================" "Green"
Say ""
if ($Interactive) {
    Read-Host "Нажмите Enter, чтобы закрыть"
}
