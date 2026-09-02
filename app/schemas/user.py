from datetime import date, datetime

from pydantic import BaseModel


class UserProfileCreate(BaseModel):
    name: str
    nickname: str
    gender: str
    birth_date: date
    profile_image_url: str | None = None


class UserProfileUpdate(BaseModel):
    name: str | None = None
    nickname: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    profile_image_url: str | None = None


class UserResponse(BaseModel):
    user_id: int
    email: str | None
    name: str | None
    nickname: str | None
    gender: str | None
    birth_date: date | None
    age: int | None
    profile_image_url: str | None
    status: str
    created_at: datetime | None

    model_config = {
        "from_attributes": True
    }
