"""Normalize perfume-note spellings before matching or vectorization.

The original display text is never changed.  This module creates a separate
comparison representation so Korean/English aliases and letter case do not
split one scent note into multiple tokens.
"""

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


# Keep this focused on note names and common spelling variants.  Broad terms
# such as "포근한" belong to preference extraction, not a literal note alias.
NOTE_ALIASES = {
    "가이악 우드": "guaiacwood",
    "가이악우드": "guaiacwood",
    "가죽": "leather",
    "그레이프프루트": "grapefruit",
    "네롤리": "neroli",
    "라브다넘": "labdanum",
    "라임": "lime",
    "레더": "leather",
    "레몬": "lemon",
    "로즈": "rose",
    "로즈 앱솔루트": "rose",
    "머스크": "musk",
    "머스키": "musk",
    "무화과": "fig",
    "바닐라": "vanilla",
    "바질": "basil",
    "베르가못": "bergamot",
    "베티버": "vetiver",
    "벤조인": "benzoin",
    "블랙 페퍼": "black pepper",
    "블랙페퍼": "black pepper",
    "샌달 우드": "sandalwood",
    "샌달우드": "sandalwood",
    "시나몬": "cinnamon",
    "시더": "cedarwood",
    "시더 우드": "cedarwood",
    "시더우드": "cedarwood",
    "앰버": "amber",
    "오렌지 블로섬": "orange blossom",
    "오렌지블로섬": "orange blossom",
    "오리스": "orris",
    "유자": "yuzu",
    "자몽": "grapefruit",
    "자스민": "jasmine",
    "제라늄": "geranium",
    "주니퍼": "juniper",
    "카다멈": "cardamom",
    "캐시미어 우드": "cashmere wood",
    "캐시미어우드": "cashmere wood",
    "클로브": "clove",
    "타바코": "tobacco",
    "타임": "thyme",
    "통카 빈": "tonka bean",
    "통카빈": "tonka bean",
    "튜베로즈": "tuberose",
    "패출리": "patchouli",
    "페티그레인": "petitgrain",
    "화이트 머스크": "musk",
    "화이트머스크": "musk",
    "히노키": "hinoki",
    "ambergris": "amber",
    "cedar wood": "cedarwood",
    "guaiac wood": "guaiacwood",
    "musc": "musk",
    "rose absolute": "rose",
    "sandal wood": "sandalwood",
    "white musk": "musk",
}

NOTE_TRANSLATIONS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "note_translations_ko.csv"
)


@lru_cache(maxsize=1)
def get_note_translations_ko() -> dict[str, str]:
    """Load translated canonical note names created by the batch script."""
    if not NOTE_TRANSLATIONS_PATH.exists():
        return {}

    with NOTE_TRANSLATIONS_PATH.open("r", encoding="utf-8", newline="") as file:
        return {
            row["canonical_note"].strip(): row["note_ko"].strip()
            for row in csv.DictReader(file)
            if row.get("canonical_note") and row.get("note_ko")
        }


def normalize_note_text(value: object) -> str:
    """Return a case-insensitive, alias-normalized text for recommendation."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[/_|]", " ", text)
    text = re.sub(r"[^0-9a-z가-힣\s,.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Long aliases must be replaced first so "화이트 머스크" is not split.
    for alias in sorted(NOTE_ALIASES, key=len, reverse=True):
        canonical = NOTE_ALIASES[alias]
        pattern = rf"(?<![0-9a-z가-힣]){re.escape(alias)}(?![0-9a-z가-힣])"
        text = re.sub(pattern, canonical, text)

    return re.sub(r"\s+", " ", text).strip()


def normalize_note_token(value: object) -> str:
    """Normalize one comma-separated note and remove dataset footer text."""
    normalized = normalize_note_text(value)
    for marker in ("click here for ingredients", "please be aware", "ingredients", "close"):
        if marker in normalized:
            normalized = normalized.split(marker)[0]
    return " ".join(normalized.split()).strip(" .:-")


def get_note_label_ko(canonical_note: str, fallback: str) -> str:
    """Return a Korean display label while preserving unknown source notes."""
    return get_note_translations_ko().get(canonical_note, fallback)


def translate_notes_to_korean(notes: object) -> str:
    """Translate a comma-separated Notes value using the shared note dictionary."""
    translated_notes = []
    for raw_note in re.split(r"[,;]", str(notes or "")):
        raw_note = raw_note.strip()
        canonical_note = normalize_note_token(raw_note)
        if not canonical_note:
            continue
        translated_notes.append(get_note_label_ko(canonical_note, raw_note))
    return ", ".join(translated_notes)
