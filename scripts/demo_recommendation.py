from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.services.recommender import PerfumeRecommender, build_user_query
from app.services.preference_extractor import extract_preferences_from_text


ONBOARDING_STEPS = [
    {
        "title": "선호하는 향 계열을 선택해주세요.",
        "options": [
            ("floral", "꽃향 계열 (플로럴)", "rose, jasmine, peony, tuberose"),
            ("citrus", "상큼한 과일 껍질 향 (시트러스)", "bergamot, lemon, orange, grapefruit"),
            ("woody", "차분한 나무 향 (우디)", "sandalwood, cedar, vetiver"),
        ],
    },
    {
        "title": "원하는 무드는 무엇인가요?",
        "options": [
            ("clean", "비누처럼 깨끗한 향 (클린)", "clean, soap, musk, powdery"),
            ("sweet", "달콤하고 포근한 향 (스위트)", "sweet, vanilla, fruity, gourmand"),
            ("elegant", "차분하고 고급스러운 향 (엘레강트)", "elegant, floral, rose, jasmine"),
        ],
    },
    {
        "title": "어떤 상황에서 사용할 향수를 찾고 있나요?",
        "options": [
            ("date", "데이트", "romantic, sweet, soft, floral"),
            ("school_work", "학교/출근", "clean, fresh, light, subtle"),
            ("summer", "더운 날 가볍게 쓰는 향 (여름)", "citrus, fresh, aquatic, green"),
            ("winter", "쌀쌀한 날 포근한 향 (겨울)", "warm, vanilla, amber, woody"),
        ],
    },
]

AVOID_OPTIONS = [
    ("none", "없음", "회피 향조를 적용하지 않음"),
    ("powdery", "분가루처럼 텁텁한 향 (파우더리)", "powdery, powder"),
    ("musk", "살냄새처럼 포근한 향 (머스크)", "musk, musky"),
    ("woody", "묵직한 나무·오드 향 (우디/오드)", "woody, wood, sandalwood, cedar, vetiver, oud"),
    ("spicy", "향신료처럼 자극적인 향 (스파이시)", "spicy, pepper, cinnamon, clove"),
    ("sweet", "과하게 달달한 향", "sweet, vanilla, caramel, gourmand"),
]

FOCUS_OPTIONS = [
    ("none", "특별히 없음", "온보딩 전체 응답을 같은 비중으로 반영"),
    ("floral", "꽃향 느낌을 가장 중요하게 (플로럴)", "rose, jasmine, peony, tuberose"),
    ("citrus", "상큼한 느낌을 가장 중요하게 (시트러스)", "bergamot, lemon, orange, grapefruit"),
    ("woody", "차분한 나무 향을 가장 중요하게 (우디)", "sandalwood, cedar, vetiver"),
    ("clean", "비누처럼 깨끗한 분위기를 가장 중요하게 (클린)", "clean, soap, musk, powdery"),
    ("sweet", "달콤하고 포근한 분위기를 가장 중요하게 (스위트)", "sweet, vanilla, fruity, gourmand"),
    ("elegant", "차분하고 고급스러운 분위기를 가장 중요하게 (엘레강트)", "elegant, floral, rose, jasmine"),
    ("date", "데이트 상황을 가장 중요하게", "romantic, sweet, soft, floral"),
    ("school_work", "학교/출근 상황을 가장 중요하게", "clean, fresh, light, subtle"),
    ("summer", "더운 날 어울리는 산뜻함을 가장 중요하게 (여름)", "citrus, fresh, aquatic, green"),
    ("winter", "쌀쌀한 날 어울리는 포근함을 가장 중요하게 (겨울)", "warm, vanilla, amber, woody"),
]


def choose_one(step):
    print()
    print(step["title"])

    for index, (_, label, keywords) in enumerate(step["options"], start=1):
        print(f"{index}. {label} ({keywords})")

    while True:
        choice = input("번호를 선택하세요: ").strip()

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(step["options"]):
                selected_id, label, _ = step["options"][index]
                print(f"선택: {label}")
                return selected_id

        print("올바른 번호를 다시 입력해주세요.")


def choose_focus_categories():
    print()
    print("마지막으로 오늘 추천에서 가장 중요하게 볼 분위기/카테고리를 선택해주세요.")

    for index, (_, label, keywords) in enumerate(FOCUS_OPTIONS, start=1):
        print(f"{index}. {label} ({keywords})")

    while True:
        choice = input("번호를 선택하세요: ").strip()

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(FOCUS_OPTIONS):
                selected_id, label, _ = FOCUS_OPTIONS[index]

                if selected_id == "none":
                    print("선택: 특별히 없음")
                    return []

                print(f"선택: {label}")
                return [selected_id]

        print("올바른 번호를 다시 입력해주세요.")


def choose_avoid_categories():
    print()
    print("피하고 싶은 향 계열이 있나요? 여러 개 선택 시 쉼표로 입력하세요.")

    for index, (_, label, keywords) in enumerate(AVOID_OPTIONS, start=1):
        print(f"{index}. {label} ({keywords})")

    while True:
        raw_choice = input("번호를 선택하세요. 예: 1 또는 3,4: ").strip()

        if not raw_choice:
            print("올바른 번호를 다시 입력해주세요.")
            continue

        choices = [value.strip() for value in raw_choice.split(",")]

        if not all(choice.isdigit() for choice in choices):
            print("숫자와 쉼표만 입력해주세요.")
            continue

        indices = [int(choice) - 1 for choice in choices]

        if not all(0 <= index < len(AVOID_OPTIONS) for index in indices):
            print("선택 가능한 번호 범위 안에서 입력해주세요.")
            continue

        selected = [AVOID_OPTIONS[index][0] for index in indices]

        if "none" in selected:
            return []

        return selected


def choose_input_mode():
    print()
    print("추천 입력 방식을 선택해주세요.")
    print("1. 자연어로 취향 입력")
    print("2. 버튼형 온보딩 선택")

    while True:
        choice = input("번호를 선택하세요: ").strip()

        if choice in {"1", "2"}:
            return choice

        print("올바른 번호를 다시 입력해주세요.")


def collect_preferences_from_text():
    print()
    print("원하는 향을 문장으로 입력해주세요.")
    print("예: 데이트할 때 쓰기 좋은 달달한 플로럴 향이 좋고, 우디한 향은 피하고 싶어요.")
    user_text = input("입력: ").strip()

    preferences = extract_preferences_from_text(user_text)
    selected_categories = preferences["selected_categories"]
    avoid_categories = preferences["avoid_categories"]

    if not selected_categories:
        print("취향을 충분히 추출하지 못해 기본값으로 clean을 적용합니다.")
        selected_categories = ["clean"]

    print()
    print("자연어 입력에서 추출한 카테고리")
    print(f"선호: {', '.join(selected_categories)}")
    print(f"회피: {', '.join(avoid_categories) if avoid_categories else '없음'}")

    return selected_categories, avoid_categories


def collect_preferences_from_buttons():
    selected_categories = [choose_one(step) for step in ONBOARDING_STEPS]
    avoid_categories = choose_avoid_categories()
    return selected_categories, avoid_categories


def print_onboarding_summary(selected_categories, avoid_categories, focus_categories, query):
    print()
    print("=" * 70)
    print("온보딩 응답 요약")
    print(f"선호 카테고리: {', '.join(selected_categories)}")
    print(f"회피 향조: {', '.join(avoid_categories) if avoid_categories else '없음'}")
    print(f"중점 반영: {', '.join(focus_categories) if focus_categories else '없음'}")
    print("선택한 취향을 기반으로 관련 향조 키워드를 자동 확장했습니다.")
    print("=" * 70)


def print_results(selected_categories, avoid_categories, focus_categories, results):
    print()
    print("=" * 70)
    print("추천 결과 Top 5")
    print(f"Selected: {', '.join(selected_categories)}")
    print(f"Avoid: {', '.join(avoid_categories) if avoid_categories else 'none'}")
    print(f"Focus: {', '.join(focus_categories) if focus_categories else 'none'}")
    print("=" * 70)

    for rank, (_, row) in enumerate(results.iterrows(), start=1):
        notes = str(row["Notes"])
        short_notes = notes[:120] + "..." if len(notes) > 120 else notes

        print(f"{rank}. {row['Name']} / {row['Brand']}")
        print(f"   Score: {row['score']:.4f}")
        print(f"   주요 노트: {short_notes}")
        if focus_categories:
            print("   추천 이유: 선택한 취향·무드·상황 중 마지막 중점 카테고리를 더 강하게 반영했습니다.")
        else:
            print("   추천 이유: 선택한 취향·무드·상황 키워드와 유사도가 높은 향수입니다.")
        print()


def main():
    print("HyangDam 온보딩 기반 향수 추천 테스트")
    print("사용자 입력을 카테고리로 변환한 뒤 TF-IDF 유사도 기반 추천 결과를 출력합니다.")

    recommender = PerfumeRecommender()
    input_mode = choose_input_mode()

    if input_mode == "1":
        selected_categories, avoid_categories = collect_preferences_from_text()
    else:
        selected_categories, avoid_categories = collect_preferences_from_buttons()

    focus_categories = choose_focus_categories()
    query = build_user_query(selected_categories + focus_categories, recommender.category_keywords)

    print_onboarding_summary(selected_categories, avoid_categories, focus_categories, query)
    results = recommender.recommend(
        selected_categories=selected_categories,
        avoid_categories=avoid_categories,
        focus_categories=focus_categories,
        top_n=5,
    )

    print_results(selected_categories, avoid_categories, focus_categories, results)


if __name__ == "__main__":
    main()
