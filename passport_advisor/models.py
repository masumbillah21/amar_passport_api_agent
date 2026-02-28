from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Profession(str, Enum):
    PRIVATE_SECTOR = "private_sector"
    GOVERNMENT_STAFF = "government_staff"
    STUDENT = "student"
    BUSINESS_OWNER = "business_owner"
    OTHER = "other"


class DeliverySpeed(str, Enum):
    REGULAR = "regular"
    EXPRESS = "express"
    SUPER_EXPRESS = "super_express"


class ApplicantProfile(BaseModel):
    age: int = Field(..., ge=0, le=120)
    profession: Profession
    page_count: Literal[48, 64]
    delivery_speed: DeliverySpeed
    requested_validity_years: int | None = Field(default=None)
    has_nid: bool = True
    has_birth_registration: bool = False
    has_profession_proof: bool = True
    name_changed: bool = False
    location: str | None = None

    @field_validator("requested_validity_years")
    @classmethod
    def validate_requested_validity(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value not in {5, 10}:
            raise ValueError("requested_validity_years must be 5, 10, or null")
        return value


class ScenarioInput(BaseModel):
    scenario: str = Field(..., min_length=10)


class ApplicantProfileDraft(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    profession: Profession | None = None
    page_count: Literal[48, 64] | None = None
    delivery_speed: DeliverySpeed | None = None
    requested_validity_years: int | None = Field(default=None)
    has_nid: bool | None = None
    has_birth_registration: bool | None = None
    has_profession_proof: bool | None = None
    name_changed: bool | None = None
    location: str | None = None

    @field_validator("requested_validity_years")
    @classmethod
    def validate_requested_validity(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value not in {5, 10}:
            raise ValueError("requested_validity_years must be 5, 10, or null")
        return value


class ScenarioParseResult(BaseModel):
    draft: ApplicantProfileDraft
    missing_fields: list[str] = Field(default_factory=list)
    parser_notes: list[str] = Field(default_factory=list)


class EligibilityDecision(BaseModel):
    permitted_validity_years: int
    required_identification: str
    age_band: str
    flags: list[str] = Field(default_factory=list)
    explanation: str


class FeeBreakdown(BaseModel):
    page_count: int
    delivery_speed: DeliverySpeed
    validity_years: int
    base_fee_bdt: int
    vat_bdt: int
    total_fee_bdt: int
    used_local_fallback: bool = True


class ChecklistResult(BaseModel):
    documents: list[str]
    flags: list[str] = Field(default_factory=list)
    explanation: str


class CrewExecution(BaseModel):
    status: str
    notes: str | None = None
    trace: str | None = None


class PassportReadinessReport(BaseModel):
    profile: ApplicantProfile
    validity_years: int
    delivery_type: DeliverySpeed
    required_identification: str
    total_fee_bdt: int
    base_fee_bdt: int
    vat_bdt: int
    documents_needed: list[str]
    flags: list[str]
    english_markdown: str
    bangla_markdown: str
    combined_markdown: str
    agent_trace: str | None = None
