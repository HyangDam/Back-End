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

class ChatRecommendationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    top_n: int = Field(default=5, ge=1, le=20)

    @field_validator("message")
    @classmethod
    def validate_recommendation_message(cls, value: str) -> str:
        message = value.strip()
        compact_message = re.sub(r"\s+", "", message).casefold()
        content_length = len(re.sub(r"[^\w가-힣]", "", compact_message))

        # Natural-language intent is interpreted by the LLM. Only reject short,
        # acknowledgement-only messages before spending an API request.
        if compact_message in CASUAL_ONLY_MESSAGES or content_length < 2:
            raise PydanticCustomError(
                "invalid_recommendation_message",
                "원하는 향이나 상황을 조금 더 자세히 입력해주세요. "
                "예시: 사회초년생이라 부담 없고 몽글몽글한 향을 찾고 있어요"
            )

        return message
