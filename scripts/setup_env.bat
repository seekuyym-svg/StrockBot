@echo off
chcp 65001 >nul
echo ============================================================
echo 🚀 StockBot 环境设置脚本
echo ============================================================
echo.

REM 检查conda是否安装
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未检测到conda，请先安装Anaconda或Miniconda
    echo.
    echo 💡 下载地址: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo ✅ 检测到conda
echo.

REM 询问用户操作
echo 请选择操作:
echo 1. 创建新环境 (stockbot-py312)
echo 2. 更新现有环境
echo 3. 删除环境并重新创建
echo 4. 仅激活环境
echo.
set /p choice="请输入选项 (1-4): "

if "%choice%"=="1" goto create
if "%choice%"=="2" goto update
if "%choice%"=="3" goto recreate
if "%choice%"=="4" goto activate
goto end

:create
echo.
echo 📦 正在创建conda环境 stockbot-py312...
call conda env create -f environment.yml -n stockbot-py312
if %errorlevel% neq 0 (
    echo ❌ 环境创建失败
    pause
    exit /b 1
)
echo ✅ 环境创建成功！
goto activate_env

:update
echo.
echo 🔄 正在更新conda环境 stockbot-py312...
call conda env update -f environment.yml -n stockbot-py312 --prune
if %errorlevel% neq 0 (
    echo ❌ 环境更新失败
    pause
    exit /b 1
)
echo ✅ 环境更新成功！
goto activate_env

:recreate
echo.
echo ⚠️  警告: 这将删除现有环境并重新创建
set /p confirm="确认继续? (y/n): "
if /i not "%confirm%"=="y" goto end

echo 🗑️  正在删除旧环境...
call conda env remove -n stockbot-py312 -y
echo 📦 正在重新创建环境...
call conda env create -f environment.yml -n stockbot-py312
if %errorlevel% neq 0 (
    echo ❌ 环境重建失败
    pause
    exit /b 1
)
echo ✅ 环境重建成功！
goto activate_env

:activate
goto activate_env

:activate_env
echo.
echo 🎯 激活环境 stockbot-py312...
call conda activate stockbot-py312

echo.
echo 📋 环境信息:
python --version
echo.

echo 📁 进入项目目录...
cd /d "%~dp0"

echo.
echo 📦 检查依赖...
pip list | findstr "fastapi uvicorn sqlalchemy pandas numpy pyyaml loguru pydantic apscheduler aiohttp requests baostock akshare"

echo.
echo ============================================================
echo ✅ 环境准备完成！
echo ============================================================
echo.
echo 💡 使用提示:
echo    - 启动服务: python main.py
echo    - 运行测试: python test_etf_system.py
echo    - 退出环境: conda deactivate
echo.
echo 📖 相关文档:
echo    - QUICKSTART.md - 快速开始指南
echo    - README.md - 完整文档
echo.
pause

:end
