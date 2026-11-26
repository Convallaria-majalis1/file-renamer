@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 批量重命名 / 归档器

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 python 命令。
    echo 请先装 Python 3.9 以上，安装时勾选 "Add Python to PATH"。
    echo 装完关掉这个窗口，重新双击运行.bat。
    echo.
    pause
    exit /b 1
)

python main.py
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，把上面的报错信息发给我。
    echo.
    pause
)
