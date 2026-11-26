@echo off
chcp 65001 >nul
title 打包批量重命名归档器

echo ==========================================
echo  第 1 步：安装打包工具
echo ==========================================
python -m pip install --upgrade pip
python -m pip install pyinstaller
if errorlevel 1 goto :error

echo.
echo ==========================================
echo  第 2 步：打包成单个 exe
echo ==========================================
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FileRenamer main.py
if errorlevel 1 goto :error

echo.
echo ==========================================
echo  完成！exe 在 dist\FileRenamer.exe
echo  这个作品只用标准库，打包快、体积小、启动也快
echo ==========================================
pause
exit /b 0

:error
echo.
echo 出错了，把上面的报错信息发给我。
pause
exit /b 1
