"""
B站弹幕 WebSocket 客户端
用于实时监控直播间开播/关播状态
参考 blrec 的 DanmakuClient 实现
"""

import asyncio
import json
import struct
import zlib
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from contextlib import suppress

import aiohttp
import brotli
from nonebot.log import logger

from utils.bilibili_api import wbi


class WS(IntEnum):
    """WebSocket 协议常量"""
    OP_HEARTBEAT = 2
    OP_HEARTBEAT_REPLY = 3
    OP_MESSAGE = 5
    OP_USER_AUTHENTICATION = 7
    OP_CONNECT_SUCCESS = 8
    PACKAGE_HEADER_TOTAL_LENGTH = 16
    BODY_PROTOCOL_VERSION_NORMAL = 0
    BODY_PROTOCOL_VERSION_DEFLATE = 2
    BODY_PROTOCOL_VERSION_BROTLI = 3
    HEADER_DEFAULT_VERSION = 1
    HEADER_DEFAULT_SEQUENCE = 1
    AUTH_OK = 0
    AUTH_TOKEN_ERROR = -101


class DanmakuCommand(Enum):
    """弹幕命令类型"""
    LIVE = 'LIVE'                    # 开播
    PREPARING = 'PREPARING'          # 准备中/关播
    ROOM_CHANGE = 'ROOM_CHANGE'      # 房间信息变更
    DANMU_MSG = 'DANMU_MSG'          # 弹幕消息
    SEND_GIFT = 'SEND_GIFT'          # 礼物
    GUARD_BUY = 'GUARD_BUY'          # 大航海
    SUPER_CHAT_MESSAGE = 'SUPER_CHAT_MESSAGE'  # SC


class Frame:
    """WebSocket 数据帧编解码"""
    HEADER_FORMAT = '>IHHII'

    @staticmethod
    def encode(op: int, msg: str) -> bytes:
        """编码消息帧"""
        body = msg.encode()
        header_length = WS.PACKAGE_HEADER_TOTAL_LENGTH
        packet_length = header_length + len(body)
        ver = WS.HEADER_DEFAULT_VERSION
        seq = WS.HEADER_DEFAULT_SEQUENCE

        header = struct.pack(
            Frame.HEADER_FORMAT,
            packet_length,
            header_length,
            ver,
            op,
            seq,
        )
        return header + body

    @staticmethod
    def decode(data: bytes) -> Tuple[int, Union[int, str, List[str]]]:
        """解码消息帧"""
        plen, hlen, ver, op, _ = struct.unpack_from(Frame.HEADER_FORMAT, data, 0)
        body = data[hlen:]

        if op == WS.OP_MESSAGE:
            # 解压消息体
            if ver == WS.BODY_PROTOCOL_VERSION_BROTLI:
                data = brotli.decompress(body)
            elif ver == WS.BODY_PROTOCOL_VERSION_DEFLATE:
                data = zlib.decompress(body)
            elif ver == WS.BODY_PROTOCOL_VERSION_NORMAL:
                pass
            else:
                raise NotImplementedError(f'不支持的协议版本: {ver}')

            # 解析多条消息
            msg_list = []
            offset = 0
            while offset < len(data):
                plen, hlen, ver, op, _ = struct.unpack_from(Frame.HEADER_FORMAT, data, offset)
                body = data[hlen + offset: plen + offset]
                msg = body.decode('utf8')
                msg_list.append(msg)
                offset += plen

            return op, msg_list
        elif op == WS.OP_HEARTBEAT_REPLY:
            online_count = struct.unpack('>I', body)[0]
            return op, online_count
        elif op == WS.OP_CONNECT_SUCCESS:
            auth_result = body.decode()
            return op, auth_result
        else:
            raise ValueError(f'未知操作类型: {op}')


# 默认弹幕服务器信息
DEFAULT_DANMU_INFO: Dict[str, Any] = {
    "token": "",
    "host_list": [
        {
            "host": "broadcastlv.chat.bilibili.com",
            "port": 2243,
            "wss_port": 443,
            "ws_port": 2244,
        }
    ],
}


class DanmakuClient:
    """B站弹幕 WebSocket 客户端"""
    
    HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）
    
    def __init__(
        self,
        session: aiohttp.ClientSession,
        room_id: int,
        cookie: Optional[str] = None,
        on_live: Optional[Callable[[], asyncio.Future]] = None,
        on_preparing: Optional[Callable[[Optional[int]], asyncio.Future]] = None,
        on_room_change: Optional[Callable[[dict], asyncio.Future]] = None,
    ):
        self.session = session
        self.room_id = room_id
        self.cookie = cookie
        
        # 回调函数
        self.on_live = on_live
        self.on_preparing = on_preparing
        self.on_room_change = on_room_change
        
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._danmu_info: Dict[str, Any] = DEFAULT_DANMU_INFO
        self._host_index = 0
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._message_task: Optional[asyncio.Task] = None
        
        # 从 cookie 提取 uid 和 buvid
        self._uid = self._extract_uid_from_cookie(cookie) if cookie else 0
        self._buvid = self._extract_buvid_from_cookie(cookie) if cookie else ''
    
    @staticmethod
    def _extract_uid_from_cookie(cookie: str) -> int:
        """从 cookie 中提取 uid"""
        try:
            for item in cookie.split(';'):
                item = item.strip()
                if item.startswith('DedeUserID='):
                    return int(item.split('=')[1])
        except:
            pass
        return 0
    
    @staticmethod
    def _extract_buvid_from_cookie(cookie: str) -> str:
        """从 cookie 中提取 buvid"""
        try:
            for item in cookie.split(';'):
                item = item.strip()
                if item.startswith('buvid3='):
                    return item.split('=')[1]
        except:
            pass
        return ''
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Connection': 'Upgrade',
        }
        if self.cookie:
            headers['Cookie'] = self.cookie
        return headers
    
    async def start(self) -> None:
        """启动弹幕客户端"""
        if self._running:
            return
        
        self._running = True
        logger.info(f"正在启动房间 {self.room_id} 的弹幕客户端...")
        logger.debug(f"房间 {self.room_id} Cookie配置: {bool(self.cookie)}, UID={self._uid}, BUVID={bool(self._buvid)}")
        
        try:
            await self._update_danmu_info()
            await self._connect()
            logger.info(f"房间 {self.room_id} 弹幕客户端已启动")
        except Exception as e:
            import traceback
            logger.error(f"房间 {self.room_id} 弹幕客户端启动失败: {e}")
            logger.debug(f"房间 {self.room_id} 启动失败详情:\n{traceback.format_exc()}")
            self._running = False
            raise
    
    async def stop(self) -> None:
        """停止弹幕客户端"""
        if not self._running:
            return
        
        logger.info(f"正在停止房间 {self.room_id} 的弹幕客户端...")
        self._running = False
        
        # 取消任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        
        if self._message_task:
            self._message_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._message_task
        
        # 关闭 WebSocket
        if self._ws and not self._ws.closed:
            await self._ws.close()
        
        logger.info(f"房间 {self.room_id} 弹幕客户端已停止")
    
    async def _update_danmu_info(self) -> None:
        """获取弹幕服务器信息（带 WBI 签名）"""
        try:
            base_url = "https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo"
            params = {
                'id': self.room_id,
                'type': 0,
            }
            headers = self._get_headers()
            
            logger.debug(f"房间 {self.room_id} 正在获取弹幕服务器信息...")
            
            # 使用 WBI 签名
            signed_query = await wbi.sign_params(self.session, params, self.cookie)
            
            if signed_query:
                url = f"{base_url}?{signed_query}"
                logger.debug(f"房间 {self.room_id} 使用WBI签名请求")
            else:
                # 降级：不使用签名
                url = base_url
                logger.warning(f"房间 {self.room_id} 无法获取WBI签名，尝试无签名请求")
            
            logger.debug(f"房间 {self.room_id} 请求URL: {url[:100]}...")
            
            # 如果使用了签名，不再传 params（已经在 URL 中）
            if signed_query:
                async with self.session.get(url, headers=headers, timeout=10) as resp:
                    await self._handle_danmu_info_response(resp)
            else:
                async with self.session.get(url, params=params, headers=headers, timeout=10) as resp:
                    await self._handle_danmu_info_response(resp)
                    
        except Exception as e:
            import traceback
            logger.warning(f"房间 {self.room_id} 获取弹幕服务器信息异常: {e}")
            logger.debug(f"房间 {self.room_id} 异常详情:\n{traceback.format_exc()}")
    
    async def _handle_danmu_info_response(self, resp: aiohttp.ClientResponse) -> None:
        """处理弹幕服务器信息响应"""
        logger.debug(f"房间 {self.room_id} HTTP状态码: {resp.status}")
        
        if resp.status == 200:
            data = await resp.json()
            logger.debug(f"房间 {self.room_id} API响应code: {data.get('code')}, message: {data.get('message')}")
            
            if data.get('code') == 0:
                self._danmu_info = data['data']
                host_list = self._danmu_info.get('host_list', [])
                token = self._danmu_info.get('token', '')[:20] + '...' if self._danmu_info.get('token') else 'None'
                logger.info(f"房间 {self.room_id} 获取弹幕服务器信息成功，服务器数量: {len(host_list)}, token: {token}")
                return
            else:
                logger.warning(f"房间 {self.room_id} API返回错误: code={data.get('code')}, message={data.get('message')}")
        else:
            resp_text = await resp.text()
            logger.warning(f"房间 {self.room_id} HTTP请求失败: status={resp.status}, body={resp_text[:200]}")
        
        logger.warning(f"房间 {self.room_id} 获取弹幕服务器信息失败，使用默认服务器")
    
    async def _connect(self) -> None:
        """连接 WebSocket"""
        host_list = self._danmu_info.get('host_list', DEFAULT_DANMU_INFO['host_list'])
        
        logger.info(f"房间 {self.room_id} 开始连接弹幕服务器，可用服务器数量: {len(host_list)}")
        
        for retry in range(len(host_list)):
            try:
                host_info = host_list[self._host_index % len(host_list)]
                url = f"wss://{host_info['host']}:{host_info['wss_port']}/sub"
                
                logger.info(f"房间 {self.room_id} 尝试连接 #{retry+1}: {url}")
                
                # 连接 WebSocket
                try:
                    self._ws = await self.session.ws_connect(
                        url, 
                        timeout=10, 
                        headers=self._get_headers(),
                        heartbeat=30.0
                    )
                    logger.debug(f"房间 {self.room_id} WebSocket 连接建立成功")
                except Exception as ws_err:
                    logger.error(f"房间 {self.room_id} WebSocket 连接失败: {type(ws_err).__name__}: {ws_err}")
                    self._host_index += 1
                    continue
                
                # 发送认证
                logger.debug(f"房间 {self.room_id} 正在发送认证...")
                await self._send_auth()
                logger.debug(f"房间 {self.room_id} 认证已发送，等待响应...")
                
                # 等待认证结果
                try:
                    msg = await self._ws.receive(timeout=10)
                    logger.debug(f"房间 {self.room_id} 收到响应: type={msg.type}")
                except Exception as recv_err:
                    logger.error(f"房间 {self.room_id} 接收认证响应失败: {type(recv_err).__name__}: {recv_err}")
                    self._host_index += 1
                    if self._ws:
                        await self._ws.close()
                    continue
                
                if msg.type == aiohttp.WSMsgType.BINARY:
                    try:
                        op, result = Frame.decode(msg.data)
                        logger.debug(f"房间 {self.room_id} 认证响应: op={op}")
                        
                        if op == WS.OP_CONNECT_SUCCESS:
                            result_data = json.loads(result)
                            code = result_data.get('code', -1)
                            logger.debug(f"房间 {self.room_id} 认证结果: code={code}, data={result_data}")
                            
                            if code == WS.AUTH_OK:
                                logger.info(f"房间 {self.room_id} 认证成功，启动心跳和消息循环")
                                # 启动心跳和消息循环
                                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                                self._message_task = asyncio.create_task(self._message_loop())
                                return
                            else:
                                logger.error(f"房间 {self.room_id} 认证失败: code={code}")
                        else:
                            logger.warning(f"房间 {self.room_id} 收到非预期的响应类型: op={op}")
                    except Exception as decode_err:
                        logger.error(f"房间 {self.room_id} 解码认证响应失败: {type(decode_err).__name__}: {decode_err}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.error(f"房间 {self.room_id} WebSocket 被服务器关闭")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"房间 {self.room_id} WebSocket 错误: {msg.data}")
                else:
                    logger.warning(f"房间 {self.room_id} 收到未知响应类型: {msg.type}")
                
                # 连接失败，尝试下一个服务器
                self._host_index += 1
                if self._ws:
                    await self._ws.close()
                    
            except Exception as e:
                import traceback
                logger.error(f"房间 {self.room_id} 连接过程异常: {type(e).__name__}: {e}")
                logger.debug(f"房间 {self.room_id} 异常详情:\n{traceback.format_exc()}")
                self._host_index += 1
                if self._ws:
                    with suppress(Exception):
                        await self._ws.close()
        
        raise ConnectionError(f"房间 {self.room_id} 无法连接到弹幕服务器（已尝试 {len(host_list)} 个服务器）")
    
    async def _send_auth(self) -> None:
        """发送认证信息"""
        token = self._danmu_info.get('token', '')
        auth_data = {
            "uid": self._uid,
            "roomid": self.room_id,
            "protover": WS.BODY_PROTOCOL_VERSION_BROTLI,
            "buvid": self._buvid,
            "platform": "web",
            "type": 2,
            "key": token,
        }
        
        # 打印认证参数（隐藏敏感信息）
        logger.debug(f"房间 {self.room_id} 认证参数: uid={self._uid}, roomid={self.room_id}, "
                    f"buvid={self._buvid[:10] + '...' if self._buvid else 'None'}, "
                    f"token={token[:20] + '...' if token else 'None'}")
        
        data = Frame.encode(WS.OP_USER_AUTHENTICATION, json.dumps(auth_data))
        logger.debug(f"房间 {self.room_id} 发送认证数据，大小: {len(data)} bytes")
        await self._ws.send_bytes(data)
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        heartbeat_data = Frame.encode(WS.OP_HEARTBEAT, '')
        
        while self._running:
            try:
                await self._ws.send_bytes(heartbeat_data)
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"房间 {self.room_id} 心跳发送失败: {e}")
                # 尝试重连
                asyncio.create_task(self._reconnect())
                break
    
    async def _message_loop(self) -> None:
        """消息接收循环"""
        while self._running:
            try:
                msg = await self._ws.receive(timeout=self.HEARTBEAT_INTERVAL * 2)
                
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await self._handle_message(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning(f"房间 {self.room_id} WebSocket 连接断开")
                    asyncio.create_task(self._reconnect())
                    break
                    
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"房间 {self.room_id} 消息接收异常: {e}")
                asyncio.create_task(self._reconnect())
                break
    
    async def _handle_message(self, data: bytes) -> None:
        """处理收到的消息"""
        try:
            op, msg = Frame.decode(data)
            
            if op == WS.OP_MESSAGE:
                for m in msg:
                    try:
                        msg_data = json.loads(m)
                        await self._dispatch_command(msg_data)
                    except json.JSONDecodeError:
                        pass
            elif op == WS.OP_HEARTBEAT_REPLY:
                # 心跳回复，包含在线人数
                pass
                
        except Exception as e:
            logger.debug(f"房间 {self.room_id} 消息处理异常: {e}")
    
    async def _dispatch_command(self, msg: dict) -> None:
        """分发命令"""
        cmd = msg.get('cmd', '')
        
        # 处理开播命令
        if cmd == DanmakuCommand.LIVE.value:
            logger.info(f"房间 {self.room_id} 收到开播信号 (LIVE)")
            if self.on_live:
                try:
                    await self.on_live()
                except Exception as e:
                    logger.error(f"房间 {self.room_id} 开播回调执行失败: {e}")
        
        # 处理关播命令
        elif cmd == DanmakuCommand.PREPARING.value:
            # round=1 表示轮播
            round_status = msg.get('round', 0)
            logger.info(f"房间 {self.room_id} 收到关播信号 (PREPARING, round={round_status})")
            if self.on_preparing:
                try:
                    await self.on_preparing(round_status)
                except Exception as e:
                    logger.error(f"房间 {self.room_id} 关播回调执行失败: {e}")
        
        # 处理房间信息变更
        elif cmd == DanmakuCommand.ROOM_CHANGE.value:
            logger.debug(f"房间 {self.room_id} 收到房间信息变更信号")
            if self.on_room_change:
                try:
                    await self.on_room_change(msg.get('data', {}))
                except Exception as e:
                    logger.error(f"房间 {self.room_id} 房间变更回调执行失败: {e}")
    
    async def _reconnect(self) -> None:
        """重新连接"""
        if not self._running:
            return
        
        logger.info(f"房间 {self.room_id} 正在重新连接...")
        
        # 取消现有任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        
        if self._ws and not self._ws.closed:
            with suppress(Exception):
                await self._ws.close()
        
        # 等待一段时间后重连
        await asyncio.sleep(3)
        
        if self._running:
            try:
                await self._connect()
                logger.info(f"房间 {self.room_id} 重新连接成功")
            except Exception as e:
                logger.error(f"房间 {self.room_id} 重新连接失败: {e}")
                # 继续尝试重连
                await asyncio.sleep(10)
                if self._running:
                    asyncio.create_task(self._reconnect())
