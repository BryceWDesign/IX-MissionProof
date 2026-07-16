"""Current human-review obligations for lifecycle-chain checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.chains import (
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
)
from ix_missionproof.claims.checkpoint_states import (
    ClaimPostureAlertLifecycleCheckpointCurrencySnapshot,
    ClaimPostureAlertLifecycleCheckpointCurrencyStatus,
)
from ix_missionproof.claims.checkpoints import (
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

_REVIEW_DOCKET_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleReviewDocketStatus(StrEnum):
    """Current human-review obligation for one lifecycle-chain head."""

    CLEAR = "clear"
    REVIEW_REQUIRED = "review-required"
    REVIEW_DEFERRED = "review-deferred"
    CORRECTIVE_ACTION_REQUIRED = "corrective-action-required"

    @property
    def requires_human_action(self) -> bool:
        """Return whether the current chain head needs human action."""

        return self is not ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR

    @property
    def requires_human_review(self) -> bool:
        """Return whether continuity review remains open."""

        return self in {
            ClaimPostureAlertLifecycleReviewDocketStatus.REVIEW_REQUIRED,
            ClaimPostureAlertLifecycleReviewDocketStatus.REVIEW_DEFERRED,
        }

    @property
    def requires_corrective_action(self) -> bool:
        """Return whether independent review rejected continuity."""

        return self is (
            ClaimPostureAlertLifecycleReviewDocketStatus
            .CORRECTIVE_ACTION_REQUIRED
        )


class ClaimPostureAlertLifecycleReviewReason(StrEnum):
    """Reason the current lifecycle-chain head requires attention."""

    CURRENT_HEAD_UNREVIEWED = "current-head-unreviewed"
    CURRENT_REVIEW_DEFERRED = "current-review-deferred"
    PRIOR_REVIEW_STALE = "prior-review-stale"
    CURRENT_CONTINUITY_REJECTED = "current-continuity-rejected"


class ClaimPostureAlertLifecycleReviewPriority(StrEnum):
    """Priority assigned to one lifecycle continuity obligation."""

    NONE = "none"
    ROUTINE = "routine"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def is_urgent(self) -> bool:
        """Return whether prompt human action is required."""

        return self in {
            ClaimPostureAlertLifecycleReviewPriority.HIGH,
            ClaimPostureAlertLifecycleReviewPriority.CRITICAL,
        }


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


def _validate_review_docket_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "lifecycle-review docket producer must be active"
        )
    if producer.kind not in _REVIEW_DOCKET_PRODUCER_KINDS:
        raise FoundationError(
            "lifecycle-review docket producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "lifecycle-review docket producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleReviewDocket:
    """Human-review obligation bound to an exact current chain head."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-review-docket-v1"
    )

    docket_id: ScopedIdentifier
    generated_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleReviewDocketStatus
    reason: ClaimPostureAlertLifecycleReviewReason | None
    priority: ClaimPostureAlertLifecycleReviewPriority
    chain_id: ScopedIdentifier
    generation_count: int
    head_entry_id: ScopedIdentifier
    current_docket_id: ScopedIdentifier
    active_alert_count: int
    checkpoint_currency_snapshot_id: ScopedIdentifier
    latest_checkpoint_id: ScopedIdentifier | None
    latest_checkpoint_status: (
        ClaimPostureAlertLifecycleCheckpointStatus | None
    )
    chain_digest: ContentDigest
    head_entry_digest: ContentDigest
    current_alert_docket_digest: ContentDigest
    checkpoint_currency_snapshot_digest: ContentDigest
    latest_checkpoint_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_checkpoint_presence()
        self._validate_review_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "docket_id",
                self.docket_id,
                "claim-posture-alert-lifecycle-review-docket",
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
            (
                "checkpoint_currency_snapshot_id",
                self.checkpoint_currency_snapshot_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
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
            self.generated_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "generated_at must be a UtcTimestamp"
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
            _REVIEW_DOCKET_PRODUCER_KINDS
        ):
            raise FoundationError(
                "lifecycle-review docket producer must be "
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
            ClaimPostureAlertLifecycleReviewDocketStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertLifecycleReviewDocketStatus"
            )
        if (
            self.reason is not None
            and not isinstance(
                self.reason,
                ClaimPostureAlertLifecycleReviewReason,
            )
        ):
            raise FoundationError(
                "reason must be a "
                "ClaimPostureAlertLifecycleReviewReason or None"
            )
        if not isinstance(
            self.priority,
            ClaimPostureAlertLifecycleReviewPriority,
        ):
            raise FoundationError(
                "priority must be a "
                "ClaimPostureAlertLifecycleReviewPriority"
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

        for field_name, value, minimum in (
            (
                "generation_count",
                self.generation_count,
                1,
            ),
            (
                "active_alert_count",
                self.active_alert_count,
                0,
            ),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise FoundationError(
                    f"{field_name} must be an integer"
                )
            if value < minimum:
                raise FoundationError(
                    f"{field_name} must be at least {minimum}"
                )

    def _validate_digests(self) -> None:
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
                "current_alert_docket_digest",
                self.current_alert_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "checkpoint_currency_snapshot_digest",
                self.checkpoint_currency_snapshot_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
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

    def _validate_checkpoint_presence(self) -> None:
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

        if (
            self.reason
            is ClaimPostureAlertLifecycleReviewReason
            .CURRENT_HEAD_UNREVIEWED
            and not checkpoint_absent
        ):
            raise FoundationError(
                "unreviewed lifecycle head must not contain "
                "a latest checkpoint"
            )

        if (
            self.reason
            is not ClaimPostureAlertLifecycleReviewReason
            .CURRENT_HEAD_UNREVIEWED
            and self.status
            is not ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
            and not checkpoint_present
        ):
            raise FoundationError(
                "review obligation requires its bound checkpoint"
            )

        if (
            self.status
            is ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
            and not checkpoint_present
        ):
            raise FoundationError(
                "clear lifecycle-review docket requires "
                "an accepted checkpoint"
            )

    def _validate_review_semantics(self) -> None:
        expected_status, expected_reason = self.classify(
            latest_checkpoint_status=self.latest_checkpoint_status,
            currency_status=self._currency_status_for_semantics(),
        )
        expected_priority = self.priority_for(
            status=expected_status,
            active_alert_count=self.active_alert_count,
        )

        if self.status is not expected_status:
            raise FoundationError(
                "lifecycle-review docket status does not match "
                "checkpoint currency"
            )
        if self.reason is not expected_reason:
            raise FoundationError(
                "lifecycle-review docket reason does not match "
                "checkpoint currency"
            )
        if self.priority is not expected_priority:
            raise FoundationError(
                "lifecycle-review docket priority does not match "
                "its current obligation"
            )

        if self.status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            if self.reason is not None:
                raise FoundationError(
                    "clear lifecycle-review docket must not "
                    "contain a review reason"
                )
            if self.latest_checkpoint_status is not (
                ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
            ):
                raise FoundationError(
                    "clear lifecycle-review docket requires "
                    "an accepted current-head checkpoint"
                )
            return

        if self.reason is None:
            raise FoundationError(
                "nonclear lifecycle-review docket requires a reason"
            )

    def _currency_status_for_semantics(
        self,
    ) -> ClaimPostureAlertLifecycleCheckpointCurrencyStatus:
        if self.status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .ACCEPTED
            )

        if self.reason is (
            ClaimPostureAlertLifecycleReviewReason
            .CURRENT_HEAD_UNREVIEWED
        ):
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .NO_REVIEW
            )

        if self.reason is (
            ClaimPostureAlertLifecycleReviewReason
            .CURRENT_REVIEW_DEFERRED
        ):
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .DEFERRED
            )

        if self.reason is (
            ClaimPostureAlertLifecycleReviewReason
            .PRIOR_REVIEW_STALE
        ):
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .STALE
            )

        if self.reason is (
            ClaimPostureAlertLifecycleReviewReason
            .CURRENT_CONTINUITY_REJECTED
        ):
            return (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .REJECTED
            )

        raise FoundationError(
            "nonclear lifecycle-review docket has "
            "an unsupported reason"
        )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        generated_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        chain: ClaimPostureAlertLifecycleChain,
        currency_snapshot: (
            ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        ),
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleReviewDocket:
        """Create the current review obligation for one chain head."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = _validate_review_docket_producer(
            producer
        )

        head = cls._validate_bindings(
            generated_at=generated_at,
            chain=chain,
            currency_snapshot=currency_snapshot,
            actor_registry=actor_registry,
        )

        status, reason = cls.classify(
            latest_checkpoint_status=(
                currency_snapshot.latest_checkpoint_status
            ),
            currency_status=currency_snapshot.status,
        )
        priority = cls.priority_for(
            status=status,
            active_alert_count=chain.current_active_alert_count,
        )

        current_docket_id = chain.current_docket_id
        current_docket_digest = chain.current_docket_digest

        if (
            current_docket_id is None
            or current_docket_digest is None
        ):
            raise FoundationError(
                "lifecycle-review docket requires "
                "a current alert docket"
            )

        return cls(
            docket_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-review-docket"
                ),
                key=key,
                namespace_field="docket namespace",
                key_field="docket key",
            ),
            generated_at=generated_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            status=status,
            reason=reason,
            priority=priority,
            chain_id=chain.chain_id,
            generation_count=chain.generation_count,
            head_entry_id=head.entry_id,
            current_docket_id=current_docket_id,
            active_alert_count=chain.current_active_alert_count,
            checkpoint_currency_snapshot_id=(
                currency_snapshot.snapshot_id
            ),
            latest_checkpoint_id=(
                currency_snapshot.latest_checkpoint_id
            ),
            latest_checkpoint_status=(
                currency_snapshot.latest_checkpoint_status
            ),
            chain_digest=chain.digest(),
            head_entry_digest=head.digest(),
            current_alert_docket_digest=current_docket_digest,
            checkpoint_currency_snapshot_digest=(
                currency_snapshot.digest()
            ),
            latest_checkpoint_digest=(
                currency_snapshot.latest_checkpoint_digest
            ),
            claim_catalog_digest=chain.claim_catalog_digest,
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        generated_at: UtcTimestamp,
        chain: ClaimPostureAlertLifecycleChain,
        currency_snapshot: (
            ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        ),
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleChainEntry:
        actor_registry_digest = actor_registry.digest()

        if chain.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "lifecycle chain is not bound to "
                "the supplied actor registry"
            )
        if (
            currency_snapshot.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "checkpoint-currency snapshot is not bound to "
                "the supplied actor registry"
            )
        if currency_snapshot.chain_id != chain.chain_id:
            raise FoundationError(
                "checkpoint-currency snapshot references "
                "a different lifecycle chain"
            )
        if currency_snapshot.chain_digest != chain.digest():
            raise FoundationError(
                "checkpoint-currency snapshot is not bound to "
                "the current lifecycle-chain digest"
            )
        if (
            currency_snapshot.claim_catalog_digest
            != chain.claim_catalog_digest
        ):
            raise FoundationError(
                "checkpoint-currency snapshot and lifecycle chain "
                "must bind the same claim catalog"
            )
        if (
            currency_snapshot.current_generation_count
            != chain.generation_count
        ):
            raise FoundationError(
                "checkpoint-currency snapshot does not describe "
                "the current chain generation"
            )

        head = chain.latest_entry

        if head is None:
            raise FoundationError(
                "lifecycle-review docket requires "
                "a nonempty lifecycle chain"
            )
        if currency_snapshot.current_head_entry_id != head.entry_id:
            raise FoundationError(
                "checkpoint-currency snapshot references "
                "a different current chain head"
            )
        if (
            currency_snapshot.current_head_entry_digest
            != head.digest()
        ):
            raise FoundationError(
                "checkpoint-currency snapshot head digest "
                "does not match the lifecycle chain"
            )

        current_docket_digest = chain.current_docket_digest

        if current_docket_digest is None:
            raise FoundationError(
                "lifecycle-review docket requires "
                "a current alert docket"
            )
        if (
            currency_snapshot.current_docket_digest
            != current_docket_digest
        ):
            raise FoundationError(
                "checkpoint-currency snapshot references "
                "a different current alert docket"
            )
        if generated_at.value < chain.created_at.value:
            raise FoundationError(
                "lifecycle-review docket must not predate "
                "the lifecycle chain"
            )
        if generated_at.value < currency_snapshot.assessed_at.value:
            raise FoundationError(
                "lifecycle-review docket must not predate "
                "the checkpoint-currency snapshot"
            )

        return head

    @staticmethod
    def classify(
        *,
        latest_checkpoint_status: (
            ClaimPostureAlertLifecycleCheckpointStatus | None
        ),
        currency_status: (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus
        ),
    ) -> tuple[
        ClaimPostureAlertLifecycleReviewDocketStatus,
        ClaimPostureAlertLifecycleReviewReason | None,
    ]:
        """Map checkpoint currency to one explicit review obligation."""

        if currency_status is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.ACCEPTED
        ):
            return (
                ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR,
                None,
            )

        if currency_status is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.NO_REVIEW
        ):
            return (
                (
                    ClaimPostureAlertLifecycleReviewDocketStatus
                    .REVIEW_REQUIRED
                ),
                (
                    ClaimPostureAlertLifecycleReviewReason
                    .CURRENT_HEAD_UNREVIEWED
                ),
            )

        if currency_status is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.DEFERRED
        ):
            return (
                (
                    ClaimPostureAlertLifecycleReviewDocketStatus
                    .REVIEW_DEFERRED
                ),
                (
                    ClaimPostureAlertLifecycleReviewReason
                    .CURRENT_REVIEW_DEFERRED
                ),
            )

        if currency_status is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE
        ):
            return (
                (
                    ClaimPostureAlertLifecycleReviewDocketStatus
                    .REVIEW_REQUIRED
                ),
                (
                    ClaimPostureAlertLifecycleReviewReason
                    .PRIOR_REVIEW_STALE
                ),
            )

        if currency_status is (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus.REJECTED
        ):
            return (
                (
                    ClaimPostureAlertLifecycleReviewDocketStatus
                    .CORRECTIVE_ACTION_REQUIRED
                ),
                (
                    ClaimPostureAlertLifecycleReviewReason
                    .CURRENT_CONTINUITY_REJECTED
                ),
            )

        raise FoundationError(
            "unsupported checkpoint-currency status"
        )

    @staticmethod
    def priority_for(
        *,
        status: ClaimPostureAlertLifecycleReviewDocketStatus,
        active_alert_count: int,
    ) -> ClaimPostureAlertLifecycleReviewPriority:
        """Assign deterministic priority to one current obligation."""

        if status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            return ClaimPostureAlertLifecycleReviewPriority.NONE

        if status is (
            ClaimPostureAlertLifecycleReviewDocketStatus
            .CORRECTIVE_ACTION_REQUIRED
        ):
            return ClaimPostureAlertLifecycleReviewPriority.CRITICAL

        if active_alert_count > 0:
            return ClaimPostureAlertLifecycleReviewPriority.HIGH

        if status is (
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ):
            return ClaimPostureAlertLifecycleReviewPriority.HIGH

        return ClaimPostureAlertLifecycleReviewPriority.ROUTINE

    @property
    def requires_human_action(self) -> bool:
        """Return whether the current head needs human action."""

        return self.status.requires_human_action

    @property
    def requires_human_review(self) -> bool:
        """Return whether independent continuity review remains open."""

        return self.status.requires_human_review

    @property
    def requires_corrective_action(self) -> bool:
        """Return whether continuity rejection requires remediation."""

        return self.status.requires_corrective_action

    @property
    def is_urgent(self) -> bool:
        """Return whether the current obligation is urgent."""

        return self.priority.is_urgent

    @property
    def continuity_reliance_allowed(self) -> bool:
        """Return whether current-head continuity was accepted."""

        return self.status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        )

    @property
    def accepted_review_covers_current_head(self) -> bool:
        """Return whether an accepted checkpoint binds this exact head."""

        return (
            self.continuity_reliance_allowed
            and self.latest_checkpoint_status
            is ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        )

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because continuity review is not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because review dockets cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because review dockets are reporting only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because review dockets grant no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic lifecycle-review docket."""

        return {
            "accepted_review_covers_current_head": (
                self.accepted_review_covers_current_head
            ),
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
            "checkpoint_currency_snapshot_digest": (
                self.checkpoint_currency_snapshot_digest.to_payload()
            ),
            "checkpoint_currency_snapshot_id": str(
                self.checkpoint_currency_snapshot_id
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "continuity_reliance_allowed": (
                self.continuity_reliance_allowed
            ),
            "current_alert_docket_digest": (
                self.current_alert_docket_digest.to_payload()
            ),
            "current_docket_id": str(self.current_docket_id),
            "docket_id": str(self.docket_id),
            "generated_at": self.generated_at.isoformat(),
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "head_entry_digest": (
                self.head_entry_digest.to_payload()
            ),
            "head_entry_id": str(self.head_entry_id),
            "is_urgent": self.is_urgent,
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
            "priority": self.priority.value,
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "reason": (
                self.reason.value
                if self.reason is not None
                else None
            ),
            "requires_corrective_action": (
                self.requires_corrective_action
            ),
            "requires_human_action": self.requires_human_action,
            "requires_human_review": self.requires_human_review,
            "schema": self.SCHEMA.value,
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical lifecycle-review docket."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete review obligation."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-review-docket"
            )
        )
