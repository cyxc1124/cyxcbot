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

# 启动应用
echo "Starting CyxcBot..."
exec python bot.py 