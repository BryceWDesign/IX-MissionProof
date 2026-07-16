"""Tamper-evident chains of claim-alert lifecycle snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.lifecycles import (
    ClaimPostureAlertLifecycleSnapshot,
    ClaimPostureAlertLifecycleSnapshotStatus,
)
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

_CHAIN_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleChainStatus(StrEnum):
    """Current aggregate state of a lifecycle chain."""

    EMPTY = "empty"
    CLEAR = "clear"
    ACTIVE = "active"

    @property
    def has_active_alerts(self) -> bool:
        """Return whether the latest generation contains active alerts."""

        return self is ClaimPostureAlertLifecycleChainStatus.ACTIVE


def _require_identifier(
    value: ScopedIdentifier,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if not isinstance(value, ScopedIdentifier):
        raise FoundationError(
            f"{field_name} must be a ScopedIdentifier"
        )
    if value.namespace != CanonicalKey(namespace):
        raise FoundationError(
            f"{field_name} namespace must be {namespace}"
        )


def _require_optional_identifier(
    value: ScopedIdentifier | None,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if value is None:
        return

    _require_identifier(
        value,
        field_name=field_name,
        namespace=namespace,
    )


def _require_digest(
    value: ContentDigest,
    *,
    field_name: str,
    domain: str,
) -> None:
    if not isinstance(value, ContentDigest):
        raise FoundationError(
            f"{field_name} must be a ContentDigest"
        )
    if value.domain != CanonicalKey(domain):
        raise FoundationError(
            f"{field_name} domain must be {domain}"
        )


def _require_optional_digest(
    value: ContentDigest | None,
    *,
    field_name: str,
    domain: str,
) -> None:
    if value is None:
        return

    _require_digest(
        value,
        field_name=field_name,
        domain=domain,
    )


def _validate_chain_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "lifecycle-chain producer must be active"
        )
    if producer.kind not in _CHAIN_PRODUCER_KINDS:
        raise FoundationError(
            "lifecycle-chain producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "lifecycle-chain producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleChainEntry:
    """One hash-linked claim-alert lifecycle generation."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-chain-entry-v1"
    )

    entry_id: ScopedIdentifier
    sequence_number: int
    linked_at: UtcTimestamp
    snapshot: ClaimPostureAlertLifecycleSnapshot
    predecessor_entry_id: ScopedIdentifier | None
    predecessor_entry_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        _require_identifier(
            self.entry_id,
            field_name="entry_id",
            namespace="claim-posture-alert-lifecycle-chain-entry",
        )
        _require_optional_identifier(
            self.predecessor_entry_id,
            field_name="predecessor_entry_id",
            namespace="claim-posture-alert-lifecycle-chain-entry",
        )

        if isinstance(
            self.sequence_number,
            bool,
        ) or not isinstance(
            self.sequence_number,
            int,
        ):
            raise FoundationError(
                "sequence_number must be an integer"
            )
        if self.sequence_number < 1:
            raise FoundationError(
                "sequence_number must be at least one"
            )
        if not isinstance(
            self.linked_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "linked_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.snapshot,
            ClaimPostureAlertLifecycleSnapshot,
        ):
            raise FoundationError(
                "snapshot must be a "
                "ClaimPostureAlertLifecycleSnapshot"
            )

        _require_optional_digest(
            self.predecessor_entry_digest,
            field_name="predecessor_entry_digest",
            domain="claim-posture-alert-lifecycle-chain-entry",
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

        predecessor_present = (
            self.predecessor_entry_id is not None
            and self.predecessor_entry_digest is not None
        )
        predecessor_absent = (
            self.predecessor_entry_id is None
            and self.predecessor_entry_digest is None
        )

        if not predecessor_present and not predecessor_absent:
            raise FoundationError(
                "predecessor entry ID and digest must be "
                "present or absent together"
            )
        if self.sequence_number == 1 and not predecessor_absent:
            raise FoundationError(
                "first lifecycle-chain entry must not "
                "declare a predecessor"
            )
        if self.sequence_number > 1 and not predecessor_present:
            raise FoundationError(
                "noninitial lifecycle-chain entry requires "
                "a predecessor"
            )
        if self.linked_at.value < self.snapshot.compared_at.value:
            raise FoundationError(
                "lifecycle-chain entry must not predate "
                "its lifecycle snapshot"
            )
        if (
            self.claim_catalog_digest
            != self.snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "lifecycle-chain entry claim-catalog digest "
                "does not match its snapshot"
            )
        if (
            self.actor_registry_digest
            != self.snapshot.actor_registry_digest
        ):
            raise FoundationError(
                "lifecycle-chain entry actor-registry digest "
                "does not match its snapshot"
            )

    @classmethod
    def link(
        cls,
        *,
        key: str,
        linked_at: UtcTimestamp,
        snapshot: ClaimPostureAlertLifecycleSnapshot,
        previous: ClaimPostureAlertLifecycleChainEntry | None = None,
    ) -> ClaimPostureAlertLifecycleChainEntry:
        """Link one lifecycle generation to its exact predecessor."""

        if previous is None:
            sequence_number = 1
            predecessor_entry_id = None
            predecessor_entry_digest = None
        else:
            cls._validate_successor(
                linked_at=linked_at,
                snapshot=snapshot,
                previous=previous,
            )
            sequence_number = previous.sequence_number + 1
            predecessor_entry_id = previous.entry_id
            predecessor_entry_digest = previous.digest()

        return cls(
            entry_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-chain-entry"
                ),
                key=key,
                namespace_field="entry namespace",
                key_field="entry key",
            ),
            sequence_number=sequence_number,
            linked_at=linked_at,
            snapshot=snapshot,
            predecessor_entry_id=predecessor_entry_id,
            predecessor_entry_digest=predecessor_entry_digest,
            claim_catalog_digest=(
                snapshot.claim_catalog_digest
            ),
            actor_registry_digest=(
                snapshot.actor_registry_digest
            ),
        )

    @staticmethod
    def _validate_successor(
        *,
        linked_at: UtcTimestamp,
        snapshot: ClaimPostureAlertLifecycleSnapshot,
        previous: ClaimPostureAlertLifecycleChainEntry,
    ) -> None:
        if (
            snapshot.claim_catalog_digest
            != previous.claim_catalog_digest
        ):
            raise FoundationError(
                "lifecycle-chain generations must bind "
                "the same claim catalog"
            )
        if (
            snapshot.actor_registry_digest
            != previous.actor_registry_digest
        ):
            raise FoundationError(
                "lifecycle-chain generations must bind "
                "the same actor registry"
            )
        if (
            snapshot.prior_docket_id
            != previous.snapshot.current_docket_id
        ):
            raise FoundationError(
                "next lifecycle snapshot must begin with "
                "the previous current alert docket"
            )
        if (
            snapshot.prior_docket_digest
            != previous.snapshot.current_docket_digest
        ):
            raise FoundationError(
                "next lifecycle snapshot prior-docket digest "
                "must match the previous current docket"
            )
        if (
            snapshot.compared_at.value
            <= previous.snapshot.compared_at.value
        ):
            raise FoundationError(
                "lifecycle snapshots must use strictly "
                "increasing comparison times"
            )
        if linked_at.value <= previous.linked_at.value:
            raise FoundationError(
                "lifecycle-chain entries must use strictly "
                "increasing link times"
            )
        if linked_at.value < snapshot.compared_at.value:
            raise FoundationError(
                "lifecycle-chain entry must not predate "
                "its lifecycle snapshot"
            )

    @property
    def snapshot_id(self) -> ScopedIdentifier:
        """Return the bound lifecycle snapshot identity."""

        return self.snapshot.snapshot_id

    @property
    def prior_docket_id(self) -> ScopedIdentifier:
        """Return the generation's prior alert docket identity."""

        return self.snapshot.prior_docket_id

    @property
    def current_docket_id(self) -> ScopedIdentifier:
        """Return the generation's current alert docket identity."""

        return self.snapshot.current_docket_id

    @property
    def prior_docket_digest(self) -> ContentDigest:
        """Return the generation's prior alert docket digest."""

        return self.snapshot.prior_docket_digest

    @property
    def current_docket_digest(self) -> ContentDigest:
        """Return the generation's current alert docket digest."""

        return self.snapshot.current_docket_digest

    @property
    def active_alert_count(self) -> int:
        """Return active alerts in this lifecycle generation."""

        return self.snapshot.active_count

    @property
    def has_active_alerts(self) -> bool:
        """Return whether this generation contains active alerts."""

        return self.snapshot.has_active_alerts

    @property
    def silent_drop_count(self) -> int:
        """Return silently dropped alerts, which must remain zero."""

        return self.snapshot.silent_drop_count

    @property
    def changes_claim_state(self) -> bool:
        """Return false because lifecycle chaining is reporting only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because lifecycle chaining grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic lifecycle-chain entry."""

        return {
            "active_alert_count": self.active_alert_count,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
            ),
            "current_docket_id": str(
                self.current_docket_id
            ),
            "entry_id": str(self.entry_id),
            "grants_authority": self.grants_authority,
            "has_active_alerts": self.has_active_alerts,
            "linked_at": self.linked_at.isoformat(),
            "predecessor_entry_digest": (
                self.predecessor_entry_digest.to_payload()
                if self.predecessor_entry_digest is not None
                else None
            ),
            "predecessor_entry_id": (
                str(self.predecessor_entry_id)
                if self.predecessor_entry_id is not None
                else None
            ),
            "prior_docket_digest": (
                self.prior_docket_digest.to_payload()
            ),
            "prior_docket_id": str(
                self.prior_docket_id
            ),
            "schema": self.SCHEMA.value,
            "sequence_number": self.sequence_number,
            "silent_drop_count": self.silent_drop_count,
            "snapshot": self.snapshot.canonical_payload(),
            "snapshot_id": str(self.snapshot_id),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical chain-entry document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the entry and predecessor link."""

        return self.to_document().digest(
            domain="claim-posture-alert-lifecycle-chain-entry"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleChain:
    """Immutable linear chain of claim-alert lifecycle generations."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-chain-v1"
    )

    chain_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest
    entries: tuple[ClaimPostureAlertLifecycleChainEntry, ...]

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        entries = tuple(
            self.entries
        )
        self._validate_entries(
            entries
        )

        ordered = tuple(
            sorted(
                entries,
                key=lambda entry: entry.sequence_number,
            )
        )
        self._validate_chain(
            ordered
        )

        object.__setattr__(
            self,
            "entries",
            ordered,
        )

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.chain_id,
            field_name="chain_id",
            namespace="claim-posture-alert-lifecycle-chain",
        )

        if not isinstance(
            self.created_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.producer_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )
        if not isinstance(
            self.producer_kind,
            ActorKind,
        ):
            raise FoundationError(
                "producer_kind must be an ActorKind"
            )
        if self.producer_kind not in _CHAIN_PRODUCER_KINDS:
            raise FoundationError(
                "lifecycle-chain producer must be "
                "a service or system actor"
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

    def _validate_digests(self) -> None:
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

    def _validate_entries(
        self,
        entries: tuple[
            ClaimPostureAlertLifecycleChainEntry,
            ...,
        ],
    ) -> None:
        for index, entry in enumerate(
            entries
        ):
            if not isinstance(
                entry,
                ClaimPostureAlertLifecycleChainEntry,
            ):
                raise FoundationError(
                    f"entries[{index}] must be a "
                    "ClaimPostureAlertLifecycleChainEntry"
                )
            if entry.linked_at.value > self.created_at.value:
                raise FoundationError(
                    "lifecycle chain must not predate "
                    "a contained entry"
                )
            if (
                entry.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every lifecycle-chain entry must bind "
                    "the same claim catalog"
                )
            if (
                entry.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every lifecycle-chain entry must bind "
                    "the same actor registry"
                )

        entry_ids = tuple(
            entry.entry_id
            for entry in entries
        )
        if len(entry_ids) != len(
            set(entry_ids)
        ):
            raise FoundationError(
                "lifecycle chain must contain "
                "unique entry IDs"
            )

        snapshot_ids = tuple(
            entry.snapshot_id
            for entry in entries
        )
        if len(snapshot_ids) != len(
            set(snapshot_ids)
        ):
            raise FoundationError(
                "lifecycle chain must contain "
                "unique lifecycle snapshot IDs"
            )

    @staticmethod
    def _validate_chain(
        entries: tuple[
            ClaimPostureAlertLifecycleChainEntry,
            ...,
        ],
    ) -> None:
        if not entries:
            return

        expected_sequences = tuple(
            range(
                1,
                len(entries) + 1,
            )
        )
        actual_sequences = tuple(
            entry.sequence_number
            for entry in entries
        )

        if actual_sequences != expected_sequences:
            raise FoundationError(
                "lifecycle-chain sequence numbers must be "
                "contiguous and begin at one"
            )

        first = entries[0]

        if (
            first.predecessor_entry_id is not None
            or first.predecessor_entry_digest is not None
        ):
            raise FoundationError(
                "first lifecycle-chain entry must not "
                "declare a predecessor"
            )

        docket_path = [
            first.prior_docket_id,
            first.current_docket_id,
        ]

        for previous, current in zip(
            entries,
            entries[1:],
            strict=False,
        ):
            if current.predecessor_entry_id != previous.entry_id:
                raise FoundationError(
                    "lifecycle-chain predecessor identity "
                    "does not match the preceding entry"
                )
            if (
                current.predecessor_entry_digest
                != previous.digest()
            ):
                raise FoundationError(
                    "lifecycle-chain predecessor digest "
                    "does not match the preceding entry"
                )
            if (
                current.prior_docket_id
                != previous.current_docket_id
            ):
                raise FoundationError(
                    "lifecycle chain contains "
                    "a docket continuity gap or fork"
                )
            if (
                current.prior_docket_digest
                != previous.current_docket_digest
            ):
                raise FoundationError(
                    "lifecycle chain contains "
                    "a prior-docket digest mismatch"
                )
            if (
                current.snapshot.compared_at.value
                <= previous.snapshot.compared_at.value
            ):
                raise FoundationError(
                    "lifecycle-chain snapshots must use "
                    "strictly increasing comparison times"
                )
            if current.linked_at.value <= previous.linked_at.value:
                raise FoundationError(
                    "lifecycle-chain entries must use "
                    "strictly increasing link times"
                )

            docket_path.append(
                current.current_docket_id
            )

        if len(docket_path) != len(
            set(docket_path)
        ):
            raise FoundationError(
                "lifecycle chain must not contain "
                "a docket cycle"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        claim_catalog_digest: ContentDigest,
        actor_registry: ActorRegistry,
        entries: Iterable[
            ClaimPostureAlertLifecycleChainEntry
        ] = (),
    ) -> ClaimPostureAlertLifecycleChain:
        """Create a linear lifecycle chain."""

        producer = actor_registry.require_actor(
            producer_id
        )
        producer_owner_id = _validate_chain_producer(
            producer
        )

        _require_digest(
            claim_catalog_digest,
            field_name="claim_catalog_digest",
            domain="claim-catalog",
        )

        return cls(
            chain_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-chain"
                ),
                key=key,
                namespace_field="chain namespace",
                key_field="chain key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            claim_catalog_digest=claim_catalog_digest,
            actor_registry_digest=actor_registry.digest(),
            entries=tuple(
                entries
            ),
        )

    @property
    def generation_count(self) -> int:
        """Return the number of lifecycle generations."""

        return len(
            self.entries
        )

    @property
    def status(self) -> ClaimPostureAlertLifecycleChainStatus:
        """Return the latest aggregate alert state."""

        latest = self.latest_entry

        if latest is None:
            return ClaimPostureAlertLifecycleChainStatus.EMPTY

        if latest.snapshot.status is (
            ClaimPostureAlertLifecycleSnapshotStatus.CLEAR
        ):
            return ClaimPostureAlertLifecycleChainStatus.CLEAR

        return ClaimPostureAlertLifecycleChainStatus.ACTIVE

    @property
    def latest_entry(
        self,
    ) -> ClaimPostureAlertLifecycleChainEntry | None:
        """Return the newest chain entry."""

        return self.entries[-1] if self.entries else None

    @property
    def latest_snapshot(
        self,
    ) -> ClaimPostureAlertLifecycleSnapshot | None:
        """Return the newest lifecycle snapshot."""

        latest = self.latest_entry

        return (
            latest.snapshot
            if latest is not None
            else None
        )

    @property
    def has_active_alerts(self) -> bool:
        """Return whether the latest generation has active alerts."""

        return self.status.has_active_alerts

    @property
    def current_active_alert_count(self) -> int:
        """Return active alerts in the latest generation."""

        latest = self.latest_entry

        return (
            latest.active_alert_count
            if latest is not None
            else 0
        )

    @property
    def current_docket_id(
        self,
    ) -> ScopedIdentifier | None:
        """Return the latest current alert docket identity."""

        latest = self.latest_entry

        return (
            latest.current_docket_id
            if latest is not None
            else None
        )

    @property
    def current_docket_digest(
        self,
    ) -> ContentDigest | None:
        """Return the latest current alert docket digest."""

        latest = self.latest_entry

        return (
            latest.current_docket_digest
            if latest is not None
            else None
        )

    @property
    def silent_drop_count(self) -> int:
        """Return silently dropped alerts across all generations."""

        return sum(
            entry.silent_drop_count
            for entry in self.entries
        )

    @property
    def all_generations_accounted_for(self) -> bool:
        """Return true because each generation is predecessor-bound."""

        return True

    @property
    def changes_claim_state(self) -> bool:
        """Return false because the chain records existing state only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because lifecycle history grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def entry_for_sequence(
        self,
        sequence_number: int,
    ) -> ClaimPostureAlertLifecycleChainEntry | None:
        """Return one chain entry by sequence number."""

        for entry in self.entries:
            if entry.sequence_number == sequence_number:
                return entry

        return None

    def require_entry_for_sequence(
        self,
        sequence_number: int,
    ) -> ClaimPostureAlertLifecycleChainEntry:
        """Return one sequence entry or fail when absent."""

        entry = self.entry_for_sequence(
            sequence_number
        )

        if entry is None:
            raise FoundationError(
                "lifecycle chain does not contain "
                f"sequence: {sequence_number}"
            )

        return entry

    def active_claim_ids(
        self,
    ) -> tuple[ScopedIdentifier, ...]:
        """Return active claim-alert identities in the latest generation."""

        latest = self.latest_snapshot

        if latest is None:
            return ()

        return tuple(
            sorted(
                (
                    lifecycle.claim_id
                    for lifecycle
                    in latest.active_lifecycles()
                ),
                key=str,
            )
        )

    def append(
        self,
        *,
        key: str,
        linked_at: UtcTimestamp,
        created_at: UtcTimestamp,
        snapshot: ClaimPostureAlertLifecycleSnapshot,
    ) -> ClaimPostureAlertLifecycleChain:
        """Return the next immutable lifecycle-chain snapshot."""

        if created_at.value < self.created_at.value:
            raise FoundationError(
                "next lifecycle-chain snapshot must not "
                "predate the current chain"
            )

        entry = ClaimPostureAlertLifecycleChainEntry.link(
            key=key,
            linked_at=linked_at,
            snapshot=snapshot,
            previous=self.latest_entry,
        )

        return ClaimPostureAlertLifecycleChain(
            chain_id=self.chain_id,
            created_at=created_at,
            producer_id=self.producer_id,
            producer_kind=self.producer_kind,
            producer_accountability_owner_id=(
                self.producer_accountability_owner_id
            ),
            claim_catalog_digest=(
                self.claim_catalog_digest
            ),
            actor_registry_digest=(
                self.actor_registry_digest
            ),
            entries=(
                *self.entries,
                entry,
            ),
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic lifecycle-chain representation."""

        entry_payloads: JsonArray = [
            entry.to_payload()
            for entry in self.entries
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "all_generations_accounted_for": (
                self.all_generations_accounted_for
            ),
            "chain_id": str(self.chain_id),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "created_at": self.created_at.isoformat(),
            "current_active_alert_count": (
                self.current_active_alert_count
            ),
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
                if self.current_docket_digest is not None
                else None
            ),
            "current_docket_id": (
                str(self.current_docket_id)
                if self.current_docket_id is not None
                else None
            ),
            "entries": entry_payloads,
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "has_active_alerts": self.has_active_alerts,
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "schema": self.SCHEMA.value,
            "silent_drop_count": self.silent_drop_count,
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical lifecycle chain."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the entire lifecycle chain."""

        return self.to_document().digest(
            domain="claim-posture-alert-lifecycle-chain"
        )
