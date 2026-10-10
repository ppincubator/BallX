"""Pure parsing contracts. Collection and normalization need separate reviewed workflows."""

import hashlib
import uuid
from collections.abc import Iterable
from typing import Any, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

from ballx.domain.types import EvidenceType


class SourceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: uuid.UUID
    source_url: HttpUrl
    retrieved_at: AwareDatetime
    media_type: str = Field(min_length=1, max_length=255)
    original_locator: str | None = None
    adapter_name: str = Field(min_length=1, max_length=255)
    adapter_version: str = Field(min_length=1, max_length=64)
    payload: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


class EvidenceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_locator: str = Field(min_length=1)
    excerpt_or_measurement: dict[str, Any]
    evidence_type: EvidenceType
    published_at: AwareDatetime | None = None


class IngestionAdapter(Protocol):
    name: str
    version: str

    def parse(self, snapshot: SourceSnapshot) -> Iterable[EvidenceDraft]: ...


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, IngestionAdapter] = {}

    def register(self, adapter: IngestionAdapter) -> None:
        if not adapter.name or not adapter.version:
            raise ValueError("Adapters require a name and version")
        if adapter.name in self._adapters:
            raise ValueError(f"Adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> IngestionAdapter:
        return self._adapters[name]
