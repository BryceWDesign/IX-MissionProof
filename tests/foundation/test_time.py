"""Tests for UTC-only timestamp primitives."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ix_missionproof.foundation import FoundationError, UtcTimestamp, require_utc


def test_utc_timestamp_normalizes_offsets() -> None:
    eastern = timezone(timedelta(hours=-5))
    timestamp = UtcTimestamp(datetime(2026, 7, 14, 12, 30, tzinfo=eastern))

    assert timestamp.value == datetime(2026, 7, 14, 17, 30, tzinfo=UTC)
    assert timestamp.isoformat() == "2026-07-14T17:30:00Z"


def test_utc_timestamp_parse_round_trips_canonical_text() -> None:
    timestamp = UtcTimestamp.parse("2026-07-14T17:30:00.125Z")

    assert str(timestamp) == "2026-07-14T17:30:00.125000Z"
    assert UtcTimestamp.parse(str(timestamp)) == timestamp


def test_utc_timestamp_now_uses_injected_clock() -> None:
    expected = datetime(2026, 7, 14, 17, 30, tzinfo=UTC)

    assert UtcTimestamp.now(clock=lambda: expected).value == expected


def test_require_utc_rejects_naive_datetimes() -> None:
    with pytest.raises(FoundationError, match="timezone-aware"):
        require_utc(datetime(2026, 7, 14, 17, 30), field_name="observed_at")
