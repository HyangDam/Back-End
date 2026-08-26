from datetime import datetime

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
    social_account = db.query(SocialAccount).filter(
        SocialAccount.provider == request.provider,
        SocialAccount.provider_user_id == request.provider_user_id,
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
        user = db.query(User).filter(User.email == request.email).first()

        if user is None:
            user = User(
                email=request.email,
                password=None,
                name=request.name,
                nickname=request.nickname,
                status=UserStatus.active,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new_user = True

        social_account = SocialAccount(
            user_id=user.user_id,
            provider=request.provider,
            provider_user_id=request.provider_user_id,
        )
        db.add(social_account)
        db.commit()

    access_token, refresh_token = issue_tokens(user.user_id, db)

    profile_required = not bool(user.name and user.nickname)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email,
        "is_new_user": is_new_user,
        "profile_required": profile_required,
    }


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

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email,
        "is_new_user": False,
        "profile_required": not bool(user.name and user.nickname),
    }


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