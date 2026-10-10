import pytest

from ballx.domain.types import EvidenceType
from ballx.ingestion.contracts import AdapterRegistry, EvidenceDraft


class SyntheticAdapter:
    name = "synthetic-test"
    version = "1"

    def parse(self, snapshot):
        yield EvidenceDraft(
            original_locator="fixture/row/1",
            excerpt_or_measurement={"model_grid_value": 0.2},
            evidence_type=EvidenceType.MODELED,
        )


def test_adapter_registration_and_evidence_classification():
    registry = AdapterRegistry()
    adapter = SyntheticAdapter()
    registry.register(adapter)
    result = list(registry.get(adapter.name).parse(None))
    assert result[0].evidence_type == EvidenceType.MODELED
    with pytest.raises(ValueError, match="already registered"):
        registry.register(adapter)
    with pytest.raises(KeyError):
        registry.get("absent")


def test_adapter_version_is_required():
    adapter = SyntheticAdapter()
    adapter.version = ""
    with pytest.raises(ValueError, match="name and version"):
        AdapterRegistry().register(adapter)
