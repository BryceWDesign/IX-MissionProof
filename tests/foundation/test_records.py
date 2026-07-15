"""Tests for canonical integrity-checked record envelopes."""

import pytest

from ix_missionproof.foundation import (
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonArray,
    JsonObject,
    RecordEnvelope,
    ScopedIdentifier,
    UtcTimestamp,
)


def _identifier(namespace: str, key: str) -> ScopedIdentifier:
    return ScopedIdentifier.create(namespace=namespace, key=key)


def test_record_envelope_captures_payload_without_retaining_mutable_input() -> None:
    evidence: JsonArray = ["test-result"]
    payload: JsonObject = {
        "approved": False,
        "evidence": evidence,
    }

    envelope = RecordEnvelope.create(
        record_id=_identifier("record", "claim-0001"),
        record_type="assurance claim",
        created_at=UtcTimestamp.parse("2026-07-14T18:00:00Z"),
        producer_id=_identifier("actor", "claim-engine"),
        payload=payload,
        subject_ids=(_identifier("system", "agent-alpha"),),
        correlation_id=_identifier("run", "run-0042"),
        labels=(" Evidence ", "Review", "evidence"),
    )

    evidence.append("later-mutation")

    assert envelope.record_type == CanonicalKey("assurance-claim")
    assert envelope.payload.require_object() == {
        "approved": False,
        "evidence": ["test-result"],
    }
    assert envelope.labels == ("evidence", "review")
    assert envelope.verify_integrity() is True


def test_record_envelope_has_deterministic_complete_representation() -> None:
    envelope = RecordEnvelope.create(
        record_id=_identifier("record", "decision-0001"),
        record_type="authority decision",
        created_at=UtcTimestamp.parse("2026-07-14T18:05:00Z"),
        producer_id=_identifier("human-reviewer", "reviewer-01"),
        payload={"decision": "defer", "reason": "missing evidence"},
        subject_ids=(
            _identifier("claim", "claim-0001"),
            _identifier("system", "agent-alpha"),
        ),
        correlation_id=_identifier("run", "run-0042"),
        causation_id=_identifier("record", "request-0001"),
        labels=("authority", "human review"),
    )

    assert envelope.canonical_payload() == {
        "causation_id": "record:request-0001",
        "correlation_id": "run:run-0042",
        "created_at": "2026-07-14T18:05:00Z",
        "labels": ["authority", "human review"],
        "payload": {
            "decision": "defer",
            "reason": "missing evidence",
        },
        "payload_digest": envelope.payload_digest.to_payload(),
        "producer_id": "human-reviewer:reviewer-01",
        "record_id": "record:decision-0001",
        "record_type": "authority-decision",
        "schema": "record-envelope-v1",
        "subject_ids": [
            "claim:claim-0001",
            "system:agent-alpha",
        ],
    }
    assert envelope.to_document() == CanonicalJsonDocument.from_value(
        envelope.canonical_payload()
    )


def test_record_digest_covers_envelope_metadata_not_only_payload() -> None:
    common_payload: JsonObject = {"status": "recorded"}
    first = RecordEnvelope.create(
        record_id=_identifier("record", "first"),
        record_type="observation",
        created_at=UtcTimestamp.parse("2026-07-14T18:10:00Z"),
        producer_id=_identifier("sensor", "sensor-01"),
        payload=common_payload,
    )
    second = RecordEnvelope.create(
        record_id=_identifier("record", "second"),
        record_type="observation",
        created_at=UtcTimestamp.parse("2026-07-14T18:10:00Z"),
        producer_id=_identifier("sensor", "sensor-01"),
        payload=common_payload,
    )

    assert first.payload_digest == second.payload_digest
    assert first.digest() != second.digest()


def test_record_envelope_rejects_mismatched_payload_digest() -> None:
    payload = CanonicalJsonDocument.from_value({"status": "recorded"})
    incorrect_digest = ContentDigest.from_payload(
        {"status": "different"},
        domain="record-payload",
    )

    with pytest.raises(
        FoundationError,
        match="payload_digest does not match the record payload",
    ):
        RecordEnvelope(
            schema=CanonicalKey("record-envelope-v1"),
            record_id=_identifier("record", "observation-0001"),
            record_type=CanonicalKey("observation"),
            created_at=UtcTimestamp.parse("2026-07-14T18:15:00Z"),
            producer_id=_identifier("sensor", "sensor-01"),
            payload=payload,
            payload_digest=incorrect_digest,
        )


def test_record_envelope_rejects_duplicate_subjects() -> None:
    subject = _identifier("system", "agent-alpha")

    with pytest.raises(
        FoundationError,
        match="subject_ids must not contain duplicates",
    ):
        RecordEnvelope.create(
            record_id=_identifier("record", "finding-0001"),
            record_type="finding",
            created_at=UtcTimestamp.parse("2026-07-14T18:20:00Z"),
            producer_id=_identifier("sentinel", "safety-sentinel"),
            payload={"finding": "unsupported claim"},
            subject_ids=(subject, subject),
        )


def test_record_envelope_rejects_self_causation() -> None:
    record_id = _identifier("record", "decision-0001")

    with pytest.raises(
        FoundationError,
        match="must not identify itself as its cause",
    ):
        RecordEnvelope.create(
            record_id=record_id,
            record_type="authority decision",
            created_at=UtcTimestamp.parse("2026-07-14T18:25:00Z"),
            producer_id=_identifier("human-reviewer", "reviewer-01"),
            payload={"decision": "defer"},
            causation_id=record_id,
        )
