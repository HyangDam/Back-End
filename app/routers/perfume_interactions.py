from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.database import get_db
from app.models.perfume_interaction import Like, PerfumeReview, UserPerfume
from app.schemas.perfume_interaction import (
    LikeResponse,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
    UserPerfumeCreate,
    UserPerfumeResponse,
)
from app.services.perfume_catalog import get_perfume_or_none

router = APIRouter(prefix="/api/v1", tags=["Perfume Interactions"])


def get_perfume_or_404(db: Session, perfume_id: int):
    perfume = get_perfume_or_none(db, perfume_id)

    if perfume is None:
        raise HTTPException(status_code=404, detail="Perfume not found.")

    return perfume


def get_like_count(db: Session, perfume_id: int) -> int:
    return db.query(func.count(Like.id)).filter(Like.perfume_id == perfume_id).scalar()


def get_owned_count(db: Session, perfume_id: int) -> int:
    return db.query(func.count(UserPerfume.id)).filter(
        UserPerfume.perfume_id == perfume_id,
        UserPerfume.status == "owned",
    ).scalar()


def get_review_count(db: Session, perfume_id: int) -> int:
    return db.query(func.count(PerfumeReview.review_id)).filter(
        PerfumeReview.perfume_id == perfume_id,
    ).scalar()


def review_to_response(db: Session, review: PerfumeReview):
    return {
        "review_id": review.review_id,
        "user_id": review.user_id,
        "perfume_id": review.perfume_id,
        "rating": review.rating,
        "content": review.content,
        "perfume": get_perfume_or_none(db, review.perfume_id),
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


@router.get("/perfumes/{perfume_id}")
def get_perfume_detail(
    perfume_id: int,
    db: Session = Depends(get_db),
):
    perfume = get_perfume_or_404(db, perfume_id)

    return {
        **perfume,
        "like_count": get_like_count(db, perfume_id),
        "owned_count": get_owned_count(db, perfume_id),
        "review_count": get_review_count(db, perfume_id),
    }


@router.post("/perfumes/{perfume_id}/likes", response_model=LikeResponse)
def like_perfume(
    perfume_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    get_perfume_or_404(db, perfume_id)

    existing_like = db.query(Like).filter(
        Like.user_id == current_user_id,
        Like.perfume_id == perfume_id,
    ).first()

    if existing_like is None:
        like = Like(user_id=current_user_id, perfume_id=perfume_id)
        db.add(like)
        db.commit()

    return {
        "perfume_id": perfume_id,
        "liked": True,
        "like_count": get_like_count(db, perfume_id),
    }


@router.delete("/perfumes/{perfume_id}/likes", response_model=LikeResponse)
def unlike_perfume(
    perfume_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    get_perfume_or_404(db, perfume_id)

    like = db.query(Like).filter(
        Like.user_id == current_user_id,
        Like.perfume_id == perfume_id,
    ).first()

    if like:
        db.delete(like)
        db.commit()

    return {
        "perfume_id": perfume_id,
        "liked": False,
        "like_count": get_like_count(db, perfume_id),
    }


@router.get("/users/me/likes/perfumes")
def get_my_liked_perfumes(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    likes = db.query(Like).filter(
        Like.user_id == current_user_id,
    ).order_by(Like.created_at.desc()).all()

    return {
        "user_id": current_user_id,
        "results": [
            {
                "id": like.id,
                "perfume_id": like.perfume_id,
                "perfume": get_perfume_or_none(db, like.perfume_id),
                "created_at": like.created_at,
            }
            for like in likes
        ],
    }


@router.post("/users/me/perfumes", response_model=UserPerfumeResponse)
def add_my_perfume(
    request: UserPerfumeCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    perfume = get_perfume_or_404(db, request.perfume_id)

    existing_perfume = db.query(UserPerfume).filter(
        UserPerfume.user_id == current_user_id,
        UserPerfume.perfume_id == request.perfume_id,
    ).first()

    if existing_perfume:
        return {
            **existing_perfume.__dict__,
            "perfume": perfume,
        }

    user_perfume = UserPerfume(
        user_id=current_user_id,
        perfume_id=request.perfume_id,
        status=request.status,
    )

    db.add(user_perfume)
    db.commit()
    db.refresh(user_perfume)

    return {
        **user_perfume.__dict__,
        "perfume": perfume,
    }


@router.delete("/users/me/perfumes/{perfume_id}")
def delete_my_perfume(
    perfume_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_perfume = db.query(UserPerfume).filter(
        UserPerfume.user_id == current_user_id,
        UserPerfume.perfume_id == perfume_id,
    ).first()

    if user_perfume is None:
        raise HTTPException(status_code=404, detail="User perfume not found.")

    db.delete(user_perfume)
    db.commit()

    return {
        "perfume_id": perfume_id,
        "deleted": True,
        "message": "perfume removed from my perfume shelf",
    }


@router.get("/users/me/perfumes")
def get_my_perfumes(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_perfumes = db.query(UserPerfume).filter(
        UserPerfume.user_id == current_user_id,
    ).order_by(UserPerfume.created_at.desc()).all()

    return {
        "user_id": current_user_id,
        "results": [
            {
                "id": item.id,
                "perfume_id": item.perfume_id,
                "status": item.status,
                "perfume": get_perfume_or_none(db, item.perfume_id),
                "created_at": item.created_at,
            }
            for item in user_perfumes
        ],
    }


@router.get("/perfumes/{perfume_id}/reviews")
def get_perfume_reviews(
    perfume_id: int,
    db: Session = Depends(get_db),
):
    get_perfume_or_404(db, perfume_id)

    reviews = db.query(PerfumeReview).filter(
        PerfumeReview.perfume_id == perfume_id,
    ).order_by(PerfumeReview.created_at.desc()).all()

    return {
        "perfume_id": perfume_id,
        "review_count": len(reviews),
        "results": [review_to_response(db, review) for review in reviews],
    }


@router.post("/perfumes/{perfume_id}/reviews", response_model=ReviewResponse)
def create_perfume_review(
    perfume_id: int,
    request: ReviewCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    get_perfume_or_404(db, perfume_id)

    owned_perfume = db.query(UserPerfume).filter(
        UserPerfume.user_id == current_user_id,
        UserPerfume.perfume_id == perfume_id,
        UserPerfume.status == "owned",
    ).first()

    if owned_perfume is None:
        raise HTTPException(
            status_code=403,
            detail="Only users who own this perfume can write a review.",
        )

    existing_review = db.query(PerfumeReview).filter(
        PerfumeReview.user_id == current_user_id,
        PerfumeReview.perfume_id == perfume_id,
    ).first()

    if existing_review:
        raise HTTPException(status_code=409, detail="Review already exists.")

    review = PerfumeReview(
        user_id=current_user_id,
        perfume_id=perfume_id,
        rating=request.rating,
        content=request.content,
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return review_to_response(db, review)


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
def update_perfume_review(
    review_id: int,
    request: ReviewUpdate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    review = db.query(PerfumeReview).filter(
        PerfumeReview.review_id == review_id,
        PerfumeReview.user_id == current_user_id,
    ).first()

    if review is None:
        raise HTTPException(status_code=404, detail="Review not found.")

    update_data = request.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(review, key, value)

    db.commit()
    db.refresh(review)

    return review_to_response(db, review)


@router.delete("/reviews/{review_id}")
def delete_perfume_review(
    review_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    review = db.query(PerfumeReview).filter(
        PerfumeReview.review_id == review_id,
        PerfumeReview.user_id == current_user_id,
    ).first()

    if review is None:
        raise HTTPException(status_code=404, detail="Review not found.")

    db.delete(review)
    db.commit()

    return {
        "review_id": review_id,
        "deleted": True,
        "message": "review deleted successfully",
    }


@router.get("/users/me/reviews")
def get_my_reviews(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    reviews = db.query(PerfumeReview).filter(
        PerfumeReview.user_id == current_user_id,
    ).order_by(PerfumeReview.created_at.desc()).all()

    return {
        "user_id": current_user_id,
        "results": [review_to_response(db, review) for review in reviews],
    }
