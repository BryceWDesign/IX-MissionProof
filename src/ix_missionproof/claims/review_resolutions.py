"""Reconcile lifecycle-review obligations against current checkpoint state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.chains import (
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
)
from ix_missionproof.claims.checkpoint_reviews import (
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
    ClaimPostureAlertLifecycleReviewPriority,
    ClaimPostureAlertLifecycleReviewReason,
)
from ix_missionproof.claims.checkpoint_states import (
    ClaimPostureAlertLifecycleCheckpointCurrencySnapshot,
    ClaimPostureAlertLifecycleCheckpointCurrencyStatus,
)
from ix_missionproof.claims.review_followups import (
    ClaimPostureAlertLifecycleReviewFollowUpSnapshot,
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

_REVIEW_RESOLUTION_PRODUCER_KINDS: Final[
    frozenset[ActorKind]
] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleReviewResolutionStatus(StrEnum):
    """Current resolution state of a prior lifecycle-review obligation."""

    NO_OPEN_OBLIGATION = "no-open-obligation"
    RESOLVED_BY_ACCEPTED_CHECKPOINT = (
        "resolved-by-accepted-checkpoint"
    )
    OPEN_UNRESPONDED = "open-unresponded"
    OPEN_TRACKED = "open-tracked"
    OPEN_OVERDUE = "open-overdue"
    CORRECTIVE_ACTION_REQUIRED = "corrective-action-required"
    SUPERSEDED_BY_NEW_HEAD = "superseded-by-new-head"

    @property
    def prior_obligation_resolved(self) -> bool:
        """Return whether the prior obligation is no longer current."""

        return self in {
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .NO_OPEN_OBLIGATION
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .RESOLVED_BY_ACCEPTED_CHECKPOINT
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .SUPERSEDED_BY_NEW_HEAD
            ),
        }

    @property
    def current_obligation_open(self) -> bool:
        """Return whether the current chain head needs human action."""

        return self in {
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_UNRESPONDED
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_TRACKED
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_OVERDUE
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .CORRECTIVE_ACTION_REQUIRED
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .SUPERSEDED_BY_NEW_HEAD
            ),
        }

    @property
    def requires_immediate_attention(self) -> bool:
        """Return whether prompt human attention is required."""

        return self in {
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_UNRESPONDED
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_OVERDUE
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .CORRECTIVE_ACTION_REQUIRED
            ),
            (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .SUPERSEDED_BY_NEW_HEAD
            ),
        }


def _require_identifier(
    value: ScopedIdentifier,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if not isinstance(
        value,
        ScopedIdentifier,
    ):
        raise FoundationError(
            f"{field_name} must be a ScopedIdentifier"
        )

    if value.namespace != CanonicalKey(
        namespace
    ):
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
    if not isinstance(
        value,
        ContentDigest,
    ):
        raise FoundationError(
            f"{field_name} must be a ContentDigest"
        )

    if value.domain != CanonicalKey(
        domain
    ):
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


def _validate_review_resolution_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "review-resolution producer must be active"
        )

    if producer.kind not in (
        _REVIEW_RESOLUTION_PRODUCER_KINDS
    ):
        raise FoundationError(
            "review-resolution producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "review-resolution producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleReviewResolutionSnapshot:
    """Reconcile a prior review obligation with current checkpoint state."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-review-resolution-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    reconciled_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleReviewResolutionStatus
    chain_id: ScopedIdentifier
    previous_generation_count: int
    current_generation_count: int
    previous_head_entry_id: ScopedIdentifier
    current_head_entry_id: ScopedIdentifier
    previous_review_docket_id: ScopedIdentifier
    current_review_docket_id: ScopedIdentifier
    previous_follow_up_snapshot_id: ScopedIdentifier
    current_currency_snapshot_id: ScopedIdentifier
    previous_review_docket_status: (
        ClaimPostureAlertLifecycleReviewDocketStatus
    )
    current_review_docket_status: (
        ClaimPostureAlertLifecycleReviewDocketStatus
    )
    current_review_reason: (
        ClaimPostureAlertLifecycleReviewReason | None
    )
    current_review_priority: (
        ClaimPostureAlertLifecycleReviewPriority
    )
    current_currency_status: (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus
    )
    previous_response_count: int
    previous_latest_response_id: ScopedIdentifier | None
    previous_assigned_to_id: ScopedIdentifier | None
    previous_action_due_at: UtcTimestamp | None
    chain_digest: ContentDigest
    previous_head_entry_digest: ContentDigest
    current_head_entry_digest: ContentDigest
    previous_review_docket_digest: ContentDigest
    current_review_docket_digest: ContentDigest
    previous_follow_up_snapshot_digest: ContentDigest
    current_currency_snapshot_digest: ContentDigest
    previous_response_ledger_digest: ContentDigest
    previous_latest_response_digest: ContentDigest | None
    previous_current_alert_docket_digest: ContentDigest
    current_alert_docket_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_response_presence()
        self._validate_resolution_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-resolution-snapshot"
                ),
            ),
            (
                "chain_id",
                self.chain_id,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "previous_head_entry_id",
                self.previous_head_entry_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "current_head_entry_id",
                self.current_head_entry_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "previous_review_docket_id",
                self.previous_review_docket_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "current_review_docket_id",
                self.current_review_docket_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "previous_follow_up_snapshot_id",
                self.previous_follow_up_snapshot_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-follow-up-snapshot"
                ),
            ),
            (
                "current_currency_snapshot_id",
                self.current_currency_snapshot_id,
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
            self.previous_latest_response_id,
            field_name="previous_latest_response_id",
            namespace=(
                "claim-posture-alert-lifecycle-"
                "review-response"
            ),
        )
        _require_optional_identifier(
            self.previous_assigned_to_id,
            field_name="previous_assigned_to_id",
            namespace="human",
        )

        if not isinstance(
            self.reconciled_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "reconciled_at must be a UtcTimestamp"
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
            _REVIEW_RESOLUTION_PRODUCER_KINDS
        ):
            raise FoundationError(
                "review-resolution producer must be "
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
            ClaimPostureAlertLifecycleReviewResolutionStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertLifecycleReviewResolutionStatus"
            )

        if not isinstance(
            self.previous_review_docket_status,
            ClaimPostureAlertLifecycleReviewDocketStatus,
        ):
            raise FoundationError(
                "previous_review_docket_status must be a "
                "ClaimPostureAlertLifecycleReviewDocketStatus"
            )

        if not isinstance(
            self.current_review_docket_status,
            ClaimPostureAlertLifecycleReviewDocketStatus,
        ):
            raise FoundationError(
                "current_review_docket_status must be a "
                "ClaimPostureAlertLifecycleReviewDocketStatus"
            )

        if (
            self.current_review_reason is not None
            and not isinstance(
                self.current_review_reason,
                ClaimPostureAlertLifecycleReviewReason,
            )
        ):
            raise FoundationError(
                "current_review_reason must be a "
                "ClaimPostureAlertLifecycleReviewReason or None"
            )

        if not isinstance(
            self.current_review_priority,
            ClaimPostureAlertLifecycleReviewPriority,
        ):
            raise FoundationError(
                "current_review_priority must be a "
                "ClaimPostureAlertLifecycleReviewPriority"
            )

        if not isinstance(
            self.current_currency_status,
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus,
        ):
            raise FoundationError(
                "current_currency_status must be a "
                "ClaimPostureAlertLifecycleCheckpointCurrencyStatus"
            )

        if (
            self.previous_action_due_at is not None
            and not isinstance(
                self.previous_action_due_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "previous_action_due_at must be "
                "a UtcTimestamp or None"
            )

        for field_name, value, minimum in (
            (
                "previous_generation_count",
                self.previous_generation_count,
                1,
            ),
            (
                "current_generation_count",
                self.current_generation_count,
                1,
            ),
            (
                "previous_response_count",
                self.previous_response_count,
                0,
            ),
        ):
            if isinstance(
                value,
                bool,
            ) or not isinstance(
                value,
                int,
            ):
                raise FoundationError(
                    f"{field_name} must be an integer"
                )

            if value < minimum:
                raise FoundationError(
                    f"{field_name} must be at least {minimum}"
                )

        if (
            self.previous_generation_count
            > self.current_generation_count
        ):
            raise FoundationError(
                "previous generation must not be newer "
                "than the current generation"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "chain_digest",
                self.chain_digest,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "previous_head_entry_digest",
                self.previous_head_entry_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "current_head_entry_digest",
                self.current_head_entry_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "previous_review_docket_digest",
                self.previous_review_docket_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "current_review_docket_digest",
                self.current_review_docket_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "previous_follow_up_snapshot_digest",
                self.previous_follow_up_snapshot_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-follow-up-snapshot"
                ),
            ),
            (
                "current_currency_snapshot_digest",
                self.current_currency_snapshot_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
            ),
            (
                "previous_response_ledger_digest",
                self.previous_response_ledger_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-response-ledger"
                ),
            ),
            (
                "previous_current_alert_docket_digest",
                self.previous_current_alert_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "current_alert_docket_digest",
                self.current_alert_docket_digest,
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
            self.previous_latest_response_digest,
            field_name="previous_latest_response_digest",
            domain=(
                "claim-posture-alert-lifecycle-"
                "review-response"
            ),
        )

    def _validate_response_presence(self) -> None:
        response_fields = (
            self.previous_latest_response_id,
            self.previous_latest_response_digest,
        )
        response_present = all(
            value is not None
            for value in response_fields
        )
        response_absent = all(
            value is None
            for value in response_fields
        )

        if not response_present and not response_absent:
            raise FoundationError(
                "previous latest-response identity and digest "
                "must be present or absent together"
            )

        if (
            self.previous_response_count == 0
            and not response_absent
        ):
            raise FoundationError(
                "zero previous response count must not contain "
                "latest-response data"
            )

        if (
            self.previous_response_count > 0
            and not response_present
        ):
            raise FoundationError(
                "positive previous response count requires "
                "latest-response data"
            )

        if response_absent and (
            self.previous_assigned_to_id is not None
            or self.previous_action_due_at is not None
        ):
            raise FoundationError(
                "resolution without previous response data must not "
                "contain assignment or due-date data"
            )

    def _validate_resolution_semantics(self) -> None:
        same_generation = (
            self.previous_generation_count
            == self.current_generation_count
        )
        same_head = (
            self.previous_head_entry_id
            == self.current_head_entry_id
            and self.previous_head_entry_digest
            == self.current_head_entry_digest
        )

        if same_generation and not same_head:
            raise FoundationError(
                "same-generation review reconciliation requires "
                "the same chain head"
            )

        if not same_generation and same_head:
            raise FoundationError(
                "newer generation must use a different chain head"
            )

        expected_status = self.classify(
            previous_review_docket_status=(
                self.previous_review_docket_status
            ),
            current_review_docket_status=(
                self.current_review_docket_status
            ),
            current_currency_status=self.current_currency_status,
            generation_advanced=not same_generation,
            previous_response_applies=(
                self.previous_response_applies_to_current_obligation
            ),
            previous_response_count=self.previous_response_count,
            previous_follow_up_overdue=self.previous_follow_up_overdue,
        )

        if self.status is not expected_status:
            raise FoundationError(
                "review-resolution status does not match "
                "the current checkpoint and obligation state"
            )

        if self.current_review_docket_status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            if self.current_review_reason is not None:
                raise FoundationError(
                    "clear current review docket must not "
                    "contain a review reason"
                )

            if self.current_currency_status is not (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .ACCEPTED
            ):
                raise FoundationError(
                    "clear current review docket requires "
                    "an accepted current checkpoint"
                )

        elif self.current_review_reason is None:
            raise FoundationError(
                "open current review docket requires a reason"
            )

        if self.status is (
            ClaimPostureAlertLifecycleReviewResolutionStatus
            .RESOLVED_BY_ACCEPTED_CHECKPOINT
        ):
            if self.previous_review_docket_status is (
                ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
            ):
                raise FoundationError(
                    "accepted-checkpoint resolution requires "
                    "a previously open obligation"
                )

            if not same_generation:
                raise FoundationError(
                    "accepted-checkpoint resolution must bind "
                    "the same chain head"
                )

        if self.status is (
            ClaimPostureAlertLifecycleReviewResolutionStatus
            .NO_OPEN_OBLIGATION
        ):
            if (
                self.previous_review_docket_status
                is not (
                    ClaimPostureAlertLifecycleReviewDocketStatus
                    .CLEAR
                )
                or self.current_review_docket_status
                is not (
                    ClaimPostureAlertLifecycleReviewDocketStatus
                    .CLEAR
                )
            ):
                raise FoundationError(
                    "no-open-obligation resolution requires "
                    "both review dockets to be clear"
                )

        if self.status is (
            ClaimPostureAlertLifecycleReviewResolutionStatus
            .SUPERSEDED_BY_NEW_HEAD
        ) and same_generation:
            raise FoundationError(
                "superseded review resolution requires "
                "a newer chain generation"
            )

    @classmethod
    def reconcile(
        cls,
        *,
        key: str,
        reconciled_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        previous_review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        previous_follow_up: (
            ClaimPostureAlertLifecycleReviewFollowUpSnapshot
        ),
        current_chain: ClaimPostureAlertLifecycleChain,
        current_currency_snapshot: (
            ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        ),
        current_review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleReviewResolutionSnapshot:
        """Reconcile an older obligation with current checkpoint state."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = (
            _validate_review_resolution_producer(
                producer
            )
        )

        previous_head, current_head = cls._validate_bindings(
            reconciled_at=reconciled_at,
            previous_review_docket=previous_review_docket,
            previous_follow_up=previous_follow_up,
            current_chain=current_chain,
            current_currency_snapshot=current_currency_snapshot,
            current_review_docket=current_review_docket,
            actor_registry=actor_registry,
        )

        generation_advanced = (
            previous_review_docket.generation_count
            < current_chain.generation_count
        )
        response_applies = (
            not generation_advanced
            and previous_review_docket.digest()
            == current_review_docket.digest()
        )

        status = cls.classify(
            previous_review_docket_status=(
                previous_review_docket.status
            ),
            current_review_docket_status=(
                current_review_docket.status
            ),
            current_currency_status=(
                current_currency_snapshot.status
            ),
            generation_advanced=generation_advanced,
            previous_response_applies=response_applies,
            previous_response_count=(
                previous_follow_up.response_count
            ),
            previous_follow_up_overdue=(
                previous_follow_up.is_overdue
            ),
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-"
                    "review-resolution-snapshot"
                ),
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            reconciled_at=reconciled_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            status=status,
            chain_id=current_chain.chain_id,
            previous_generation_count=(
                previous_review_docket.generation_count
            ),
            current_generation_count=(
                current_chain.generation_count
            ),
            previous_head_entry_id=previous_head.entry_id,
            current_head_entry_id=current_head.entry_id,
            previous_review_docket_id=(
                previous_review_docket.docket_id
            ),
            current_review_docket_id=(
                current_review_docket.docket_id
            ),
            previous_follow_up_snapshot_id=(
                previous_follow_up.snapshot_id
            ),
            current_currency_snapshot_id=(
                current_currency_snapshot.snapshot_id
            ),
            previous_review_docket_status=(
                previous_review_docket.status
            ),
            current_review_docket_status=(
                current_review_docket.status
            ),
            current_review_reason=current_review_docket.reason,
            current_review_priority=current_review_docket.priority,
            current_currency_status=(
                current_currency_snapshot.status
            ),
            previous_response_count=(
                previous_follow_up.response_count
            ),
            previous_latest_response_id=(
                previous_follow_up.latest_response_id
            ),
            previous_assigned_to_id=(
                previous_follow_up.assigned_to_id
            ),
            previous_action_due_at=(
                previous_follow_up.action_due_at
            ),
            chain_digest=current_chain.digest(),
            previous_head_entry_digest=previous_head.digest(),
            current_head_entry_digest=current_head.digest(),
            previous_review_docket_digest=(
                previous_review_docket.digest()
            ),
            current_review_docket_digest=(
                current_review_docket.digest()
            ),
            previous_follow_up_snapshot_digest=(
                previous_follow_up.digest()
            ),
            current_currency_snapshot_digest=(
                current_currency_snapshot.digest()
            ),
            previous_response_ledger_digest=(
                previous_follow_up.response_ledger_digest
            ),
            previous_latest_response_digest=(
                previous_follow_up.latest_response_digest
            ),
            previous_current_alert_docket_digest=(
                previous_review_docket
                .current_alert_docket_digest
            ),
            current_alert_docket_digest=(
                current_review_docket
                .current_alert_docket_digest
            ),
            claim_catalog_digest=(
                current_chain.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        reconciled_at: UtcTimestamp,
        previous_review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        previous_follow_up: (
            ClaimPostureAlertLifecycleReviewFollowUpSnapshot
        ),
        current_chain: ClaimPostureAlertLifecycleChain,
        current_currency_snapshot: (
            ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        ),
        current_review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        actor_registry: ActorRegistry,
    ) -> tuple[
        ClaimPostureAlertLifecycleChainEntry,
        ClaimPostureAlertLifecycleChainEntry,
    ]:
        actor_registry_digest = actor_registry.digest()

        for role, digest in (
            (
                "previous lifecycle-review docket",
                previous_review_docket.actor_registry_digest,
            ),
            (
                "previous review follow-up",
                previous_follow_up.actor_registry_digest,
            ),
            (
                "current lifecycle chain",
                current_chain.actor_registry_digest,
            ),
            (
                "current checkpoint-currency snapshot",
                current_currency_snapshot.actor_registry_digest,
            ),
            (
                "current lifecycle-review docket",
                current_review_docket.actor_registry_digest,
            ),
        ):
            if digest != actor_registry_digest:
                raise FoundationError(
                    f"{role} is not bound to "
                    "the supplied actor registry"
                )

        if (
            previous_follow_up.review_docket_id
            != previous_review_docket.docket_id
        ):
            raise FoundationError(
                "previous review follow-up references "
                "a different lifecycle-review docket"
            )

        if (
            previous_follow_up.review_docket_digest
            != previous_review_docket.digest()
        ):
            raise FoundationError(
                "previous review follow-up is not bound to "
                "the previous lifecycle-review docket"
            )

        if (
            previous_follow_up.chain_id
            != previous_review_docket.chain_id
        ):
            raise FoundationError(
                "previous review follow-up references "
                "a different lifecycle chain"
            )

        if (
            previous_follow_up.generation_count
            != previous_review_docket.generation_count
        ):
            raise FoundationError(
                "previous review follow-up references "
                "a different chain generation"
            )

        if (
            previous_follow_up.head_entry_id
            != previous_review_docket.head_entry_id
        ):
            raise FoundationError(
                "previous review follow-up references "
                "a different chain head"
            )

        if (
            previous_follow_up.head_entry_digest
            != previous_review_docket.head_entry_digest
        ):
            raise FoundationError(
                "previous review follow-up is not bound to "
                "the previous chain head"
            )

        if (
            previous_review_docket.chain_id
            != current_chain.chain_id
        ):
            raise FoundationError(
                "previous lifecycle-review docket references "
                "a different lifecycle chain"
            )

        if current_review_docket.chain_id != current_chain.chain_id:
            raise FoundationError(
                "current lifecycle-review docket references "
                "a different lifecycle chain"
            )

        if (
            current_currency_snapshot.chain_id
            != current_chain.chain_id
        ):
            raise FoundationError(
                "current checkpoint-currency snapshot references "
                "a different lifecycle chain"
            )

        if (
            current_currency_snapshot.chain_digest
            != current_chain.digest()
        ):
            raise FoundationError(
                "current checkpoint-currency snapshot is not bound "
                "to the current lifecycle-chain digest"
            )

        if (
            current_review_docket.chain_digest
            != current_chain.digest()
        ):
            raise FoundationError(
                "current lifecycle-review docket is not bound "
                "to the current lifecycle-chain digest"
            )

        if (
            current_review_docket
            .checkpoint_currency_snapshot_id
            != current_currency_snapshot.snapshot_id
        ):
            raise FoundationError(
                "current lifecycle-review docket references "
                "a different checkpoint-currency snapshot"
            )

        if (
            current_review_docket
            .checkpoint_currency_snapshot_digest
            != current_currency_snapshot.digest()
        ):
            raise FoundationError(
                "current lifecycle-review docket is not bound "
                "to the checkpoint-currency snapshot"
            )

        if (
            current_review_docket.generation_count
            != current_chain.generation_count
        ):
            raise FoundationError(
                "current lifecycle-review docket does not describe "
                "the current chain generation"
            )

        current_head = current_chain.latest_entry

        if current_head is None:
            raise FoundationError(
                "review-resolution snapshot requires "
                "a nonempty lifecycle chain"
            )

        if (
            current_review_docket.head_entry_id
            != current_head.entry_id
        ):
            raise FoundationError(
                "current lifecycle-review docket references "
                "a different current chain head"
            )

        if (
            current_review_docket.head_entry_digest
            != current_head.digest()
        ):
            raise FoundationError(
                "current lifecycle-review docket head digest "
                "does not match the lifecycle chain"
            )

        if (
            current_currency_snapshot.current_head_entry_id
            != current_head.entry_id
        ):
            raise FoundationError(
                "current checkpoint-currency snapshot references "
                "a different current chain head"
            )

        if (
            current_currency_snapshot.current_head_entry_digest
            != current_head.digest()
        ):
            raise FoundationError(
                "current checkpoint-currency head digest "
                "does not match the lifecycle chain"
            )

        if (
            previous_review_docket.generation_count
            > current_chain.generation_count
        ):
            raise FoundationError(
                "previous review docket references a generation "
                "newer than the current lifecycle chain"
            )

        previous_head = current_chain.require_entry_for_sequence(
            previous_review_docket.generation_count
        )

        if (
            previous_head.entry_id
            != previous_review_docket.head_entry_id
        ):
            raise FoundationError(
                "previous review-docket head identity does not "
                "match the current lifecycle-chain history"
            )

        if (
            previous_head.digest()
            != previous_review_docket.head_entry_digest
        ):
            raise FoundationError(
                "previous review-docket head digest does not "
                "match the current lifecycle-chain history"
            )

        for role, digest in (
            (
                "previous lifecycle-review docket",
                previous_review_docket.claim_catalog_digest,
            ),
            (
                "previous review follow-up",
                previous_follow_up.claim_catalog_digest,
            ),
            (
                "current checkpoint-currency snapshot",
                current_currency_snapshot.claim_catalog_digest,
            ),
            (
                "current lifecycle-review docket",
                current_review_docket.claim_catalog_digest,
            ),
        ):
            if digest != current_chain.claim_catalog_digest:
                raise FoundationError(
                    f"{role} is not bound to "
                    "the current claim catalog"
                )

        if (
            reconciled_at.value
            < previous_follow_up.assessed_at.value
        ):
            raise FoundationError(
                "review-resolution snapshot must not predate "
                "the previous follow-up assessment"
            )

        if (
            reconciled_at.value
            < current_currency_snapshot.assessed_at.value
        ):
            raise FoundationError(
                "review-resolution snapshot must not predate "
                "the current checkpoint-currency assessment"
            )

        if (
            reconciled_at.value
            < current_review_docket.generated_at.value
        ):
            raise FoundationError(
                "review-resolution snapshot must not predate "
                "the current lifecycle-review docket"
            )

        return previous_head, current_head

    @staticmethod
    def classify(
        *,
        previous_review_docket_status: (
            ClaimPostureAlertLifecycleReviewDocketStatus
        ),
        current_review_docket_status: (
            ClaimPostureAlertLifecycleReviewDocketStatus
        ),
        current_currency_status: (
            ClaimPostureAlertLifecycleCheckpointCurrencyStatus
        ),
        generation_advanced: bool,
        previous_response_applies: bool,
        previous_response_count: int,
        previous_follow_up_overdue: bool,
    ) -> ClaimPostureAlertLifecycleReviewResolutionStatus:
        """Classify current resolution without crediting response activity."""

        if generation_advanced:
            return (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .SUPERSEDED_BY_NEW_HEAD
            )

        if current_review_docket_status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            if current_currency_status is not (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .ACCEPTED
            ):
                raise FoundationError(
                    "clear current review docket requires "
                    "accepted checkpoint currency"
                )

            if previous_review_docket_status is (
                ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
            ):
                return (
                    ClaimPostureAlertLifecycleReviewResolutionStatus
                    .NO_OPEN_OBLIGATION
                )

            return (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .RESOLVED_BY_ACCEPTED_CHECKPOINT
            )

        if current_review_docket_status is (
            ClaimPostureAlertLifecycleReviewDocketStatus
            .CORRECTIVE_ACTION_REQUIRED
        ):
            return (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .CORRECTIVE_ACTION_REQUIRED
            )

        if not previous_response_applies:
            return (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_UNRESPONDED
            )

        if previous_follow_up_overdue:
            return (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_OVERDUE
            )

        if previous_response_count > 0:
            return (
                ClaimPostureAlertLifecycleReviewResolutionStatus
                .OPEN_TRACKED
            )

        return (
            ClaimPostureAlertLifecycleReviewResolutionStatus
            .OPEN_UNRESPONDED
        )

    @property
    def generation_advanced(self) -> bool:
        """Return whether the lifecycle chain moved to a newer head."""

        return (
            self.current_generation_count
            > self.previous_generation_count
        )

    @property
    def same_chain_head(self) -> bool:
        """Return whether both obligations address the same head."""

        return (
            not self.generation_advanced
            and self.previous_head_entry_id
            == self.current_head_entry_id
            and self.previous_head_entry_digest
            == self.current_head_entry_digest
        )

    @property
    def previous_review_docket_is_current(self) -> bool:
        """Return whether the prior docket is the exact current docket."""

        return (
            self.same_chain_head
            and self.previous_review_docket_id
            == self.current_review_docket_id
            and self.previous_review_docket_digest
            == self.current_review_docket_digest
        )

    @property
    def previous_response_applies_to_current_obligation(self) -> bool:
        """Return whether prior response activity binds the current docket."""

        return self.previous_review_docket_is_current

    @property
    def previous_follow_up_overdue(self) -> bool:
        """Return whether prior assigned work is overdue at reconciliation."""

        return (
            self.previous_action_due_at is not None
            and self.reconciled_at.value
            > self.previous_action_due_at.value
        )

    @property
    def prior_obligation_resolved(self) -> bool:
        """Return whether the prior obligation is no longer current."""

        return self.status.prior_obligation_resolved

    @property
    def current_obligation_open(self) -> bool:
        """Return whether the current docket requires human action."""

        return (
            self.current_review_docket_status
            is not ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        )

    @property
    def requires_human_action(self) -> bool:
        """Return whether the current review docket remains actionable."""

        return self.current_obligation_open

    @property
    def requires_immediate_attention(self) -> bool:
        """Return whether prompt action is required."""

        return self.status.requires_immediate_attention

    @property
    def resolved_by_current_checkpoint(self) -> bool:
        """Return whether current accepted review resolved the obligation."""

        return self.status is (
            ClaimPostureAlertLifecycleReviewResolutionStatus
            .RESOLVED_BY_ACCEPTED_CHECKPOINT
        )

    @property
    def resolved_by_response_activity(self) -> bool:
        """Return false because responses cannot resolve review."""

        return False

    @property
    def continuity_reliance_allowed(self) -> bool:
        """Return whether current-head continuity is accepted."""

        return (
            self.current_review_docket_status
            is ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
            and self.current_currency_status
            is (
                ClaimPostureAlertLifecycleCheckpointCurrencyStatus
                .ACCEPTED
            )
            and not self.generation_advanced
        )

    @property
    def previous_response_carries_forward(self) -> bool:
        """Return whether old response activity applies unchanged."""

        return (
            self.previous_response_applies_to_current_obligation
            and self.previous_response_count > 0
        )

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because continuity acceptance is not claim approval."""

        return False

    @property
    def clears_claim_alerts(self) -> bool:
        """Return false because only claim posture clears claim alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because reconciliation does not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because reconciliation grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic review-resolution representation."""

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
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_claim_alerts": self.clears_claim_alerts,
            "continuity_reliance_allowed": (
                self.continuity_reliance_allowed
            ),
            "current_alert_docket_digest": (
                self.current_alert_docket_digest.to_payload()
            ),
            "current_currency_snapshot_digest": (
                self.current_currency_snapshot_digest.to_payload()
            ),
            "current_currency_snapshot_id": str(
                self.current_currency_snapshot_id
            ),
            "current_currency_status": (
                self.current_currency_status.value
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
            "current_obligation_open": self.current_obligation_open,
            "current_review_docket_digest": (
                self.current_review_docket_digest.to_payload()
            ),
            "current_review_docket_id": str(
                self.current_review_docket_id
            ),
            "current_review_docket_status": (
                self.current_review_docket_status.value
            ),
            "current_review_priority": (
                self.current_review_priority.value
            ),
            "current_review_reason": (
                self.current_review_reason.value
                if self.current_review_reason is not None
                else None
            ),
            "generation_advanced": self.generation_advanced,
            "grants_authority": self.grants_authority,
            "previous_action_due_at": (
                self.previous_action_due_at.isoformat()
                if self.previous_action_due_at is not None
                else None
            ),
            "previous_assigned_to_id": (
                str(self.previous_assigned_to_id)
                if self.previous_assigned_to_id is not None
                else None
            ),
            "previous_current_alert_docket_digest": (
                self.previous_current_alert_docket_digest
                .to_payload()
            ),
            "previous_follow_up_overdue": (
                self.previous_follow_up_overdue
            ),
            "previous_follow_up_snapshot_digest": (
                self.previous_follow_up_snapshot_digest.to_payload()
            ),
            "previous_follow_up_snapshot_id": str(
                self.previous_follow_up_snapshot_id
            ),
            "previous_generation_count": (
                self.previous_generation_count
            ),
            "previous_head_entry_digest": (
                self.previous_head_entry_digest.to_payload()
            ),
            "previous_head_entry_id": str(
                self.previous_head_entry_id
            ),
            "previous_latest_response_digest": (
                self.previous_latest_response_digest.to_payload()
                if self.previous_latest_response_digest is not None
                else None
            ),
            "previous_latest_response_id": (
                str(self.previous_latest_response_id)
                if self.previous_latest_response_id is not None
                else None
            ),
            "previous_response_applies_to_current_obligation": (
                self.previous_response_applies_to_current_obligation
            ),
            "previous_response_carries_forward": (
                self.previous_response_carries_forward
            ),
            "previous_response_count": (
                self.previous_response_count
            ),
            "previous_response_ledger_digest": (
                self.previous_response_ledger_digest.to_payload()
            ),
            "previous_review_docket_digest": (
                self.previous_review_docket_digest.to_payload()
            ),
            "previous_review_docket_id": str(
                self.previous_review_docket_id
            ),
            "previous_review_docket_is_current": (
                self.previous_review_docket_is_current
            ),
            "previous_review_docket_status": (
                self.previous_review_docket_status.value
            ),
            "prior_obligation_resolved": (
                self.prior_obligation_resolved
            ),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "reconciled_at": self.reconciled_at.isoformat(),
            "requires_human_action": self.requires_human_action,
            "requires_immediate_attention": (
                self.requires_immediate_attention
            ),
            "resolved_by_current_checkpoint": (
                self.resolved_by_current_checkpoint
            ),
            "resolved_by_response_activity": (
                self.resolved_by_response_activity
            ),
            "same_chain_head": self.same_chain_head,
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical resolution snapshot."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete reconciliation."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-"
                "review-resolution-snapshot"
            )
        )
