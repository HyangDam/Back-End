from datetime import datetime

from pydantic import BaseModel, Field


class CurrentPerfume(BaseModel):
    perfume_id: int
    name: str
    brand: str


class OnboardingPreferenceRequest(BaseModel):
    current_perfumes: list[CurrentPerfume] = Field(default_factory=list)
    preferred_target: str | None = Field(
        default=None,
        description="선호 대상 성별: male, female, unisex",
    )
    selected_categories: list[str] = Field(default_factory=list)
    avoid_categories: list[str] = Field(default_factory=list)
    focus_categories: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)


class OnboardingPreferenceResponse(BaseModel):
    onboarding_id: int
    user_id: int
    current_perfumes: list[CurrentPerfume] | None
    preferred_target: str | None
    selected_categories: list[str]
    avoid_categories: list[str]
    focus_categories: list[str]
    preferred_brands: list[str]
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {
        "from_attributes": True
    }