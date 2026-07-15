"""Canonical integrity-checked record envelopes for MissionProof domains."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_missionproof.foundation.digests import ContentDigest
from ix_missionproof.foundation.documents import CanonicalJsonDocument
from ix_missionproof.foundation.errors import FoundationError
from ix_missionproof.foundation.identifiers import CanonicalKey, ScopedIdentifier
from ix_missionproof.foundation.serialization import JsonObject, JsonValue
from ix_missionproof.foundation.text import normalize_labels
from ix_missionproof.foundation.time import UtcTimestamp

_RECORD_ENVELOPE_SCHEMA = CanonicalKey("record-envelope-v1")
_RECORD_ENVELOPE_DOMAIN = CanonicalKey("record-envelope")
_RECORD_PAYLOAD_DOMAIN = CanonicalKey("record-payload")


def _normalize_subject_ids(
    values: Iterable[ScopedIdentifier],
) -> tuple[ScopedIdentifier, ...]:
    normalized = tuple(values)
    for index, value in enumerate(normalized):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(f"subject_ids[{index}] must be a ScopedIdentifier")
    if len(normalized) != len(set(normalized)):
        raise FoundationError("subject_ids must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class RecordEnvelope:
    """An immutable record whose payload and complete envelope are reproducible."""

    schema: CanonicalKey
    record_id: ScopedIdentifier
    record_type: CanonicalKey
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    payload: CanonicalJsonDocument
    payload_digest: ContentDigest
    subject_ids: tuple[ScopedIdentifier, ...] = ()
    correlation_id: ScopedIdentifier | None = None
    causation_id: ScopedIdentifier | None = None
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema != _RECORD_ENVELOPE_SCHEMA:
            raise FoundationError(
                f"record schema must be {_RECORD_ENVELOPE_SCHEMA.value}"
            )
        if not isinstance(self.record_id, ScopedIdentifier):
            raise FoundationError("record_id must be a ScopedIdentifier")
        if not isinstance(self.record_type, CanonicalKey):
            raise FoundationError("record_type must be a CanonicalKey")
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError("producer_id must be a ScopedIdentifier")
        if not isinstance(self.payload, CanonicalJsonDocument):
            raise FoundationError("payload must be a CanonicalJsonDocument")
        if not isinstance(self.payload_digest, ContentDigest):
            raise FoundationError("payload_digest must be a ContentDigest")
        if self.payload_digest.domain != _RECORD_PAYLOAD_DOMAIN:
            raise FoundationError(
                f"payload_digest domain must be {_RECORD_PAYLOAD_DOMAIN.value}"
            )
        if not self.payload_digest.verifies(self.payload.to_value()):
            raise FoundationError("payload_digest does not match the record payload")
        if self.correlation_id is not None and not isinstance(
            self.correlation_id,
            ScopedIdentifier,
        ):
            raise FoundationError("correlation_id must be a ScopedIdentifier or None")
        if self.causation_id is not None and not isinstance(
            self.causation_id,
            ScopedIdentifier,
        ):
            raise FoundationError("causation_id must be a ScopedIdentifier or None")
        if self.causation_id == self.record_id:
            raise FoundationError("a record must not identify itself as its cause")

        object.__setattr__(
            self,
            "subject_ids",
            _normalize_subject_ids(self.subject_ids),
        )
        object.__setattr__(
            self,
            "labels",
            normalize_labels(self.labels, field_name="labels"),
        )

    @classmethod
    def create(
        cls,
        *,
        record_id: ScopedIdentifier,
        record_type: CanonicalKey | str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        payload: JsonValue,
        subject_ids: Iterable[ScopedIdentifier] = (),
        correlation_id: ScopedIdentifier | None = None,
        causation_id: ScopedIdentifier | None = None,
        labels: Iterable[str] = (),
    ) -> RecordEnvelope:
        """Capture a payload and its provenance metadata as one immutable record."""

        canonical_record_type = (
            record_type
            if isinstance(record_type, CanonicalKey)
            else CanonicalKey.from_text(record_type, field_name="record_type")
        )
        document = CanonicalJsonDocument.from_value(payload)
        return cls(
            schema=_RECORD_ENVELOPE_SCHEMA,
            record_id=record_id,
            record_type=canonical_record_type,
            created_at=created_at,
            producer_id=producer_id,
            payload=document,
            payload_digest=document.digest(domain=_RECORD_PAYLOAD_DOMAIN),
            subject_ids=tuple(subject_ids),
            correlation_id=correlation_id,
            causation_id=causation_id,
            labels=tuple(labels),
        )

    def verify_integrity(self) -> bool:
        """Return whether the stored payload digest still matches the payload."""

        return self.payload_digest.verifies(self.payload.to_value())

    def canonical_payload(self) -> JsonObject:
        """Return the complete deterministic record representation."""

        return {
            "causation_id": (
                str(self.causation_id) if self.causation_id is not None else None
            ),
            "correlation_id": (
                str(self.correlation_id)
                if self.correlation_id is not None
                else None
            ),
            "created_at": self.created_at.isoformat(),
            "labels": list(self.labels),
            "payload": self.payload.to_value(),
            "payload_digest": self.payload_digest.to_payload(),
            "producer_id": str(self.producer_id),
            "record_id": str(self.record_id),
            "record_type": self.record_type.value,
            "schema": self.schema.value,
            "subject_ids": [str(subject_id) for subject_id in self.subject_ids],
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical representation of the full envelope."""

        return CanonicalJsonDocument.from_value(self.canonical_payload())

    def digest(self) -> ContentDigest:
        """Return a domain-separated digest covering the complete envelope."""

        return self.to_document().digest(domain=_RECORD_ENVELOPE_DOMAIN)
