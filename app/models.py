from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Clinician(Base):
    __tablename__ = "clinicians"
    __table_args__ = (
        Index("ix_clinicians_speciality", "speciality"),
        Index("ix_clinicians_location", "location"),
        Index("ix_clinicians_county", "county"),
        Index("ix_clinicians_rating", "rating"),
        Index("ix_clinicians_years_experience", "years_experience"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    clinic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    speciality: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    county: Mapped[str] = mapped_column(String(120), nullable=False)
    years_experience: Mapped[int] = mapped_column(Integer, nullable=False)
    education: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str] = mapped_column(String(120), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)

    languages: Mapped[list["ClinicianLanguage"]] = relationship(
        back_populates="clinician",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ClinicianLanguage(Base):
    __tablename__ = "clinician_languages"
    __table_args__ = (
        UniqueConstraint("clinician_id", "language", name="uq_clinician_language"),
        Index("ix_clinician_languages_language", "language"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinician_id: Mapped[int] = mapped_column(ForeignKey("clinicians.id", ondelete="CASCADE"), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)

    clinician: Mapped[Clinician] = relationship(back_populates="languages")
