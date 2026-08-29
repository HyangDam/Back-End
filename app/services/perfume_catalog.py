from functools import lru_cache

import pandas as pd

from app.services.recommender import load_perfume_data


@lru_cache(maxsize=1)
def get_perfume_data():
    return load_perfume_data()


def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value)


def row_to_perfume(row_index, row, include_description=False):
    perfume = {
        "perfume_id": int(row_index) + 1,
        "name": clean_value(row["Name"]),
        "brand": clean_value(row["Brand"]),
        "notes": clean_value(row["Notes"]),
        "image_url": clean_value(row["Image URL"]),
    }

    if include_description:
        perfume["description"] = clean_value(row["Description"])

    return perfume


def get_perfume_or_none(perfume_id: int):
    df = get_perfume_data()
    row_index = perfume_id - 1

    if row_index < 0 or row_index >= len(df):
        return None

    row = df.iloc[row_index]
    return row_to_perfume(row_index, row, include_description=True)


def search_perfumes_from_csv(keyword: str = "", limit: int = 10):
    df = get_perfume_data()
    data = df.copy()

    if keyword:
        keyword_lower = keyword.lower()
        mask = (
            data["Name"].astype(str).str.lower().str.contains(keyword_lower, na=False, regex=False)
            | data["Brand"].astype(str).str.lower().str.contains(keyword_lower, na=False, regex=False)
        )
        data = data[mask]

    return [
        row_to_perfume(index, row)
        for index, row in data.head(limit).iterrows()
    ]