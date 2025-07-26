from pydantic import BaseModel
from typing import List

class Config(BaseModel):
    """状态查询插件配置"""
    # 允许查询状态的QQ号列表
    allowed_qq_numbers: List[int] = [120674547]
    
    # 是否显示详细状态信息
    show_detailed_status: bool = True
    
    # 是否显示机器人运行时间
    show_uptime: bool = True
    
    # 是否显示内存使用情况
    show_memory_usage: bool = True 