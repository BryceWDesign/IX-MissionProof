"""Operational follow-up state for lifecycle-review obligations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.checkpoint_reviews import (
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
    ClaimPostureAlertLifecycleReviewPriority,
    ClaimPostureAlertLifecycleReviewReason,
)
from ix_missionproof.claims.review_responses import (
    ClaimPostureAlertLifecycleReviewResponse,
    ClaimPostureAlertLifecycleReviewResponseAction,
    ClaimPostureAlertLifecycleReviewResponseLedger,
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

_REVIEW_FOLLOW_UP_PRODUCER_KINDS: Final[
    frozenset[ActorKind]
] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleReviewFollowUpStatus(StrEnum):
    """Latest operational response state for one review obligation."""

    CLEAR = "clear"
    UNRESPONDED = "unresponded"
    ACKNOWLEDGED = "acknowledged"
    REVIEW_ASSIGNED = "review-assigned"
    ESCALATED = "escalated"
    CORRECTIVE_ACTION_OPEN = "corrective-action-open"

    @property
    def has_response(self) -> bool:
        """Return whether human activity exists for the obligation."""

        return self not in {
            ClaimPostureAlertLifecycleReviewFollowUpStatus.CLEAR,
            ClaimPostureAlertLifecycleReviewFollowUpStatus.UNRESPONDED,
        }

    @property
    def has_assignment(self) -> bool:
        """Return whether the latest response requires an assignee."""

        return self in {
            (
                ClaimPostureAlertLifecycleReviewFollowUpStatus
                .REVIEW_ASSIGNED
            ),
            ClaimPostureAlertLifecycleReviewFollowUpStatus.ESCALATED,
            (
                ClaimPostureAlertLifecycleReviewFollowUpStatus
                .CORRECTIVE_ACTION_OPEN
            ),
        }

    @property
    def tracks_open_obligation(self) -> bool:
        """Return whether the status represents tracked open work."""

        return self in {
            (
                ClaimPostureAlertLifecycleReviewFollowUpStatus
                .ACKNOWLEDGED
            ),
            (
                ClaimPostureAlertLifecycleReviewFollowUpStatus
                .REVIEW_ASSIGNED
            ),
            ClaimPostureAlertLifecycleReviewFollowUpStatus.ESCALATED,
            (
                ClaimPostureAlertLifecycleReviewFollowUpStatus
                .CORRECTIVE_ACTION_OPEN
            ),
        }


_ACTION_TO_STATUS: Final[
    dict[
        ClaimPostureAlertLifecycleReviewResponseAction,
        ClaimPostureAlertLifecycleReviewFollowUpStatus,
    ]
] = {
    ClaimPostureAlertLifecycleReviewResponseAction.ACKNOWLEDGE: (
        ClaimPostureAlertLifecycleReviewFollowUpStatus.ACKNOWLEDGED
    ),
    ClaimPostureAlertLifecycleReviewResponseAction.ASSIGN_REVIEW: (
        ClaimPostureAlertLifecycleReviewFollowUpStatus.REVIEW_ASSIGNED
    ),
    ClaimPostureAlertLifecycleReviewResponseAction.ESCALATE: (
        ClaimPostureAlertLifecycleReviewFollowUpStatus.ESCALATED
    ),
    (
        ClaimPostureAlertLifecycleReviewResponseAction
        .OPEN_CORRECTIVE_ACTION
    ): (
        ClaimPostureAlertLifecycleReviewFollowUpStatus
        .CORRECTIVE_ACTION_OPEN
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


def _validate_review_follow_up_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "review follow-up producer must be active"
        )
    if producer.kind not in (
        _REVIEW_FOLLOW_UP_PRODUCER_KINDS
    ):
        raise FoundationError(
            "review follow-up producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "review follow-up producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleReviewFollowUpSnapshot:
    """Current operational state of one exact review obligation."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-review-follow-up-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    assessed_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleReviewFollowUpStatus
    review_docket_id: ScopedIdentifier
    review_docket_status: (
        ClaimPostureAlertLifecycleReviewDocketStatus
    )
    review_reason: ClaimPostureAlertLifecycleReviewReason | None
    review_priority: ClaimPostureAlertLifecycleReviewPriority
    chain_id: ScopedIdentifier
    generation_count: int
    head_entry_id: ScopedIdentifier
    response_ledger_id: ScopedIdentifier
    response_count: int
    latest_response_id: ScopedIdentifier | None
    latest_response_action: (
        ClaimPostureAlertLifecycleReviewResponseAction | None
    )
    latest_responded_at: UtcTimestamp | None
    latest_responded_by_id: ScopedIdentifier | None
    assigned_to_id: ScopedIdentifier | None
    action_due_at: UtcTimestamp | None
    review_docket_digest: ContentDigest
    response_ledger_digest: ContentDigest
    chain_digest: ContentDigest
    head_entry_digest: ContentDigest
    current_alert_docket_digest: ContentDigest
    checkpoint_currency_snapshot_digest: ContentDigest
    latest_response_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_response_presence()
        self._validate_status_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-follow-up-snapshot"
                ),
            ),
            (
                "review_docket_id",
                self.review_docket_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "chain_id",
                self.chain_id,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "head_entry_id",
                self.head_entry_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "response_ledger_id",
                self.response_ledger_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-response-ledger"
                ),
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        _require_optional_identifier(
            self.latest_response_id,
            field_name="latest_response_id",
            namespace=(
                "claim-posture-alert-lifecycle-"
                "review-response"
            ),
        )
        _require_optional_identifier(
            self.latest_responded_by_id,
            field_name="latest_responded_by_id",
            namespace="human",
        )
        _require_optional_identifier(
            self.assigned_to_id,
            field_name="assigned_to_id",
            namespace="human",
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
            _REVIEW_FOLLOW_UP_PRODUCER_KINDS
        ):
            raise FoundationError(
                "review follow-up producer must be "
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
            ClaimPostureAlertLifecycleReviewFollowUpStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertLifecycleReviewFollowUpStatus"
            )
        if not isinstance(
            self.review_docket_status,
            ClaimPostureAlertLifecycleReviewDocketStatus,
        ):
            raise FoundationError(
                "review_docket_status must be a "
                "ClaimPostureAlertLifecycleReviewDocketStatus"
            )
        if (
            self.review_reason is not None
            and not isinstance(
                self.review_reason,
                ClaimPostureAlertLifecycleReviewReason,
            )
        ):
            raise FoundationError(
                "review_reason must be a "
                "ClaimPostureAlertLifecycleReviewReason or None"
            )
        if not isinstance(
            self.review_priority,
            ClaimPostureAlertLifecycleReviewPriority,
        ):
            raise FoundationError(
                "review_priority must be a "
                "ClaimPostureAlertLifecycleReviewPriority"
            )
        if (
            self.latest_response_action is not None
            and not isinstance(
                self.latest_response_action,
                (
                    ClaimPostureAlertLifecycleReviewResponseAction
                ),
            )
        ):
            raise FoundationError(
                "latest_response_action must be a "
                "ClaimPostureAlertLifecycleReviewResponseAction "
                "or None"
            )
        if (
            self.latest_responded_at is not None
            and not isinstance(
                self.latest_responded_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "latest_responded_at must be "
                "a UtcTimestamp or None"
            )
        if (
            self.action_due_at is not None
            and not isinstance(
                self.action_due_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "action_due_at must be "
                "a UtcTimestamp or None"
            )

        for field_name, value, minimum in (
            (
                "generation_count",
                self.generation_count,
                1,
            ),
            (
                "response_count",
                self.response_count,
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

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "review_docket_digest",
                self.review_docket_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "response_ledger_digest",
                self.response_ledger_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-response-ledger"
                ),
            ),
            (
                "chain_digest",
                self.chain_digest,
                "claim-posture-alert-lifecycle-chain",
            ),
            (
                "head_entry_digest",
                self.head_entry_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
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
            self.latest_response_digest,
            field_name="latest_response_digest",
            domain=(
                "claim-posture-alert-lifecycle-"
                "review-response"
            ),
        )

    def _validate_response_presence(self) -> None:
        response_fields = (
            self.latest_response_id,
            self.latest_response_action,
            self.latest_responded_at,
            self.latest_responded_by_id,
            self.latest_response_digest,
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
                "latest response identity, action, time, actor, "
                "and digest must be present or absent together"
            )

        if self.response_count == 0 and not response_absent:
            raise FoundationError(
                "zero response count must not contain "
                "latest response data"
            )

        if self.response_count > 0 and not response_present:
            raise FoundationError(
                "positive response count requires "
                "complete latest response data"
            )

        if response_absent:
            if (
                self.assigned_to_id is not None
                or self.action_due_at is not None
            ):
                raise FoundationError(
                    "follow-up without a response must not contain "
                    "assignment or due-date data"
                )
            return

        action = self.latest_response_action

        if action is None:
            raise FoundationError(
                "latest response action is required"
            )

        if (
            action.requires_assignment
            and self.assigned_to_id is None
        ):
            raise FoundationError(
                "latest response action requires "
                "an assigned human"
            )

        if (
            not action.requires_assignment
            and self.assigned_to_id is not None
        ):
            raise FoundationError(
                "latest response action must not "
                "contain an assignee"
            )

        if (
            action.requires_due_at
            and self.action_due_at is None
        ):
            raise FoundationError(
                "latest response action requires "
                "an action due time"
            )

        if (
            not action.requires_due_at
            and self.action_due_at is not None
        ):
            raise FoundationError(
                "latest response action must not "
                "contain an action due time"
            )

    def _validate_status_semantics(self) -> None:
        expected_status = self.classify(
            review_docket_status=self.review_docket_status,
            latest_response_action=self.latest_response_action,
        )

        if self.status is not expected_status:
            raise FoundationError(
                "review follow-up status does not match "
                "the review docket and latest response"
            )

        if self.status is (
            ClaimPostureAlertLifecycleReviewFollowUpStatus.CLEAR
        ):
            if self.response_count != 0:
                raise FoundationError(
                    "clear review follow-up must have "
                    "no response history"
                )
            if self.review_reason is not None:
                raise FoundationError(
                    "clear review follow-up must not contain "
                    "a review reason"
                )
            return

        if self.review_docket_status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            raise FoundationError(
                "clear review docket must produce "
                "a clear follow-up status"
            )

        if self.review_reason is None:
            raise FoundationError(
                "open review follow-up requires a review reason"
            )

        if (
            self.latest_responded_at is not None
            and self.assessed_at.value
            < self.latest_responded_at.value
        ):
            raise FoundationError(
                "review follow-up assessment must not predate "
                "the latest response"
            )

    @classmethod
    def assess(
        cls,
        *,
        key: str,
        assessed_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        response_ledger: (
            ClaimPostureAlertLifecycleReviewResponseLedger
        ),
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleReviewFollowUpSnapshot:
        """Assess response activity without closing the obligation."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = (
            _validate_review_follow_up_producer(
                producer
            )
        )

        cls._validate_bindings(
            assessed_at=assessed_at,
            review_docket=review_docket,
            response_ledger=response_ledger,
            actor_registry=actor_registry,
        )

        latest = response_ledger.latest_response
        status = cls.classify(
            review_docket_status=review_docket.status,
            latest_response_action=(
                latest.action
                if latest is not None
                else None
            ),
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-"
                    "review-follow-up-snapshot"
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
            review_docket_id=review_docket.docket_id,
            review_docket_status=review_docket.status,
            review_reason=review_docket.reason,
            review_priority=review_docket.priority,
            chain_id=review_docket.chain_id,
            generation_count=review_docket.generation_count,
            head_entry_id=review_docket.head_entry_id,
            response_ledger_id=response_ledger.ledger_id,
            response_count=response_ledger.response_count,
            latest_response_id=(
                latest.response_id
                if latest is not None
                else None
            ),
            latest_response_action=(
                latest.action
                if latest is not None
                else None
            ),
            latest_responded_at=(
                latest.responded_at
                if latest is not None
                else None
            ),
            latest_responded_by_id=(
                latest.responded_by_id
                if latest is not None
                else None
            ),
            assigned_to_id=(
                latest.assigned_to_id
                if latest is not None
                else None
            ),
            action_due_at=(
                latest.action_due_at
                if latest is not None
                else None
            ),
            review_docket_digest=review_docket.digest(),
            response_ledger_digest=response_ledger.digest(),
            chain_digest=review_docket.chain_digest,
            head_entry_digest=review_docket.head_entry_digest,
            current_alert_docket_digest=(
                review_docket.current_alert_docket_digest
            ),
            checkpoint_currency_snapshot_digest=(
                review_docket
                .checkpoint_currency_snapshot_digest
            ),
            latest_response_digest=(
                latest.digest()
                if latest is not None
                else None
            ),
            claim_catalog_digest=(
                review_docket.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        assessed_at: UtcTimestamp,
        review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        response_ledger: (
            ClaimPostureAlertLifecycleReviewResponseLedger
        ),
        actor_registry: ActorRegistry,
    ) -> None:
        actor_registry_digest = actor_registry.digest()

        if (
            review_docket.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "lifecycle-review docket is not bound to "
                "the supplied actor registry"
            )

        if (
            response_ledger.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "review-response ledger is not bound to "
                "the supplied actor registry"
            )

        if (
            response_ledger.review_docket_id
            != review_docket.docket_id
        ):
            raise FoundationError(
                "review-response ledger references "
                "a different lifecycle-review docket"
            )

        if (
            response_ledger.review_docket_digest
            != review_docket.digest()
        ):
            raise FoundationError(
                "review-response ledger is not bound to "
                "the supplied lifecycle-review docket"
            )

        if response_ledger.chain_id != review_docket.chain_id:
            raise FoundationError(
                "review-response ledger references "
                "a different lifecycle chain"
            )

        if (
            response_ledger.chain_digest
            != review_docket.chain_digest
        ):
            raise FoundationError(
                "review-response ledger is not bound to "
                "the review docket's lifecycle chain"
            )

        if (
            response_ledger.generation_count
            != review_docket.generation_count
        ):
            raise FoundationError(
                "review-response ledger references "
                "a different chain generation"
            )

        if (
            response_ledger.head_entry_id
            != review_docket.head_entry_id
        ):
            raise FoundationError(
                "review-response ledger references "
                "a different chain head"
            )

        if (
            response_ledger.head_entry_digest
            != review_docket.head_entry_digest
        ):
            raise FoundationError(
                "review-response ledger is not bound to "
                "the review docket's chain head"
            )

        if (
            response_ledger.current_alert_docket_digest
            != review_docket.current_alert_docket_digest
        ):
            raise FoundationError(
                "review-response ledger references "
                "a different current alert docket"
            )

        if (
            response_ledger
            .checkpoint_currency_snapshot_digest
            != review_docket
            .checkpoint_currency_snapshot_digest
        ):
            raise FoundationError(
                "review-response ledger references "
                "a different checkpoint-currency snapshot"
            )

        if (
            response_ledger.claim_catalog_digest
            != review_docket.claim_catalog_digest
        ):
            raise FoundationError(
                "review-response ledger and review docket "
                "must bind the same claim catalog"
            )

        if assessed_at.value < review_docket.generated_at.value:
            raise FoundationError(
                "review follow-up snapshot must not predate "
                "the lifecycle-review docket"
            )

        if assessed_at.value < response_ledger.created_at.value:
            raise FoundationError(
                "review follow-up snapshot must not predate "
                "the review-response ledger"
            )

    @staticmethod
    def classify(
        *,
        review_docket_status: (
            ClaimPostureAlertLifecycleReviewDocketStatus
        ),
        latest_response_action: (
            ClaimPostureAlertLifecycleReviewResponseAction | None
        ),
    ) -> ClaimPostureAlertLifecycleReviewFollowUpStatus:
        """Classify the latest operational follow-up state."""

        if review_docket_status is (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ):
            if latest_response_action is not None:
                raise FoundationError(
                    "clear lifecycle-review docket must not "
                    "contain response activity"
                )

            return (
                ClaimPostureAlertLifecycleReviewFollowUpStatus.CLEAR
            )

        if latest_response_action is None:
            return (
                ClaimPostureAlertLifecycleReviewFollowUpStatus
                .UNRESPONDED
            )

        return _ACTION_TO_STATUS[
            latest_response_action
        ]

    @property
    def obligation_remains_open(self) -> bool:
        """Return whether checkpoint state still requires attention."""

        return self.review_docket_status is not (
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        )

    @property
    def has_response(self) -> bool:
        """Return whether at least one human response exists."""

        return self.status.has_response

    @property
    def has_assignment(self) -> bool:
        """Return whether the latest response has an assignee."""

        return (
            self.status.has_assignment
            and self.assigned_to_id is not None
        )

    @property
    def response_tracks_obligation(self) -> bool:
        """Return whether response activity is tracking open work."""

        return self.status.tracks_open_obligation

    @property
    def is_overdue(self) -> bool:
        """Return whether the latest assigned action is overdue."""

        return (
            self.action_due_at is not None
            and self.assessed_at.value
            > self.action_due_at.value
        )

    @property
    def immediate_follow_up_required(self) -> bool:
        """Return whether response or overdue work needs attention."""

        return (
            self.obligation_remains_open
            and (
                not self.has_response
                or self.is_overdue
            )
        )

    @property
    def requires_human_action(self) -> bool:
        """Return whether the underlying docket remains actionable."""

        return self.obligation_remains_open

    @property
    def escalated(self) -> bool:
        """Return whether the latest action is escalation."""

        return self.status is (
            ClaimPostureAlertLifecycleReviewFollowUpStatus.ESCALATED
        )

    @property
    def corrective_action_open(self) -> bool:
        """Return whether corrective action is currently tracked."""

        return self.status is (
            ClaimPostureAlertLifecycleReviewFollowUpStatus
            .CORRECTIVE_ACTION_OPEN
        )

    @property
    def response_resolves_obligation(self) -> bool:
        """Return false because response activity cannot resolve review."""

        return False

    @property
    def accepts_continuity(self) -> bool:
        """Return false because follow-up activity cannot accept continuity."""

        return False

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because follow-up activity is not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because follow-up activity cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because follow-up state does not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because follow-up state grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic review follow-up snapshot."""

        return {
            "accepts_continuity": self.accepts_continuity,
            "action_due_at": (
                self.action_due_at.isoformat()
                if self.action_due_at is not None
                else None
            ),
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "approves_underlying_claims": (
                self.approves_underlying_claims
            ),
            "assessed_at": self.assessed_at.isoformat(),
            "assigned_to_id": (
                str(self.assigned_to_id)
                if self.assigned_to_id is not None
                else None
            ),
            "changes_claim_state": self.changes_claim_state,
            "chain_digest": self.chain_digest.to_payload(),
            "chain_id": str(self.chain_id),
            "checkpoint_currency_snapshot_digest": (
                self.checkpoint_currency_snapshot_digest
                .to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "corrective_action_open": self.corrective_action_open,
            "current_alert_docket_digest": (
                self.current_alert_docket_digest.to_payload()
            ),
            "escalated": self.escalated,
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "has_assignment": self.has_assignment,
            "has_response": self.has_response,
            "head_entry_digest": (
                self.head_entry_digest.to_payload()
            ),
            "head_entry_id": str(self.head_entry_id),
            "immediate_follow_up_required": (
                self.immediate_follow_up_required
            ),
            "is_overdue": self.is_overdue,
            "latest_responded_at": (
                self.latest_responded_at.isoformat()
                if self.latest_responded_at is not None
                else None
            ),
            "latest_responded_by_id": (
                str(self.latest_responded_by_id)
                if self.latest_responded_by_id is not None
                else None
            ),
            "latest_response_action": (
                self.latest_response_action.value
                if self.latest_response_action is not None
                else None
            ),
            "latest_response_digest": (
                self.latest_response_digest.to_payload()
                if self.latest_response_digest is not None
                else None
            ),
            "latest_response_id": (
                str(self.latest_response_id)
                if self.latest_response_id is not None
                else None
            ),
            "obligation_remains_open": (
                self.obligation_remains_open
            ),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "requires_human_action": self.requires_human_action,
            "response_count": self.response_count,
            "response_ledger_digest": (
                self.response_ledger_digest.to_payload()
            ),
            "response_ledger_id": str(
                self.response_ledger_id
            ),
            "response_resolves_obligation": (
                self.response_resolves_obligation
            ),
            "response_tracks_obligation": (
                self.response_tracks_obligation
            ),
            "review_docket_digest": (
                self.review_docket_digest.to_payload()
            ),
            "review_docket_id": str(self.review_docket_id),
            "review_docket_status": (
                self.review_docket_status.value
            ),
            "review_priority": self.review_priority.value,
            "review_reason": (
                self.review_reason.value
                if self.review_reason is not None
                else None
            ),
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical follow-up snapshot."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete follow-up state."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-"
                "review-follow-up-snapshot"
            )
        )
