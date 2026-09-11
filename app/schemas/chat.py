from pydantic import BaseModel, Field


class ChatRecommendationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    top_n: int = Field(default=5, ge=1, le=20)
