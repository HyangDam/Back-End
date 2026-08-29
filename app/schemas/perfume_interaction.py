from datetime import datetime

from pydantic import BaseModel, Field


class UserPerfumeCreate(BaseModel):
    perfume_id: int
    status: str = "owned"


class UserPerfumeResponse(BaseModel):
    id: int
    user_id: int
    perfume_id: int
    status: str
    perfume: dict
    created_at: datetime | None

    model_config = {"from_attributes": True}


class LikeResponse(BaseModel):
    perfume_id: int
    liked: bool
    like_count: int


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(..., min_length=1)


class ReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str | None = Field(default=None, min_length=1)


class ReviewResponse(BaseModel):
    review_id: int
    user_id: int
    perfume_id: int
    rating: int
    content: str
    perfume: dict | None = None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}