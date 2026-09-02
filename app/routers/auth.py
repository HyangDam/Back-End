from datetime import datetime
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
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
KAKAO_JWKS_URL = "https://kauth.kakao.com/.well-known/jwks.json"
KAKAO_EVENT_ISSUER = "https://kauth.kakao.com"
KAKAO_USER_UNLINKED_EVENT = (
    "https://schemas.openid.net/secevent/oauth/event-type/user-unlinked"
)
GOOGLE_USER_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
ALLOW_DEV_SOCIAL_LOGIN = os.getenv("ALLOW_DEV_SOCIAL_LOGIN", "false").lower() == "true"
kakao_jwk_client = jwt.PyJWKClient(KAKAO_JWKS_URL, cache_keys=True)


def request_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    form_data: dict[str, str] | None = None,
) -> dict:
    data = None

    if form_data is not None:
        data = urlencode(form_data).encode("utf-8")

    request = UrlRequest(
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
    if not KAKAO_REST_API_KEY:
        raise HTTPException(status_code=500, detail="Kakao REST API key is not configured.")
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

    return {
        "provider": "google",
        "provider_user_id": user_response["sub"],
        "email": email,
        "name": user_response.get("name"),
        "nickname": user_response.get("name"),
        "profile_image_url": user_response.get("picture"),
    }


def get_dev_profile(request: SocialLoginRequest) -> dict:
    if not ALLOW_DEV_SOCIAL_LOGIN:
        raise HTTPException(
            status_code=400,
            detail="Use a Kakao authorization code or Google provider token.",
        )
    if not request.provider_user_id:
        raise HTTPException(
            status_code=400,
            detail="provider_user_id is required for dev social login.",
        )

    return {
        "provider": request.provider,
        "provider_user_id": request.provider_user_id,
        "email": str(request.email) if request.email else None,
        "name": request.name,
        "nickname": request.nickname,
        "profile_image_url": None,
    }


def resolve_social_profile(request: SocialLoginRequest) -> dict:
    if request.provider == "kakao":
        if request.code and request.redirect_uri:
            return get_kakao_profile(request.code, request.redirect_uri)
        if request.code or request.redirect_uri:
            raise HTTPException(
                status_code=400,
                detail="Kakao login requires both code and redirect_uri.",
            )
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
    profile_required = not bool(
        user.name and user.nickname and user.gender and user.birth_date
    )

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
        email = social_profile.get("email")
        user = None

        if email:
            user = db.query(User).filter(User.email == email).first()

        if user is None:
            user = User(
                email=email,
                password=None,
                # Collect recommendation-related profile data after social login.
                name=None,
                nickname=None,
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


def verify_kakao_event_token(event_token: str) -> dict:
    if not KAKAO_REST_API_KEY:
        raise ValueError("Kakao REST API key is not configured.")

    signing_key = kakao_jwk_client.get_signing_key_from_jwt(event_token)
    return jwt.decode(
        event_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=KAKAO_REST_API_KEY,
        issuer=KAKAO_EVENT_ISSUER,
    )


def process_kakao_user_unlinked(provider_user_id: str, db: Session) -> None:
    social_account = db.query(SocialAccount).filter(
        SocialAccount.provider == "kakao",
        SocialAccount.provider_user_id == provider_user_id,
    ).first()

    if social_account is None:
        return

    user_id = social_account.user_id
    db.delete(social_account)
    db.flush()

    remaining_social_accounts = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
    ).count()

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: datetime.utcnow()})

    if remaining_social_accounts == 0:
        user = db.get(User, user_id)
        if user and user.status == UserStatus.active:
            user.status = UserStatus.deleted
            user.deleted_at = datetime.utcnow()

    db.commit()


@router.post("/kakao/unlink-webhook", status_code=status.HTTP_202_ACCEPTED)
async def kakao_account_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive and verify Kakao's signed Security Event Token (SET)."""
    event_token = (await request.body()).decode("utf-8").strip()

    try:
        payload = verify_kakao_event_token(event_token)
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"err": "invalid_request", "description": str(exc)},
        )

    if KAKAO_USER_UNLINKED_EVENT in (payload.get("events") or {}):
        provider_user_id = str(payload.get("sub", ""))
        if provider_user_id:
            process_kakao_user_unlinked(provider_user_id, db)

    return Response(status_code=status.HTTP_202_ACCEPTED)
