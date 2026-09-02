"""개발·시연 환경에서만 사용하는 최소 목데이터."""

from sqlalchemy.orm import Session

from app.models.like import Like
from app.models.review import PerfumeReview
from app.models.user import User, UserStatus
from app.models.user_perfume import UserPerfume

DEMO_USERS = [
    {
        "email": "demo.review.1@hyangdam.local",
        "name": "향담 데모",
        "nickname": "포근한향",
    },
    {
        "email": "demo.review.2@hyangdam.local",
        "name": "향담 데모",
        "nickname": "산뜻한향",
    },
]

DEMO_REVIEWS = [
    {
        "email": "demo.review.1@hyangdam.local",
        "perfume_id": 50,
        "rating": 5,
        "content": "은은한 꽃향과 포근한 잔향이 잘 어울려 데일리로 사용하기 좋았어요.",
    },
    {
        "email": "demo.review.2@hyangdam.local",
        "perfume_id": 50,
        "rating": 4,
        "content": "처음에는 산뜻하고, 시간이 지나면 부드러워져서 부담 없이 사용했어요.",
    },
]


def seed_demo_reviews(db: Session) -> int:
    """반복 실행해도 중복되지 않는 시연용 보유 향수 및 리뷰를 생성한다."""
    users_by_email: dict[str, User] = {}

    for user_data in DEMO_USERS:
        user = db.query(User).filter(User.email == user_data["email"]).first()
        if user is None:
            user = User(
                email=user_data["email"],
                password=None,
                name=user_data["name"],
                nickname=user_data["nickname"],
                status=UserStatus.active,
            )
            db.add(user)
            db.flush()
        users_by_email[user.email] = user

    inserted_reviews = 0
    for review_data in DEMO_REVIEWS:
        user = users_by_email[review_data["email"]]
        perfume_id = review_data["perfume_id"]

        owned_perfume = db.query(UserPerfume).filter(
            UserPerfume.user_id == user.user_id,
            UserPerfume.perfume_id == perfume_id,
        ).first()
        if owned_perfume is None:
            db.add(
                UserPerfume(
                    user_id=user.user_id,
                    perfume_id=perfume_id,
                    status="owned",
                )
            )

        existing_like = db.query(Like).filter(
            Like.user_id == user.user_id,
            Like.perfume_id == perfume_id,
        ).first()
        if existing_like is None:
            db.add(Like(user_id=user.user_id, perfume_id=perfume_id))

        existing_review = db.query(PerfumeReview).filter(
            PerfumeReview.user_id == user.user_id,
            PerfumeReview.perfume_id == perfume_id,
        ).first()
        if existing_review is None:
            db.add(
                PerfumeReview(
                    user_id=user.user_id,
                    perfume_id=perfume_id,
                    rating=review_data["rating"],
                    content=review_data["content"],
                )
            )
            inserted_reviews += 1

    db.commit()
    return inserted_reviews
