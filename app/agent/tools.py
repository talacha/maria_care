from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services import clinicians as clinician_service

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_facets",
            "description": (
                "List valid specialities, locations, counties, languages, and availability "
                "values in the clinician directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_clinicians",
            "description": (
                "Search clinicians with structured filters. Prefer last_name/first_name/"
                "speciality over free-text q. For pronouns like she/he, set likely_gender. "
                "Carry forward prior constraints on follow-up turns. Always report total."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "speciality": {"type": "string"},
                    "location": {"type": "string"},
                    "county": {"type": "string"},
                    "language": {"type": "string"},
                    "first_name": {
                        "type": "string",
                        "description": "Exact first name match (case-insensitive).",
                    },
                    "last_name": {
                        "type": "string",
                        "description": "Exact last name match (case-insensitive).",
                    },
                    "likely_gender": {
                        "type": "string",
                        "enum": ["female", "male"],
                        "description": (
                            "Soft filter inferred from first-name lexicon when the user "
                            "says she/he/her/him. Schema has no gender field."
                        ),
                    },
                    "min_rating": {"type": "number"},
                    "min_years_experience": {"type": "integer"},
                    "q": {
                        "type": "string",
                        "description": "Fallback free-text over name/clinic; prefer last_name.",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["rating", "years_experience"],
                    },
                    "order": {"type": "string", "enum": ["asc", "desc"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "offset": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clinician",
            "description": "Get one clinician by numeric id from a previous search result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clinician_id": {"type": "integer"},
                },
                "required": ["clinician_id"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(db: Session, name: str, arguments: dict[str, Any]) -> str:
    settings = get_settings()

    if name == "list_facets":
        meta = clinician_service.get_meta(db)
        return meta.model_dump_json()

    if name == "search_clinicians":
        limit = min(int(arguments.get("limit") or 10), settings.max_search_limit)
        offset = max(int(arguments.get("offset") or 0), 0)
        items, total, applied_filters = clinician_service.search_clinicians(
            db,
            speciality=arguments.get("speciality"),
            location=arguments.get("location"),
            county=arguments.get("county"),
            language=arguments.get("language"),
            first_name=arguments.get("first_name"),
            last_name=arguments.get("last_name"),
            likely_gender=arguments.get("likely_gender"),
            min_rating=arguments.get("min_rating"),
            min_years_experience=arguments.get("min_years_experience"),
            q=arguments.get("q"),
            sort=arguments.get("sort") or "rating",
            order=arguments.get("order") or "desc",
            limit=limit,
            offset=offset,
        )
        payload = {
            "total": total,
            "returned": len(items),
            "limit": limit,
            "offset": offset,
            "applied_filters": applied_filters,
            "items": [item.model_dump() for item in items],
            "guidance": (
                f"Authoritative match count is {total}. Quote this exact total. "
                "Only mention clinicians present in items. "
                "If total > 1, ask for another constraint "
                "(city, clinic, rating, language, etc.). Only present a single doctor "
                "as definitive when total == 1 or the user selects an id."
            ),
        }
        return json.dumps(payload)

    if name == "get_clinician":
        clinician_id = int(arguments["clinician_id"])
        clinician = clinician_service.get_clinician(db, clinician_id)
        if clinician is None:
            return json.dumps({"error": "Clinician not found", "clinician_id": clinician_id})
        return clinician.model_dump_json()

    return json.dumps({"error": f"Unknown tool: {name}"})
