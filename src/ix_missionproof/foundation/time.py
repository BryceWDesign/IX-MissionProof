"""UTC-only timestamp primitives for replayable MissionProof records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from ix_missionproof.foundation.errors import FoundationError
from ix_missionproof.foundation.text import require_text

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(UTC)


def require_utc(value: datetime, *, field_name: str) -> datetime:
    """Require an aware datetime and normalize it to UTC."""

    if not isinstance(value, datetime):
        raise FoundationError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise FoundationError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True, order=True)
class UtcTimestamp:
    """A normalized UTC timestamp with a canonical RFC 3339 representation."""

    value: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            require_utc(self.value, field_name="timestamp"),
        )

    @classmethod
    def now(cls, *, clock: Clock = utc_now) -> UtcTimestamp:
        """Capture the current time through an injectable clock."""

        return cls(require_utc(clock(), field_name="clock result"))

    @classmethod
    def parse(cls, value: str, *, field_name: str = "timestamp") -> UtcTimestamp:
        """Parse an RFC 3339/ISO 8601 timestamp and normalize it to UTC."""

        normalized = require_text(value, field_name=field_name)
        candidate = f"{normalized[:-1]}+00:00" if normalized.endswith(("Z", "z")) else normalized
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as error:
            raise FoundationError(f"{field_name} must be a valid ISO 8601 timestamp") from error
        return cls(require_utc(parsed, field_name=field_name))

    def isoformat(self) -> str:
        """Return a stable UTC representation ending in ``Z``."""

        return self.value.isoformat().replace("+00:00", "Z")

    def __str__(self) -> str:
        return self.isoformat()
