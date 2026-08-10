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
                "Search clinicians with structured filters. Use exact facet values from "
                "list_facets when possible."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "speciality": {"type": "string"},
                    "location": {"type": "string"},
                    "county": {"type": "string"},
                    "language": {"type": "string"},
                    "min_rating": {"type": "number"},
                    "min_years_experience": {"type": "integer"},
                    "q": {
                        "type": "string",
                        "description": "Name or clinic name search text",
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
        items, total = clinician_service.search_clinicians(
            db,
            speciality=arguments.get("speciality"),
            location=arguments.get("location"),
            county=arguments.get("county"),
            language=arguments.get("language"),
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
            "limit": limit,
            "offset": offset,
            "items": [item.model_dump() for item in items],
        }
        return json.dumps(payload)

    if name == "get_clinician":
        clinician_id = int(arguments["clinician_id"])
        clinician = clinician_service.get_clinician(db, clinician_id)
        if clinician is None:
            return json.dumps({"error": "Clinician not found", "clinician_id": clinician_id})
        return clinician.model_dump_json()

    return json.dumps({"error": f"Unknown tool: {name}"})
