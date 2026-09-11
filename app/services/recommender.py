from pathlib import Path
from collections import Counter
import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.note_normalizer import normalize_note_text, normalize_note_token

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_PATH = DATA_DIR / "perfumes.csv"
KOREAN_MARKET_DATA_PATH = DATA_DIR / "korean_market_perfumes.csv"
DESCRIPTION_KO_PATH = DATA_DIR / "perfume_descriptions_ko.csv"
MAX_AUTO_KEYWORDS_PER_CATEGORY = 80


CATEGORY_KEYWORDS = {
    "date": ["romantic", "sweet", "soft", "floral"],
    "school_work": ["clean", "fresh", "light", "subtle"],
    "summer": ["citrus", "fresh", "aquatic", "green"],
    "winter": ["warm", "vanilla", "amber", "woody"],
    "clean": ["clean", "soap", "musk", "powdery"],
    "sweet": ["sweet", "vanilla", "fruity", "gourmand"],
    "elegant": ["elegant", "floral", "rose", "jasmine"],
    "floral": ["rose", "jasmine", "peony", "tuberose"],
    "citrus": ["bergamot", "lemon", "orange", "grapefruit"],
    "woody": ["sandalwood", "cedar", "vetiver"],
    "musk": ["musk", "musky", "white musk"],
    "oriental": ["amber", "vanilla", "incense", "resin", "labdanum", "spice"],
    "aquatic": ["aquatic", "marine", "water", "sea", "ocean"],
    "green": ["green", "leaf", "leaves", "grass", "herbal", "mint"],
    "spicy": ["spicy", "pepper", "cinnamon", "clove", "cardamom"],
    "powdery": ["powdery", "powder", "iris", "violet"],
    "gourmand": ["gourmand", "vanilla", "caramel", "chocolate", "honey", "almond"],
    "fresh": ["fresh", "clean", "citrus", "bergamot", "green", "light"],
    "earthy": ["earthy", "patchouli", "oakmoss", "moss", "soil", "vetiver"]
}

AUTO_CATEGORY_SEEDS = {
    "date": [
        "rose", "jasmine", "vanilla", "musk", "sweet", "floral", "peony",
        "gardenia", "tuberose", "amber",
    ],
    "school_work": [
        "clean", "fresh", "musk", "tea", "citrus", "bergamot", "lemon",
        "green", "soap", "aldehyde", "cotton",
    ],
    "summer": [
        "citrus", "bergamot", "lemon", "orange", "grapefruit", "lime",
        "mandarin", "yuzu", "aquatic", "marine", "water", "green", "mint",
    ],
    "winter": [
        "amber", "vanilla", "benzoin", "tonka", "cinnamon", "incense",
        "sandalwood", "cedar", "oud", "labdanum", "resin",
    ],
    "clean": [
        "clean", "musk", "white musk", "soap", "powder", "aldehyde",
        "iris", "violet", "cotton", "linen", "tea",
    ],
    "sweet": [
        "sweet", "vanilla", "tonka", "caramel", "honey", "almond",
        "praline", "chocolate", "cacao", "coconut", "sugar", "coffee",
        "gourmand",
    ],
    "elegant": [
        "rose", "jasmine", "iris", "violet", "osmanthus", "magnolia",
        "sandalwood", "musk", "amber", "floral", "powder",
    ],
    "floral": [
        "rose", "jasmine", "tuberose", "violet", "iris", "geranium",
        "orange blossom", "neroli", "ylang", "magnolia", "gardenia",
        "peony", "lily", "osmanthus", "flower", "floral",
    ],
    "citrus": [
        "bergamot", "lemon", "grapefruit", "orange", "mandarin", "lime",
        "yuzu", "tangerine", "citron", "petitgrain", "citrus",
    ],
    "woody": [
        "sandalwood", "cedar", "cedarwood", "vetiver", "oud", "agarwood",
        "guaiac", "oakmoss", "patchouli", "wood", "woody",
    ],
}

AVOID_KEYWORDS = {
    "powdery": ["powdery", "powder", "iris", "violet"],
    "musk": ["musk", "musky", "white musk"],
    "woody": ["woody", "wood", "sandalwood", "cedar", "vetiver", "oud"],
    "spicy": ["spicy", "pepper", "cinnamon", "clove"],
    "sweet": ["sweet", "vanilla", "caramel", "gourmand"],
    "oriental": ["amber", "incense", "resin", "labdanum", "oriental"],
    "aquatic": ["aquatic", "marine", "water", "sea", "ocean"],
    "green": ["green", "leaf", "leaves", "grass", "herbal", "mint"],
    "gourmand": ["gourmand", "vanilla", "caramel", "chocolate", "honey", "almond"],
    "fresh": ["fresh", "clean", "citrus", "bergamot", "green", "light"],
    "earthy": ["earthy", "patchouli", "oakmoss", "moss", "soil", "vetiver"],
}


def normalize_note(note):
    return normalize_note_token(note)


def note_matches_seed(note, seed):
    if " " in seed:
        return seed in note

    pattern = rf"\b{re.escape(seed)}\b"
    return re.search(pattern, note) is not None


def extract_note_counts(notes_series):
    notes = []

    for value in notes_series.fillna("").astype(str):
        for part in value.replace(";", ",").split(","):
            note = normalize_note(part)
            if note:
                notes.append(note)

    return Counter(notes)


def build_auto_category_keywords(df):
    note_counts = extract_note_counts(df["Notes"])
    auto_keywords = {}

    for category, base_keywords in CATEGORY_KEYWORDS.items():
        seeds = AUTO_CATEGORY_SEEDS.get(category, [])
        matched_notes = []

        for note, _ in note_counts.most_common():
            if any(note_matches_seed(note, seed) for seed in seeds):
                matched_notes.append(note)

        merged_keywords = list(
            dict.fromkeys(base_keywords + matched_notes[:MAX_AUTO_KEYWORDS_PER_CATEGORY])
        )
        auto_keywords[category] = merged_keywords

    return auto_keywords


def load_perfume_data():
    base_df = pd.read_csv(DATA_PATH, encoding="latin1")

    required_columns = ["Name", "Brand", "Description", "Notes", "Image URL"]
    missing_columns = [column for column in required_columns if column not in base_df.columns]

    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")

    for column in required_columns:
        base_df[column] = base_df[column].fillna("")

    # The original CSV keeps its IDs forever.  Existing likes/reviews therefore
    # stay connected even when a Korean-market catalog is appended later.
    base_df["perfume_id"] = base_df.index + 1
    base_df["catalog_key"] = "luckyscent:" + base_df["perfume_id"].astype(str)
    base_df["catalog_source"] = "kaggle_luckyscent"
    base_df["Description KR"] = ""

    catalog_frames = [base_df]
    if KOREAN_MARKET_DATA_PATH.exists():
        korean_df = pd.read_csv(KOREAN_MARKET_DATA_PATH, encoding="utf-8")
        korean_missing = [
            column for column in required_columns if column not in korean_df.columns
        ]
        if korean_missing:
            raise ValueError(
                f"Missing Korean-market catalog columns: {korean_missing}"
            )

        for column in required_columns:
            korean_df[column] = korean_df[column].fillna("")

        korean_df["perfume_id"] = range(
            len(base_df) + 1,
            len(base_df) + len(korean_df) + 1,
        )
        korean_df["catalog_key"] = (
            "official:"
            + korean_df["Brand"].map(_slugify_catalog_part)
            + ":"
            + korean_df["Name"].map(_slugify_catalog_part)
        )
        korean_df["catalog_source"] = korean_df.get("Source", "official").fillna(
            "official"
        )
        korean_df["Description KR"] = korean_df.get("Summary KR", "").fillna("")
        catalog_frames.append(korean_df)

    # Different product catalogs are unioned vertically.  Localized description
    # text describes the same product, so it is joined by catalog_key below.
    df = pd.concat(catalog_frames, ignore_index=True, sort=False)

    if DESCRIPTION_KO_PATH.exists():
        descriptions_ko = pd.read_csv(DESCRIPTION_KO_PATH, encoding="utf-8")
        expected_translation_columns = {"catalog_key", "description_ko"}
        if expected_translation_columns.issubset(descriptions_ko.columns):
            df = df.merge(
                descriptions_ko[["catalog_key", "description_ko"]]
                .drop_duplicates(subset=["catalog_key"], keep="last"),
                on="catalog_key",
                how="left",
            )
            df["Description KR"] = df["description_ko"].fillna(df["Description KR"])
            df = df.drop(columns=["description_ko"])

    # Display text remains intact.  Only comparison text is normalized.
    df["notes_text"] = df["Notes"].map(normalize_note_text)
    df["desc_text"] = df["Description"].map(normalize_note_text)
    df["brand_text"] = df["Brand"].map(normalize_note_text)

    return df


def _slugify_catalog_part(value: object) -> str:
    normalized = normalize_note_text(value)
    return re.sub(r"[^0-9a-z]+", "-", normalized).strip("-") or "unknown"


def build_user_query(selected_categories, category_keywords=None):
    if category_keywords is None:
        category_keywords = CATEGORY_KEYWORDS

    keywords = []

    for category in selected_categories:
        keywords.extend(category_keywords.get(category, []))

    return " ".join(keywords)


class PerfumeRecommender:
    def __init__(self):
        self.df = load_perfume_data()
        self.category_keywords = build_auto_category_keywords(self.df)

        self.notes_vectorizer = TfidfVectorizer()
        self.desc_vectorizer = TfidfVectorizer()
        self.brand_vectorizer = TfidfVectorizer()

        self.notes_matrix = self.notes_vectorizer.fit_transform(self.df["notes_text"])
        self.desc_matrix = self.desc_vectorizer.fit_transform(self.df["desc_text"])
        self.brand_matrix = self.brand_vectorizer.fit_transform(self.df["brand_text"])

    def recommend(
        self,
        selected_categories,
        avoid_categories=None,
        focus_categories=None,
        top_n=5,
    ):
        if avoid_categories is None:
            avoid_categories = []

        if focus_categories is None:
            focus_categories = []

        query = build_user_query(selected_categories, self.category_keywords)

        query_notes_vec = self.notes_vectorizer.transform([query])
        query_desc_vec = self.desc_vectorizer.transform([query])
        query_brand_vec = self.brand_vectorizer.transform([query])

        notes_sim = cosine_similarity(query_notes_vec, self.notes_matrix).flatten()
        desc_sim = cosine_similarity(query_desc_vec, self.desc_matrix).flatten()
        brand_sim = cosine_similarity(query_brand_vec, self.brand_matrix).flatten()

        base_score = (
            0.70 * notes_sim +
            0.25 * desc_sim +
            0.05 * brand_sim
        )

        final_score = base_score

        if focus_categories:
            focus_query = build_user_query(focus_categories, self.category_keywords)
            focus_notes_vec = self.notes_vectorizer.transform([focus_query])
            focus_desc_vec = self.desc_vectorizer.transform([focus_query])

            focus_notes_sim = cosine_similarity(focus_notes_vec, self.notes_matrix).flatten()
            focus_desc_sim = cosine_similarity(focus_desc_vec, self.desc_matrix).flatten()
            focus_score = (0.80 * focus_notes_sim) + (0.20 * focus_desc_sim)

            final_score = (0.70 * base_score) + (0.30 * focus_score)

        avoid_terms = []
        for category in avoid_categories:
            avoid_terms.extend(AVOID_KEYWORDS.get(category, []))

        if avoid_terms:
            avoid_pattern = "|".join(avoid_terms)
            avoid_mask = (
                self.df["notes_text"].str.contains(avoid_pattern, case=False, regex=True) |
                self.df["desc_text"].str.contains(avoid_pattern, case=False, regex=True)
            )

            final_score = final_score - (0.10 * avoid_mask.astype(float))

        top_indices = final_score.argsort()[::-1][:top_n]

        results = self.df.iloc[top_indices][
            [
                "perfume_id",
                "catalog_key",
                "Name",
                "Brand",
                "Description",
                "Description KR",
                "Notes",
                "Image URL",
            ]
        ].copy()

        results["score"] = final_score[top_indices]
        return results


if __name__ == "__main__":
    recommender = PerfumeRecommender()

    selected = ["date", "sweet", "floral"]
    avoid = ["woody"]

    focus = ["floral"]
    results = recommender.recommend(
        selected,
        avoid_categories=avoid,
        focus_categories=focus,
        top_n=5,
    )

    print(f"Selected categories: {', '.join(selected)}")
    print(f"Avoid categories: {', '.join(avoid)}")
    print(f"Focus categories: {', '.join(focus)}")

    for _, row in results.iterrows():
        print("=" * 60)
        print(f"Name: {row['Name']}")
        print(f"Brand: {row['Brand']}")
        print(f"Score: {row['score']:.4f}")
        print(f"Notes: {row['Notes']}")
        print(f"Description: {row['Description'][:200]}")
