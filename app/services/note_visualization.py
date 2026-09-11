"""Build explainable note-visualization data from the source Notes field."""

from __future__ import annotations

import re

from app.services.note_normalizer import normalize_note_token


ACCORD_DEFINITIONS = {
    "floral": {
        "label": "플로럴",
        "color": "#D9A7B0",
        "keywords": ["rose", "jasmine", "tuberose", "violet", "iris", "geranium", "neroli", "orange blossom", "magnolia", "gardenia", "peony", "flower", "floral"],
    },
    "woody": {
        "label": "우디",
        "color": "#C7B38A",
        "keywords": ["sandalwood", "cedarwood", "cedar", "vetiver", "oud", "agarwood", "guaiacwood", "cashmere wood", "wood", "woody"],
    },
    "musk": {
        "label": "머스크",
        "color": "#B8A797",
        "keywords": ["musk"],
    },
    "citrus": {
        "label": "시트러스",
        "color": "#E6C866",
        "keywords": ["bergamot", "lemon", "orange", "grapefruit", "lime", "yuzu", "mandarin", "tangerine", "citron", "petitgrain", "citrus"],
    },
    "spicy": {
        "label": "스파이시",
        "color": "#BE7D5D",
        "keywords": ["pepper", "cinnamon", "clove", "cardamom", "nutmeg", "saffron", "spice", "spicy"],
    },
    "green": {
        "label": "그린",
        "color": "#A9B27A",
        "keywords": ["green", "leaf", "leaves", "grass", "herbal", "mint", "basil", "thyme", "fig leaf"],
    },
    "amber": {
        "label": "앰버",
        "color": "#C99055",
        "keywords": ["amber", "benzoin", "labdanum", "resin", "incense", "olibanum", "myrrh"],
    },
    "gourmand": {
        "label": "구르망",
        "color": "#C69663",
        "keywords": ["vanilla", "caramel", "chocolate", "cacao", "honey", "almond", "praline", "coffee", "sugar", "coconut"],
    },
    "aquatic": {
        "label": "아쿠아틱",
        "color": "#88B8C8",
        "keywords": ["aquatic", "marine", "water", "sea", "ocean", "saltwater"],
    },
    "powdery": {
        "label": "파우더리",
        "color": "#D3C6D4",
        "keywords": ["powder", "orris", "iris", "violet", "heliotrope"],
    },
    "fruity": {
        "label": "프루티",
        "color": "#D99478",
        "keywords": ["apple", "pear", "peach", "plum", "berry", "fig", "blackberry", "apricot", "fruit", "fruity"],
    },
    "leather": {
        "label": "레더",
        "color": "#8A6C59",
        "keywords": ["leather", "suede", "tobacco"],
    },
}

NOTE_LABELS = {
    "amber": ("앰버", "Amber"),
    "bergamot": ("베르가못", "Bergamot"),
    "cardamom": ("카다멈", "Cardamom"),
    "cedarwood": ("시더우드", "Cedarwood"),
    "fig": ("무화과", "Fig"),
    "geranium": ("제라늄", "Geranium"),
    "guaiacwood": ("가이악우드", "Guaiacwood"),
    "jasmine": ("자스민", "Jasmine"),
    "musk": ("머스크", "Musk"),
    "neroli": ("네롤리", "Neroli"),
    "orange blossom": ("오렌지 블로섬", "Orange Blossom"),
    "orris": ("오리스", "Orris"),
    "patchouli": ("패출리", "Patchouli"),
    "rose": ("로즈", "Rose"),
    "sandalwood": ("샌달우드", "Sandalwood"),
    "tuberose": ("튜베로즈", "Tuberose"),
    "vanilla": ("바닐라", "Vanilla"),
    "vetiver": ("베티버", "Vetiver"),
    "violet": ("바이올렛", "Violet"),
    "yuzu": ("유자", "Yuzu"),
}


def _contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _split_notes(notes: str) -> list[dict]:
    raw_parts = re.split(r"[,;]", str(notes or ""))
    parsed_notes = []

    for raw_part in raw_parts:
        raw_note = raw_part.strip()
        canonical_note = normalize_note_token(raw_note)
        if not canonical_note:
            continue

        label_ko, label_en = NOTE_LABELS.get(
            canonical_note,
            (raw_note, raw_note),
        )
        icon_key = re.sub(r"[^a-z0-9]+", "-", canonical_note).strip("-")
        parsed_notes.append(
            {
                "id": canonical_note,
                "label_ko": label_ko,
                "label_en": label_en,
                "icon_key": icon_key or "unknown",
                "raw_note": raw_note,
            }
        )

    return parsed_notes


def _infer_note_pyramid(notes: list[dict]) -> dict:
    if not notes:
        return {
            "source": "not_available",
            "message": "노트 정보가 없습니다.",
            "top": [],
            "middle": [],
            "base": [],
        }

    if len(notes) < 3:
        return {
            "source": "not_available",
            "message": "원본 데이터에 탑/미들/베이스 구분이 없습니다.",
            "top": [],
            "middle": [],
            "base": [],
        }

    first_cut = (len(notes) + 2) // 3
    second_cut = first_cut + (len(notes) - first_cut + 1) // 2
    return {
        "source": "inferred_from_note_order",
        "message": "원본 Notes의 나열 순서를 3구간으로 나눈 추정 결과입니다.",
        "top": notes[:first_cut],
        "middle": notes[first_cut:second_cut],
        "base": notes[second_cut:],
    }


def build_note_visualization(notes: str, top_n: int = 3) -> dict:
    """Return display-ready accord and note data from a flat Notes string."""
    parsed_notes = _split_notes(notes)
    accords = []

    for accord_id, definition in ACCORD_DEFINITIONS.items():
        matched_notes = [
            note
            for note in parsed_notes
            if any(_contains_keyword(note["id"], keyword) for keyword in definition["keywords"])
        ]
        if not matched_notes:
            continue

        accords.append(
            {
                "id": accord_id,
                "label": definition["label"],
                "color": definition["color"],
                "score": len(matched_notes),
                "matched_notes": [note["id"] for note in matched_notes],
            }
        )

    accords.sort(key=lambda accord: (-accord["score"], accord["label"]))
    total_matches = sum(accord["score"] for accord in accords)
    for accord in accords:
        accord["percentage"] = (
            round((accord["score"] / total_matches) * 100)
            if total_matches
            else 0
        )

    return {
        "source": "derived_from_notes",
        "message": "메인 어코드 비율은 Notes에서 분류된 노트의 매칭 비중입니다.",
        "main_accords": accords[:top_n],
        "accord_bars": accords[:5],
        "featured_notes": parsed_notes[:top_n],
        "note_pyramid": _infer_note_pyramid(parsed_notes),
    }
