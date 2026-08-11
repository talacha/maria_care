"""Deterministic likely-gender inference from Romanian first names in this dataset.

The schema has no gender field. Soft cues like "she" / "he" are mapped via this lexicon
so the agent can filter without inventing attributes.
"""

from __future__ import annotations

from typing import Literal

LikelyGender = Literal["female", "male", "unknown"]

# Closed set covering every first_name currently present in healthcare_data.json.
_FEMALE_FIRST_NAMES = frozenset(
    {
        "Alina",
        "Ana",
        "Bianca",
        "Carmen",
        "Claudia",
        "Cristina",
        "Daria",
        "Diana",
        "Elena",
        "Georgiana",
        "Ioana",
        "Irina",
        "Laura",
        "Maria",
        "Oana",
        "Raluca",
    }
)

_MALE_FIRST_NAMES = frozenset(
    {
        "Alexandru",
        "Andrei",
        "Bogdan",
        "Cosmin",
        "Daniel",
        "Florin",
        "Ionut",
        "Mihai",
        "Nicolae",
        "Radu",
        "Sorin",
        "Stefan",
        "Tudor",
        "Vlad",
    }
)


def normalize_first_name(name: str | None) -> str:
    return (name or "").strip()


def infer_likely_gender(first_name: str | None) -> LikelyGender:
    key = normalize_first_name(first_name)
    if not key:
        return "unknown"
    # Case-insensitive match against the closed lexicon.
    lowered = {n.lower(): "female" for n in _FEMALE_FIRST_NAMES}
    lowered.update({n.lower(): "male" for n in _MALE_FIRST_NAMES})
    return lowered.get(key.lower(), "unknown")  # type: ignore[return-value]


def first_names_for_gender(gender: LikelyGender) -> frozenset[str]:
    if gender == "female":
        return _FEMALE_FIRST_NAMES
    if gender == "male":
        return _MALE_FIRST_NAMES
    return frozenset()


def parse_likely_gender(value: str | None) -> LikelyGender | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"female", "f", "woman", "she", "her"}:
        return "female"
    if normalized in {"male", "m", "man", "he", "him", "his"}:
        return "male"
    if normalized in {"unknown", "any", ""}:
        return None
    return None
