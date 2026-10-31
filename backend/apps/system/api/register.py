import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from apps.system.crud.user import check_account_exists, check_pwd_format
from apps.system.models.user import UserModel
from apps.system.schemas.system_schema import EMAIL_REGEX
from common.core.config import settings
from common.core.deps import SessionDep, Trans
from common.core.security import create_access_token, md5pwd
from common.utils.crypto import sqlbot_decrypt

router = APIRouter(tags=["login"], prefix="/login")

# 注册用户默认加入的工作空间（默认工作空间 id=1）
DEFAULT_WORKSPACE_ID = 1


class RegisterStatus(BaseModel):
    enabled: bool
    pwd_pattern: str
    pwd_hint: str


class RegisterForm(BaseModel):
    # username / password 为前端 RSA 加密后的密文，长度不固定，这里放宽上限
    username: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=1, max_length=2048)
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=100)


@router.get("/register-status", response_model=RegisterStatus)
async def register_status() -> RegisterStatus:
    return RegisterStatus(
        enabled=settings.REGISTER_ENABLED,
        pwd_pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$",
        pwd_hint="8-20 位，需包含大写字母、小写字母、数字和特殊字符",
    )


@router.post("/register")
async def register(session: SessionDep, trans: Trans, form: RegisterForm):
    if not settings.REGISTER_ENABLED:
        raise HTTPException(status_code=403, detail="自助注册未开放，请联系管理员开通账号")

    account = await sqlbot_decrypt(form.username)
    password = await sqlbot_decrypt(form.password)
    name = (form.name or account).strip()
    email = (form.email or "").strip()
    if not account or not password:
        raise HTTPException(status_code=400, detail="账号和密码不能为空")

    if not re.fullmatch(r"^[A-Za-z0-9_.@-]{3,50}$", account):
        raise HTTPException(status_code=400, detail="账号需为 3-50 位字母、数字或 _ . @ - 组合")

    if check_account_exists(session=session, account=account):
        raise HTTPException(status_code=400, detail=f"账号 [{account}] 已存在，请直接登录")

    if not check_pwd_format(password):
        raise HTTPException(
            status_code=400,
            detail="密码需 8-20 位，且同时包含大写字母、小写字母、数字和特殊字符",
        )

    if email and not EMAIL_REGEX.fullmatch(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    # UserInfoDTO 对 email 有 min_length=1 约束，未填邮箱时补一个内部占位地址，
    # 否则该用户每次鉴权都会因 email 为空而失败
    if not email:
        email = f"{account}@sqlhub.local"

    # name 字段在库中是唯一约束，重名时自动追加后缀避免插入失败
    unique_name = name
    if session.exec(select(UserModel).where(UserModel.name == unique_name)).first():
        suffix = 2
        while session.exec(select(UserModel).where(UserModel.name == f"{name}{suffix}")).first():
            suffix += 1
        unique_name = f"{name}{suffix}"

    user = UserModel(
        account=account,
        name=unique_name,
        email=email,
        password=md5pwd(password),
        oid=DEFAULT_WORKSPACE_ID,
        status=1,
        origin=0,
        language="zh-CN",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # 注册成功后直接签发登录态，避免用户再手动登录一次
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        {"id": user.id, "account": user.account, "oid": user.oid},
        expires_delta=access_token_expires,
    )
    return {"access_token": token, "need_change_pwd": False}
