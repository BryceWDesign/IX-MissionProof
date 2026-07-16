"""Canonical evidence records and closed evidence-ledger snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.foundation import (
    ActorKind,
    ActorRegistry,
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonArray,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
    normalize_labels,
    require_text,
)


class EvidenceKind(StrEnum):
    """Kinds of material that may enter the MissionProof evidence layer."""

    OBSERVATION = "observation"
    MEASUREMENT = "measurement"
    EXECUTION_RECEIPT = "execution-receipt"
    TEST_RESULT = "test-result"
    HUMAN_REVIEW = "human-review"
    SOURCE_RECORD = "source-record"
    SIMULATION_RESULT = "simulation-result"
    POLICY_EVALUATION = "policy-evaluation"


class EvidenceOrigin(StrEnum):
    """How an evidence payload came into existence."""

    OBSERVED = "observed"
    MEASURED = "measured"
    EXECUTED = "executed"
    HUMAN_ATTESTED = "human-attested"
    IMPORTED = "imported"
    DERIVED = "derived"
    SIMULATED = "simulated"
    ASSERTED = "asserted"

    @property
    def is_primary(self) -> bool:
        """Return whether the origin records a direct event or human attestation."""

        return self in _PRIMARY_ORIGINS

    @property
    def requires_corroboration(self) -> bool:
        """Return whether the origin must not stand alone as claim support."""

        return self in _CORROBORATION_REQUIRED_ORIGINS


class EvidenceStatus(StrEnum):
    """Recorded disposition of an evidence item."""

    RECORDED = "recorded"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"
    INVALIDATED = "invalidated"

    @property
    def is_adverse(self) -> bool:
        """Return whether the record reports a negative or blocking outcome."""

        return self in {
            EvidenceStatus.FAILED,
            EvidenceStatus.BLOCKED,
            EvidenceStatus.INVALIDATED,
        }

    @property
    def is_usable(self) -> bool:
        """Return whether the record remains available for later admission review."""

        return self is not EvidenceStatus.INVALIDATED


_PRIMARY_ORIGINS: Final[frozenset[EvidenceOrigin]] = frozenset(
    {
        EvidenceOrigin.OBSERVED,
        EvidenceOrigin.MEASURED,
        EvidenceOrigin.EXECUTED,
        EvidenceOrigin.HUMAN_ATTESTED,
    }
)

_CORROBORATION_REQUIRED_ORIGINS: Final[frozenset[EvidenceOrigin]] = frozenset(
    {
        EvidenceOrigin.IMPORTED,
        EvidenceOrigin.DERIVED,
        EvidenceOrigin.SIMULATED,
        EvidenceOrigin.ASSERTED,
    }
)

_HUMAN_ACTOR_NAMESPACE: Final[CanonicalKey] = CanonicalKey("human")
_ORGANIZATION_ACTOR_NAMESPACE: Final[CanonicalKey] = CanonicalKey("organization")
_MACHINE_ACTOR_NAMESPACES: Final[frozenset[CanonicalKey]] = frozenset(
    CanonicalKey(kind.value) for kind in ActorKind if kind.is_machine
)

_ALLOWED_ORIGINS_BY_KIND: Final[dict[EvidenceKind, frozenset[EvidenceOrigin]]] = {
    EvidenceKind.OBSERVATION: frozenset({EvidenceOrigin.OBSERVED}),
    EvidenceKind.MEASUREMENT: frozenset({EvidenceOrigin.MEASURED}),
    EvidenceKind.EXECUTION_RECEIPT: frozenset({EvidenceOrigin.EXECUTED}),
    EvidenceKind.TEST_RESULT: frozenset({EvidenceOrigin.EXECUTED}),
    EvidenceKind.HUMAN_REVIEW: frozenset({EvidenceOrigin.HUMAN_ATTESTED}),
    EvidenceKind.SIMULATION_RESULT: frozenset({EvidenceOrigin.SIMULATED}),
    EvidenceKind.POLICY_EVALUATION: frozenset(
        {
            EvidenceOrigin.EXECUTED,
            EvidenceOrigin.HUMAN_ATTESTED,
        }
    ),
    EvidenceKind.SOURCE_RECORD: frozenset(EvidenceOrigin),
}

_OUTCOME_KINDS: Final[frozenset[EvidenceKind]] = frozenset(
    {
        EvidenceKind.EXECUTION_RECEIPT,
        EvidenceKind.TEST_RESULT,
        EvidenceKind.HUMAN_REVIEW,
        EvidenceKind.POLICY_EVALUATION,
    }
)


def _validate_producer_identity(
    producer_id: ScopedIdentifier,
    accountability_owner_id: ScopedIdentifier | None,
    *,
    field_prefix: str,
) -> None:
    if not isinstance(producer_id, ScopedIdentifier):
        raise FoundationError(f"{field_prefix}_id must be a ScopedIdentifier")

    if accountability_owner_id is not None:
        if not isinstance(accountability_owner_id, ScopedIdentifier):
            raise FoundationError(
                f"{field_prefix}_accountability_owner_id must be "
                "a ScopedIdentifier or None"
            )
        if accountability_owner_id.namespace != _HUMAN_ACTOR_NAMESPACE:
            raise FoundationError(
                f"{field_prefix}_accountability_owner_id must identify a human actor"
            )
        if accountability_owner_id == producer_id:
            raise FoundationError(
                f"{field_prefix} must not be its own accountability owner"
            )

    namespace = producer_id.namespace

    if namespace == _HUMAN_ACTOR_NAMESPACE:
        if accountability_owner_id is not None:
            raise FoundationError(
                f"human {field_prefix} must not declare an accountability owner"
            )
        return

    if namespace in _MACHINE_ACTOR_NAMESPACES:
        if accountability_owner_id is None:
            raise FoundationError(
                f"machine {field_prefix} must identify an accountable human owner"
            )
        return

    if namespace == _ORGANIZATION_ACTOR_NAMESPACE:
        raise FoundationError(f"organization must not act as {field_prefix}")

    raise FoundationError(
        f"{field_prefix}_id namespace is not a recognized actor kind"
    )


def _normalize_identifiers(
    values: Iterable[ScopedIdentifier],
    *,
    field_name: str,
    required_namespace: CanonicalKey | None = None,
) -> tuple[ScopedIdentifier, ...]:
    normalized: set[ScopedIdentifier] = set()

    for index, value in enumerate(values):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(
                f"{field_name}[{index}] must be a ScopedIdentifier"
            )
        if required_namespace is not None and value.namespace != required_namespace:
            raise FoundationError(
                f"{field_name}[{index}] namespace must be "
                f"{required_namespace.value}"
            )
        normalized.add(value)

    return tuple(sorted(normalized, key=str))


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """An immutable evidence item with explicit origin and claim boundary."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("evidence-record-v1")

    record_id: ScopedIdentifier
    created_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_accountability_owner_id: ScopedIdentifier | None
    kind: EvidenceKind
    origin: EvidenceOrigin
    status: EvidenceStatus
    subject_ids: tuple[ScopedIdentifier, ...]
    summary: str
    payload: CanonicalJsonDocument
    payload_digest: ContentDigest
    source_record_ids: tuple[ScopedIdentifier, ...]
    actor_registry_digest: ContentDigest
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._validate_identity()
        self._validate_types()
        self._validate_payload()

        subjects = _normalize_identifiers(
            self.subject_ids,
            field_name="subject_ids",
        )
        if not subjects:
            raise FoundationError(
                "evidence records must identify at least one subject"
            )
        object.__setattr__(self, "subject_ids", subjects)

        sources = _normalize_identifiers(
            self.source_record_ids,
            field_name="source_record_ids",
            required_namespace=CanonicalKey("record"),
        )
        if self.record_id in sources:
            raise FoundationError(
                "an evidence record must not cite itself as a source"
            )
        if self.origin.requires_corroboration and not sources:
            raise FoundationError(
                f"evidence origin {self.origin.value} requires "
                "at least one source record"
            )

        object.__setattr__(self, "source_record_ids", sources)
        object.__setattr__(
            self,
            "summary",
            require_text(
                self.summary,
                field_name="summary",
            ),
        )
        object.__setattr__(
            self,
            "labels",
            normalize_labels(
                self.labels,
                field_name="labels",
            ),
        )

        self._validate_origin_semantics()
        self._validate_status_semantics()

    def _validate_identity(self) -> None:
        if not isinstance(self.record_id, ScopedIdentifier):
            raise FoundationError(
                "record_id must be a ScopedIdentifier"
            )
        if self.record_id.namespace != CanonicalKey("record"):
            raise FoundationError(
                "record_id namespace must be record"
            )

        _validate_producer_identity(
            self.produced_by_id,
            self.producer_accountability_owner_id,
            field_prefix="producer",
        )

    def _validate_types(self) -> None:
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(self.kind, EvidenceKind):
            raise FoundationError(
                "kind must be an EvidenceKind"
            )
        if not isinstance(self.origin, EvidenceOrigin):
            raise FoundationError(
                "origin must be an EvidenceOrigin"
            )
        if not isinstance(self.status, EvidenceStatus):
            raise FoundationError(
                "status must be an EvidenceStatus"
            )

    def _validate_payload(self) -> None:
        if not isinstance(self.payload, CanonicalJsonDocument):
            raise FoundationError(
                "payload must be a CanonicalJsonDocument"
            )
        self.payload.require_object()

        if not isinstance(self.payload_digest, ContentDigest):
            raise FoundationError(
                "payload_digest must be a ContentDigest"
            )
        if self.payload_digest.domain != CanonicalKey(
            "evidence-payload"
        ):
            raise FoundationError(
                "payload_digest domain must be evidence-payload"
            )
        if not self.payload_digest.verifies(
            self.payload.to_value()
        ):
            raise FoundationError(
                "payload_digest does not match the evidence payload"
            )

        if not isinstance(
            self.actor_registry_digest,
            ContentDigest,
        ):
            raise FoundationError(
                "actor_registry_digest must be a ContentDigest"
            )
        if self.actor_registry_digest.domain != CanonicalKey(
            "actor-registry"
        ):
            raise FoundationError(
                "actor_registry_digest domain must be actor-registry"
            )

    def _validate_origin_semantics(self) -> None:
        allowed_origins = _ALLOWED_ORIGINS_BY_KIND[self.kind]

        if self.origin not in allowed_origins:
            raise FoundationError(
                f"evidence kind {self.kind.value} must not use origin "
                f"{self.origin.value}"
            )

        if (
            self.origin is EvidenceOrigin.HUMAN_ATTESTED
            and self.produced_by_id.namespace
            != _HUMAN_ACTOR_NAMESPACE
        ):
            raise FoundationError(
                "human-attested evidence must be produced "
                "by a human actor"
            )

        if (
            self.origin is EvidenceOrigin.EXECUTED
            and self.produced_by_id.namespace
            not in _MACHINE_ACTOR_NAMESPACES
        ):
            raise FoundationError(
                "executed evidence must be produced by a machine actor"
            )

    def _validate_status_semantics(self) -> None:
        if self.status in {
            EvidenceStatus.PASSED,
            EvidenceStatus.FAILED,
        }:
            if self.kind not in _OUTCOME_KINDS:
                raise FoundationError(
                    f"evidence kind {self.kind.value} must not use "
                    f"status {self.status.value}"
                )

        if (
            self.status is EvidenceStatus.BLOCKED
            and self.kind not in _OUTCOME_KINDS
        ):
            raise FoundationError(
                f"evidence kind {self.kind.value} must not use "
                "status blocked"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        kind: EvidenceKind,
        origin: EvidenceOrigin,
        status: EvidenceStatus,
        subject_ids: Iterable[ScopedIdentifier],
        summary: str,
        payload: JsonObject,
        actor_registry: ActorRegistry,
        source_record_ids: Iterable[ScopedIdentifier] = (),
        labels: Iterable[str] = (),
    ) -> EvidenceRecord:
        """Create a record after validating the producer against a registry."""

        producer = actor_registry.require_actor(
            produced_by_id
        )

        if not producer.is_active:
            raise FoundationError(
                "evidence producer must be an active actor"
            )
        if not (
            producer.is_human
            or producer.is_machine
        ):
            raise FoundationError(
                "evidence producer must be a human or "
                "executable machine actor"
            )
        if (
            producer.is_machine
            and producer.accountability_owner_id is None
        ):
            raise FoundationError(
                "machine evidence producer must identify "
                "an accountable human owner"
            )

        payload_document = CanonicalJsonDocument.from_value(
            payload
        )

        return cls(
            record_id=ScopedIdentifier.create(
                namespace="record",
                key=key,
                namespace_field="record namespace",
                key_field="record key",
            ),
            created_at=created_at,
            produced_by_id=produced_by_id,
            producer_accountability_owner_id=(
                producer.accountability_owner_id
            ),
            kind=kind,
            origin=origin,
            status=status,
            subject_ids=tuple(subject_ids),
            summary=summary,
            payload=payload_document,
            payload_digest=payload_document.digest(
                domain="evidence-payload"
            ),
            source_record_ids=tuple(
                source_record_ids
            ),
            actor_registry_digest=actor_registry.digest(),
            labels=tuple(labels),
        )

    @property
    def is_primary(self) -> bool:
        """Return whether the record captures a direct event or attestation."""

        return self.origin.is_primary

    @property
    def requires_corroboration(self) -> bool:
        """Return whether the record must not stand alone as claim support."""

        return self.origin.requires_corroboration

    @property
    def establishes_claim(self) -> bool:
        """Return false: recording evidence never independently proves a claim."""

        return False

    def concerns(
        self,
        subject_id: ScopedIdentifier,
    ) -> bool:
        """Return whether this record explicitly concerns a subject."""

        if not isinstance(
            subject_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "subject_id must be a ScopedIdentifier"
            )

        return subject_id in self.subject_ids

    def to_payload(self) -> JsonObject:
        """Return the deterministic JSON representation of this evidence record."""

        subject_payload: JsonArray = [
            str(subject_id)
            for subject_id in self.subject_ids
        ]
        source_payload: JsonArray = [
            str(record_id)
            for record_id in self.source_record_ids
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "created_at": self.created_at.isoformat(),
            "establishes_claim": self.establishes_claim,
            "is_primary": self.is_primary,
            "kind": self.kind.value,
            "labels": list(self.labels),
            "origin": self.origin.value,
            "payload": self.payload.to_value(),
            "payload_digest": self.payload_digest.to_payload(),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": (
                str(self.producer_accountability_owner_id)
                if self.producer_accountability_owner_id
                is not None
                else None
            ),
            "record_id": str(self.record_id),
            "requires_corroboration": (
                self.requires_corroboration
            ),
            "schema": self.SCHEMA.value,
            "source_record_ids": source_payload,
            "status": self.status.value,
            "subject_ids": subject_payload,
            "summary": self.summary,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical evidence-record document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete evidence record."""

        return self.to_document().digest(
            domain="evidence-record"
        )


@dataclass(frozen=True, slots=True)
class EvidenceLedger:
    """A closed deterministic evidence snapshot with resolved source links."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_accountability_owner_id: ScopedIdentifier | None
    actor_registry_digest: ContentDigest
    records: tuple[EvidenceRecord, ...]

    def __post_init__(self) -> None:
        self._validate_metadata()

        records = tuple(self.records)
        self._validate_records(records)

        ordered = tuple(
            sorted(
                records,
                key=lambda record: (
                    record.created_at.value,
                    str(record.record_id),
                ),
            )
        )

        self._validate_source_graph(ordered)

        object.__setattr__(
            self,
            "records",
            ordered,
        )

    def _validate_metadata(self) -> None:
        if not isinstance(
            self.ledger_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "ledger_id must be a ScopedIdentifier"
            )
        if self.ledger_id.namespace != CanonicalKey(
            "evidence-ledger"
        ):
            raise FoundationError(
                "ledger_id namespace must be evidence-ledger"
            )
        if not isinstance(
            self.created_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )

        _validate_producer_identity(
            self.producer_id,
            self.producer_accountability_owner_id,
            field_prefix="producer",
        )

        if not isinstance(
            self.actor_registry_digest,
            ContentDigest,
        ):
            raise FoundationError(
                "actor_registry_digest must be a ContentDigest"
            )
        if self.actor_registry_digest.domain != CanonicalKey(
            "actor-registry"
        ):
            raise FoundationError(
                "actor_registry_digest domain must be actor-registry"
            )

    def _validate_records(
        self,
        records: tuple[EvidenceRecord, ...],
    ) -> None:
        for index, record in enumerate(records):
            if not isinstance(
                record,
                EvidenceRecord,
            ):
                raise FoundationError(
                    f"records[{index}] must be an EvidenceRecord"
                )
            if (
                record.created_at.value
                > self.created_at.value
            ):
                raise FoundationError(
                    "evidence ledger must not predate "
                    "a contained record"
                )
            if (
                record.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every evidence record must bind "
                    "the same actor registry"
                )

        record_ids = tuple(
            record.record_id
            for record in records
        )
        if len(record_ids) != len(set(record_ids)):
            raise FoundationError(
                "evidence ledger must contain unique record IDs"
            )

    @staticmethod
    def _validate_source_graph(
        records: tuple[EvidenceRecord, ...],
    ) -> None:
        records_by_id = {
            record.record_id: record
            for record in records
        }
        edges: dict[
            ScopedIdentifier,
            tuple[ScopedIdentifier, ...],
        ] = {}

        for record in records:
            for source_id in record.source_record_ids:
                source = records_by_id.get(source_id)

                if source is None:
                    raise FoundationError(
                        f"evidence record {record.record_id} "
                        f"references missing source {source_id}"
                    )

                if (
                    source.created_at.value
                    > record.created_at.value
                ):
                    raise FoundationError(
                        f"evidence record {record.record_id} "
                        f"references a future source {source_id}"
                    )

            edges[
                record.record_id
            ] = record.source_record_ids

        EvidenceLedger._reject_source_cycles(
            edges
        )

    @staticmethod
    def _reject_source_cycles(
        edges: dict[
            ScopedIdentifier,
            tuple[ScopedIdentifier, ...],
        ],
    ) -> None:
        visiting: set[ScopedIdentifier] = set()
        visited: set[ScopedIdentifier] = set()

        def visit(
            record_id: ScopedIdentifier,
        ) -> None:
            if record_id in visited:
                return

            if record_id in visiting:
                raise FoundationError(
                    "evidence source graph must not contain cycles"
                )

            visiting.add(record_id)

            for source_id in edges[record_id]:
                visit(source_id)

            visiting.remove(record_id)
            visited.add(record_id)

        for record_id in edges:
            visit(record_id)

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        actor_registry: ActorRegistry,
        records: Iterable[EvidenceRecord] = (),
    ) -> EvidenceLedger:
        """Create a closed evidence-ledger snapshot."""

        producer = actor_registry.require_actor(
            producer_id
        )

        if not producer.is_active:
            raise FoundationError(
                "evidence-ledger producer must be an active actor"
            )
        if not (
            producer.is_human
            or producer.is_machine
        ):
            raise FoundationError(
                "evidence-ledger producer must be a human or "
                "executable machine actor"
            )
        if (
            producer.is_machine
            and producer.accountability_owner_id is None
        ):
            raise FoundationError(
                "machine evidence-ledger producer must identify "
                "an accountable human owner"
            )

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace="evidence-ledger",
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            producer_accountability_owner_id=(
                producer.accountability_owner_id
            ),
            actor_registry_digest=actor_registry.digest(),
            records=tuple(records),
        )

    def record_for(
        self,
        record_id: ScopedIdentifier,
    ) -> EvidenceRecord | None:
        """Return an evidence record by identifier, when present."""

        for record in self.records:
            if record.record_id == record_id:
                return record

        return None

    def require_record(
        self,
        record_id: ScopedIdentifier,
    ) -> EvidenceRecord:
        """Return an evidence record or fail when it is absent."""

        record = self.record_for(
            record_id
        )

        if record is None:
            raise FoundationError(
                "evidence ledger does not contain record: "
                f"{record_id}"
            )

        return record

    def records_for_subject(
        self,
        subject_id: ScopedIdentifier,
    ) -> tuple[EvidenceRecord, ...]:
        """Return records explicitly linked to a subject."""

        return tuple(
            record
            for record in self.records
            if record.concerns(subject_id)
        )

    def records_by_kind(
        self,
        kind: EvidenceKind,
    ) -> tuple[EvidenceRecord, ...]:
        """Return records of one evidence kind."""

        if not isinstance(
            kind,
            EvidenceKind,
        ):
            raise FoundationError(
                "kind must be an EvidenceKind"
            )

        return tuple(
            record
            for record in self.records
            if record.kind is kind
        )

    def primary_records(
        self,
    ) -> tuple[EvidenceRecord, ...]:
        """Return direct-event and human-attested records."""

        return tuple(
            record
            for record in self.records
            if record.is_primary
        )

    def records_requiring_corroboration(
        self,
    ) -> tuple[EvidenceRecord, ...]:
        """Return records that must not stand alone as claim support."""

        return tuple(
            record
            for record in self.records
            if record.requires_corroboration
        )

    def adverse_records(
        self,
    ) -> tuple[EvidenceRecord, ...]:
        """Return failed, blocked, and invalidated evidence records."""

        return tuple(
            record
            for record in self.records
            if record.status.is_adverse
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this evidence ledger."""

        record_payloads: JsonArray = [
            record.to_payload()
            for record in self.records
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "created_at": self.created_at.isoformat(),
            "ledger_id": str(self.ledger_id),
            "producer_accountability_owner_id": (
                str(self.producer_accountability_owner_id)
                if self.producer_accountability_owner_id
                is not None
                else None
            ),
            "producer_id": str(self.producer_id),
            "records": record_payloads,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical evidence-ledger document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete evidence ledger."""

        return self.to_document().digest(
            domain="evidence-ledger"
        )
