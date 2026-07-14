"""Provenance vocabulary.

Every metric in the system carries a `MeasurementKind` so the UI can always
distinguish directly-measured data, device estimates, self-reports, values the
system derived, and experimental predictions. Nothing estimated may be
presented as a clinical measurement.
"""

import enum


class MeasurementKind(str, enum.Enum):
    MEASURED = "measured"  # directly measured by a sensor
    DEVICE_ESTIMATED = "device_estimated"  # derived on-device by opaque firmware
    SELF_REPORTED = "self_reported"  # entered by the user
    SYSTEM_DERIVED = "system_derived"  # computed by this application
    EXPERIMENTAL = "experimental"  # experimental prediction, low trust


class Confidence(str, enum.Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT = "insufficient_data"


class Source(str, enum.Enum):
    SLEEP_AS_ANDROID = "sleep_as_android"
    OURA = "oura"
    WHOOP = "whoop"
    HEALTH_CONNECT = "health_connect"
    GENERIC_CSV = "generic_csv"
    GENERIC_JSON = "generic_json"
    MANUAL = "manual"


def field_meta(
    original_field: str,
    unit: str | None,
    kind: MeasurementKind,
    confidence: Confidence = Confidence.MODERATE,
) -> dict:
    """Provenance record stored per canonical field on every imported metric."""
    return {
        "original_field": original_field,
        "unit": unit,
        "kind": kind.value,
        "confidence": confidence.value,
    }
