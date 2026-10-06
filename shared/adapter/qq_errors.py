"""QQ 官方发消息错误码。文档列出的码只记一条日志，不打堆栈。

级别：info 是平台正常拒绝（权限、过期、禁言、去重）；warning 是内容、配置或可稍后重试的失败。
"""

from __future__ import annotations

from nonebot.log import logger

# 群聊与单聊共用同一套级别。两边都有的码只登记一次。
# https://bot.q.qq.com/wiki/develop/api-v2/autogen/api/v2_groups_group_openid_messages.post.html
# https://bot.q.qq.com/wiki/develop/api-v2/autogen/api/v2_users_user_openid_messages.post.html
_INFO = {
    304064: "订阅消息未授权",
    304103: "消息 ID 已过期",
    40034005: "回复消息已过期",
    40034026: "事件 ID 已过期",
    40034027: "该事件不支持回复",
    40034105: "主动消息无权限",
    40034122: "召回消息已达区间上限",
    40034128: "被动回复时间或次数超限",
    40054002: "机器人被禁言",
    40054004: "无好友关系",
    40054005: "消息被去重",
    40054010: "不允许发送 URL",
    40054013: "用户拒收消息",
}
_WARNING = {
    50059: "输入类型错误",
    22006: "消息类型与内容不匹配",
    304004: "无 ARK 模板权限",
    304036: "无 Markdown 模板权限",
    304061: "消息内容无效",
    304062: "订阅按钮数量达到上限",
    304080: "文件信息无效",
    305007: "键盘样式参数错误",
    340067: "获取机器人信息失败",
    340069: "消息类型无效",
    40034004: "富媒体转存失败",
    40034006: "消息内容违规",
    40034008: "Markdown 参数有空值",
    40034009: "Markdown 参数有换行符",
    40034010: "模板参数含有 Markdown 语法",
    40034011: "无效的 Markdown 内容",
    40034024: "msg_id 无效或越权",
    40034025: "event_id 无效",
    40034029: "内联键盘超限",
    40034100: "主动消息超过频控",
    40034101: "机器人不是群成员",
    40034106: "消息不支持该指令类型",
    40034108: "指令参数超长",
    40034109: "指令参数解析失败",
    40034123: "不支持召回消息",
    40034124: "Markdown 参数错误",
    40034127: "无 Markdown 模板权限",
    40054003: "机器人不是群成员",
    40054006: "验证好友关系失败",
    40054007: "消息长度超限",
    40054016: "机器人已下线",
    40054018: "消息过长或异常",
    50055001: "消息发送异常，可稍后重试",
    50055002: "消息发送异常，可稍后重试",
    50055006: "ARK 消息发送异常，可稍后重试",
}


class LoggedQQApiError(Exception):
    """文档中的官方接口错误。日志已经记过，调用方不要再打堆栈。"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.api_message = message
        super().__init__(f"{code} {message}")


def qq_api_code(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    if isinstance(code, str) and code.isdigit():
        return int(code)
    return None


def note_qq_api_error(exc: BaseException, *, target: str) -> LoggedQQApiError | None:
    code = qq_api_code(exc)
    if code is None:
        return None
    text = _INFO.get(code)
    level = "info"
    if text is None:
        text = _WARNING.get(code)
        level = "warning"
    if text is None:
        return None
    getattr(logger, level)("官方消息未发出 {}：{}（{}）", target, text, code)
    api_message = getattr(exc, "message", None) or text
    return LoggedQQApiError(code, str(api_message))
