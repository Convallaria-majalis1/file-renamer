@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 打包 批量重命名归档器

echo ==========================================
echo   批量重命名 / 归档器 - 一键打包
echo   当前目录：%CD%
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 python 命令。
    echo 请先装 Python 3.9 以上，安装时勾选 "Add Python to PATH"，装完重开窗口再试。
    echo.
    pause
    exit /b 1
)

echo 第 1 步：安装 / 升级 PyInstaller
echo ------------------------------------------
python -m pip install --upgrade pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo [错误] PyInstaller 安装失败，多半是网络问题。
    echo 换个网络或关掉代理再试，也可以先在 CMD 里手动执行：
    echo     python -m pip install pyinstaller
    echo.
    pause
    exit /b 1
)

echo.
echo 第 2 步：检查源码能不能导入
echo ------------------------------------------
python -c "import tkinter, core, pathlib, shutil, re; print('源码检查通过')"
if errorlevel 1 (
    echo.
    echo [错误] 源码导入失败，看上面那行报错。
    echo.
    pause
    exit /b 1
)

echo.
echo 第 3 步：打包成单个 exe
echo ------------------------------------------
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FileRenamer main.py
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，把上面最后 10 行红字发给我。
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   完成！
echo   产物：dist\FileRenamer.exe
echo   这个作品只用标准库，体积约 12-18MB，启动一两秒
echo ==========================================
echo.
if exist "dist\FileRenamer.exe" (
    dir "dist\FileRenamer.exe"
) else (
    echo [警告] 没找到 dist\FileRenamer.exe，请把上面的输出发给我。
)
echo.
echo 下一步：双击 dist\FileRenamer.exe 跑一遍改名和撤销，确认没问题再去发 Release。
echo.
pause
exit /b 0
