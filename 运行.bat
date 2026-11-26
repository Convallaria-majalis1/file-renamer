@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 批量重命名 / 归档器
python main.py
if errorlevel 1 pause
