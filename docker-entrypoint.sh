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

# 检查环境变量
if [ -z "$HOST" ]; then
    export HOST="0.0.0.0"
    echo "Using default HOST: $HOST"
fi

if [ -z "$PORT" ]; then
    export PORT="8080"
    echo "Using default PORT: $PORT"
fi

# 检查配置文件
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found, using default configuration"
    echo "Please mount .env file or set environment variables"
fi

# 显示配置信息
echo "Configuration:"
echo "- HOST: $HOST"
echo "- PORT: $PORT"
echo "- SUPERUSERS: ${SUPERUSERS:-Not set}"
echo "- NOTIFY_GROUPS: ${NOTIFY_GROUPS:-Not set}"
echo "=========================================="

# 启动应用
echo "Starting CyxcBot..."
exec python bot.py 