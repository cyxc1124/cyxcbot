import nonebot
from nonebot.adapters.console import Adapter as ConsoleAdapter  # 避免重复命名
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter  # 添加OneBot适配器

# 初始化 NoneBot
nonebot.init()

# 配置控制台适配器为无头模式
nonebot.get_driver().config.console_headless_mode = True

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ConsoleAdapter)
driver.register_adapter(OneBotAdapter)  # 注册OneBot适配器

# 在这里加载插件
nonebot.load_builtin_plugins("echo")  # 内置插件
nonebot.load_plugins("plugins")  # 加载本地插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件

if __name__ == "__main__":
    nonebot.run()