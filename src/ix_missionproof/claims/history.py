"""Temporal claim-resolution history and current claim posture."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, Final

from ix_missionproof.claims.evaluations import ClaimEvidenceEvaluation
from ix_missionproof.claims.resolutions import (
    ClaimResolution,
    ClaimResolutionSource,
    ClaimResolutionStatus,
)
from ix_missionproof.claims.specifications import ClaimCatalog, ClaimSpecification
from ix_missionproof.foundation import (
    ActorIdentity,
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
)

_HISTORY_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {ActorKind.SERVICE, ActorKind.SYSTEM}
)


def _require_identifier(
    value: ScopedIdentifier,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if not isinstance(value, ScopedIdentifier):
        raise FoundationError(f"{field_name} must be a ScopedIdentifier")
    if value.namespace != CanonicalKey(namespace):
        raise FoundationError(f"{field_name} namespace must be {namespace}")


def _require_digest(
    value: ContentDigest,
    *,
    field_name: str,
    domain: str,
) -> None:
    if not isinstance(value, ContentDigest):
        raise FoundationError(f"{field_name} must be a ContentDigest")
    if value.domain != CanonicalKey(domain):
        raise FoundationError(f"{field_name} domain must be {domain}")


def _validate_history_producer(producer: ActorIdentity) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError("claim-history producer must be active")
    if producer.kind not in _HISTORY_PRODUCER_KINDS:
        raise FoundationError(
            "claim-history producer must be a service or system actor"
        )

    owner_id = producer.accountability_owner_id
    if owner_id is None:
        raise FoundationError(
            "claim-history producer must identify an accountable human owner"
        )
    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimResolutionHistoryEntry:
    """One resolution event bound to an exact claim evidence evaluation."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-resolution-history-entry-v1"
    )

    entry_id: ScopedIdentifier
    recorded_at: UtcTimestamp
    claim_id: ScopedIdentifier
    evaluation_id: ScopedIdentifier
    evaluation_evaluated_at: UtcTimestamp
    resolution_id: ScopedIdentifier
    resolution_resolved_at: UtcTimestamp
    status: ClaimResolutionStatus
    source: ClaimResolutionSource
    claim_digest: ContentDigest
    evaluation_digest: ContentDigest
    resolution_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    decision_ledger_digest: ContentDigest
    resolution_snapshot_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        for field_name, value, namespace in (
            (
                "entry_id",
                self.entry_id,
                "claim-resolution-history-entry",
            ),
            ("claim_id", self.claim_id, "claim"),
            (
                "evaluation_id",
                self.evaluation_id,
                "claim-evidence-evaluation",
            ),
            ("resolution_id", self.resolution_id, "claim-resolution"),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        for field_name, value in (
            ("recorded_at", self.recorded_at),
            (
                "evaluation_evaluated_at",
                self.evaluation_evaluated_at,
            ),
            (
                "resolution_resolved_at",
                self.resolution_resolved_at,
            ),
        ):
            if not isinstance(value, UtcTimestamp):
                raise FoundationError(
                    f"{field_name} must be a UtcTimestamp"
                )

        if not isinstance(self.status, ClaimResolutionStatus):
            raise FoundationError(
                "status must be a ClaimResolutionStatus"
            )
        if not isinstance(self.source, ClaimResolutionSource):
            raise FoundationError(
                "source must be a ClaimResolutionSource"
            )

        for field_name, value, domain in (
            (
                "claim_digest",
                self.claim_digest,
                "claim-specification",
            ),
            (
                "evaluation_digest",
                self.evaluation_digest,
                "claim-evidence-evaluation",
            ),
            (
                "resolution_digest",
                self.resolution_digest,
                "claim-resolution",
            ),
            (
                "claim_catalog_digest",
                self.claim_catalog_digest,
                "claim-catalog",
            ),
            (
                "decision_ledger_digest",
                self.decision_ledger_digest,
                "claim-adjudication-decision-ledger",
            ),
            (
                "resolution_snapshot_digest",
                self.resolution_snapshot_digest,
                "evidence-admission-resolution-snapshot",
            ),
            (
                "evidence_ledger_digest",
                self.evidence_ledger_digest,
                "evidence-ledger",
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                "actor-registry",
            ),
        ):
            _require_digest(
                value,
                field_name=field_name,
                domain=domain,
            )

        if self.recorded_at.value < self.resolution_resolved_at.value:
            raise FoundationError(
                "claim-resolution history entry must not predate its resolution"
            )
        if (
            self.resolution_resolved_at.value
            < self.evaluation_evaluated_at.value
        ):
            raise FoundationError(
                "claim resolution must not predate its evidence evaluation"
            )

    @classmethod
    def capture(
        cls,
        *,
        key: str,
        recorded_at: UtcTimestamp,
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
        resolution: ClaimResolution,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
    ) -> ClaimResolutionHistoryEntry:
        """Capture one exact resolution event for temporal comparison."""

        cls._validate_bindings(
            claim=claim,
            evaluation=evaluation,
            resolution=resolution,
            claim_catalog=claim_catalog,
            actor_registry=actor_registry,
        )

        return cls(
            entry_id=ScopedIdentifier.create(
                namespace="claim-resolution-history-entry",
                key=key,
                namespace_field="entry namespace",
                key_field="entry key",
            ),
            recorded_at=recorded_at,
            claim_id=claim.claim_id,
            evaluation_id=evaluation.evaluation_id,
            evaluation_evaluated_at=evaluation.evaluated_at,
            resolution_id=resolution.resolution_id,
            resolution_resolved_at=resolution.resolved_at,
            status=resolution.status,
            source=resolution.source,
            claim_digest=claim.digest(),
            evaluation_digest=evaluation.digest(),
            resolution_digest=resolution.digest(),
            claim_catalog_digest=claim_catalog.digest(),
            decision_ledger_digest=resolution.decision_ledger_digest,
            resolution_snapshot_digest=(
                resolution.resolution_snapshot_digest
            ),
            evidence_ledger_digest=resolution.evidence_ledger_digest,
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
        resolution: ClaimResolution,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
    ) -> None:
        catalog_claim = claim_catalog.require_claim(claim.claim_id)
        if catalog_claim.digest() != claim.digest():
            raise FoundationError(
                "claim does not match the supplied claim catalog"
            )
        if evaluation.claim_id != claim.claim_id:
            raise FoundationError(
                "evaluation references a different claim"
            )
        if evaluation.claim_digest != claim.digest():
            raise FoundationError(
                "evaluation claim digest does not match the claim"
            )
        if evaluation.claim_catalog_id != claim_catalog.catalog_id:
            raise FoundationError(
                "evaluation references a different claim catalog"
            )
        if evaluation.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError(
                "evaluation claim-catalog digest does not match"
            )
        if resolution.claim_id != claim.claim_id:
            raise FoundationError(
                "resolution references a different claim"
            )
        if resolution.claim_digest != claim.digest():
            raise FoundationError(
                "resolution claim digest does not match the claim"
            )
        if resolution.evaluation_id != evaluation.evaluation_id:
            raise FoundationError(
                "resolution references a different evaluation"
            )
        if resolution.evaluation_digest != evaluation.digest():
            raise FoundationError(
                "resolution evaluation digest does not match"
            )
        if resolution.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError(
                "resolution claim-catalog digest does not match"
            )

        actor_registry_digest = actor_registry.digest()
        for role, digest in (
            ("claim", claim.actor_registry_digest),
            ("claim catalog", claim_catalog.actor_registry_digest),
            ("evaluation", evaluation.actor_registry_digest),
            ("resolution", resolution.actor_registry_digest),
        ):
            if digest != actor_registry_digest:
                raise FoundationError(
                    f"{role} is not bound to the supplied actor registry"
                )

    @property
    def supports_claim(self) -> bool:
        """Return whether this historical resolution supported the claim."""

        return self.status.supports_claim

    @property
    def is_terminal_for_evaluation(self) -> bool:
        """Return whether this event closed its exact evaluation."""

        return self.status.is_terminal_for_evaluation

    @property
    def requires_human_attention(self) -> bool:
        """Return whether this historical state required human attention."""

        return self.status.requires_human_attention

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because history preserves bounded resolutions only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim history never grants authority."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic history-entry representation."""

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "decision_ledger_digest": (
                self.decision_ledger_digest.to_payload()
            ),
            "entry_id": str(self.entry_id),
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "evaluated_at": self.evaluation_evaluated_at.isoformat(),
            "evaluation_digest": self.evaluation_digest.to_payload(),
            "evaluation_id": str(self.evaluation_id),
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "grants_authority": self.grants_authority,
            "is_terminal_for_evaluation": (
                self.is_terminal_for_evaluation
            ),
            "recorded_at": self.recorded_at.isoformat(),
            "requires_human_attention": (
                self.requires_human_attention
            ),
            "resolution_digest": self.resolution_digest.to_payload(),
            "resolution_id": str(self.resolution_id),
            "resolution_snapshot_digest": (
                self.resolution_snapshot_digest.to_payload()
            ),
            "resolved_at": self.resolution_resolved_at.isoformat(),
            "schema": self.SCHEMA.value,
            "source": self.source.value,
            "status": self.status.value,
            "supports_claim": self.supports_claim,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical history-entry document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete history entry."""

        return self.to_document().digest(
            domain="claim-resolution-history-entry"
        )


@dataclass(frozen=True, slots=True)
class ClaimResolutionHistory:
    """Immutable temporal history with deterministic current claim posture."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-resolution-history-v1"
    )

    history_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    claim_catalog_id: ScopedIdentifier
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest
    entries: tuple[ClaimResolutionHistoryEntry, ...]

    def __post_init__(self) -> None:
        _require_identifier(
            self.history_id,
            field_name="history_id",
            namespace="claim-resolution-history",
        )
        _require_identifier(
            self.claim_catalog_id,
            field_name="claim_catalog_id",
            namespace="claim-catalog",
        )

        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )
        if not isinstance(self.producer_kind, ActorKind):
            raise FoundationError(
                "producer_kind must be an ActorKind"
            )
        if self.producer_kind not in _HISTORY_PRODUCER_KINDS:
            raise FoundationError(
                "claim-history producer must be a service "
                "or system actor"
            )
        if self.producer_id.namespace != CanonicalKey(
            self.producer_kind.value
        ):
            raise FoundationError(
                "producer_id namespace must match producer_kind"
            )
        _require_identifier(
            self.producer_accountability_owner_id,
            field_name="producer_accountability_owner_id",
            namespace="human",
        )
        _require_digest(
            self.claim_catalog_digest,
            field_name="claim_catalog_digest",
            domain="claim-catalog",
        )
        _require_digest(
            self.actor_registry_digest,
            field_name="actor_registry_digest",
            domain="actor-registry",
        )

        entries = tuple(self.entries)
        self._validate_entries(entries)
        ordered = tuple(
            sorted(
                entries,
                key=lambda entry: (
                    entry.evaluation_evaluated_at.value,
                    entry.resolution_resolved_at.value,
                    entry.recorded_at.value,
                    str(entry.entry_id),
                ),
            )
        )
        self._validate_evaluation_sequences(ordered)
        self._validate_evaluation_time_uniqueness(ordered)
        object.__setattr__(self, "entries", ordered)

    def _validate_entries(
        self,
        entries: tuple[ClaimResolutionHistoryEntry, ...],
    ) -> None:
        for index, entry in enumerate(entries):
            if not isinstance(
                entry,
                ClaimResolutionHistoryEntry,
            ):
                raise FoundationError(
                    f"entries[{index}] must be a "
                    "ClaimResolutionHistoryEntry"
                )
            if entry.recorded_at.value > self.created_at.value:
                raise FoundationError(
                    "claim-resolution history must not predate "
                    "a contained entry"
                )
            if entry.claim_catalog_digest != self.claim_catalog_digest:
                raise FoundationError(
                    "every history entry must bind "
                    "the same claim catalog"
                )
            if entry.actor_registry_digest != self.actor_registry_digest:
                raise FoundationError(
                    "every history entry must bind "
                    "the same actor registry"
                )

        entry_ids = tuple(entry.entry_id for entry in entries)
        if len(entry_ids) != len(set(entry_ids)):
            raise FoundationError(
                "claim-resolution history must contain unique entry IDs"
            )

        resolution_ids = tuple(entry.resolution_id for entry in entries)
        if len(resolution_ids) != len(set(resolution_ids)):
            raise FoundationError(
                "claim-resolution history must contain "
                "unique resolution IDs"
            )

    @staticmethod
    def _validate_evaluation_sequences(
        entries: tuple[ClaimResolutionHistoryEntry, ...],
    ) -> None:
        latest: dict[
            ScopedIdentifier,
            ClaimResolutionHistoryEntry,
        ] = {}

        for entry in entries:
            previous = latest.get(entry.evaluation_id)
            if previous is not None:
                if (
                    previous.claim_id != entry.claim_id
                    or previous.claim_digest != entry.claim_digest
                    or previous.evaluation_digest != entry.evaluation_digest
                    or previous.evaluation_evaluated_at
                    != entry.evaluation_evaluated_at
                ):
                    raise FoundationError(
                        "resolution history for one evaluation must "
                        "preserve its claim and evaluation bindings"
                    )
                if (
                    previous.resolution_resolved_at.value
                    >= entry.resolution_resolved_at.value
                ):
                    raise FoundationError(
                        "resolutions for one evaluation must use "
                        "strictly increasing resolution times"
                    )
                if previous.is_terminal_for_evaluation:
                    raise FoundationError(
                        "terminal claim resolutions must not be replaced "
                        "for the same evidence evaluation"
                    )
            latest[entry.evaluation_id] = entry

    @staticmethod
    def _validate_evaluation_time_uniqueness(
        entries: tuple[ClaimResolutionHistoryEntry, ...],
    ) -> None:
        evaluation_times: dict[
            tuple[ScopedIdentifier, UtcTimestamp],
            ScopedIdentifier,
        ] = {}

        for entry in entries:
            key = (
                entry.claim_id,
                entry.evaluation_evaluated_at,
            )
            existing = evaluation_times.get(key)
            if (
                existing is not None
                and existing != entry.evaluation_id
            ):
                raise FoundationError(
                    "distinct evaluations of one claim must not "
                    "share the same evaluation time"
                )
            evaluation_times[key] = entry.evaluation_id

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
        entries: Iterable[ClaimResolutionHistoryEntry] = (),
    ) -> ClaimResolutionHistory:
        """Create a temporal claim-resolution history."""

        producer = actor_registry.require_actor(producer_id)
        owner_id = _validate_history_producer(producer)

        if claim_catalog.actor_registry_digest != actor_registry.digest():
            raise FoundationError(
                "claim catalog is not bound to "
                "the supplied actor registry"
            )
        if created_at.value < claim_catalog.created_at.value:
            raise FoundationError(
                "claim-resolution history must not predate "
                "the claim catalog"
            )

        return cls(
            history_id=ScopedIdentifier.create(
                namespace="claim-resolution-history",
                key=key,
                namespace_field="history namespace",
                key_field="history key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=owner_id,
            claim_catalog_id=claim_catalog.catalog_id,
            claim_catalog_digest=claim_catalog.digest(),
            actor_registry_digest=actor_registry.digest(),
            entries=tuple(entries),
        )

    def entries_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> tuple[ClaimResolutionHistoryEntry, ...]:
        """Return all temporal resolution entries for one claim."""

        return tuple(
            entry
            for entry in self.entries
            if entry.claim_id == claim_id
        )

    def entries_for_evaluation(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> tuple[ClaimResolutionHistoryEntry, ...]:
        """Return all resolution entries for one exact evaluation."""

        return tuple(
            entry
            for entry in self.entries
            if entry.evaluation_id == evaluation_id
        )

    def latest_for_evaluation(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> ClaimResolutionHistoryEntry | None:
        """Return the latest resolution entry for an evaluation."""

        entries = self.entries_for_evaluation(evaluation_id)
        return entries[-1] if entries else None

    def current_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimResolutionHistoryEntry | None:
        """Return the latest evaluated posture for one claim."""

        entries = self.entries_for_claim(claim_id)
        if not entries:
            return None

        latest_evaluated_at = max(
            entry.evaluation_evaluated_at.value
            for entry in entries
        )
        latest_evaluation_entries = tuple(
            entry
            for entry in entries
            if entry.evaluation_evaluated_at.value
            == latest_evaluated_at
        )
        return latest_evaluation_entries[-1]

    def require_current_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimResolutionHistoryEntry:
        """Return the current claim posture or fail when absent."""

        entry = self.current_for_claim(claim_id)
        if entry is None:
            raise FoundationError(
                "claim-resolution history does not contain "
                f"claim: {claim_id}"
            )
        return entry

    def is_currently_supported(
        self,
        claim_id: ScopedIdentifier,
    ) -> bool:
        """Return whether the newest evaluation is currently supported."""

        entry = self.current_for_claim(claim_id)
        return entry is not None and entry.supports_claim

    def superseded_supported_entries(
        self,
        claim_id: ScopedIdentifier,
    ) -> tuple[ClaimResolutionHistoryEntry, ...]:
        """Return historical support that is not the current posture."""

        current = self.current_for_claim(claim_id)
        return tuple(
            entry
            for entry in self.entries_for_claim(claim_id)
            if entry.supports_claim
            and (
                current is None
                or entry.entry_id != current.entry_id
            )
        )

    def claims_requiring_attention(
        self,
    ) -> tuple[ScopedIdentifier, ...]:
        """Return claims whose newest evaluated posture requires attention."""

        claim_ids = {entry.claim_id for entry in self.entries}
        requiring_attention = {
            claim_id
            for claim_id in claim_ids
            if self.require_current_for_claim(
                claim_id
            ).requires_human_attention
        }
        return tuple(sorted(requiring_attention, key=str))

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because history is not absolute truth."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim history never grants authority."""

        return False

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic claim-history representation."""

        entry_payloads: JsonArray = [
            entry.to_payload()
            for entry in self.entries
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_catalog_id": str(self.claim_catalog_id),
            "created_at": self.created_at.isoformat(),
            "entries": entry_payloads,
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "grants_authority": self.grants_authority,
            "history_id": str(self.history_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical claim-history document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete claim history."""

        return self.to_document().digest(
            domain="claim-resolution-history"
        )
