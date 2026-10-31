"""机器人配置 CRUD。

配置以单条记录存储（按 platform 唯一）。App Secret 使用 AES 加密落库，
读取时只做脱敏处理，明文仅在机器人管理器内部解密使用。
"""
from typing import Optional

from sqlmodel import select

from apps.datasource.utils.utils import aes_encrypt, aes_decrypt
from apps.system.models.robot_model import RobotConfigModel
from common.core.deps import SessionDep
from common.utils.time import get_timestamp

DEFAULT_PLATFORM = "feishu"


def _get(session, platform: str) -> Optional[RobotConfigModel]:
    stmt = select(RobotConfigModel).where(RobotConfigModel.platform == platform)
    return session.exec(stmt).first()


def get_config(session, platform: str = DEFAULT_PLATFORM) -> Optional[RobotConfigModel]:
    return _get(session, platform)


def get_app_secret(session, platform: str = DEFAULT_PLATFORM) -> Optional[str]:
    """解密并返回明文 App Secret（仅供机器人管理器内部使用）。"""
    model = _get(session, platform)
    if not model or not model.app_secret_encrypted:
        return None
    try:
        return aes_decrypt(model.app_secret_encrypted)
    except Exception:
        return None


def mask_secret(secret: Optional[str]) -> Optional[str]:
    """脱敏展示：只保留前 4 位，其余以 * 代替。"""
    if not secret:
        return None
    if len(secret) <= 8:
        return secret[:2] + "****"
    return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]


async def save_config(
    session: SessionDep,
    *,
    platform: str = DEFAULT_PLATFORM,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    auto_start: bool = False,
) -> RobotConfigModel:
    """保存（创建或更新）机器人配置。

    注意：当 app_secret 为 None/空串时，表示「不修改」现有密钥；
    需要清空密钥时应显式传空串，这里约定空串视为清空。
    """
    model = _get(session, platform)
    now = get_timestamp()

    if model is None:
        model = RobotConfigModel(
            platform=platform,
            app_id=app_id,
            auto_start=auto_start,
            create_time=now,
            update_time=now,
        )
        session.add(model)
    else:
        model.app_id = app_id
        model.auto_start = auto_start
        model.update_time = now

    # app_secret 处理：None -> 保持不变；空串 -> 清空；有值 -> 加密更新
    if app_secret is not None:
        if app_secret == "":
            model.app_secret_encrypted = None
        else:
            model.app_secret_encrypted = aes_encrypt(app_secret).decode("utf-8")

    session.add(model)
    session.commit()
    session.refresh(model)
    return model
