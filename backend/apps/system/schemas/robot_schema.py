from typing import Optional

from pydantic import BaseModel, Field


class RobotConfigIn(BaseModel):
    """前端提交的机器人配置。app_secret 为明文，后端负责加密落库。"""

    platform: str = Field(default="feishu", max_length=32)
    app_id: Optional[str] = Field(default=None, max_length=255)
    app_secret: Optional[str] = Field(default=None, max_length=255)
    auto_start: bool = Field(default=False)


class RobotConfigOut(BaseModel):
    """返回给前端的配置。app_secret 已脱敏（掩码），绝不回传明文。"""

    platform: str
    app_id: Optional[str] = None
    app_secret_masked: Optional[str] = None
    configured: bool = False
    auto_start: bool = False


class RobotStatusOut(BaseModel):
    """机器人运行状态。"""

    platform: str
    running: bool = False
    configured: bool = False
    auto_start: bool = False
    message: str = ""
