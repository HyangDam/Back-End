import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

NEGATIVE_MARKERS = [
    "싫", "피하", "제외", "빼고", "말고", "안 좋아", "안좋아",
    "원하지", "별로", "부담", "너무", "과한", "과하게", "강한", "강하거나", "독한",
]

CATEGORY_RULES = {
    "floral": ["플로럴", "꽃", "꽃향", "장미", "로즈", "자스민", "rose", "jasmine", "floral"],
    "citrus": ["시트러스", "상큼", "산뜻", "레몬", "오렌지", "베르가못", "자몽", "citrus", "lemon", "bergamot"],
    "woody": ["우디", "나무", "오드", "샌달우드", "시더", "oud", "wood", "woody", "sandalwood", "cedar"],
    "clean": [
        "깨끗", "비누", "클린", "깔끔", "머스크", "파우더", "clean", "soap", "musk", "powder",
        "처음", "입문", "초보", "은은", "무난", "가벼운", "가볍", "부담스럽지", "부담 없는",
        "부담없", "강하지", "강하지 않은", "순한", "튀지", "데일리", "편안", "자연스러운",
    ],
    "sweet": ["달달", "달콤", "바닐라", "꿀", "카라멜", "구르망", "sweet", "vanilla", "caramel", "gourmand"],
    "elegant": [
        "우아", "고급", "차분", "성숙", "격식", "중요한 자리", "공식", "포멀", "행사", "모임",
        "차려입", "차리는 자리", "격식을 차", "formal", "elegant", "iris",
    ],
    "date": ["데이트", "소개팅", "로맨틱", "romantic", "date"],
    "school_work": ["학교", "출근", "회사", "수업", "사무실", "데일리", "직장", "회의", "면접", "office", "work"],
    "summer": ["여름", "더운", "습한", "휴양", "바다", "summer", "fresh"],
    "winter": ["겨울", "쌀쌀", "추운", "포근", "따뜻", "warm", "winter", "amber"],
}

AVOID_RULES = {
    "powdery": ["파우더", "파우더리", "powder", "powdery"],
    "musk": ["머스크", "musk", "musky"],
    "woody": ["우디", "오드", "나무", "샌달우드", "시더", "oud", "wood", "woody", "sandalwood", "cedar"],
    "spicy": ["스파이시", "매운", "향신료", "후추", "자극", "강한", "강하거나", "독한", "spicy", "pepper", "cinnamon", "clove"],
    "sweet": ["달달", "달콤", "바닐라", "카라멜", "구르망", "과한", "과하게", "sweet", "vanilla", "caramel", "gourmand"],
}

CATEGORY_DESCRIPTIONS = {
    "floral": "꽃향 플로럴 장미 자스민 튜베로즈처럼 부드럽고 여성스럽고 화사한 향을 좋아하는 취향",
    "citrus": "상큼하고 산뜻한 레몬 오렌지 베르가못 자몽 같은 가볍고 시원한 향을 원하는 취향",
    "woody": "나무 숲 우디 샌달우드 시더 베티버 오드처럼 차분하고 깊이 있는 향을 좋아하는 취향",
    "clean": "향수를 처음 쓰는 사람에게 좋은 부담스럽지 않고 은은하고 깨끗하고 무난한 비누향 클린 향",
    "sweet": "달달하고 포근한 바닐라 캐러멜 꿀 디저트 구르망 계열의 향을 좋아하는 취향",
    "elegant": "격식 있는 자리 중요한 자리 공식적인 모임 차려입는 상황에 어울리는 우아하고 고급스러운 향",
    "date": "데이트 소개팅 로맨틱한 상황에서 좋은 부드럽고 달콤하고 호감 가는 향",
    "school_work": "학교 출근 회사 사무실 회의 면접처럼 일상에서 부담 없이 쓰기 좋은 깔끔한 향",
    "summer": "여름 더운 날 습한 날 휴양지 바다처럼 산뜻하고 시원하고 가벼운 향",
    "winter": "겨울 쌀쌀한 날 포근하고 따뜻하고 안정적인 앰버 바닐라 우디 계열 향",
}

AVOID_DESCRIPTIONS = {
    "powdery": "파우더리하고 분가루 같은 텁텁한 향을 피하고 싶은 경우",
    "musk": "머스크 향이 답답하거나 무겁게 느껴져 피하고 싶은 경우",
    "woody": "우디 오드 나무 향이 너무 무겁거나 성숙해서 피하고 싶은 경우",
    "spicy": "강하고 자극적이고 매운 향신료 같은 향을 피하고 싶은 경우",
    "sweet": "너무 달달하고 과한 바닐라 캐러멜 구르망 향을 피하고 싶은 경우",
}

PHRASE_BOOSTS = [
    (["처음", "입문", "초보"], ["clean"], []),
    (["부담스럽지", "부담 없는", "부담없", "강하지", "무난", "은은"], ["clean"], ["spicy"]),
    (["너무 강", "강하거나", "독한", "자극적"], ["clean"], ["spicy"]),
    (["격식", "중요한 자리", "공식", "포멀", "차려입", "차리는 자리"], ["elegant"], []),
    (["회사", "출근", "사무실", "회의", "면접"], ["school_work", "clean"], []),
]


def normalize_text(text):
    normalized = str(text).lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    compact = re.sub(r"\s+", "", normalized)
    return normalized, compact


def keyword_matches(text, compact_text, keyword):
    keyword = str(keyword).lower().strip()
    compact_keyword = re.sub(r"\s+", "", keyword)
    return keyword in text or compact_keyword in compact_text


def contains_any(text, compact_text, keywords):
    return any(keyword_matches(text, compact_text, keyword) for keyword in keywords)


def has_negative_context(text, compact_text, keywords):
    if contains_any(text, compact_text, ["달지 않은", "달지않은", "너무 달", "과하게 달"]):
        if contains_any(text, compact_text, ["달달", "달콤", "바닐라", "sweet", "vanilla"]):
            return True

    for keyword in keywords:
        keyword = str(keyword).lower().strip()
        start = text.find(keyword)

        while start != -1:
            left = max(0, start - 8)
            right = min(len(text), start + len(keyword) + 8)
            context, compact_context = normalize_text(text[left:right])

            if contains_any(context, compact_context, NEGATIVE_MARKERS):
                return True

            start = text.find(keyword, start + len(keyword))

    return False


def unique_keep_order(values):
    return list(dict.fromkeys(values))


def add_score(scores, category, amount):
    scores[category] = scores.get(category, 0) + amount


def tfidf_description_scores(user_text, descriptions):
    labels = list(descriptions.keys())
    documents = [user_text] + [descriptions[label] for label in labels]

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(documents)
    similarities = cosine_similarity(matrix[0], matrix[1:]).flatten()

    return dict(zip(labels, similarities))


def apply_tfidf_scores(scores, tfidf_scores, threshold=0.08, weight=5.0, top_k=3):
    ranked = sorted(tfidf_scores.items(), key=lambda item: -item[1])[:top_k]

    for category, similarity in ranked:
        if similarity >= threshold:
            add_score(scores, category, similarity * weight)


def extract_preferences_from_text(user_text):
    text, compact_text = normalize_text(user_text)
    selected_scores = {}
    avoid_scores = {}

    for triggers, selected_categories, avoid_categories in PHRASE_BOOSTS:
        if contains_any(text, compact_text, triggers):
            for category in selected_categories:
                add_score(selected_scores, category, 2)
            for category in avoid_categories:
                add_score(avoid_scores, category, 2)

    for category, keywords in CATEGORY_RULES.items():
        matched_count = sum(1 for keyword in keywords if keyword_matches(text, compact_text, keyword))
        if matched_count:
            if category in AVOID_RULES and has_negative_context(text, compact_text, keywords):
                add_score(avoid_scores, category, matched_count)
            else:
                add_score(selected_scores, category, matched_count)

    for category, keywords in AVOID_RULES.items():
        matched_count = sum(1 for keyword in keywords if keyword_matches(text, compact_text, keyword))
        if matched_count and has_negative_context(text, compact_text, keywords):
            add_score(avoid_scores, category, matched_count)

    selected_tfidf_scores = tfidf_description_scores(user_text, CATEGORY_DESCRIPTIONS)
    apply_tfidf_scores(selected_scores, selected_tfidf_scores, threshold=0.12, weight=5.0, top_k=3)

    if contains_any(text, compact_text, NEGATIVE_MARKERS):
        avoid_tfidf_scores = tfidf_description_scores(user_text, AVOID_DESCRIPTIONS)
        apply_tfidf_scores(avoid_scores, avoid_tfidf_scores, threshold=0.18, weight=4.0, top_k=2)

    selected_categories = [
        category for category, _ in sorted(selected_scores.items(), key=lambda item: -item[1])
    ]
    avoid_categories = [
        category for category, _ in sorted(avoid_scores.items(), key=lambda item: -item[1])
    ]

    selected_categories = [category for category in selected_categories if category not in avoid_categories]

    return {
        "selected_categories": unique_keep_order(selected_categories),
        "avoid_categories": unique_keep_order(avoid_categories),
        "selected_scores": selected_scores,
        "avoid_scores": avoid_scores,
        "selected_tfidf_scores": selected_tfidf_scores,
    }
