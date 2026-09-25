"""Create resumable Korean display names for the perfume catalog.

Examples:
    python scripts/translate_perfume_names_brands.py --limit 25
    python scripts/translate_perfume_names_brands.py --all

The source CSV stays untouched. Generated display values are stored by
``catalog_key`` so the API can show and search Korean names while retaining
the original product data for recommendation matching.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from app.services.recommender import load_perfume_data  # noqa: E402


OUTPUT_PATH = ROOT_DIR / "app" / "data" / "perfume_names_brands_ko.csv"
OUTPUT_FIELDS = ["catalog_key", "name_ko", "brand_ko", "translated_at", "model"]
BATCH_SIZE = 25
REQUEST_ATTEMPTS = 3
MAX_CONSECUTIVE_FAILURES = 3
SYSTEM_INSTRUCTIONS = """
You localize perfume brands and product names for a Korean perfume-service UI.
Return exactly one JSON array. Each item must have catalog_key, name_ko, and
brand_ko. Keep catalog_key unchanged. Write commonly used Korean brand names
or natural Hangul transliterations. Translate concentration terms naturally,
for example Eau de Parfum -> 오 드 퍼퓸 and Eau de Toilette -> 오 드 뚜왈렛.
Do not invent fragrance details, remove edition names, or add commentary.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--limit", type=int, help="Number of untranslated products")
    scope.add_argument("--all", action="store_true", help="Translate every remaining product")
    return parser.parse_args()


def load_completed_keys() -> set[str]:
    if not OUTPUT_PATH.exists():
        return set()
    with OUTPUT_PATH.open("r", encoding="utf-8", newline="") as file:
        return {
            row["catalog_key"]
            for row in csv.DictReader(file)
            if row.get("catalog_key")
            and row.get("name_ko")
            and row.get("brand_ko")
        }


def ensure_output_file() -> None:
    if OUTPUT_PATH.exists():
        return
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        csv.DictWriter(file, fieldnames=OUTPUT_FIELDS).writeheader()


def translate_batch(
    client: OpenAI, model: str, products: list[dict[str, str]]
) -> list[dict[str, str]]:
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=json.dumps(products, ensure_ascii=False),
        max_output_tokens=3000,
    )
    text = response.output_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()
    translated = json.loads(text)
    if not isinstance(translated, list):
        raise ValueError("Translation response was not a JSON array.")
    return [
        item
        for item in translated
        if isinstance(item, dict)
        and str(item.get("catalog_key", "")).strip()
        and str(item.get("name_ko", "")).strip()
        and str(item.get("brand_ko", "")).strip()
    ]


def translate_batch_with_retry(
    client: OpenAI, model: str, products: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Retry temporary API and network failures without skipping a batch."""
    last_error: Exception | None = None
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            return translate_batch(client, model, products)
        except Exception as exc:
            last_error = exc
            if attempt == REQUEST_ATTEMPTS:
                break
            wait_seconds = 2**attempt
            print(
                f"Temporary error ({exc}). Retrying in {wait_seconds}s "
                f"[{attempt}/{REQUEST_ATTEMPTS}]...",
                flush=True,
            )
            time.sleep(wait_seconds)
    raise RuntimeError(f"Request failed after {REQUEST_ATTEMPTS} attempts: {last_error}")


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required. Add it to .env before running.")

    completed = load_completed_keys()
    data = load_perfume_data()
    # Existing official Korean-market labels are already curated. Translate the
    # English-only source rows, then leave curated labels as the API priority.
    remaining = data[
        ~data["catalog_key"].isin(completed)
        & data["Name KR"].fillna("").astype(str).str.strip().eq("")
    ][["catalog_key", "Name", "Brand"]]
    if not args.all:
        if args.limit <= 0:
            raise ValueError("--limit must be at least 1")
        remaining = remaining.head(args.limit)
    if remaining.empty:
        print("No English-only product names remain.")
        return

    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=45.0,
        max_retries=1,
    )
    ensure_output_file()
    products = [
        {
            "catalog_key": str(row.catalog_key),
            "name": str(row.Name),
            "brand": str(row.Brand),
        }
        for row in remaining.itertuples(index=False)
    ]

    with OUTPUT_PATH.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        consecutive_failures = 0
        for offset in range(0, len(products), BATCH_SIZE):
            batch = products[offset : offset + BATCH_SIZE]
            try:
                translated = translate_batch_with_retry(client, model, batch)
            except Exception as exc:
                consecutive_failures += 1
                print(f"[{offset + 1}/{len(products)}] Failed: {exc}", flush=True)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(
                        "Stopping after repeated connection failures. "
                        "Run the same command later to resume safely.",
                        flush=True,
                    )
                    return
                continue

            consecutive_failures = 0

            translated_at = datetime.now(timezone.utc).isoformat()
            for item in translated:
                writer.writerow(
                    {
                        "catalog_key": str(item["catalog_key"]).strip(),
                        "name_ko": str(item["name_ko"]).strip(),
                        "brand_ko": str(item["brand_ko"]).strip(),
                        "translated_at": translated_at,
                        "model": model,
                    }
                )
            file.flush()
            print(
                f"[{min(offset + len(batch), len(products))}/{len(products)}] Saved",
                flush=True,
            )


if __name__ == "__main__":
    main()
