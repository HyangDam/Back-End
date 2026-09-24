import re

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError


CASUAL_ONLY_MESSAGES = {
    "ㅇ",
    "ㅇㅇ",
    "ㅇㅇㅇ",
    "오",
    "오오",
    "오오오",
    "히",
    "히히",
    "ㅎㅎ",
    "ㅋㅋ",
    "ㅋㅋㅋ",
    "네",
    "넹",
    "응",
    "웅",
}

PREFERENCE_HINT_PATTERN = re.compile(
    r"향수|향기|향조|노트|추천|좋아|싫어|피하|부담|강하|은은|가볍|진하|"
    r"달콤|깨끗|상쾌|청량|시원|포근|차분|우아|격식|데이트|출근|학교|여름|겨울|"
    r"플로럴|우디|시트러스|머스크|바닐라|장미|꽃|비누|파우더|"
    r"fresh|clean|citrus|floral|woody|musk|sweet|perfume",
    re.IGNORECASE,
)


class ChatRecommendationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    top_n: int = Field(default=5, ge=1, le=20)

    @field_validator("message")
    @classmethod
    def validate_recommendation_message(cls, value: str) -> str:
        message = value.strip()
        compact_message = re.sub(r"\s+", "", message).casefold()

        if compact_message in CASUAL_ONLY_MESSAGES or not PREFERENCE_HINT_PATTERN.search(
            message
        ):
            raise PydanticCustomError(
                "invalid_recommendation_message",
                "유효한 문장을 입력해주세요. "
                "예시 문장: 중요한 자리에 어울리는 은은하고 깨끗한 향을 추천해줘"
            )

        return message
