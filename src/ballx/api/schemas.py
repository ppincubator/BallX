import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ballx.domain.types import ConstructionType

Confidence = Annotated[Decimal, Field(ge=0, le=1, max_digits=5, decimal_places=4)]
Name = Annotated[str, Field(min_length=1, max_length=255)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)


class GroundFields(StrictSchema):
    name: Name
    aliases: list[Name] = Field(default_factory=list, max_length=100)
    latitude: Annotated[Decimal, Field(ge=-90, le=90, decimal_places=7)] | None = None
    longitude: Annotated[Decimal, Field(ge=-180, le=180, decimal_places=7)] | None = None
    timezone: str | None = Field(default=None, max_length=128)
    owner_id: uuid.UUID | None = None
    operator_id: uuid.UUID | None = None
    association_id: uuid.UUID | None = None
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def coordinate_pair(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both latitude and longitude, or leave both unknown")
        return self

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Use a valid IANA timezone") from exc
        return value


class GroundCreate(GroundFields):
    evidence_id: uuid.UUID


class GroundRead(GroundFields):
    id: uuid.UUID
    created_at: datetime


class PitchFields(StrictSchema):
    ground_id: uuid.UUID
    local_strip_identifier: str | None = Field(default=None, min_length=1, max_length=128)
    construction_type: ConstructionType | None = None
    identity_confidence: Confidence | None = None
    evidence_id: uuid.UUID


class PitchCreate(PitchFields):
    """Only submit a distinct physical strip supported by reviewed identity evidence."""


class PitchRead(PitchFields):
    id: uuid.UUID
    created_at: datetime


class ProvenanceRead(StrictSchema):
    id: uuid.UUID
    evidence_id: uuid.UUID
    field_name: str
    asserted_value: object
    created_at: datetime
