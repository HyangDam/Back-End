from pydantic import BaseModel, EmailStr


class SocialLoginRequest(BaseModel):
    provider: str
    provider_token: str | None = None
    code: str | None = None
    redirect_uri: str | None = None
    provider_user_id: str | None = None
    email: EmailStr | None = None
    name: str | None = None
    nickname: str | None = None


class AuthUserResponse(BaseModel):
    user_id: int
    email: str | None
    name: str | None
    nickname: str | None
    profile_image_url: str | None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str | None
    is_new_user: bool
    profile_required: bool
    user: AuthUserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str
