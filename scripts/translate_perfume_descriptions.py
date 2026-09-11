"""Create a resumable Korean-description sidecar for the Kaggle perfume CSV.

Examples:
    python scripts/translate_perfume_descriptions.py --limit 5
    python scripts/translate_perfume_descriptions.py --all

The script only translates the existing Description column.  It never alters
the source CSV or Notes column, and writes each completed row immediately so a
later run continues where the previous one stopped.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from app.services.recommender import load_perfume_data  # noqa: E402


OUTPUT_PATH = ROOT_DIR / "app" / "data" / "perfume_descriptions_ko.csv"
OUTPUT_FIELDS = [
    "catalog_key",
    "description_ko",
    "source_description_hash",
    "translated_at",
    "model",
]
SYSTEM_INSTRUCTIONS = """
Translate the supplied English perfume description into natural Korean.
Return only the Korean translation with no title, markdown, commentary, or
added facts. Preserve perfume-note names where a Korean transliteration is
commonly used. Do not translate the Notes field because it is not supplied.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--limit", type=int, help="Number of untranslated rows to process")
    scope.add_argument("--all", action="store_true", help="Translate all remaining rows")
    return parser.parse_args()


def load_completed_keys() -> set[str]:
    if not OUTPUT_PATH.exists():
        return set()

    with OUTPUT_PATH.open("r", encoding="utf-8", newline="") as file:
        return {
            row["catalog_key"]
            for row in csv.DictReader(file)
            if row.get("catalog_key") and row.get("description_ko")
        }


def ensure_output_file() -> None:
    if OUTPUT_PATH.exists():
        return

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        csv.DictWriter(file, fieldnames=OUTPUT_FIELDS).writeheader()


def translate_description(client: OpenAI, model: str, description: str) -> str:
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=description,
        max_output_tokens=1800,
    )
    return response.output_text.strip()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required. Add it to .env before running.")

    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    completed_keys = load_completed_keys()
    data = load_perfume_data()
    original_rows = data[data["catalog_source"] == "kaggle_luckyscent"]
    remaining = original_rows[
        ~original_rows["catalog_key"].isin(completed_keys)
        & original_rows["Description"].astype(str).str.strip().ne("")
    ]
    if not args.all:
        if args.limit <= 0:
            raise ValueError("--limit must be at least 1")
        remaining = remaining.head(args.limit)

    if remaining.empty:
        print("No untranslated Kaggle descriptions remain.")
        return

    ensure_output_file()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    total = len(remaining)

    with OUTPUT_PATH.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        for index, (_, row) in enumerate(remaining.iterrows(), start=1):
            description = str(row["Description"]).strip()
            try:
                translated = translate_description(client, model, description)
            except Exception as exc:
                print(f"[{index}/{total}] Failed: {row['catalog_key']} ({exc})")
                continue

            if not translated:
                print(f"[{index}/{total}] Empty response: {row['catalog_key']}")
                continue

            writer.writerow(
                {
                    "catalog_key": row["catalog_key"],
                    "description_ko": translated,
                    "source_description_hash": hashlib.sha256(
                        description.encode("utf-8")
                    ).hexdigest(),
                    "translated_at": datetime.now(timezone.utc).isoformat(),
                    "model": model,
                }
            )
            file.flush()
            print(f"[{index}/{total}] Saved: {row['catalog_key']}")


if __name__ == "__main__":
    main()
