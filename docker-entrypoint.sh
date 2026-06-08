#!/bin/bash

# 设置错误时退出
set -e

# 显示构建信息
echo "=========================================="
echo "CyxcBot - Bilibili Live Notification Bot"
echo "=========================================="
echo "Git Tag: ${GIT_TAG:-N/A}"
echo "Git Commit: ${GIT_COMMIT:-N/A}"
echo "Git Branch: ${GIT_BRANCH:-N/A}"
echo "Build Time: ${BUILD_TIME:-N/A}"
echo "Build Number: ${BUILD_NUMBER:-N/A}"
echo "=========================================="

# 设置默认环境变量（静默）
if [ -z "$HOST" ]; then
    export HOST="0.0.0.0"
fi

if [ -z "$PORT" ]; then
    export PORT="8080"
fi

if [ -z "$WEB_PORT" ]; then
    export WEB_PORT="8081"
fi

# 确保数据目录存在（SQLite 默认路径）
mkdir -p /app/data

# 数据库迁移/初始化在 bot.py 启动时自动完成
echo "Starting CyxcBot (OneBot: ${PORT}, Web Admin: ${WEB_PORT})..."
exec python bot.py
