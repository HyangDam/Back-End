"""기존 import 경로 호환용 모듈.

실제 모델은 도메인별 파일에 분리해 두고, 기존 라우터의 import는 유지한다.
"""

from app.models.like import Like
from app.models.review import PerfumeReview
from app.models.user_perfume import UserPerfume

__all__ = ["Like", "PerfumeReview", "UserPerfume"]
