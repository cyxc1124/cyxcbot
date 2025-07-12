from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot import get_plugin_config
from nonebot.drivers import Request, Response, HTTPServerSetup
from nonebot.log import logger
import json
from typing import Dict
from yarl import URL

from .config import Config

# 获取插件配置
config = get_plugin_config(Config)

# 创建API路由处理器
@get_driver().on_startup
async def setup_api():
    """设置B站直播事件API路由"""
    driver = get_driver()
    
    # 注册HTTP路由 - B站直播事件API
    async def bilibili_live_api(request: Request) -> Response:
        """处理B站直播事件API请求（通过blrec webhook）"""
        try:
            # 获取请求数据
            data = request.json
            logger.info(f"收到B站直播事件请求")
            logger.info(f"请求来源: {request.client.host if hasattr(request, 'client') else 'Unknown'}")
            logger.info(f"请求方法: {request.method}")
            logger.info(f"请求路径: {request.url.path}")
            logger.info(f"请求数据: {data}")
            
            # 解析B站事件数据
            event_type = data.get("type")
            event_data = data.get("data", {})
            logger.info(f"事件类型: {event_type}")
            logger.info(f"事件数据: {event_data}")
            
            if event_type == "LiveBeganEvent":
                # 开播事件
                user_info = event_data.get("user_info", {})
                room_info = event_data.get("room_info", {})
                
                streamer_name = user_info.get("name", "主播")
                title = room_info.get("title", "")
                room_id = room_info.get("room_id", "")
                area_name = room_info.get("area_name", "")
                
                logger.info(f"主播信息: {user_info}")
                logger.info(f"房间信息: {room_info}")
                logger.info(f"处理B站开播事件: {streamer_name} - {title} (房间号: {room_id}, 分区: {area_name})")
                await send_bilibili_notification("start", streamer_name, room_info, user_info)
                
            elif event_type == "LiveEndedEvent":
                # 下播事件
                user_info = event_data.get("user_info", {})
                room_info = event_data.get("room_info", {})
                
                streamer_name = user_info.get("name", "主播")
                online = room_info.get("online", 0)
                title = room_info.get("title", "")
                
                logger.info(f"主播信息: {user_info}")
                logger.info(f"房间信息: {room_info}")
                logger.info(f"处理B站下播事件: {streamer_name} - {title} (直播时长: {online}秒)")
                await send_bilibili_notification("end", streamer_name, room_info, user_info)
                
            else:
                logger.warning(f"不支持的事件类型: {event_type}")
                logger.warning(f"支持的事件类型: LiveBeganEvent, LiveEndedEvent")
                logger.warning(f"完整请求数据: {data}")
                return Response(
                    status_code=400,
                    content=json.dumps({"success": False, "error": "Unsupported event type"})
                )
            
            logger.success("B站直播事件处理成功")
            return Response(
                status_code=200,
                content=json.dumps({"success": True, "message": "B站直播事件处理成功"})
            )
            
        except Exception as e:
            logger.error(f"B站直播事件API错误: {e}")
            import traceback
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            logger.error(f"请求数据: {data}")
            return Response(
                status_code=500,
                content=json.dumps({"success": False, "error": str(e)})
            )
    
    # 设置B站直播事件HTTP路由
    driver.setup_http_server(
        HTTPServerSetup(
            path=URL("/api/bilibili/live"),
            method="POST",
            name="bilibili_live_api",
            handle_func=bilibili_live_api
        )
    )
    logger.info("B站直播事件API路由已注册: /api/bilibili/live")

async def send_bilibili_notification(status: str, streamer_name: str, room_info: Dict, user_info: Dict):
    """发送B站直播通知"""
    logger.info(f"开始发送B站直播通知 - 状态: {status}, 主播: {streamer_name}")
    try:
        # 获取所有机器人实例
        bots = get_driver().bots
        logger.info(f"可用机器人数量: {len(bots)}")
        
        for bot_id, bot in bots.items():
            logger.info(f"检查机器人: {bot_id}, 类型: {type(bot).__name__}")
            if isinstance(bot, Bot):  # 确保是OneBot适配器
                logger.info(f"找到OneBot适配器: {bot_id}")
                # 发送到配置的群组
                logger.info(f"配置的通知群组: {config.notify_groups}")
                for group_id in config.notify_groups:
                    try:
                        if status == "start":
                            # 开播消息
                            title = room_info.get("title", "")
                            room_id = room_info.get("room_id", "")
                            area_name = room_info.get("area_name", "")
                            live_start_time = room_info.get("live_start_time", 0)  # 开播时间戳
                            
                            logger.info(f"构建开播消息 - 标题: {title}, 房间号: {room_id}, 分区: {area_name}, 开播时间戳: {live_start_time}")
                            
                            # 转换时间戳为可读格式
                            if live_start_time > 0:
                                import datetime
                                start_time = datetime.datetime.fromtimestamp(live_start_time)
                                time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                                logger.info(f"开播时间转换结果: {time_str}")
                            else:
                                time_str = "未知"
                                logger.warning("未获取到有效的开播时间戳")
                            
                            message = f"🎉 {streamer_name} 开播啦！\n"
                            if config.include_room_info:
                                message += f"直播间标题：{title}\n"
                                message += f"房间号：{room_id}\n"
                                message += f"开播时间：{time_str}\n"
                                message += f"点我直达：https://live.bilibili.com/{room_id}\n"
                                
                            message += str(MessageSegment.at("all"))
                            
                        else:
                            # 下播消息
                            online = room_info.get("online", 0)  # 直播时长（秒）
                            
                            logger.info(f"构建下播消息 - 直播时长: {online}秒")
                            
                            # 将秒数转换为时分秒格式
                            hours = online // 3600
                            minutes = (online % 3600) // 60
                            seconds = online % 60
                            
                            if hours > 0:
                                duration_str = f"{hours}小时{minutes}分钟{seconds}秒"
                            elif minutes > 0:
                                duration_str = f"{minutes}分钟{seconds}秒"
                            else:
                                duration_str = f"{seconds}秒"
                            
                            logger.info(f"时长转换结果: {duration_str}")
                            
                            message = f"【下播提醒】\n"
                            message += f"{streamer_name}下播啦！\n"
                            message += f"直播时长：{duration_str}"
                        
                        # 发送消息到群组
                        logger.info(f"准备发送消息到群组 {group_id}")
                        logger.info(f"消息内容: {message}")
                        await bot.send_group_msg(
                            group_id=group_id,
                            message=message
                        )
                        logger.success(f"B站直播{status}通知已发送到群组 {group_id}")
                        logger.info(f"消息发送完成 - 机器人: {bot_id}, 群组: {group_id}")
                        
                    except Exception as e:
                        logger.error(f"发送B站直播消息到群组 {group_id} 失败: {e}")
                        logger.error(f"错误类型: {type(e).__name__}")
                        logger.error(f"机器人ID: {bot_id}")
                        logger.error(f"主播信息: {streamer_name}")
                        logger.error(f"房间信息: {room_info}")
                        import traceback
                        logger.error(f"详细错误堆栈: {traceback.format_exc()}")
                        
    except Exception as e:
        logger.error(f"发送B站直播通知失败: {e}")
        logger.error(f"错误类型: {type(e).__name__}")
        logger.error(f"状态: {status}")
        logger.error(f"主播信息: {streamer_name}")
        logger.error(f"房间信息: {room_info}")
        logger.error(f"用户信息: {user_info}")
        import traceback
        logger.error(f"详细错误堆栈: {traceback.format_exc()}")
    else:
        logger.info(f"B站直播通知发送流程完成 - 状态: {status}, 主播: {streamer_name}") 