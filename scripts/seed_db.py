#!/usr/bin/env python3
"""Load healthcare_data.json into SQLite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import DEFAULT_DB_PATH, get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Clinician, ClinicianLanguage  # noqa: E402

JSON_PATH = ROOT / "healthcare_data.json"
BATCH_SIZE = 500


def seed(json_path: Path = JSON_PATH, replace: bool = True) -> int:
    if not json_path.exists():
        raise FileNotFoundError(f"Missing source data: {json_path}")

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    print(f"Database: {settings.database_url}")

    if replace:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with json_path.open(encoding="utf-8") as fh:
        rows = json.load(fh)

    if not isinstance(rows, list):
        raise ValueError("Expected a JSON array of clinician records")

    inserted = 0
    with SessionLocal() as db:
        batch: list[Clinician] = []
        for row in rows:
            clinician = Clinician(
                first_name=row["first_name"],
                last_name=row["last_name"],
                clinic_name=row["clinic_name"],
                location=row["location"],
                speciality=row["speciality"],
                address=row["address"],
                phone=row["phone"],
                email=row["email"],
                postal_code=row["postal_code"],
                county=row["county"],
                years_experience=int(row["years_experience"]),
                education=row["education"],
                availability=row["availability"],
                rating=float(row["rating"]),
                languages=[
                    ClinicianLanguage(language=language)
                    for language in sorted(set(row.get("languages") or []))
                ],
            )
            batch.append(clinician)
            if len(batch) >= BATCH_SIZE:
                db.add_all(batch)
                db.commit()
                inserted += len(batch)
                print(f"Inserted {inserted}/{len(rows)}")
                batch = []

        if batch:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)

    print(f"Seed complete: {inserted} clinicians")
    return inserted


if __name__ == "__main__":
    seed()
