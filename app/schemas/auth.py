from pydantic import BaseModel, EmailStr


class SocialLoginRequest(BaseModel):
    provider: str
    provider_user_id: str
    email: EmailStr
    name: str | None = None
    nickname: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    is_new_user: bool
    profile_required: bool


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str
