@echo off
REM PictureWeb 一直开着模式
REM 启动 server (完全脱离 shell) + watchdog 后台守护
REM 用法:双击 start_forever.bat 即可

setlocal
set "PWD=D:\Mac\Mac\Mac\workteam\05_space\03_architect\Mobile\_ArchitectMobileLib\PictureWeb"
set "PYTHON=C:\Users\yongzhang\AppData\Local\Programs\Python\Python312\python.exe"
set "PORT=9004"
set "PYTHONIOENCODING=utf-8"

cd /d "%PWD%"

REM 1. 先杀旧进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM 2. 用 cmd /c start 彻底脱离 shell(不像 PowerShell Start-Process 会被 mavis shell 拉死)
start "PictureWeb-Server" /B /D "%PWD%" cmd /c "set PICTUREWEB_TEST_PORT=%PORT%&& set PYTHONIOENCODING=utf-8&& \"%PYTHON%\" -X utf8 server.py"

REM 3. 启动 watchdog(每 30s 检查,死了拉起)
start "PictureWeb-Watchdog" /B /D "%PWD%" powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%PWD%\watchdog.ps1"

echo.
echo PictureWeb 已启动:
echo   主页:http://127.0.0.1:%PORT%/
echo   Watchdog 已后台守护
echo.
echo 不要关这个窗口(可最小化,不能 X 掉)
pause
