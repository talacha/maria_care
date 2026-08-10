from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.schemas import ClinicianListResponse, ClinicianOut, HealthResponse, MetaResponse
from app.services import clinicians as clinician_service

router = APIRouter(tags=["clinicians"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    try:
        count = clinician_service.clinician_count(db)
        status = "ok" if settings.openai_api_key else "degraded"
        return HealthResponse(
            status=status,
            database_ready=True,
            clinician_count=count,
            chat_ready=bool(settings.openai_api_key),
        )
    except Exception:
        return HealthResponse(
            status="degraded",
            database_ready=False,
            clinician_count=0,
            chat_ready=bool(settings.openai_api_key),
        )


@router.get("/meta", response_model=MetaResponse)
def meta(db: Session = Depends(get_db)) -> MetaResponse:
    return clinician_service.get_meta(db)


@router.get("/clinicians", response_model=ClinicianListResponse)
def list_clinicians(
    speciality: str | None = None,
    location: str | None = None,
    county: str | None = None,
    language: str | None = None,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    min_years_experience: int | None = Query(default=None, ge=0),
    q: str | None = None,
    sort: Literal["rating", "years_experience"] = "rating",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ClinicianListResponse:
    settings = get_settings()
    capped_limit = min(limit, settings.max_search_limit)
    items, total = clinician_service.search_clinicians(
        db,
        speciality=speciality,
        location=location,
        county=county,
        language=language,
        min_rating=min_rating,
        min_years_experience=min_years_experience,
        q=q,
        sort=sort,
        order=order,
        limit=capped_limit,
        offset=offset,
    )
    return ClinicianListResponse(total=total, limit=capped_limit, offset=offset, items=items)


@router.get("/clinicians/{clinician_id}", response_model=ClinicianOut)
def get_clinician(clinician_id: int, db: Session = Depends(get_db)) -> ClinicianOut:
    clinician = clinician_service.get_clinician(db, clinician_id)
    if clinician is None:
        raise HTTPException(status_code=404, detail="Clinician not found")
    return clinician
