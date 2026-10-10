from enum import StrEnum


class ConstructionType(StrEnum):
    NATURAL = "natural"
    HYBRID = "hybrid"
    SYNTHETIC = "synthetic"
    DROP_IN = "drop-in"
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class EvidenceType(StrEnum):
    OBSERVED = "observed"
    MEASURED = "measured"
    MODELED = "modeled"
    PROXY = "proxy"
    EXPERIMENTAL = "experimental"
