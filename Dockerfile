# 使用官方 Python 基础镜像
FROM python:3.11-slim

# 构建参数（由GitHub Action传入）
ARG GIT_TAG=""
ARG GIT_COMMIT=""
ARG GIT_BRANCH=""
ARG BUILD_TIME=""
ARG BUILD_NUMBER=""

# 添加 OCI 标签以连接到 GitHub 仓库
LABEL org.opencontainers.image.source=https://github.com/cyxc1124/cyxcbot
LABEL org.opencontainers.image.description="NoneBot2机器人 - B站直播通知插件"
LABEL org.opencontainers.image.title="CyxcBot - Bilibili Live Notification Bot"
LABEL org.opencontainers.image.vendor="cyxc1124"
LABEL org.opencontainers.image.version=${GIT_TAG}
LABEL org.opencontainers.image.revision=${GIT_COMMIT}

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    GIT_TAG=${GIT_TAG} \
    GIT_COMMIT=${GIT_COMMIT} \
    GIT_BRANCH=${GIT_BRANCH} \
    BUILD_TIME=${BUILD_TIME} \
    BUILD_NUMBER=${BUILD_NUMBER}

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        vim \
        curl \
        procps \
        net-tools \
        iputils-ping \
        telnet \
        gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建非root用户
RUN useradd -m -u 1000 bot && chown -R bot:bot /app
USER bot

# 暴露端口
EXPOSE 8080

# 设置默认 shell 为 bash
SHELL ["/bin/bash", "-c"]

# 使用 bash 启动脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"] 