"""群机器人配置与启停接口。

提供：
- GET  /system/robot/config   读取配置（Secret 脱敏）
- PUT  /system/robot/config   保存配置
- POST /system/robot/start    启动机器人（长连接）
- POST /system/robot/stop     停止机器人
- GET  /system/robot/status   查询运行状态
"""
from fastapi import APIRouter

from apps.system.core.robot_manager import robot_manager
from apps.system.crud import robot_manage
from apps.system.schemas.permission import SqlbotPermission, require_permissions
from apps.system.schemas.robot_schema import RobotConfigIn, RobotConfigOut, RobotStatusOut
from common.core.deps import SessionDep

router = APIRouter(tags=["system_robot"], prefix="/system/robot")


@router.get("/config", response_model=RobotConfigOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def get_robot_config(session: SessionDep) -> RobotConfigOut:
    model = robot_manage.get_config(session)
    if model is None:
        return RobotConfigOut(
            platform="feishu",
            configured=False,
        )
    secret = robot_manage.get_app_secret(session)
    return RobotConfigOut(
        platform=model.platform,
        app_id=model.app_id,
        app_secret_masked=robot_manage.mask_secret(secret),
        configured=bool(model.app_id and secret),
        auto_start=model.auto_start,
    )


@router.put("/config", response_model=RobotConfigOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def save_robot_config(session: SessionDep, dto: RobotConfigIn) -> RobotConfigOut:
    model = await robot_manage.save_config(
        session,
        platform=dto.platform,
        app_id=dto.app_id,
        app_secret=dto.app_secret,
        auto_start=dto.auto_start,
    )
    secret = robot_manage.get_app_secret(session, dto.platform)
    return RobotConfigOut(
        platform=model.platform,
        app_id=model.app_id,
        app_secret_masked=robot_manage.mask_secret(secret),
        configured=bool(model.app_id and secret),
        auto_start=model.auto_start,
    )


@router.post("/start", response_model=RobotStatusOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def start_robot(session: SessionDep) -> RobotStatusOut:
    result = robot_manager.start(session, platform="feishu")
    model = robot_manage.get_config(session)
    configured = bool(model and model.app_id and robot_manage.get_app_secret(session))
    return RobotStatusOut(
        platform="feishu",
        running=robot_manager.running,
        configured=configured,
        message=result["message"],
    )


@router.post("/stop", response_model=RobotStatusOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def stop_robot(session: SessionDep) -> RobotStatusOut:
    result = robot_manager.stop()
    model = robot_manage.get_config(session)
    configured = bool(model and model.app_id and robot_manage.get_app_secret(session))
    return RobotStatusOut(
        platform="feishu",
        running=False,
        configured=configured,
        message=result["message"],
    )


@router.get("/status", response_model=RobotStatusOut)
@require_permissions(permission=SqlbotPermission(role=["admin"]))
async def robot_status(session: SessionDep) -> RobotStatusOut:
    model = robot_manage.get_config(session)
    configured = bool(model and model.app_id and robot_manage.get_app_secret(session))
    st = robot_manager.status()
    return RobotStatusOut(
        platform="feishu",
        running=st["running"],
        configured=configured,
        auto_start=bool(model and model.auto_start),
        message=st.get("last_error", "") if st["running"] else "",
    )
