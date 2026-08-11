"""Extract progressive search constraints from user text for reliable narrowing."""

from __future__ import annotations

import re
from typing import Any

from app.gender import LikelyGender

_LAST_NAME_PATTERNS = [
    re.compile(r"\blast\s*name\s*(?:is|=|:)?\s*([A-Za-zÀ-ÿ\-']+)", re.I),
    re.compile(r"\blastname\s*(?:is|=|:)?\s*([A-Za-zÀ-ÿ\-']+)", re.I),
    re.compile(r"\bnamed\s+([A-Za-zÀ-ÿ\-']+)\b", re.I),
]

_FIRST_NAME_PATTERNS = [
    re.compile(r"\bfirst\s*name\s*(?:is|=|:)?\s*([A-Za-zÀ-ÿ\-']+)", re.I),
]

_SPECIALITY_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"infectious\s+diseases?", re.I), "Infectious Diseases"),
    (re.compile(r"\bcardiolog", re.I), "Cardiology"),
    (re.compile(r"\bdermato", re.I), "Dermatology"),
    (re.compile(r"\bpsychiatr", re.I), "Psychiatry"),
    (re.compile(r"\bneurolog", re.I), "Neurology"),
    (re.compile(r"\bpediatr", re.I), "Pediatrics"),
    (re.compile(r"\boncolog", re.I), "Oncology"),
    (re.compile(r"\burolog", re.I), "Urology"),
    (re.compile(r"\bgastro", re.I), "Gastroenterology"),
    (re.compile(r"obstetrics|\bgyn[ae]colog", re.I), "Obstetrics and Gynecology"),
    (re.compile(r"\bfamily\s+medicine", re.I), "Family Medicine"),
    (re.compile(r"\binternal\s+medicine", re.I), "Internal Medicine"),
    (re.compile(r"\bophthalm", re.I), "Ophthalmology"),
    (re.compile(r"\borthoped", re.I), "Orthopedics"),
    (re.compile(r"\bpulmonolog", re.I), "Pulmonology"),
    (re.compile(r"\bradiolog", re.I), "Radiology"),
    (re.compile(r"\brheumatolog", re.I), "Rheumatology"),
    (re.compile(r"\bnephrolog", re.I), "Nephrology"),
    (re.compile(r"\bendocrin", re.I), "Endocrinology"),
    (re.compile(r"\bENT\b|\botolaryng", re.I), "ENT"),
]

_FEMALE_CUES = re.compile(r"\b(she|her|hers|woman|female)\b", re.I)
_MALE_CUES = re.compile(r"\b(he|him|his|man|male)\b", re.I)


def extract_constraints_from_text(text: str) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    for pattern in _LAST_NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            constraints["last_name"] = match.group(1).strip().title()
            break
    for pattern in _FIRST_NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            constraints["first_name"] = match.group(1).strip().title()
            break
    for pattern, speciality in _SPECIALITY_ALIASES:
        if pattern.search(text):
            constraints["speciality"] = speciality
            break
    if _FEMALE_CUES.search(text):
        constraints["likely_gender"] = "female"
    elif _MALE_CUES.search(text):
        constraints["likely_gender"] = "male"
    return constraints


def merge_constraints(history: list[dict[str, Any]] | None, message: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in history or []:
        if item.get("role") != "user":
            continue
        content = item.get("content")
        if isinstance(content, str):
            merged.update(extract_constraints_from_text(content))
    merged.update(extract_constraints_from_text(message))
    return merged


def format_search_answer(
    *,
    total: int,
    items: list[dict[str, Any]],
    applied_filters: dict[str, Any],
) -> str:
    filter_bits = []
    for key in ("last_name", "first_name", "speciality", "location", "language", "likely_gender"):
        if key in applied_filters:
            filter_bits.append(f"{key}={applied_filters[key]}")
    filter_text = ", ".join(filter_bits) if filter_bits else "no structured filters"

    if total == 0:
        return (
            f"No clinicians matched ({filter_text}). "
            "Try another city, speciality, or spelling."
        )

    lines = [f"Found {total} match{'es' if total != 1 else ''} ({filter_text})."]
    if total == 1:
        lines.append("Here is the matching clinician:")
    else:
        lines.append("Here is a sample from the results:")

    for item in items[:8]:
        languages = ", ".join(item.get("languages") or [])
        lines.append(
            "- "
            f"id {item.get('id')}: {item.get('first_name')} {item.get('last_name')} — "
            f"{item.get('speciality')}, {item.get('clinic_name')}, {item.get('location')}, "
            f"rating {item.get('rating')}, likely_gender={item.get('likely_gender')}, "
            f"languages={languages or 'n/a'}, phone {item.get('phone')}"
        )

    if total > 1:
        lines.append(
            "This is not unique yet. Share city, clinic, language, or rating to narrow further."
        )
    return "\n".join(lines)


def should_use_deterministic_search(constraints: dict[str, Any]) -> bool:
    return bool(
        constraints.get("last_name")
        or constraints.get("first_name")
        or constraints.get("speciality")
        or constraints.get("likely_gender")
    )
