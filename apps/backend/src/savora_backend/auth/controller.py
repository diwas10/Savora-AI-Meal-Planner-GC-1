"""Auth routes: register, login, logout, me."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from savora_backend.auth.dependencies import CurrentUser
from savora_backend.auth.service import AuthService
from savora_backend.auth.session import clear_session_cookie, set_session_cookie
from savora_backend.core.users import AuthResponse, LoginRequest, RegisterRequest, UserDto
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


@auth_router.get("/me")
@response_message("Current user retrieved")
async def get_me(user: CurrentUser) -> UserDto:
    return UserDto.model_validate(user)
