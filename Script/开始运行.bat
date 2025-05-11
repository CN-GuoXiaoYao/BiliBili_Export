@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title B站缓存工具箱运行助手(By.郭逍遥)
echo B站缓存工具箱(By.郭逍遥) 环境检测助手

timeout /t 1 /nobreak >nul

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 验证Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python环境！
    echo.
    echo 请从以下地址安装Python 3.8+：
    echo https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    pause
    start "" "https://www.python.org/downloads/"
    exit
)

REM 安装必要依赖
echo.
echo 正在检查依赖库...
echo ----------------------------------------------
pip install requests yutto
if %errorlevel% neq 0 (
    echo.
    echo [错误] 依赖安装失败，请尝试以下方案：
    echo 1. 以管理员身份运行此脚本
    echo 2. 检查网络连接
    pause
    exit
)

REM 启动主程序
echo.
echo ██████████████████████████████████████████████████
echo 正在启动主程序...
echo ---------------------------------------------

start "" python gui_app.py
exit