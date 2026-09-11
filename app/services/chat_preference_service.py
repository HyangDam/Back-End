import json
import logging
import os

from openai import OpenAI

from app.services.preference_extractor import extract_preferences_from_text
from app.services.recommender import AVOID_KEYWORDS, CATEGORY_KEYWORDS

logger = logging.getLogger(__name__)


CATEGORY_LABELS = {
    "clean": "깨끗하고 부담 없는 느낌",
    "sweet": "달콤하고 포근한 느낌",
    "elegant": "차분하고 격식 있는 느낌",
    "floral": "꽃향 계열",
    "citrus": "상큼한 시트러스 계열",
    "woody": "차분한 나무 향 계열",
    "spicy": "자극적인 향신료 계열",
    "musk": "머스크 계열",
    "powdery": "파우더리 계열",
    "gourmand": "디저트 같은 구르망 계열",
    "aquatic": "시원한 아쿠아틱 계열",
    "green": "싱그러운 그린 계열",
    "fresh": "상쾌한 프레시 계열",
    "oriental": "따뜻한 오리엔탈 계열",
    "earthy": "흙내음의 어시 계열",
    "date": "데이트/약속 상황",
    "school_work": "학교/출근 상황",
    "summer": "여름처럼 산뜻한 분위기",
    "winter": "겨울처럼 포근한 분위기",
}


def _build_assistant_message(selected_categories, avoid_categories, summary=None):
    if summary:
        return str(summary).strip()[:220]

    selected_labels = [
        CATEGORY_LABELS.get(category, category) for category in selected_categories[:2]
    ]
    avoid_labels = [
        CATEGORY_LABELS.get(category, category) for category in avoid_categories[:2]
    ]

    assistant_message = f"{', '.join(selected_labels)}을 중심으로 추천했어요."
    if avoid_labels:
        assistant_message += f" {'; '.join(avoid_labels)}은 추천 점수에서 낮췄어요."
    return assistant_message


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
            selected_categories, avoid_categories
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
        "preference_summary": {"type": "string", "maxLength": 220},
    },
    "required": [
        "selected_categories",
        "avoid_categories",
        "focus_categories",
        "preference_summary",
    ],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTIONS = """
You are a Korean perfume-preference analyzer for HyangDam.
Extract the user's intent into only the supplied category IDs.
Do not recommend a product, invent a category, claim that a scent is certain,
or write more than one short Korean sentence in preference_summary.
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
            avoid_categories,
            parsed.get("preference_summary"),
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
