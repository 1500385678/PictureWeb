#!/bin/bash
# PictureWeb 启动脚本 (macOS)
# 双击或在终端运行: ./start.sh

cd "$(dirname "$0")"
echo "Library 启动中..."
echo "访问地址: http://127.0.0.1:8081/"
echo "关闭请按 Ctrl+C"
echo ""
python3 server.py
