"""Auth routes: register, login, logout, me, forgot and reset password."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.auth.dependencies import CurrentUser
from savora_backend.auth.mailer import MailerDep
from savora_backend.auth.service import AuthService, send_reset_email
from savora_backend.auth.session import clear_session_cookie, set_session_cookie
from savora_backend.config import get_settings
from savora_backend.core.users import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserDto,
)
from savora_backend.database import get_session
from savora_backend.decorators import response_message
from savora_backend.interceptors import TransformRoute

auth_router = APIRouter(prefix="/auth", tags=["auth"], route_class=TransformRoute)


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
@response_message("User registered")
async def register(
    body: RegisterRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    result = await AuthService(session).register(body)
    set_session_cookie(response, result.access_token)
    return result


@auth_router.post("/login")
@response_message("Logged in")
async def login(
    body: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    result = await AuthService(session).login(body)
    set_session_cookie(response, result.access_token)
    return result


@auth_router.post("/logout")
@response_message("Logged out")
async def logout(response: Response) -> None:
    """Clears the session cookie; needs no valid session (an expired one must clear too)."""
    clear_session_cookie(response)


@auth_router.post("/forgot-password")
@response_message("If that email is registered, a reset link is on its way.")
async def forgot_password(
    body: ForgotPasswordRequest,
    tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    mailer: MailerDep,
) -> None:
    """Always the same answer, so it cannot be used to find out who has an account."""
    found = await AuthService(session).request_password_reset(body)
    if found is not None:
        email, link = found
        minutes = get_settings().password_reset_expire_minutes
        tasks.add_task(send_reset_email, mailer, email, link, minutes)


@auth_router.post("/reset-password")
@response_message("Password updated. Sign in with your new password.")
async def reset_password(
    body: ResetPasswordRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await AuthService(session).reset_password(body)
    clear_session_cookie(response)


@auth_router.get("/me")
@response_message("Current user retrieved")
async def get_me(user: CurrentUser) -> UserDto:
    return UserDto.model_validate(user)
