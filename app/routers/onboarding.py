from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database import get_db
from app.models.onboarding import UserOnboarding
from app.models.perfume import Perfume
from app.schemas.onboarding import (
    OnboardingPreferenceRequest,
    OnboardingPreferenceResponse,
)

router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["Onboarding"],
)


def build_current_perfumes(db: Session, selected_perfumes: list) -> list[dict]:
    """프론트가 보낸 ID를 기준으로 DB의 공식 향수명과 브랜드를 저장한다."""
    perfume_ids = [item.perfume_id for item in selected_perfumes]
    if not perfume_ids:
        return []

    perfumes = db.query(Perfume).filter(Perfume.perfume_id.in_(perfume_ids)).all()
    perfume_by_id = {perfume.perfume_id: perfume for perfume in perfumes}
    missing_ids = [perfume_id for perfume_id in perfume_ids if perfume_id not in perfume_by_id]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Perfume not found: {missing_ids}",
        )

    return [
        {
            "perfume_id": perfume_id,
            "name": perfume_by_id[perfume_id].name,
            "brand": perfume_by_id[perfume_id].brand,
        }
        for perfume_id in perfume_ids
    ]


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
        current_perfumes=build_current_perfumes(db, request.current_perfumes),
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

    if "current_perfumes" in update_data:
        update_data["current_perfumes"] = build_current_perfumes(
            db,
            request.current_perfumes,
        )

    for key, value in update_data.items():
        setattr(onboarding, key, value)

    db.commit()
    db.refresh(onboarding)

    return onboarding
