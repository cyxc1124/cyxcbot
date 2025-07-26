"""
机器人状态查询插件
仅允许特定QQ号查询机器人运行状态
"""

from . import status_checker

__plugin_meta__ = {
    "name": "机器人状态查询",
    "description": "仅允许特定QQ号查询机器人运行状态",
    "usage": "/status - 查询机器人运行状态",
    "version": "1.0.0",
    "author": "cyxcbot"
} 