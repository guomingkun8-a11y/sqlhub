from typing import Optional

from sqlmodel import BigInteger, Field, SQLModel, Text

from common.core.models import SnowflakeBase


class RobotConfigBase(SQLModel):
    """群机器人配置基类（飞书等）。

    目前支持飞书企业自建应用（长连接模式），后续可扩展企业微信、钉钉等。
    """

    # 平台标识：feishu / wecom / dingtalk
    platform: str = Field(default="feishu", max_length=32, nullable=False)
    # 应用凭据（App Secret 以 AES 密文落库，前端展示为掩码）
    app_id: Optional[str] = Field(default=None, max_length=255, nullable=True)
    app_secret_encrypted: Optional[str] = Field(default=None, sa_type=Text(), nullable=True)
    # 是否在启动时自动拉起
    auto_start: bool = Field(default=False, nullable=False)


class RobotConfigModel(SnowflakeBase, RobotConfigBase, table=True):
    __tablename__ = "sys_robot_config"

    create_time: int = Field(default=0, sa_type=BigInteger())
    update_time: int = Field(default=0, sa_type=BigInteger())
