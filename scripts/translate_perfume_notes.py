"""Create a resumable Korean note dictionary for the perfume catalog.

Examples:
    python scripts/translate_perfume_notes.py --limit 100
    python scripts/translate_perfume_notes.py --all

The source Notes text remains untouched. The generated sidecar is reused by
list/detail/recommendation responses and note visualization.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from app.services.note_normalizer import normalize_note_token  # noqa: E402
from app.services.recommender import load_perfume_data  # noqa: E402


OUTPUT_PATH = ROOT_DIR / "app" / "data" / "note_translations_ko.csv"
OUTPUT_FIELDS = ["canonical_note", "note_ko", "translated_at", "model"]
BATCH_SIZE = 50
SYSTEM_INSTRUCTIONS = """
You translate perfume note names into concise, commonly used Korean labels.
Return one JSON object only. Each key must be the supplied English note name
exactly and each value must be its Korean display label. Keep established
perfume spellings such as bergamot=베르가못, patchouli=패출리,
sandalwood=샌달우드, and do not add explanations or facts.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--limit", type=int, help="Number of untranslated notes")
    scope.add_argument("--all", action="store_true", help="Translate every remaining note")
    return parser.parse_args()


def load_completed_notes() -> set[str]:
    if not OUTPUT_PATH.exists():
        return set()
    with OUTPUT_PATH.open("r", encoding="utf-8", newline="") as file:
        return {
            row["canonical_note"]
            for row in csv.DictReader(file)
            if row.get("canonical_note") and row.get("note_ko")
        }


def unique_notes() -> Counter[str]:
    counts: Counter[str] = Counter()
    for value in load_perfume_data()["Notes"].fillna("").astype(str):
        for raw_note in value.replace(";", ",").split(","):
            note = normalize_note_token(raw_note)
            if note:
                counts[note] += 1
    return counts


def translate_batch(client: OpenAI, model: str, notes: list[str]) -> dict[str, str]:
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=json.dumps(notes, ensure_ascii=False),
        max_output_tokens=2500,
    )
    payload = json.loads(response.output_text)
    if not isinstance(payload, dict):
        raise ValueError("Translation response was not a JSON object.")
    return {
        note: str(payload[note]).strip()
        for note in notes
        if str(payload.get(note, "")).strip()
    }


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required. Add it to .env before running.")

    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    completed = load_completed_notes()
    remaining = [note for note, _ in unique_notes().most_common() if note not in completed]
    if not args.all:
        if args.limit <= 0:
            raise ValueError("--limit must be at least 1")
        remaining = remaining[: args.limit]
    if not remaining:
        print("No untranslated notes remain.")
        return

    if not OUTPUT_PATH.exists():
        with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
            csv.DictWriter(file, fieldnames=OUTPUT_FIELDS).writeheader()

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=45.0,
        max_retries=1,
    )
    with OUTPUT_PATH.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        for offset in range(0, len(remaining), BATCH_SIZE):
            batch = remaining[offset : offset + BATCH_SIZE]
            try:
                translations = translate_batch(client, model, batch)
            except Exception as exc:
                print(f"[{offset + 1}/{len(remaining)}] Failed: {exc}")
                continue

            translated_at = datetime.now(timezone.utc).isoformat()
            for note, note_ko in translations.items():
                writer.writerow(
                    {
                        "canonical_note": note,
                        "note_ko": note_ko,
                        "translated_at": translated_at,
                        "model": model,
                    }
                )
            file.flush()
            print(f"[{min(offset + len(batch), len(remaining))}/{len(remaining)}] Saved")


if __name__ == "__main__":
    main()
