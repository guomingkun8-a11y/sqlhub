"""群机器人配置与启停接口（飞书 / 钉钉 / 企业微信）。

提供：
- GET  /system/robot/config   读取三个平台的配置（Secret 脱敏）
- PUT  /system/robot/config   保存单个平台配置
- POST /system/robot/start    启动指定平台机器人（长连接）
- POST /system/robot/stop     停止指定平台机器人
- GET  /system/robot/status   查询三个平台运行状态
"""
from fastapi import APIRouter, Query

from apps.system.core.robot_manager import (
    SUPPORTED_PLATFORMS,
    robot_manager,
)
from apps.system.crud import robot_manage
from apps.system.schemas.permission import SqlbotPermission, require_permissions
from apps.system.schemas.robot_schema import RobotConfigIn, RobotConfigOut, RobotStatusOut
from common.core.deps import SessionDep

router = APIRouter(tags=["system_robot"], prefix="/system/robot")


def _config_out(session, platform: str) -> RobotConfigOut:
    model = robot_manage.get_config(session, platform)
    secret = robot_manage.get_app_secret(session, platform)
    return RobotConfigOut(
        platform=platform,
        app_id=model.app_id if model else None,
        app_secret_masked=robot_manage.mask_secret(secret),
        configured=bool(model and model.app_id and secret),
        auto_start=bool(model and model.auto_start),
    )


def _status_out(session, platform: str) -> RobotStatusOut:
    config = _config_out(session, platform)
    state = robot_manager.status(platform)
    return RobotStatusOut(
        platform=platform,
        running=state["running"],
        configured=config.configured,
        auto_start=config.auto_start,
        message=state.get("last_error", ""),
    )


@router.get("/config", response_model=list[RobotConfigOut])
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def get_robot_config(session: SessionDep) -> list[RobotConfigOut]:
    return [_config_out(session, platform) for platform in SUPPORTED_PLATFORMS]


@router.put("/config", response_model=RobotConfigOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def save_robot_config(session: SessionDep, dto: RobotConfigIn) -> RobotConfigOut:
    platform = (dto.platform or "feishu").lower()
    if platform not in SUPPORTED_PLATFORMS:
        return RobotConfigOut(platform=platform, configured=False)
    await robot_manage.save_config(
        session,
        platform=platform,
        app_id=dto.app_id,
        app_secret=dto.app_secret,
        auto_start=dto.auto_start,
    )
    return _config_out(session, platform)


@router.post("/start", response_model=RobotStatusOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def start_robot(
    session: SessionDep, platform: str = Query(default="feishu")
) -> RobotStatusOut:
    platform = (platform or "feishu").lower()
    result = robot_manager.start(session, platform=platform)
    status = _status_out(session, platform)
    status.message = result["message"]
    return status


@router.post("/stop", response_model=RobotStatusOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def stop_robot(
    session: SessionDep, platform: str = Query(default="feishu")
) -> RobotStatusOut:
    platform = (platform or "feishu").lower()
    result = robot_manager.stop(platform)
    status = _status_out(session, platform)
    status.message = result["message"]
    return status


@router.get("/status", response_model=list[RobotStatusOut])
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def robot_status(session: SessionDep) -> list[RobotStatusOut]:
    return [_status_out(session, platform) for platform in SUPPORTED_PLATFORMS]
