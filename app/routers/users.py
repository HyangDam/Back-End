from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database import get_db
from app.models.user import User, UserStatus
from app.schemas.user import UserProfileCreate, UserProfileUpdate, UserResponse

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)


def calculate_age(birth_date: date) -> int:
    today = date.today()
    age = today.year - birth_date.year

    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age


@router.post("/me/profile", response_model=UserResponse)
def create_user_profile(
    request: UserProfileCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == current_user_id,
        User.status == UserStatus.active,
    ).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    nickname_owner = db.query(User).filter(
        User.nickname == request.nickname,
        User.user_id != current_user_id,
    ).first()

    if nickname_owner:
        raise HTTPException(status_code=409, detail="Nickname already exists.")

    user.name = request.name
    user.nickname = request.nickname
    user.gender = request.gender
    user.birth_date = request.birth_date
    user.age = calculate_age(request.birth_date)

    if request.profile_image_url is not None:
        user.profile_image_url = request.profile_image_url

    db.commit()
    db.refresh(user)

    return user


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == current_user_id,
        User.status == UserStatus.active,
    ).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return user


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    request: UserProfileUpdate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == current_user_id,
        User.status == UserStatus.active,
    ).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    update_data = request.model_dump(exclude_unset=True)

    if "birth_date" in update_data and update_data["birth_date"] is not None:
        update_data["age"] = calculate_age(update_data["birth_date"])

    if "nickname" in update_data and update_data["nickname"] is not None:
        nickname_owner = db.query(User).filter(
            User.nickname == update_data["nickname"],
            User.user_id != current_user_id,
        ).first()
        if nickname_owner:
            raise HTTPException(status_code=409, detail="Nickname already exists.")

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user


@router.delete("/me")
def delete_my_account(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.user_id == current_user_id,
        User.status == UserStatus.active,
    ).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    user.status = UserStatus.deleted
    user.deleted_at = datetime.utcnow()

    db.commit()

    return {
        "user_id": user.user_id,
        "deleted": True,
        "message": "user deleted successfully",
    }
