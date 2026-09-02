from datetime import datetime
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
)
from app.database import get_db
from app.models.auth import RefreshToken, SocialAccount
from app.models.user import User, UserStatus
from app.schemas.auth import (
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    SocialLoginRequest,
    TokenResponse,
)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Auth"],
)

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
GOOGLE_USER_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
KAKAO_REST_API_KEY = os.getenv(
    "KAKAO_REST_API_KEY",
    "404563302b790bd01fff700150811b32",
)
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")


def request_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    form_data: dict[str, str] | None = None,
) -> dict:
    data = None

    if form_data is not None:
        data = urlencode(form_data).encode("utf-8")

    request = Request(
        url,
        data=data,
        headers=headers or {},
        method=method,
    )

    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=401,
            detail=f"Social provider authentication failed: {error_body}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=502,
            detail="Social provider authentication server is unavailable.",
        ) from exc


def get_kakao_profile(code: str, redirect_uri: str) -> dict:
    form_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": redirect_uri,
        "code": code,
    }

    if KAKAO_CLIENT_SECRET:
        form_data["client_secret"] = KAKAO_CLIENT_SECRET

    token_response = request_json(
        KAKAO_TOKEN_URL,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        form_data=form_data,
    )
    provider_token = token_response.get("access_token")

    if not provider_token:
        raise HTTPException(status_code=401, detail="Kakao access token was not issued.")

    user_response = request_json(
        KAKAO_USER_INFO_URL,
        headers={"Authorization": f"Bearer {provider_token}"},
    )
    kakao_account = user_response.get("kakao_account") or {}
    profile = kakao_account.get("profile") or {}
    email = kakao_account.get("email")

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Kakao account email was not provided. Check Kakao consent settings.",
        )

    return {
        "provider": "kakao",
        "provider_user_id": str(user_response["id"]),
        "email": email,
        "name": kakao_account.get("name"),
        "nickname": profile.get("nickname"),
        "profile_image_url": profile.get("profile_image_url")
        or profile.get("thumbnail_image_url"),
    }


def get_google_profile(provider_token: str) -> dict:
    user_response = request_json(
        GOOGLE_USER_INFO_URL,
        headers={"Authorization": f"Bearer {provider_token}"},
    )
    email = user_response.get("email")

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Google account email was not provided.",
        )

    return {
        "provider": "google",
        "provider_user_id": user_response["sub"],
        "email": email,
        "name": user_response.get("name"),
        "nickname": user_response.get("name"),
        "profile_image_url": user_response.get("picture"),
    }


def get_dev_profile(request: SocialLoginRequest) -> dict:
    if not request.provider_user_id or not request.email:
        raise HTTPException(
            status_code=400,
            detail="provider_user_id and email are required for dev social login.",
        )

    return {
        "provider": request.provider,
        "provider_user_id": request.provider_user_id,
        "email": str(request.email),
        "name": request.name,
        "nickname": request.nickname,
        "profile_image_url": None,
    }


def resolve_social_profile(request: SocialLoginRequest) -> dict:
    if request.provider == "kakao":
        if request.code and request.redirect_uri:
            return get_kakao_profile(request.code, request.redirect_uri)
        return get_dev_profile(request)

    if request.provider == "google":
        if request.provider_token:
            return get_google_profile(request.provider_token)
        return get_dev_profile(request)

    raise HTTPException(status_code=400, detail="Unsupported social provider.")


def build_token_response(
    user: User,
    access_token: str,
    refresh_token: str,
    is_new_user: bool,
) -> dict:
    profile_required = not bool(user.name and user.nickname)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email,
        "is_new_user": is_new_user,
        "profile_required": profile_required,
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "nickname": user.nickname,
            "profile_image_url": user.profile_image_url,
        },
    }


def issue_tokens(user_id: int, db: Session) -> tuple[str, str]:
    access_token = create_access_token(user_id)
    refresh_token, expires_at = create_refresh_token()

    db_refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )

    db.add(db_refresh_token)
    db.commit()

    return access_token, refresh_token


@router.post("/social-login", response_model=TokenResponse)
def social_login(
    request: SocialLoginRequest,
    db: Session = Depends(get_db),
):
    social_profile = resolve_social_profile(request)

    social_account = db.query(SocialAccount).filter(
        SocialAccount.provider == social_profile["provider"],
        SocialAccount.provider_user_id == social_profile["provider_user_id"],
    ).first()

    is_new_user = False

    if social_account:
        user = db.query(User).filter(
            User.user_id == social_account.user_id,
            User.status == UserStatus.active,
        ).first()

        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
    else:
        user = db.query(User).filter(User.email == social_profile["email"]).first()

        if user is None:
            user = User(
                email=social_profile["email"],
                password=None,
                name=social_profile["name"],
                nickname=social_profile["nickname"],
                profile_image_url=social_profile["profile_image_url"],
                status=UserStatus.active,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new_user = True

        social_account = SocialAccount(
            user_id=user.user_id,
            provider=social_profile["provider"],
            provider_user_id=social_profile["provider_user_id"],
        )
        db.add(social_account)
        db.commit()

    access_token, refresh_token = issue_tokens(user.user_id, db)

    return build_token_response(user, access_token, refresh_token, is_new_user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    token_hash = hash_token(request.refresh_token)

    db_refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    ).first()

    if db_refresh_token is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    if db_refresh_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired.")

    user = db.query(User).filter(
        User.user_id == db_refresh_token.user_id,
        User.status == UserStatus.active,
    ).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    access_token, new_refresh_token = issue_tokens(user.user_id, db)

    db_refresh_token.revoked_at = datetime.utcnow()
    db.commit()

    return build_token_response(user, access_token, new_refresh_token, False)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db),
):
    token_hash = hash_token(request.refresh_token)

    db_refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    ).first()

    if db_refresh_token:
        db_refresh_token.revoked_at = datetime.utcnow()
        db.commit()

    return {"message": "logout success"}
