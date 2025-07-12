# NoneBot2 机器人项目

一个基于 NoneBot2 框架的机器人项目。

## 开发环境初始化

### 1. 创建虚拟环境

```bash
py -3.11 -m venv venv --prompt nonebot2
```

### 2. 激活虚拟环境

```bash
.\venv\Scripts\Activate.ps1
```

### 3. 安装依赖

```bash
pip install 'nonebot2[fastapi]'
pip install nonebot-adapter-console
```

## 配置文件设置

### 环境配置文件 (.env)

在项目文件夹中创建一个 `.env` 文本文件，并写入以下内容：

```env
# 基础配置
HOST=0.0.0.0          # 配置 NoneBot 监听的 IP / 主机名
PORT=8080             # 配置 NoneBot 监听的端口
COMMAND_START=["/"]   # 配置命令起始字符
COMMAND_SEP=["."]     # 配置命令分割字符
```

### 机器人主文件 (bot.py)

在项目文件夹中创建一个 `bot.py` 文件，并写入以下内容：

```python
import nonebot
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名

# 初始化 NoneBot
nonebot.init()

# 配置控制台适配器为无头模式
nonebot.get_driver().config.console_headless_mode = True

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ConsoleAdapter)

# 在这里加载插件
nonebot.load_builtin_plugins("echo")  # 内置插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件
# nonebot.load_plugins("awesome_bot/plugins")  # 本地插件

if __name__ == "__main__":
    nonebot.run()
```

## 启动机器人

配置完成后，运行以下命令启动机器人：

```bash
python bot.py
```

## 项目结构

```
cyxcbot/
├── bot.py              # 机器人主文件
├── .env                # 环境配置文件
├── venv/               # 虚拟环境
├── plugins/            # 插件目录
│   └── stream_notify/  # B站直播通知插件
├── test_api.py         # API测试脚本
├── test_env.py         # 环境配置测试脚本
└── README.md           # 项目说明文档
```

<p align="center">
<sub>Made with ❤️ by <a href="https://github.com/cyxc1124">cyxc1124</a></sub><br>
<sub>Developed with ❤️ for Mituantuan Miho Live Stream</sub>
</p>