from typing import Literal

from pydantic import BaseModel, Field


class ClinicianOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    clinic_name: str
    location: str
    speciality: str
    address: str
    phone: str
    email: str
    postal_code: str
    county: str
    years_experience: int
    education: str
    languages: list[str]
    availability: str
    rating: float

    model_config = {"from_attributes": True}


class ClinicianListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ClinicianOut]


class MetaResponse(BaseModel):
    total_clinicians: int
    specialities: list[str]
    locations: list[str]
    counties: list[str]
    languages: list[str]
    availability: list[str]


class HealthResponse(BaseModel):
    status: str
    database_ready: bool
    clinician_count: int
    chat_ready: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    refused: bool = False
