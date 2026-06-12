---
sidebar_position: 2
---

# 测试

## 运行测试

```bash
./venv/bin/pytest
```

测试文件位于 `tests/` 目录，使用 pytest + pytest-asyncio。

## 代码检查

```bash
./venv/bin/ruff check .
./venv/bin/ruff format .
```

Ruff 配置见 `pyproject.toml`，`web/` 与 `venv/` 已排除。

## 前端

```bash
cd web
npm run build   # 类型检查 + 构建
```

## 文档站

```bash
cd docs
npm run build   # 构建静态文档
npm start       # 本地预览（http://localhost:3000）
```

## 编写测试

- 新功能优先在 `tests/` 添加单元测试
- 异步代码使用 `pytest.mark.asyncio`
- 测试配置见 `tests/conftest.py`
