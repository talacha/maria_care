from typing import Any, Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.gender import LikelyGender, first_names_for_gender, infer_likely_gender, parse_likely_gender
from app.models import Clinician, ClinicianLanguage
from app.schemas import ClinicianOut, MetaResponse

SortField = Literal["rating", "years_experience"]
SortOrder = Literal["asc", "desc"]


def clinician_to_out(clinician: Clinician) -> ClinicianOut:
    return ClinicianOut(
        id=clinician.id,
        first_name=clinician.first_name,
        last_name=clinician.last_name,
        clinic_name=clinician.clinic_name,
        location=clinician.location,
        speciality=clinician.speciality,
        address=clinician.address,
        phone=clinician.phone,
        email=clinician.email,
        postal_code=clinician.postal_code,
        county=clinician.county,
        years_experience=clinician.years_experience,
        education=clinician.education,
        languages=sorted(lang.language for lang in clinician.languages),
        availability=clinician.availability,
        rating=clinician.rating,
        likely_gender=infer_likely_gender(clinician.first_name),
    )


def _apply_filters(
    stmt: Select,
    *,
    speciality: str | None = None,
    location: str | None = None,
    county: str | None = None,
    language: str | None = None,
    min_rating: float | None = None,
    min_years_experience: int | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    likely_gender: LikelyGender | None = None,
    q: str | None = None,
) -> Select:
    if speciality:
        stmt = stmt.where(Clinician.speciality == speciality)
    if location:
        stmt = stmt.where(Clinician.location == location)
    if county:
        stmt = stmt.where(Clinician.county == county)
    if min_rating is not None:
        stmt = stmt.where(Clinician.rating >= min_rating)
    if min_years_experience is not None:
        stmt = stmt.where(Clinician.years_experience >= min_years_experience)
    if language:
        stmt = stmt.where(
            Clinician.id.in_(
                select(ClinicianLanguage.clinician_id).where(ClinicianLanguage.language == language)
            )
        )
    if first_name:
        stmt = stmt.where(Clinician.first_name.ilike(first_name.strip()))
    if last_name:
        stmt = stmt.where(Clinician.last_name.ilike(last_name.strip()))
    if likely_gender in {"female", "male"}:
        names = first_names_for_gender(likely_gender)
        stmt = stmt.where(func.lower(Clinician.first_name).in_([n.lower() for n in names]))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Clinician.first_name.ilike(pattern),
                Clinician.last_name.ilike(pattern),
                Clinician.clinic_name.ilike(pattern),
                (Clinician.first_name + " " + Clinician.last_name).ilike(pattern),
            )
        )
    return stmt


def _applied_filters(
    *,
    speciality: str | None,
    location: str | None,
    county: str | None,
    language: str | None,
    min_rating: float | None,
    min_years_experience: int | None,
    first_name: str | None,
    last_name: str | None,
    likely_gender: LikelyGender | None,
    q: str | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if speciality:
        filters["speciality"] = speciality
    if location:
        filters["location"] = location
    if county:
        filters["county"] = county
    if language:
        filters["language"] = language
    if min_rating is not None:
        filters["min_rating"] = min_rating
    if min_years_experience is not None:
        filters["min_years_experience"] = min_years_experience
    if first_name:
        filters["first_name"] = first_name.strip()
    if last_name:
        filters["last_name"] = last_name.strip()
    if likely_gender in {"female", "male"}:
        filters["likely_gender"] = likely_gender
        filters["likely_gender_note"] = (
            "Inferred from first-name lexicon; schema has no gender field."
        )
    if q:
        filters["q"] = q.strip()
    return filters


def search_clinicians(
    db: Session,
    *,
    speciality: str | None = None,
    location: str | None = None,
    county: str | None = None,
    language: str | None = None,
    min_rating: float | None = None,
    min_years_experience: int | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    likely_gender: str | None = None,
    q: str | None = None,
    sort: SortField = "rating",
    order: SortOrder = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ClinicianOut], int, dict[str, Any]]:
    gender = parse_likely_gender(likely_gender) if isinstance(likely_gender, str) else likely_gender
    if gender == "unknown":
        gender = None

    base = select(Clinician)
    base = _apply_filters(
        base,
        speciality=speciality,
        location=location,
        county=county,
        language=language,
        min_rating=min_rating,
        min_years_experience=min_years_experience,
        first_name=first_name,
        last_name=last_name,
        likely_gender=gender,
        q=q,
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.scalar(count_stmt) or 0

    sort_col = Clinician.rating if sort == "rating" else Clinician.years_experience
    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    stmt = base.order_by(sort_expr, Clinician.id.asc()).limit(limit).offset(offset)
    rows = db.scalars(stmt).unique().all()
    applied = _applied_filters(
        speciality=speciality,
        location=location,
        county=county,
        language=language,
        min_rating=min_rating,
        min_years_experience=min_years_experience,
        first_name=first_name,
        last_name=last_name,
        likely_gender=gender,
        q=q,
    )
    return [clinician_to_out(row) for row in rows], total, applied


def get_clinician(db: Session, clinician_id: int) -> ClinicianOut | None:
    clinician = db.get(Clinician, clinician_id)
    if clinician is None:
        return None
    return clinician_to_out(clinician)


def get_meta(db: Session) -> MetaResponse:
    total = db.scalar(select(func.count()).select_from(Clinician)) or 0
    specialities = db.scalars(select(Clinician.speciality).distinct().order_by(Clinician.speciality)).all()
    locations = db.scalars(select(Clinician.location).distinct().order_by(Clinician.location)).all()
    counties = db.scalars(select(Clinician.county).distinct().order_by(Clinician.county)).all()
    languages = db.scalars(
        select(ClinicianLanguage.language).distinct().order_by(ClinicianLanguage.language)
    ).all()
    availability = db.scalars(
        select(Clinician.availability).distinct().order_by(Clinician.availability)
    ).all()
    return MetaResponse(
        total_clinicians=total,
        specialities=list(specialities),
        locations=list(locations),
        counties=list(counties),
        languages=list(languages),
        availability=list(availability),
    )


def clinician_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Clinician)) or 0
