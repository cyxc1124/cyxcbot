"""
主播开播关播通知插件
提供API接口接收主播状态，并在指定群组发送通知
"""

from . import stream_api

__plugin_meta__ = {
    "name": "主播开播关播通知",
    "description": "接收主播开播关播状态并在群组发送通知",
    "usage": "通过API接口接收主播状态信息",
    "version": "1.0.0",
    "author": "cyxcbot"
} 