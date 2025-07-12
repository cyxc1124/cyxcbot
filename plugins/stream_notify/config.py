from pydantic import BaseModel, Field
from typing import List, Optional


class Config(BaseModel):
    """B站直播通知插件配置"""
    
    # 需要发送通知的群组ID列表
    notify_groups: List[str] = Field(
        default=[], 
        description="需要发送通知的群组ID列表"
    )
    
    # 主播信息配置
    streamer_name: str = Field(
        default="主播", 
        description="主播名称（当API请求中未提供时使用）"
    )
    
    # API接口配置
    api_secret: str = Field(
        default="your_secret_key", 
        description="API密钥，用于验证blrec webhook请求"
    )
    
    # 消息配置
    include_room_info: bool = Field(
        default=True, 
        description="是否包含房间信息（标题、链接等）"
    )
    
    class Config:
        env_prefix = "STREAM_NOTIFY_"  # 环境变量前缀
        env_file = ".env"  # 从.env文件读取
        env_file_encoding = "utf-8" 