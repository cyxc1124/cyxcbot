---
sidebar_position: 2
---

# 测试

使用仓库根目录的 Python **3.14** 虚拟环境，以及 Node.js **26 LTS（26.13.0+，26.x）**。安装步骤见 [本地开发](../getting-started/local-dev)。按改动范围选择测试；文档文字调整通常只需检查链接与文档构建。

## 运行测试

```bash
./.venv/bin/pytest
```

测试文件位于 `tests/` 目录，使用 pytest + pytest-asyncio。可将相关文件传给 pytest，仅运行受影响的回归测试，例如 `./.venv/bin/pytest tests/test_dynamic_timestamps.py`。

使用隔离数据库和测试目标。不要把启动 `bot.py` 当作无副作用的检查：启动会连接配置的数据库、执行迁移并加载监控任务。

## 代码检查

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
```

Ruff 配置见 `pyproject.toml`，`web/` 与 `.venv/` 已排除。实际格式化时只对本次修改的 Python 文件执行 `ruff format`。

## 前端

```bash
cd web
node ../scripts/secure_npm.cjs run lint
node ../scripts/secure_npm.cjs test        # Vitest；可追加 -- <相关测试文件>
node ../scripts/secure_npm.cjs run build   # 类型检查 + 构建
```

## 文档站

```bash
cd docs
node ../scripts/secure_npm.cjs run build   # 构建静态文档
node ../scripts/secure_npm.cjs start       # 本地预览（http://localhost:3000）
```

文档 workflow 在相关路径变更时触发：`develop` 推送与 PR 仅构建校验，`main` 推送构建成功后部署 GitHub Pages。Python 和前端检查由独立构建 workflow 执行，见仓库 `.github/workflows/`。

## 编写测试

- 新功能优先在 `tests/` 添加单元测试
- 异步代码使用 `pytest.mark.asyncio`
- 测试配置见 `tests/conftest.py`
