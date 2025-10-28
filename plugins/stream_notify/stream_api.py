from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot import get_plugin_config
from nonebot.drivers import Request, Response, HTTPServerSetup
from nonebot.log import logger
import json
import time
from typing import Dict
from yarl import URL

from .config import Config

# 全局字典，用于存储房间的开播时间戳
# 格式: {room_id: start_timestamp}
room_start_times = {}

def cleanup_expired_start_times():
    """清理超过24小时的开播时间戳记录"""
    current_time = int(time.time())
    expired_rooms = []
    
    logger.info(f"开始清理过期的开播时间戳记录，当前存储数量: {len(room_start_times)}")
    
    for room_id, start_time in room_start_times.items():
        # 如果记录超过24小时（86400秒），则清理
        if current_time - start_time > 86400:
            expired_rooms.append(room_id)
    
    for room_id in expired_rooms:
        del room_start_times[room_id]
        logger.info(f"清理过期的开播时间戳记录: 房间 {room_id}")
    
    if expired_rooms:
        logger.info(f"清理了 {len(expired_rooms)} 个过期的开播时间戳记录")
    else:
        logger.info("没有需要清理的过期记录")

# 创建API路由处理器
@get_driver().on_startup
async def setup_api():
    """设置B站直播事件API路由"""
    driver = get_driver()
    
    # 获取插件配置
    config = get_plugin_config(Config)
    logger.info(f"插件配置加载完成: streamer_group_mapping={config.streamer_group_mapping}, include_room_info={config.include_room_info}")
    
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
                
                # 记录开播时间戳
                current_time = int(time.time())
                api_live_start_time = room_info.get("live_start_time", 0)  # API返回的开播时间戳
                
                logger.info(f"房间 {room_id} API返回的开播时间戳: {api_live_start_time}")
                logger.info(f"房间 {room_id} 当前时间戳: {current_time}")
                
                # 如果API返回的开播时间戳为0，使用当前时间戳作为备用方案
                if api_live_start_time == 0:
                    room_start_times[room_id] = current_time
                    logger.info(f"API返回开播时间戳为0，使用当前时间戳作为备用方案: {current_time}")
                else:
                    room_start_times[room_id] = api_live_start_time
                    logger.info(f"使用API返回的开播时间戳: {api_live_start_time}")
                
                logger.info(f"记录房间 {room_id} 开播时间戳: {room_start_times[room_id]}")
                logger.info(f"当前存储的开播时间戳数量: {len(room_start_times)}")
                logger.info(f"存储的房间列表: {list(room_start_times.keys())}")
                
                logger.info(f"主播信息: {user_info}")
                logger.info(f"房间信息: {room_info}")
                logger.info(f"处理B站开播事件: {streamer_name} - {title} (房间号: {room_id}, 分区: {area_name})")
                logger.info(f"开播事件处理完成 - 记录开播时间戳: {room_start_times[room_id]}, 来源: {'API' if api_live_start_time > 0 else '当前时间'}")
                await send_bilibili_notification("start", streamer_name, room_info, user_info, config)
                
            elif event_type == "LiveEndedEvent":
                # 下播事件
                user_info = event_data.get("user_info", {})
                room_info = event_data.get("room_info", {})
                
                streamer_name = user_info.get("name", "主播")
                title = room_info.get("title", "")
                room_id = room_info.get("room_id", "")
                
                # 计算实际直播时长
                current_time = int(time.time())
                start_time = room_start_times.get(room_id, 0)
                api_online = room_info.get("online", 0)  # API返回的直播时长
                
                logger.info(f"房间 {room_id} API返回的直播时长: {api_online}秒")
                logger.info(f"房间 {room_id} 记录的开播时间戳: {start_time}")
                
                # 情况1: API返回的online为0，优先使用记录的开播时间戳计算
                if api_online == 0 and start_time > 0:
                    actual_duration = current_time - start_time
                    # 更新room_info中的online字段
                    room_info["online"] = actual_duration
                    logger.info(f"API返回时长为0，使用备用方案计算实际直播时长: {actual_duration}秒 (开播时间: {start_time}, 下播时间: {current_time})")
                    # 清理记录的开播时间戳
                    del room_start_times[room_id]
                    duration_source = "本地计算"
                    logger.info(f"情况1处理完成 - 使用本地计算时长: {actual_duration}秒")
                # 情况2: API返回的online有数值，且有记录的开播时间戳，进行校验
                elif api_online > 0 and start_time > 0:
                    # 如果有记录的开播时间戳，进行校验
                    calculated_duration = current_time - start_time
                    duration_diff = abs(calculated_duration - api_online)
                    
                    logger.info(f"API返回时长: {api_online}秒, 计算时长: {calculated_duration}秒, 差异: {duration_diff}秒")
                    
                    # 如果差异在3秒以内，信任API返回的时长
                    if duration_diff <= 3:
                        logger.info(f"时长差异在3秒以内，信任API返回的时长: {api_online}秒")
                        room_info["online"] = api_online
                        duration_source = "API"
                    else:
                        # 如果差异超过3秒，使用计算出的时长并记录警告
                        logger.warning(f"时长差异超过3秒，使用计算出的时长: {calculated_duration}秒 (API: {api_online}秒, 差异: {duration_diff}秒)")
                        room_info["online"] = calculated_duration
                        duration_source = "本地计算"
                    
                    # 清理记录的开播时间戳
                    del room_start_times[room_id]
                    logger.info(f"情况2处理完成 - 最终使用时长: {room_info['online']}秒，来源: {duration_source}")
                # 情况3&4: 没有记录的开播时间戳，使用API返回的online字段
                else:
                    # 如果没有记录的开播时间戳，使用API返回的online字段
                    logger.warning(f"房间 {room_id} 未找到开播时间戳记录，使用API返回的时长: {api_online}秒")
                    if api_online > 0:
                        duration_source = "API"
                    else:
                        duration_source = ""
                    if api_online == 0:
                        logger.warning(f"房间 {room_id} API返回时长为0且无开播记录")
                    logger.info(f"情况3&4处理完成 - API返回时长: {api_online}秒，来源: {duration_source}")
                
                # 清理过期的开播时间戳记录
                cleanup_expired_start_times()
                
                logger.info(f"主播信息: {user_info}")
                logger.info(f"房间信息: {room_info}")
                logger.info(f"处理B站下播事件: {streamer_name} - {title} (房间号: {room_id})")
                logger.info(f"传递给消息函数的online值: {room_info.get('online', 0)}秒，来源: {duration_source}")
                await send_bilibili_notification("end", streamer_name, room_info, user_info, config, duration_source)
                
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

async def send_bilibili_notification(status: str, streamer_name: str, room_info: Dict, user_info: Dict, config: Config, duration_source: str = ""):
    """发送B站直播通知"""
    logger.info(f"开始发送B站直播通知 - 状态: {status}, 主播: {streamer_name}")
    
    # 获取房间号
    room_id = str(room_info.get("room_id", ""))
    logger.info(f"房间号: {room_id}")
    
    # 检查房间号是否在映射配置中
    if room_id not in config.streamer_group_mapping:
        logger.warning(f"房间号 {room_id} ({streamer_name}) 未在 STREAMER_GROUP_MAPPING 中配置，跳过发送通知")
        return
    
    # 获取该房间号对应的群组列表
    target_groups = config.streamer_group_mapping[room_id]
    logger.info(f"房间号 {room_id} ({streamer_name}) 的目标群组: {target_groups}")
    
    if not target_groups:
        logger.warning(f"房间号 {room_id} ({streamer_name}) 配置的群组列表为空，跳过发送通知")
        return
    
    try:
        # 获取所有机器人实例
        bots = get_driver().bots
        logger.info(f"可用机器人数量: {len(bots)}")
        
        for bot_id, bot in bots.items():
            logger.info(f"检查机器人: {bot_id}, 类型: {type(bot).__name__}")
            if isinstance(bot, Bot):  # 确保是OneBot适配器
                logger.info(f"找到OneBot适配器: {bot_id}")
                # 发送到该房间配置的群组
                logger.info(f"准备发送到群组: {target_groups}")
                for group_id in target_groups:
                    try:
                        # 检查机器人是否有管理员权限
                        can_at_all = await check_bot_admin_permission(bot, group_id)
                        logger.info(f"机器人 {bot_id} 在群组 {group_id} 中是否有管理员权限: {can_at_all}")
                        
                        if status == "start":
                            # 开播消息
                            title = room_info.get("title", "")
                            room_id = room_info.get("room_id", "")
                            area_name = room_info.get("area_name", "")
                            
                            # 使用记录的开播时间戳（可能来自API或备用方案）
                            recorded_start_time = room_start_times.get(room_id, 0)
                            
                            logger.info(f"构建开播消息 - 标题: {title}, 房间号: {room_id}, 分区: {area_name}, 记录的开播时间戳: {recorded_start_time}")
                            
                            # 转换时间戳为可读格式
                            if recorded_start_time > 0:
                                import datetime
                                start_time = datetime.datetime.fromtimestamp(recorded_start_time)
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
                            
                            # 根据权限决定是否@全体成员
                            if can_at_all:
                                message += str(MessageSegment.at("all"))
                                logger.info("使用@全体成员")
                            else:
                                message += "\n📢 请关注直播动态！"
                                logger.info("机器人无管理员权限，使用普通提醒消息")
                            
                        else:
                            # 下播消息
                            # 注意：这里的online可能已经在事件处理中被更新为计算出的实际时长
                            online = room_info.get("online", 0)  # 直播时长（秒）
                            logger.info(f"构建下播消息 - 直播时长: {online}秒 ，来源: {duration_source}")
                            
                            if online > 0:
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
                            else:
                                # 如果时长为0，不显示时长
                                logger.warning("直播时长为0，不显示时长")
                                message = f"【下播提醒】\n"
                                message += f"{streamer_name}下播啦！"
                        
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

async def check_bot_admin_permission(bot: Bot, group_id: str) -> bool:
    """检查机器人在群组中是否有管理员权限"""
    try:
        # 获取机器人自己的群成员信息
        bot_info = await bot.get_group_member_info(
            group_id=int(group_id),
            user_id=int(bot.self_id),
            no_cache=False
        )
        
        # 检查角色是否为管理员或群主
        role = bot_info.get("role", "member")
        logger.info(f"机器人在群组 {group_id} 中的角色: {role}")
        
        # 只有管理员(admin)和群主(owner)可以@全体成员
        return role in ["admin", "owner"]
        
    except Exception as e:
        logger.warning(f"检查机器人管理员权限失败: {e}")
        logger.warning(f"群组ID: {group_id}, 机器人ID: {bot.self_id}")
        # 如果检查失败，默认返回False（不使用@全体成员）
        return False 