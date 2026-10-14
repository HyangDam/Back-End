import json
import logging
import os

from openai import OpenAI

from app.services.preference_extractor import extract_preferences_from_text
from app.services.recommender import AVOID_KEYWORDS, CATEGORY_KEYWORDS

logger = logging.getLogger(__name__)


CATEGORY_RECOMMENDATION_PHRASES = {
    "clean": "깨끗하고 부담 없는",
    "sweet": "달콤하고 포근한",
    "elegant": "차분하고 우아한",
    "floral": "꽃향이 돋보이는",
    "citrus": "상큼한 시트러스",
    "woody": "차분한 우디",
    "spicy": "개성 있는 스파이시",
    "musk": "부드러운 머스크",
    "powdery": "포근한 파우더리",
    "gourmand": "달콤한 구르망",
    "aquatic": "시원한 아쿠아틱",
    "green": "싱그러운 그린",
    "fresh": "가볍고 프레시한",
    "oriental": "따뜻한 오리엔탈",
    "earthy": "깊이 있는 어시",
    "date": "데이트에 어울리는",
    "school_work": "학교나 출근길에 부담 없는",
    "summer": "여름에 어울리는 산뜻한",
    "winter": "겨울에 어울리는 포근한",
}


def _build_preference_confirmation(selected_categories, focus_categories):
    """Turn extracted categories into a short, user-facing confirmation."""
    categories = set(selected_categories) | set(focus_categories)

    if "winter" in categories and ("sweet" in categories or "musk" in categories):
        return "편안하고 포근한 향을 찾으시는군요."
    if "clean" in categories and "sweet" in categories:
        return "부담 없이 은은하면서도 달콤한 향을 찾으시는군요."
    if "date" in categories:
        return "특별한 약속에 어울리는 향을 찾으시는군요."
    if "school_work" in categories:
        return "일상에서 부담 없이 쓸 향을 찾으시는군요."
    if "summer" in categories:
        return "가볍고 산뜻한 향을 찾으시는군요."
    if "winter" in categories:
        return "따뜻하고 포근한 향을 찾으시는군요."
    if "musk" in categories:
        return "부드럽고 편안한 머스크 계열을 찾으시는군요."
    if "floral" in categories:
        return "화사한 꽃향이 돋보이는 향을 찾으시는군요."
    if "woody" in categories:
        return "차분하고 깊이 있는 우디 향을 찾으시는군요."
    if "citrus" in categories:
        return "상큼하고 시원한 시트러스 향을 찾으시는군요."
    if "sweet" in categories:
        return "달콤하고 포근한 향을 찾으시는군요."
    if "clean" in categories:
        return "깨끗하고 부담 없는 향을 찾으시는군요."

    return "입력하신 취향에 어울리는 향을 찾으시는군요."


def _build_assistant_message(selected_categories, focus_categories):
    """Keep the chat card headline short and consistent across analyzers."""
    primary_category = (focus_categories or selected_categories or ["clean"])[0]
    phrase = CATEGORY_RECOMMENDATION_PHRASES.get(
        primary_category,
        "입력하신 취향에 어울리는",
    )
    confirmation = _build_preference_confirmation(
        selected_categories, focus_categories
    )
    return f"{confirmation} {phrase} 향수를 추천했어요."


def _rule_tfidf_analysis(message: str, analysis_source="rule_tfidf") -> dict:
    extracted = extract_preferences_from_text(message)
    selected_categories = extracted["selected_categories"] or ["clean"]
    avoid_categories = extracted["avoid_categories"]
    focus_categories = selected_categories[:1]

    return {
        "analysis_source": analysis_source,
        "selected_categories": selected_categories,
        "avoid_categories": avoid_categories,
        "focus_categories": focus_categories,
        "selected_scores": extracted["selected_scores"],
        "avoid_scores": extracted["avoid_scores"],
        "assistant_message": _build_assistant_message(
            selected_categories, focus_categories
        ),
    }


SELECTED_CATEGORY_IDS = list(CATEGORY_KEYWORDS)
AVOID_CATEGORY_IDS = list(AVOID_KEYWORDS)

LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_categories": {
            "type": "array",
            "items": {"type": "string", "enum": SELECTED_CATEGORY_IDS},
            "maxItems": 5,
        },
        "avoid_categories": {
            "type": "array",
            "items": {"type": "string", "enum": AVOID_CATEGORY_IDS},
            "maxItems": 5,
        },
        "focus_categories": {
            "type": "array",
            "items": {"type": "string", "enum": SELECTED_CATEGORY_IDS},
            "maxItems": 2,
        },
    },
    "required": [
        "selected_categories",
        "avoid_categories",
        "focus_categories",
    ],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTIONS = """
You are a Korean perfume-preference analyzer for HyangDam.
Extract the user's intent into only the supplied category IDs.
Do not recommend a product, invent a category, or claim that a scent is certain.
Treat clearly negative expressions such as '피하고 싶다', '싫다', '부담스럽다'
as avoid_categories. Choose clean when the user wants an unobtrusive first perfume.
focus_categories must contain the one or two most important positive categories.
""".strip()


def _unique_valid(values, allowed):
    return list(dict.fromkeys(value for value in values if value in allowed))


def _llm_analysis(message: str) -> dict:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        instructions=SYSTEM_INSTRUCTIONS,
        input=message,
        max_output_tokens=220,
        text={
            "format": {
                "type": "json_schema",
                "name": "perfume_preference",
                "strict": True,
                "schema": LLM_RESPONSE_SCHEMA,
            }
        },
    )
    parsed = json.loads(response.output_text)

    selected_categories = _unique_valid(
        parsed["selected_categories"], SELECTED_CATEGORY_IDS
    )
    avoid_categories = _unique_valid(parsed["avoid_categories"], AVOID_CATEGORY_IDS)
    selected_categories = [
        category for category in selected_categories if category not in avoid_categories
    ] or ["clean"]
    focus_categories = _unique_valid(parsed["focus_categories"], selected_categories)

    return {
        "analysis_source": "openai",
        "selected_categories": selected_categories,
        "avoid_categories": avoid_categories,
        "focus_categories": focus_categories or selected_categories[:1],
        "selected_scores": {},
        "avoid_scores": {},
        "assistant_message": _build_assistant_message(
            selected_categories,
            focus_categories or selected_categories[:1],
        ),
    }


def analyze_chat_message(message: str) -> dict:
    """Use OpenAI only when enabled, otherwise keep the free local analyzer."""
    llm_enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
    has_api_key = bool(os.getenv("OPENAI_API_KEY"))

    if not llm_enabled or not has_api_key:
        return _rule_tfidf_analysis(message)

    try:
        return _llm_analysis(message)
    except Exception:
        logger.exception("OpenAI preference analysis failed; using rule/TF-IDF fallback")
        return _rule_tfidf_analysis(message, analysis_source="rule_tfidf_fallback")
