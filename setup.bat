@echo off
rem Thin launcher only - ASCII only, no line continuations.
rem cmd.exe reads .bat files in the OEM code page, so non-ASCII text here
rem corrupts parsing. All installer logic lives in setup.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
