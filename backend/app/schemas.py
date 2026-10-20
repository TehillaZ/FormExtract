"""Pydantic models: what the vision model returns (RawExtraction) and what we store (Field, CommitmentRecord)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PField, field_validator

ModelSource = Literal["printed", "handwritten", "sticker", "stamp", "barcode"]
Source = ModelSource | Literal["manual"]   # "manual" = typed by a person
Confidence = Literal["high", "medium", "low"]


# ---- model output -------------------------------------------------------------------------------

class RawValue(BaseModel):
    value: str | None = None
    source: ModelSource | None = None
    highlighted: bool = False   # yellow marker on the page: the wanted value

    @field_validator("source", mode="before")
    @classmethod
    def _known_source(cls, v):
        # an unexpected label from the model must not fail the whole page
        return v if v in get_args(ModelSource) else None

    @field_validator("highlighted", mode="before")
    @classmethod
    def _bool(cls, v):
        return bool(v)


class RawExtraction(BaseModel):
    """Structured output requested from the vision model. Everything optional: null = not found."""
    template: str | None = None
    is_continuation: bool = False
    text_upside_down: bool = False
    image_unreadable: bool = False
    first_name: RawValue = PField(default_factory=RawValue)
    last_name: RawValue = PField(default_factory=RawValue)
    id_numbers: list[RawValue] = []          # every ID occurrence on the page, to cross-check
    central_numbers: list[RawValue] = []
    received_date: RawValue = PField(default_factory=RawValue)
    stamp_date: RawValue = PField(default_factory=RawValue)
    handwritten_date: RawValue = PField(default_factory=RawValue)
    sender: RawValue = PField(default_factory=RawValue)
    other_senders: list[RawValue] = []     # other HMOs/hospitals/labs visible on the page
    commitment_numbers: list[RawValue] = []

    @field_validator("first_name", "last_name", "received_date", "stamp_date", "handwritten_date", "sender", mode="before")
    @classmethod
    def _null_value(cls, v):
        if v is None:
            return {}
        return {"value": str(v)} if isinstance(v, (str, int)) else v

    @field_validator("id_numbers", "central_numbers", "commitment_numbers", "other_senders", mode="before")
    @classmethod
    def _null_list(cls, v):
        # models sometimes return null, a bare string, or strings instead of {value, source} objects
        if v is None:
            return []
        if not isinstance(v, list):
            v = [v]
        return [{"value": str(x)} if isinstance(x, (str, int)) else x for x in v]


# ---- stored record ------------------------------------------------------------------------------

class Field(BaseModel):
    value: str | None = None       # None = not found, never guessed
    raw_text: str | None = None    # what was read before normalization
    confidence: Confidence = "low"
    source: Source | None = None
    reasons: list[str] = []


class Correction(BaseModel):
    field: str
    old_value: str | None
    new_value: str | None
    at: datetime


class CommitmentRecord(BaseModel):
    id: UUID = PField(default_factory=uuid4)
    document_id: UUID | None = None
    page_numbers: list[int] = []
    page_ids: list[UUID] = []
    template: str | None = None
    provider: str | None = None
    first_name: Field = PField(default_factory=Field)
    last_name: Field = PField(default_factory=Field)
    id_number: Field = PField(default_factory=Field)
    central_numbers: list[Field] = []
    received_date: Field = PField(default_factory=Field)
    sender: Field = PField(default_factory=Field)
    commitment_numbers: list[Field] = []
    status: Literal["pending", "approved"] = "pending"
    approved_at: datetime | None = None
    corrections: list[Correction] = []
    duplicate_warnings: list[str] = []   # filled when read, never stored

    def all_fields(self) -> list[Field]:
        return [self.first_name, self.last_name, self.id_number, self.received_date, self.sender,
                *self.central_numbers, *self.commitment_numbers]

    def needs_review(self) -> bool:
        """True when any field is not high-confidence (shown orange in the UI)."""
        return any(f.confidence != "high" for f in self.all_fields())

