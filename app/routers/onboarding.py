from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database import get_db
from app.models.onboarding import UserOnboarding
from app.schemas.onboarding import (
    OnboardingPreferenceRequest,
    OnboardingPreferenceResponse,
)

router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["Onboarding"],
)


@router.post("/preferences", response_model=OnboardingPreferenceResponse)
def save_onboarding_preferences(
    request: OnboardingPreferenceRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_id = current_user_id

    existing_onboarding = db.query(UserOnboarding).filter(
        UserOnboarding.user_id == user_id
    ).first()

    if existing_onboarding:
        raise HTTPException(
            status_code=409,
            detail="Onboarding preferences already exist.",
        )

    onboarding = UserOnboarding(
        user_id=user_id,
        current_perfumes=[
            perfume.model_dump() for perfume in request.current_perfumes
        ],
        preferred_target=request.preferred_target,
        selected_categories=request.selected_categories,
        avoid_categories=request.avoid_categories,
        focus_categories=request.focus_categories,
        preferred_brands=request.preferred_brands,
    )

    db.add(onboarding)
    db.commit()
    db.refresh(onboarding)

    return onboarding


@router.get("/me", response_model=OnboardingPreferenceResponse)
def get_my_onboarding_preferences(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_id = current_user_id

    onboarding = db.query(UserOnboarding).filter(
        UserOnboarding.user_id == user_id
    ).first()

    if onboarding is None:
        raise HTTPException(status_code=404, detail="Onboarding preferences not found.")

    return onboarding


@router.patch("/preferences", response_model=OnboardingPreferenceResponse)
def update_onboarding_preferences(
    request: OnboardingPreferenceRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_id = current_user_id

    onboarding = db.query(UserOnboarding).filter(
        UserOnboarding.user_id == user_id
    ).first()

    if onboarding is None:
        raise HTTPException(status_code=404, detail="Onboarding preferences not found.")

    update_data = request.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(onboarding, key, value)

    db.commit()
    db.refresh(onboarding)

    return onboarding