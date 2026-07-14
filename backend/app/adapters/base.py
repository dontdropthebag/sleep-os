"""Plugin adapter interface.

New devices are added by subclassing BaseAdapter and registering it; the
analytics engine only ever sees canonical ParsedSession objects and never
needs to change per device.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class ParseIssue:
    severity: str  # error|warning|info
    message: str
    record_ref: str | None = None


@dataclass
class ParsedSession:
    """Canonical session emitted by adapters. UTC datetimes throughout."""

    source: str
    source_session_id: str | None
    timezone_name: str
    in_bed_utc: datetime | None
    sleep_onset_utc: datetime | None
    final_wake_utc: datetime | None
    out_of_bed_utc: datetime | None
    time_in_bed_min: float | None = None
    total_sleep_min: float | None = None
    sleep_latency_min: float | None = None
    waso_min: float | None = None
    awakenings_count: int | None = None
    stage_intervals: list | None = None
    is_nap: bool = False
    user_rating: float | None = None
    comments: str | None = None
    tags: list | None = None
    snore_minutes: float | None = None
    noise_level: float | None = None
    cycles: int | None = None
    deep_sleep_fraction: float | None = None
    movement_timeline: list | None = None
    noise_timeline: list | None = None
    event_timeline: list | None = None
    field_provenance: dict = field(default_factory=dict)
    raw_payload: dict = field(default_factory=dict)  # original record, preserved
    missing_metrics: list[str] = field(default_factory=list)
    physio: list[dict] = field(default_factory=list)  # canonical physio observations


@dataclass
class ParseResult:
    source: str
    parser_version: str
    sessions: list[ParsedSession] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    extras: dict = field(default_factory=dict)  # noise metadata, prefs, etc.


class BaseAdapter:
    name: ClassVar[str] = "base"
    parser_version: ClassVar[str] = "0.0.0"

    @classmethod
    def sniff(cls, filename: str, data: bytes) -> bool:
        """Return True if this adapter can likely parse the file."""
        raise NotImplementedError

    @classmethod
    def parse(cls, filename: str, data: bytes) -> ParseResult:
        raise NotImplementedError


ADAPTERS: list[type[BaseAdapter]] = []


def register(adapter: type[BaseAdapter]) -> type[BaseAdapter]:
    ADAPTERS.append(adapter)
    return adapter


def get_adapter(filename: str, data: bytes, source_hint: str | None = None) -> type[BaseAdapter]:
    if source_hint:
        for a in ADAPTERS:
            if a.name == source_hint:
                return a
    for a in ADAPTERS:
        try:
            if a.sniff(filename, data):
                return a
        except Exception:
            continue
    raise ValueError("No adapter recognises this file. Supported: " + ", ".join(a.name for a in ADAPTERS))
