"""Independent human checkpoints over exact claim-alert lifecycle chains."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.chains import (
    ClaimPostureAlertLifecycleChain,
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
    require_text,
)

_CHECKPOINT_LEDGER_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleCheckpointStatus(StrEnum):
    """Independent human disposition of one exact lifecycle-chain head."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"

    @property
    def is_terminal(self) -> bool:
        """Return whether the checkpoint closes review of this exact head."""

        return self in {
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED,
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED,
        }

    @property
    def accepts_continuity(self) -> bool:
        """Return whether the reviewer accepted chain continuity."""

        return self is ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED


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


def _validate_checkpoint_ledger_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "checkpoint-ledger producer must be active"
        )
    if producer.kind not in _CHECKPOINT_LEDGER_PRODUCER_KINDS:
        raise FoundationError(
            "checkpoint-ledger producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "checkpoint-ledger producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleCheckpoint:
    """Independent human review of one exact lifecycle-chain head."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-checkpoint-v1"
    )

    checkpoint_id: ScopedIdentifier
    decided_at: UtcTimestamp
    decided_by_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleCheckpointStatus
    rationale: str
    chain_id: ScopedIdentifier
    generation_count: int
    head_entry_id: ScopedIdentifier
    current_docket_id: ScopedIdentifier
    active_alert_count: int
    chain_digest: ContentDigest
    head_entry_digest: ContentDigest
    current_docket_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        for field_name, value, namespace in (
            (
                "checkpoint_id",
                self.checkpoint_id,
                "claim-posture-alert-lifecycle-checkpoint",
            ),
            (
                "decided_by_id",
                self.decided_by_id,
                "human",
            ),
            (
                "chain_id",
                self.chain_id,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "head_entry_id",
                self.head_entry_id,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
            (
                "current_docket_id",
                self.current_docket_id,
                "claim-posture-alert-docket",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        if not isinstance(
            self.decided_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "decided_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.status,
            ClaimPostureAlertLifecycleCheckpointStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertLifecycleCheckpointStatus"
            )

        object.__setattr__(
            self,
            "rationale",
            require_text(
                self.rationale,
                field_name="rationale",
            ),
        )

        for field_name, value in (
            ("generation_count", self.generation_count),
            ("active_alert_count", self.active_alert_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise FoundationError(
                    f"{field_name} must be an integer"
                )
            if value < 0:
                raise FoundationError(
                    f"{field_name} must not be negative"
                )

        if self.generation_count < 1:
            raise FoundationError(
                "checkpoint requires at least one lifecycle generation"
            )

        for field_name, value, domain in (
            (
                "chain_digest",
                self.chain_digest,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "head_entry_digest",
                self.head_entry_digest,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
            (
                "current_docket_digest",
                self.current_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "claim_catalog_digest",
                self.claim_catalog_digest,
                "claim-catalog",
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

    @classmethod
    def decide(
        cls,
        *,
        key: str,
        decided_at: UtcTimestamp,
        decided_by_id: ScopedIdentifier,
        status: ClaimPostureAlertLifecycleCheckpointStatus,
        rationale: str,
        chain: ClaimPostureAlertLifecycleChain,
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleCheckpoint:
        """Record independent human judgment over one exact chain head."""

        actor_registry_digest = actor_registry.digest()

        if chain.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "lifecycle chain is not bound to "
                "the supplied actor registry"
            )

        head = chain.latest_entry

        if head is None:
            raise FoundationError(
                "lifecycle-chain checkpoint requires "
                "at least one generation"
            )
        if decided_at.value < chain.created_at.value:
            raise FoundationError(
                "lifecycle-chain checkpoint must not predate the chain"
            )

        reviewer = actor_registry.require_actor(
            decided_by_id
        )

        if not reviewer.is_eligible_for_human_authority:
            raise FoundationError(
                "lifecycle-chain checkpoint reviewer must be "
                "an active human actor"
            )
        if (
            reviewer.actor_id
            == chain.producer_accountability_owner_id
        ):
            raise FoundationError(
                "lifecycle-chain checkpoint reviewer must be "
                "independent of the chain producer's "
                "accountability owner"
            )

        if (
            status
            is ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
            and (
                chain.silent_drop_count != 0
                or not chain.all_generations_accounted_for
            )
        ):
            raise FoundationError(
                "accepted lifecycle-chain checkpoint requires "
                "complete continuity with zero silent drops"
            )

        current_docket_id = chain.current_docket_id
        current_docket_digest = chain.current_docket_digest

        if (
            current_docket_id is None
            or current_docket_digest is None
        ):
            raise FoundationError(
                "lifecycle-chain checkpoint requires "
                "a current alert docket"
            )

        return cls(
            checkpoint_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-checkpoint"
                ),
                key=key,
                namespace_field="checkpoint namespace",
                key_field="checkpoint key",
            ),
            decided_at=decided_at,
            decided_by_id=reviewer.actor_id,
            status=status,
            rationale=rationale,
            chain_id=chain.chain_id,
            generation_count=chain.generation_count,
            head_entry_id=head.entry_id,
            current_docket_id=current_docket_id,
            active_alert_count=chain.current_active_alert_count,
            chain_digest=chain.digest(),
            head_entry_digest=head.digest(),
            current_docket_digest=current_docket_digest,
            claim_catalog_digest=chain.claim_catalog_digest,
            actor_registry_digest=actor_registry_digest,
        )

    @property
    def is_terminal(self) -> bool:
        """Return whether review of this exact chain head is closed."""

        return self.status.is_terminal

    @property
    def accepts_continuity(self) -> bool:
        """Return whether the reviewer accepted lifecycle continuity."""

        return self.status.accepts_continuity

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because continuity review is not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because checkpoints cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because checkpoints do not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because checkpoints grant no action authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic checkpoint representation."""

        return {
            "accepts_continuity": self.accepts_continuity,
            "active_alert_count": self.active_alert_count,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "approves_underlying_claims": (
                self.approves_underlying_claims
            ),
            "chain_digest": self.chain_digest.to_payload(),
            "chain_id": str(self.chain_id),
            "changes_claim_state": self.changes_claim_state,
            "checkpoint_id": str(self.checkpoint_id),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
            ),
            "current_docket_id": str(self.current_docket_id),
            "decided_at": self.decided_at.isoformat(),
            "decided_by_id": str(self.decided_by_id),
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "head_entry_digest": (
                self.head_entry_digest.to_payload()
            ),
            "head_entry_id": str(self.head_entry_id),
            "is_terminal": self.is_terminal,
            "rationale": self.rationale,
            "schema": self.SCHEMA.value,
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical checkpoint document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete checkpoint."""

        return self.to_document().digest(
            domain="claim-posture-alert-lifecycle-checkpoint"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleCheckpointLedger:
    """Immutable review sequence for one exact lifecycle-chain head."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-checkpoint-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    chain_id: ScopedIdentifier
    generation_count: int
    head_entry_id: ScopedIdentifier
    checkpoints: tuple[ClaimPostureAlertLifecycleCheckpoint, ...]
    chain_digest: ContentDigest
    head_entry_digest: ContentDigest
    current_docket_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        _require_identifier(
            self.ledger_id,
            field_name="ledger_id",
            namespace=(
                "claim-posture-alert-lifecycle-checkpoint-ledger"
            ),
        )
        _require_identifier(
            self.chain_id,
            field_name="chain_id",
            namespace="claim-posture-alert-lifecycle-chain",
        )
        _require_identifier(
            self.head_entry_id,
            field_name="head_entry_id",
            namespace=(
                "claim-posture-alert-lifecycle-chain-entry"
            ),
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
        if self.producer_kind not in (
            _CHECKPOINT_LEDGER_PRODUCER_KINDS
        ):
            raise FoundationError(
                "checkpoint-ledger producer must be "
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

        if isinstance(
            self.generation_count,
            bool,
        ) or not isinstance(
            self.generation_count,
            int,
        ):
            raise FoundationError(
                "generation_count must be an integer"
            )
        if self.generation_count < 1:
            raise FoundationError(
                "generation_count must be at least one"
            )

        for field_name, value, domain in (
            (
                "chain_digest",
                self.chain_digest,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "head_entry_digest",
                self.head_entry_digest,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
            (
                "current_docket_digest",
                self.current_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "claim_catalog_digest",
                self.claim_catalog_digest,
                "claim-catalog",
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

        checkpoints = tuple(
            self.checkpoints
        )
        self._validate_checkpoints(
            checkpoints
        )

        ordered = tuple(
            sorted(
                checkpoints,
                key=lambda checkpoint: (
                    checkpoint.decided_at.value,
                    str(checkpoint.checkpoint_id),
                ),
            )
        )
        self._validate_sequence(
            ordered
        )

        object.__setattr__(
            self,
            "checkpoints",
            ordered,
        )

    def _validate_checkpoints(
        self,
        checkpoints: tuple[
            ClaimPostureAlertLifecycleCheckpoint,
            ...,
        ],
    ) -> None:
        for index, checkpoint in enumerate(
            checkpoints
        ):
            if not isinstance(
                checkpoint,
                ClaimPostureAlertLifecycleCheckpoint,
            ):
                raise FoundationError(
                    f"checkpoints[{index}] must be a "
                    "ClaimPostureAlertLifecycleCheckpoint"
                )
            if checkpoint.decided_at.value > self.created_at.value:
                raise FoundationError(
                    "checkpoint ledger must not predate "
                    "a contained checkpoint"
                )
            if checkpoint.chain_id != self.chain_id:
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same lifecycle chain"
                )
            if checkpoint.chain_digest != self.chain_digest:
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same lifecycle-chain digest"
                )
            if (
                checkpoint.generation_count
                != self.generation_count
            ):
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same generation count"
                )
            if checkpoint.head_entry_id != self.head_entry_id:
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same chain head"
                )
            if (
                checkpoint.head_entry_digest
                != self.head_entry_digest
            ):
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same chain-head digest"
                )
            if (
                checkpoint.current_docket_digest
                != self.current_docket_digest
            ):
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same current alert docket"
                )
            if (
                checkpoint.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same claim catalog"
                )
            if (
                checkpoint.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every checkpoint must bind "
                    "the same actor registry"
                )

        checkpoint_ids = tuple(
            checkpoint.checkpoint_id
            for checkpoint in checkpoints
        )

        if len(checkpoint_ids) != len(
            set(checkpoint_ids)
        ):
            raise FoundationError(
                "checkpoint ledger must contain "
                "unique checkpoint IDs"
            )

    @staticmethod
    def _validate_sequence(
        checkpoints: tuple[
            ClaimPostureAlertLifecycleCheckpoint,
            ...,
        ],
    ) -> None:
        previous: (
            ClaimPostureAlertLifecycleCheckpoint | None
        ) = None

        for checkpoint in checkpoints:
            if previous is not None:
                if (
                    previous.decided_at.value
                    >= checkpoint.decided_at.value
                ):
                    raise FoundationError(
                        "lifecycle-chain checkpoints must use "
                        "strictly increasing decision times"
                    )
                if previous.is_terminal:
                    raise FoundationError(
                        "terminal lifecycle-chain checkpoint "
                        "must not be followed by another decision"
                    )

            previous = checkpoint

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        chain: ClaimPostureAlertLifecycleChain,
        actor_registry: ActorRegistry,
        checkpoints: Iterable[
            ClaimPostureAlertLifecycleCheckpoint
        ] = (),
    ) -> ClaimPostureAlertLifecycleCheckpointLedger:
        """Create a checkpoint ledger for one exact chain head."""

        producer = actor_registry.require_actor(
            producer_id
        )
        producer_owner_id = (
            _validate_checkpoint_ledger_producer(
                producer
            )
        )

        actor_registry_digest = actor_registry.digest()

        if chain.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "lifecycle chain is not bound to "
                "the supplied actor registry"
            )

        head = chain.latest_entry
        current_docket_digest = chain.current_docket_digest

        if head is None or current_docket_digest is None:
            raise FoundationError(
                "checkpoint ledger requires "
                "a nonempty lifecycle chain"
            )
        if created_at.value < chain.created_at.value:
            raise FoundationError(
                "checkpoint ledger must not predate "
                "the lifecycle chain"
            )

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-ledger"
                ),
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            chain_id=chain.chain_id,
            generation_count=chain.generation_count,
            head_entry_id=head.entry_id,
            checkpoints=tuple(
                checkpoints
            ),
            chain_digest=chain.digest(),
            head_entry_digest=head.digest(),
            current_docket_digest=current_docket_digest,
            claim_catalog_digest=chain.claim_catalog_digest,
            actor_registry_digest=actor_registry_digest,
        )

    @property
    def checkpoint_count(self) -> int:
        """Return the number of recorded human checkpoints."""

        return len(
            self.checkpoints
        )

    @property
    def latest_checkpoint(
        self,
    ) -> ClaimPostureAlertLifecycleCheckpoint | None:
        """Return the latest checkpoint decision."""

        return self.checkpoints[-1] if self.checkpoints else None

    @property
    def terminal_checkpoint(
        self,
    ) -> ClaimPostureAlertLifecycleCheckpoint | None:
        """Return the terminal checkpoint, when present."""

        latest = self.latest_checkpoint

        if latest is not None and latest.is_terminal:
            return latest

        return None

    @property
    def continuity_accepted(self) -> bool:
        """Return whether the exact chain head was terminally accepted."""

        terminal = self.terminal_checkpoint

        return (
            terminal is not None
            and terminal.accepts_continuity
        )

    @property
    def review_open(self) -> bool:
        """Return whether review lacks a terminal checkpoint."""

        return self.terminal_checkpoint is None

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because continuity review is not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because checkpoint ledgers cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because checkpoint ledgers do not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because checkpoint ledgers grant no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def require_terminal_checkpoint(
        self,
    ) -> ClaimPostureAlertLifecycleCheckpoint:
        """Return the terminal checkpoint or fail when review is open."""

        checkpoint = self.terminal_checkpoint

        if checkpoint is None:
            raise FoundationError(
                "lifecycle-chain checkpoint review "
                "does not have a terminal decision"
            )

        return checkpoint

    def append(
        self,
        checkpoint: ClaimPostureAlertLifecycleCheckpoint,
        *,
        created_at: UtcTimestamp,
    ) -> ClaimPostureAlertLifecycleCheckpointLedger:
        """Return the next immutable checkpoint-ledger snapshot."""

        if created_at.value < self.created_at.value:
            raise FoundationError(
                "next checkpoint-ledger snapshot must not "
                "predate the current ledger"
            )

        return ClaimPostureAlertLifecycleCheckpointLedger(
            ledger_id=self.ledger_id,
            created_at=created_at,
            producer_id=self.producer_id,
            producer_kind=self.producer_kind,
            producer_accountability_owner_id=(
                self.producer_accountability_owner_id
            ),
            chain_id=self.chain_id,
            generation_count=self.generation_count,
            head_entry_id=self.head_entry_id,
            checkpoints=(
                *self.checkpoints,
                checkpoint,
            ),
            chain_digest=self.chain_digest,
            head_entry_digest=self.head_entry_digest,
            current_docket_digest=self.current_docket_digest,
            claim_catalog_digest=self.claim_catalog_digest,
            actor_registry_digest=self.actor_registry_digest,
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic checkpoint-ledger representation."""

        checkpoint_payloads: JsonArray = [
            checkpoint.to_payload()
            for checkpoint in self.checkpoints
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "approves_underlying_claims": (
                self.approves_underlying_claims
            ),
            "chain_digest": self.chain_digest.to_payload(),
            "chain_id": str(self.chain_id),
            "changes_claim_state": self.changes_claim_state,
            "checkpoint_count": self.checkpoint_count,
            "checkpoints": checkpoint_payloads,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "continuity_accepted": self.continuity_accepted,
            "created_at": self.created_at.isoformat(),
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
            ),
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "head_entry_digest": (
                self.head_entry_digest.to_payload()
            ),
            "head_entry_id": str(self.head_entry_id),
            "ledger_id": str(self.ledger_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "review_open": self.review_open,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical checkpoint ledger."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete checkpoint ledger."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-checkpoint-ledger"
            )
        )
