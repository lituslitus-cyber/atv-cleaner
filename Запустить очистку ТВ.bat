@echo off
chcp 65001 >nul
title Очистка Xiaomi TV
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""

if not defined PY (
    echo Python не найден, устанавливаю через winget...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
    ) else (
        echo.
        echo Не удалось установить Python автоматически.
        echo Скачайте его с https://www.python.org/downloads/ ^(при установке
        echo отметьте "Add Python to PATH"^) и запустите этот файл снова.
        pause
        exit /b 1
    )
)

%PY% xiaomi_tv_cleanup.py %*
echo.
pause
