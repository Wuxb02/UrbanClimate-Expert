@echo off
chcp 65001 >nul
echo ========================================
echo UrbanClimate-Expert 服务启动脚本
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/3] 检查环境...
if not exist ".env" (
    echo ❌ 错误: .env 文件不存在
    echo 请先复制 .env.example 为 .env 并配置数据库连接
    pause
    exit /b 1
)

echo ✅ 环境配置文件已找到
echo.

echo [2/3] 检查数据库配置...
python -c "from app.core.config import settings; print(f'数据库: {settings.mysql_dsn.split(chr(64))[1]}')" 2>nul
if errorlevel 1 (
    echo ⚠️  警告: 无法读取数据库配置
    echo 请确保 .env 文件配置正确
)
echo.

echo [3/3] 启动后端服务...
echo 当前目录: %CD%
echo 访问地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
