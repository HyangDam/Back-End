from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "perfumes.csv"


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
}

AVOID_KEYWORDS = {
    "powdery": ["powdery", "powder"],
    "musk": ["musk", "musky"],
    "woody": ["woody", "wood", "sandalwood", "cedar", "vetiver", "oud"],
    "spicy": ["spicy", "pepper", "cinnamon", "clove"],
    "sweet": ["sweet", "vanilla", "caramel", "gourmand"],
}


def load_perfume_data():
    df = pd.read_csv(DATA_PATH, encoding="latin1")

    required_columns = ["Name", "Brand", "Description", "Notes", "Image URL"]
    missing_columns = [column for column in required_columns if column not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")

    for column in required_columns:
        df[column] = df[column].fillna("")

    df["notes_text"] = df["Notes"].str.lower()
    df["desc_text"] = df["Description"].str.lower()
    df["brand_text"] = df["Brand"].str.lower()

    return df


def build_user_query(selected_categories):
    keywords = []

    for category in selected_categories:
        keywords.extend(CATEGORY_KEYWORDS.get(category, []))

    return " ".join(keywords)


class PerfumeRecommender:
    def __init__(self):
        self.df = load_perfume_data()

        self.notes_vectorizer = TfidfVectorizer()
        self.desc_vectorizer = TfidfVectorizer()
        self.brand_vectorizer = TfidfVectorizer()

        self.notes_matrix = self.notes_vectorizer.fit_transform(self.df["notes_text"])
        self.desc_matrix = self.desc_vectorizer.fit_transform(self.df["desc_text"])
        self.brand_matrix = self.brand_vectorizer.fit_transform(self.df["brand_text"])

    def recommend(self, selected_categories, avoid_categories=None, top_n=5):
        if avoid_categories is None:
            avoid_categories = []

        query = build_user_query(selected_categories)

        query_notes_vec = self.notes_vectorizer.transform([query])
        query_desc_vec = self.desc_vectorizer.transform([query])
        query_brand_vec = self.brand_vectorizer.transform([query])

        notes_sim = cosine_similarity(query_notes_vec, self.notes_matrix).flatten()
        desc_sim = cosine_similarity(query_desc_vec, self.desc_matrix).flatten()
        brand_sim = cosine_similarity(query_brand_vec, self.brand_matrix).flatten()

        final_score = (
            0.70 * notes_sim +
            0.25 * desc_sim +
            0.05 * brand_sim
        )

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
            ["Name", "Brand", "Description", "Notes", "Image URL"]
        ].copy()

        results["score"] = final_score[top_indices]
        return results


if __name__ == "__main__":
    recommender = PerfumeRecommender()

    selected = ["date", "sweet", "floral"]
    avoid = ["woody"]

    results = recommender.recommend(selected, avoid_categories=avoid, top_n=5)

    print(f"Selected categories: {', '.join(selected)}")
    print(f"Avoid categories: {', '.join(avoid)}")

    for _, row in results.iterrows():
        print("=" * 60)
        print(f"Name: {row['Name']}")
        print(f"Brand: {row['Brand']}")
        print(f"Score: {row['score']:.4f}")
        print(f"Notes: {row['Notes']}")
        print(f"Description: {row['Description'][:200]}")