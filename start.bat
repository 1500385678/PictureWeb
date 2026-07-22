@echo off
chcp 65001 >nul 2>&1
cd /d %~dp0
echo Library 启动中…
echo 访问地址: http://127.0.0.1:8081/
echo 关闭请关闭此窗口
echo.
python -X utf8 server.py
