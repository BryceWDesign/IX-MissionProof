"""Current applicability of lifecycle-chain checkpoint reviews."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.chains import (
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
)
from ix_missionproof.claims.checkpoints import (
    ClaimPostureAlertLifecycleCheckpoint,
    ClaimPostureAlertLifecycleCheckpointLedger,
    ClaimPostureAlertLifecycleCheckpointStatus,
)
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
)

_CHECKPOINT_STATE_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleCheckpointCurrencyStatus(StrEnum):
    """Applicability of a checkpoint ledger to the current chain head."""

    NO_REVIEW = "no-review"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STALE = "stale"

    @property
    def applies_to_current_head(self) -> bool:
        """Return whether review binds the current chain head."""

        return self is not (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE
        )

    @property
    def continuity_accepted(self) -> bool:
        """Return whether continuity is accepted for the current head."""

        return self is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.ACCEPTED
        )

    @property
    def review_required(self) -> bool:
        """Return whether the current chain head still needs review."""

        return self in {
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.NO_REVIEW,
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.DEFERRED,
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE,
        }

    @property
    def continuity_rejected(self) -> bool:
        """Return whether the current chain head was rejected."""

        return self is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.REJECTED
        )


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


def _validate_checkpoint_state_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "checkpoint-currency producer must be active"
        )
    if producer.kind not in _CHECKPOINT_STATE_PRODUCER_KINDS:
        raise FoundationError(
            "checkpoint-currency producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "checkpoint-currency producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleCheckpointCurrencySnapshot:
    """Determine whether a checkpoint still applies to the current head."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-checkpoint-currency-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    assessed_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleCheckpointCurrencyStatus
    chain_id: ScopedIdentifier
    checkpoint_ledger_id: ScopedIdentifier
    current_generation_count: int
    reviewed_generation_count: int
    current_head_entry_id: ScopedIdentifier
    reviewed_head_entry_id: ScopedIdentifier
    latest_checkpoint_id: ScopedIdentifier | None
    latest_checkpoint_status: (
        ClaimPostureAlertLifecycleCheckpointStatus | None
    )
    chain_digest: ContentDigest
    reviewed_chain_digest: ContentDigest
    current_head_entry_digest: ContentDigest
    reviewed_head_entry_digest: ContentDigest
    latest_checkpoint_digest: ContentDigest | None
    checkpoint_ledger_digest: ContentDigest
    current_docket_digest: ContentDigest
    reviewed_docket_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_checkpoint_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
            ),
            (
                "chain_id",
                self.chain_id,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "checkpoint_ledger_id",
                self.checkpoint_ledger_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-ledger"
                ),
            ),
            (
                "current_head_entry_id",
                self.current_head_entry_id,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
            (
                "reviewed_head_entry_id",
                self.reviewed_head_entry_id,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        _require_optional_identifier(
            self.latest_checkpoint_id,
            field_name="latest_checkpoint_id",
            namespace=(
                "claim-posture-alert-lifecycle-checkpoint"
            ),
        )

        if not isinstance(
            self.assessed_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "assessed_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.produced_by_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "produced_by_id must be a ScopedIdentifier"
            )
        if not isinstance(
            self.producer_kind,
            ActorKind,
        ):
            raise FoundationError(
                "producer_kind must be an ActorKind"
            )
        if self.producer_kind not in (
            _CHECKPOINT_STATE_PRODUCER_KINDS
        ):
            raise FoundationError(
                "checkpoint-currency producer must be "
                "a service or system actor"
            )
        if self.produced_by_id.namespace != CanonicalKey(
            self.producer_kind.value
        ):
            raise FoundationError(
                "produced_by_id namespace must match producer_kind"
            )

        _require_identifier(
            self.producer_accountability_owner_id,
            field_name="producer_accountability_owner_id",
            namespace="human",
        )

        if not isinstance(
            self.status,
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertLifecycleCheckpointCurrencyStatus"
            )
        if (
            self.latest_checkpoint_status is not None
            and not isinstance(
                self.latest_checkpoint_status,
                ClaimPostureAlertLifecycleCheckpointStatus,
            )
        ):
            raise FoundationError(
                "latest_checkpoint_status must be a "
                "ClaimPostureAlertLifecycleCheckpointStatus or None"
            )

        for field_name, value in (
            (
                "current_generation_count",
                self.current_generation_count,
            ),
            (
                "reviewed_generation_count",
                self.reviewed_generation_count,
            ),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise FoundationError(
                    f"{field_name} must be an integer"
                )
            if value < 1:
                raise FoundationError(
                    f"{field_name} must be at least one"
                )

        if (
            self.reviewed_generation_count
            > self.current_generation_count
        ):
            raise FoundationError(
                "reviewed generation must not be newer "
                "than the current chain"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "chain_digest",
                self.chain_digest,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "reviewed_chain_digest",
                self.reviewed_chain_digest,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "current_head_entry_digest",
                self.current_head_entry_digest,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
            (
                "reviewed_head_entry_digest",
                self.reviewed_head_entry_digest,
                "claim-posture-alert-lifecycle-chain-entry",
            ),
            (
                "checkpoint_ledger_digest",
                self.checkpoint_ledger_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-ledger"
                ),
            ),
            (
                "current_docket_digest",
                self.current_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "reviewed_docket_digest",
                self.reviewed_docket_digest,
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

        _require_optional_digest(
            self.latest_checkpoint_digest,
            field_name="latest_checkpoint_digest",
            domain=(
                "claim-posture-alert-lifecycle-checkpoint"
            ),
        )

    def _validate_checkpoint_semantics(self) -> None:
        checkpoint_present = (
            self.latest_checkpoint_id is not None
            and self.latest_checkpoint_status is not None
            and self.latest_checkpoint_digest is not None
        )
        checkpoint_absent = (
            self.latest_checkpoint_id is None
            and self.latest_checkpoint_status is None
            and self.latest_checkpoint_digest is None
        )

        if not checkpoint_present and not checkpoint_absent:
            raise FoundationError(
                "latest checkpoint identity, status, and digest "
                "must be present or absent together"
            )

        expected = self.classify(
            current_generation_count=self.current_generation_count,
            reviewed_generation_count=self.reviewed_generation_count,
            latest_checkpoint_status=self.latest_checkpoint_status,
        )

        if self.status is not expected:
            raise FoundationError(
                "checkpoint-currency status does not match "
                "the reviewed and current chain heads"
            )

        if (
            self.status
            is ClaimPostureAlertLifecycleCheckpointCurrencyStatus.NO_REVIEW
            and not checkpoint_absent
        ):
            raise FoundationError(
                "no-review checkpoint currency must not "
                "contain a checkpoint"
            )

        if (
            self.status
            not in {
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus.NO_REVIEW,
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE,
            }
            and not checkpoint_present
        ):
            raise FoundationError(
                "current reviewed checkpoint currency requires "
                "a latest checkpoint"
            )

        if self.status.applies_to_current_head:
            if (
                self.current_generation_count
                != self.reviewed_generation_count
            ):
                raise FoundationError(
                    "current checkpoint review requires matching "
                    "generation counts"
                )
            if (
                self.current_head_entry_id
                != self.reviewed_head_entry_id
            ):
                raise FoundationError(
                    "current checkpoint review requires matching "
                    "chain-head identities"
                )
            if (
                self.current_head_entry_digest
                != self.reviewed_head_entry_digest
            ):
                raise FoundationError(
                    "current checkpoint review requires matching "
                    "chain-head digests"
                )
            if self.chain_digest != self.reviewed_chain_digest:
                raise FoundationError(
                    "current checkpoint review requires matching "
                    "lifecycle-chain digests"
                )
            if (
                self.current_docket_digest
                != self.reviewed_docket_digest
            ):
                raise FoundationError(
                    "current checkpoint review requires matching "
                    "alert-docket digests"
                )
        elif (
            self.current_generation_count
            <= self.reviewed_generation_count
        ):
            raise FoundationError(
                "stale checkpoint review requires "
                "a newer current chain generation"
            )

    @classmethod
    def assess(
        cls,
        *,
        key: str,
        assessed_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        chain: ClaimPostureAlertLifecycleChain,
        checkpoint_ledger: (
            ClaimPostureAlertLifecycleCheckpointLedger
        ),
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleCheckpointCurrencySnapshot:
        """Assess whether checkpoint review applies to the current head."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = (
            _validate_checkpoint_state_producer(
                producer
            )
        )

        current_head, reviewed_head = cls._validate_bindings(
            assessed_at=assessed_at,
            chain=chain,
            checkpoint_ledger=checkpoint_ledger,
            actor_registry=actor_registry,
        )

        latest = checkpoint_ledger.latest_checkpoint
        status = cls.classify(
            current_generation_count=chain.generation_count,
            reviewed_generation_count=(
                checkpoint_ledger.generation_count
            ),
            latest_checkpoint_status=(
                latest.status
                if latest is not None
                else None
            ),
        )

        current_docket_digest = chain.current_docket_digest

        if current_docket_digest is None:
            raise FoundationError(
                "checkpoint-currency assessment requires "
                "a current alert docket"
            )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            assessed_at=assessed_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            status=status,
            chain_id=chain.chain_id,
            checkpoint_ledger_id=checkpoint_ledger.ledger_id,
            current_generation_count=chain.generation_count,
            reviewed_generation_count=(
                checkpoint_ledger.generation_count
            ),
            current_head_entry_id=current_head.entry_id,
            reviewed_head_entry_id=reviewed_head.entry_id,
            latest_checkpoint_id=(
                latest.checkpoint_id
                if latest is not None
                else None
            ),
            latest_checkpoint_status=(
                latest.status
                if latest is not None
                else None
            ),
            chain_digest=chain.digest(),
            reviewed_chain_digest=(
                checkpoint_ledger.chain_digest
            ),
            current_head_entry_digest=current_head.digest(),
            reviewed_head_entry_digest=reviewed_head.digest(),
            latest_checkpoint_digest=(
                latest.digest()
                if latest is not None
                else None
            ),
            checkpoint_ledger_digest=checkpoint_ledger.digest(),
            current_docket_digest=current_docket_digest,
            reviewed_docket_digest=(
                checkpoint_ledger.current_docket_digest
            ),
            claim_catalog_digest=chain.claim_catalog_digest,
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        assessed_at: UtcTimestamp,
        chain: ClaimPostureAlertLifecycleChain,
        checkpoint_ledger: (
            ClaimPostureAlertLifecycleCheckpointLedger
        ),
        actor_registry: ActorRegistry,
    ) -> tuple[
        ClaimPostureAlertLifecycleChainEntry,
        ClaimPostureAlertLifecycleChainEntry,
    ]:
        actor_registry_digest = actor_registry.digest()

        if chain.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "lifecycle chain is not bound to "
                "the supplied actor registry"
            )
        if (
            checkpoint_ledger.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "checkpoint ledger is not bound to "
                "the supplied actor registry"
            )
        if checkpoint_ledger.chain_id != chain.chain_id:
            raise FoundationError(
                "checkpoint ledger references "
                "a different lifecycle chain"
            )
        if (
            checkpoint_ledger.claim_catalog_digest
            != chain.claim_catalog_digest
        ):
            raise FoundationError(
                "checkpoint ledger and lifecycle chain must bind "
                "the same claim catalog"
            )
        if (
            checkpoint_ledger.generation_count
            > chain.generation_count
        ):
            raise FoundationError(
                "checkpoint ledger references a generation "
                "newer than the current lifecycle chain"
            )
        if assessed_at.value < chain.created_at.value:
            raise FoundationError(
                "checkpoint-currency assessment must not predate "
                "the lifecycle chain"
            )
        if assessed_at.value < checkpoint_ledger.created_at.value:
            raise FoundationError(
                "checkpoint-currency assessment must not predate "
                "the checkpoint ledger"
            )

        current_head = chain.latest_entry

        if current_head is None:
            raise FoundationError(
                "checkpoint-currency assessment requires "
                "a nonempty lifecycle chain"
            )

        reviewed_head = chain.require_entry_for_sequence(
            checkpoint_ledger.generation_count
        )

        if (
            reviewed_head.entry_id
            != checkpoint_ledger.head_entry_id
        ):
            raise FoundationError(
                "checkpoint ledger head identity does not match "
                "the current lifecycle-chain history"
            )
        if (
            reviewed_head.digest()
            != checkpoint_ledger.head_entry_digest
        ):
            raise FoundationError(
                "checkpoint ledger head digest does not match "
                "the current lifecycle-chain history"
            )
        if (
            reviewed_head.current_docket_digest
            != checkpoint_ledger.current_docket_digest
        ):
            raise FoundationError(
                "checkpoint ledger docket digest does not match "
                "the reviewed lifecycle generation"
            )

        if (
            checkpoint_ledger.generation_count
            == chain.generation_count
            and checkpoint_ledger.chain_digest != chain.digest()
        ):
            raise FoundationError(
                "checkpoint ledger chain digest does not match "
                "the current lifecycle-chain head"
            )

        return current_head, reviewed_head

    @staticmethod
    def classify(
        *,
        current_generation_count: int,
        reviewed_generation_count: int,
        latest_checkpoint_status: (
            ClaimPostureAlertLifecycleCheckpointStatus | None
        ),
    ) -> ClaimPostureAlertLifecycleCheckpointCurrencyStatus:
        """Classify checkpoint review currency."""

        if reviewed_generation_count < current_generation_count:
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE
            )

        if latest_checkpoint_status is None:
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .NO_REVIEW
            )

        return {
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED: (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .DEFERRED
            ),
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED: (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .ACCEPTED
            ),
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED: (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .REJECTED
            ),
        }[latest_checkpoint_status]

    @property
    def applies_to_current_head(self) -> bool:
        """Return whether review binds the current chain head."""

        return self.status.applies_to_current_head

    @property
    def continuity_accepted_for_current_head(self) -> bool:
        """Return whether current continuity was independently accepted."""

        return self.status.continuity_accepted

    @property
    def continuity_rejected_for_current_head(self) -> bool:
        """Return whether current continuity was independently rejected."""

        return self.status.continuity_rejected

    @property
    def review_required(self) -> bool:
        """Return whether the current chain head still needs review."""

        return self.status.review_required

    @property
    def stale_review_cannot_cover_current_head(self) -> bool:
        """Return whether an older review is barred from covering this head."""

        return self.status is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE
        )

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because continuity review is not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because checkpoint currency cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because checkpoint currency is reporting only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because checkpoint currency grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic checkpoint-currency representation."""

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "applies_to_current_head": (
                self.applies_to_current_head
            ),
            "approves_underlying_claims": (
                self.approves_underlying_claims
            ),
            "assessed_at": self.assessed_at.isoformat(),
            "chain_digest": self.chain_digest.to_payload(),
            "chain_id": str(self.chain_id),
            "changes_claim_state": self.changes_claim_state,
            "checkpoint_ledger_digest": (
                self.checkpoint_ledger_digest.to_payload()
            ),
            "checkpoint_ledger_id": str(
                self.checkpoint_ledger_id
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "continuity_accepted_for_current_head": (
                self.continuity_accepted_for_current_head
            ),
            "continuity_rejected_for_current_head": (
                self.continuity_rejected_for_current_head
            ),
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
            ),
            "current_generation_count": (
                self.current_generation_count
            ),
            "current_head_entry_digest": (
                self.current_head_entry_digest.to_payload()
            ),
            "current_head_entry_id": str(
                self.current_head_entry_id
            ),
            "grants_authority": self.grants_authority,
            "latest_checkpoint_digest": (
                self.latest_checkpoint_digest.to_payload()
                if self.latest_checkpoint_digest is not None
                else None
            ),
            "latest_checkpoint_id": (
                str(self.latest_checkpoint_id)
                if self.latest_checkpoint_id is not None
                else None
            ),
            "latest_checkpoint_status": (
                self.latest_checkpoint_status.value
                if self.latest_checkpoint_status is not None
                else None
            ),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "review_required": self.review_required,
            "reviewed_chain_digest": (
                self.reviewed_chain_digest.to_payload()
            ),
            "reviewed_docket_digest": (
                self.reviewed_docket_digest.to_payload()
            ),
            "reviewed_generation_count": (
                self.reviewed_generation_count
            ),
            "reviewed_head_entry_digest": (
                self.reviewed_head_entry_digest.to_payload()
            ),
            "reviewed_head_entry_id": str(
                self.reviewed_head_entry_id
            ),
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "stale_review_cannot_cover_current_head": (
                self.stale_review_cannot_cover_current_head
            ),
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical checkpoint-currency snapshot."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete currency assessment."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-"
                "checkpoint-currency-snapshot"
            )
        )
