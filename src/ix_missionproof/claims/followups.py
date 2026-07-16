"""Operational follow-up status for active claim-posture alerts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.alerts import (
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertSeverity,
)
from ix_missionproof.claims.responses import (
    ClaimPostureAlertResponse,
    ClaimPostureAlertResponseAction,
    ClaimPostureAlertResponseLedger,
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

_FOLLOW_UP_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertFollowUpStatus(StrEnum):
    """Latest recorded human-response state for one active alert."""

    UNRESPONDED = "unresponded"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATION_OPEN = "investigation-open"
    ESCALATED = "escalated"
    DEFERRED = "deferred"

    @property
    def has_response(self) -> bool:
        """Return whether at least one human response exists."""

        return self is not ClaimPostureAlertFollowUpStatus.UNRESPONDED


class ClaimPostureAlertFollowUpSnapshotStatus(StrEnum):
    """Aggregate follow-up posture across one current alert docket."""

    NO_ACTIVE_ALERTS = "no-active-alerts"
    TRACKED = "tracked"
    ACTION_REQUIRED = "action-required"
    OVERDUE = "overdue"
    ESCALATION_REQUIRED = "escalation-required"

    @property
    def requires_human_action(self) -> bool:
        """Return whether the follow-up snapshot requires human action."""

        return self in {
            ClaimPostureAlertFollowUpSnapshotStatus.ACTION_REQUIRED,
            ClaimPostureAlertFollowUpSnapshotStatus.OVERDUE,
            ClaimPostureAlertFollowUpSnapshotStatus.ESCALATION_REQUIRED,
        }


_ACTION_TO_STATUS: Final[
    dict[
        ClaimPostureAlertResponseAction,
        ClaimPostureAlertFollowUpStatus,
    ]
] = {
    ClaimPostureAlertResponseAction.ACKNOWLEDGE: (
        ClaimPostureAlertFollowUpStatus.ACKNOWLEDGED
    ),
    ClaimPostureAlertResponseAction.OPEN_INVESTIGATION: (
        ClaimPostureAlertFollowUpStatus.INVESTIGATION_OPEN
    ),
    ClaimPostureAlertResponseAction.ESCALATE: (
        ClaimPostureAlertFollowUpStatus.ESCALATED
    ),
    ClaimPostureAlertResponseAction.DEFER: (
        ClaimPostureAlertFollowUpStatus.DEFERRED
    ),
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


def _validate_follow_up_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "alert follow-up producer must be active"
        )
    if producer.kind not in _FOLLOW_UP_PRODUCER_KINDS:
        raise FoundationError(
            "alert follow-up producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "alert follow-up producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertFollowUp:
    """Current response and due-date state for one still-active alert."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-follow-up-v1"
    )

    follow_up_id: ScopedIdentifier
    assessed_at: UtcTimestamp
    alert_id: ScopedIdentifier
    claim_id: ScopedIdentifier
    alert_severity: ClaimPostureAlertSeverity
    status: ClaimPostureAlertFollowUpStatus
    response_count: int
    latest_response_id: ScopedIdentifier | None
    latest_response_action: ClaimPostureAlertResponseAction | None
    latest_responded_at: UtcTimestamp | None
    latest_responded_by_id: ScopedIdentifier | None
    assigned_to_id: ScopedIdentifier | None
    review_due_at: UtcTimestamp | None
    alert_digest: ContentDigest
    latest_response_digest: ContentDigest | None
    docket_digest: ContentDigest
    response_ledger_digest: ContentDigest
    current_posture_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_response_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "follow_up_id",
                self.follow_up_id,
                "claim-posture-alert-follow-up",
            ),
            (
                "alert_id",
                self.alert_id,
                "claim-posture-alert",
            ),
            (
                "claim_id",
                self.claim_id,
                "claim",
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
            namespace="claim-posture-alert-response",
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
            self.review_due_at is not None
            and not isinstance(
                self.review_due_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "review_due_at must be a UtcTimestamp or None"
            )
        if not isinstance(
            self.alert_severity,
            ClaimPostureAlertSeverity,
        ):
            raise FoundationError(
                "alert_severity must be "
                "a ClaimPostureAlertSeverity"
            )
        if not isinstance(
            self.status,
            ClaimPostureAlertFollowUpStatus,
        ):
            raise FoundationError(
                "status must be "
                "a ClaimPostureAlertFollowUpStatus"
            )
        if (
            self.latest_response_action is not None
            and not isinstance(
                self.latest_response_action,
                ClaimPostureAlertResponseAction,
            )
        ):
            raise FoundationError(
                "latest_response_action must be "
                "a ClaimPostureAlertResponseAction or None"
            )
        if isinstance(
            self.response_count,
            bool,
        ) or not isinstance(
            self.response_count,
            int,
        ):
            raise FoundationError(
                "response_count must be an integer"
            )
        if self.response_count < 0:
            raise FoundationError(
                "response_count must not be negative"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "alert_digest",
                self.alert_digest,
                "claim-posture-alert",
            ),
            (
                "docket_digest",
                self.docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "response_ledger_digest",
                self.response_ledger_digest,
                "claim-posture-alert-response-ledger",
            ),
            (
                "current_posture_digest",
                self.current_posture_digest,
                "claim-posture",
            ),
            (
                "current_snapshot_digest",
                self.current_snapshot_digest,
                "claim-posture-snapshot",
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
            domain="claim-posture-alert-response",
        )
        _require_optional_digest(
            self.delta_snapshot_digest,
            field_name="delta_snapshot_digest",
            domain="claim-posture-delta-snapshot",
        )

    def _validate_response_semantics(self) -> None:
        response_values = (
            self.latest_response_id,
            self.latest_response_action,
            self.latest_responded_at,
            self.latest_responded_by_id,
            self.latest_response_digest,
        )
        response_fields_present = tuple(
            value is not None
            for value in response_values
        )

        if self.status is ClaimPostureAlertFollowUpStatus.UNRESPONDED:
            if self.response_count != 0:
                raise FoundationError(
                    "unresponded follow-up must have "
                    "a zero response count"
                )
            if any(response_fields_present):
                raise FoundationError(
                    "unresponded follow-up must not contain "
                    "latest response data"
                )
            if (
                self.assigned_to_id is not None
                or self.review_due_at is not None
            ):
                raise FoundationError(
                    "unresponded follow-up must not contain "
                    "assignment or due-date data"
                )
            return

        if self.response_count < 1:
            raise FoundationError(
                "responded follow-up must have "
                "at least one response"
            )
        if not all(response_fields_present):
            raise FoundationError(
                "responded follow-up requires complete "
                "latest response data"
            )

        action = self.latest_response_action
        responded_at = self.latest_responded_at

        if action is None or responded_at is None:
            raise FoundationError(
                "responded follow-up requires action "
                "and response time"
            )

        expected_status = _ACTION_TO_STATUS[
            action
        ]

        if self.status is not expected_status:
            raise FoundationError(
                "follow-up status does not match "
                "the latest response action"
            )
        if self.assessed_at.value < responded_at.value:
            raise FoundationError(
                "follow-up assessment must not predate "
                "the latest human response"
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
            and self.review_due_at is None
        ):
            raise FoundationError(
                "latest response action requires "
                "a review due time"
            )
        if (
            not action.requires_due_at
            and self.review_due_at is not None
        ):
            raise FoundationError(
                "latest response action must not "
                "contain a review due time"
            )

    @classmethod
    def assess(
        cls,
        *,
        key: str,
        assessed_at: UtcTimestamp,
        alert: ClaimPostureAlert,
        docket: ClaimPostureAlertDocket,
        response_ledger: ClaimPostureAlertResponseLedger,
    ) -> ClaimPostureAlertFollowUp:
        """Assess one alert while preserving it as active."""

        cls._validate_bindings(
            assessed_at=assessed_at,
            alert=alert,
            docket=docket,
            response_ledger=response_ledger,
        )

        responses = response_ledger.responses_for_alert(
            alert.alert_id
        )
        latest = (
            responses[-1]
            if responses
            else None
        )

        if latest is None:
            status = (
                ClaimPostureAlertFollowUpStatus.UNRESPONDED
            )
        else:
            status = _ACTION_TO_STATUS[
                latest.action
            ]

        return cls(
            follow_up_id=ScopedIdentifier.create(
                namespace="claim-posture-alert-follow-up",
                key=key,
                namespace_field="follow-up namespace",
                key_field="follow-up key",
            ),
            assessed_at=assessed_at,
            alert_id=alert.alert_id,
            claim_id=alert.claim_id,
            alert_severity=alert.severity,
            status=status,
            response_count=len(
                responses
            ),
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
            review_due_at=(
                latest.review_due_at
                if latest is not None
                else None
            ),
            alert_digest=alert.digest(),
            latest_response_digest=(
                latest.digest()
                if latest is not None
                else None
            ),
            docket_digest=docket.digest(),
            response_ledger_digest=response_ledger.digest(),
            current_posture_digest=(
                alert.current_posture_digest
            ),
            current_snapshot_digest=(
                alert.current_snapshot_digest
            ),
            delta_snapshot_digest=(
                alert.delta_snapshot_digest
            ),
            claim_catalog_digest=(
                alert.claim_catalog_digest
            ),
            actor_registry_digest=(
                alert.actor_registry_digest
            ),
        )

    @staticmethod
    def _validate_bindings(
        *,
        assessed_at: UtcTimestamp,
        alert: ClaimPostureAlert,
        docket: ClaimPostureAlertDocket,
        response_ledger: ClaimPostureAlertResponseLedger,
    ) -> None:
        bound_alert = docket.require_alert(
            alert.claim_id
        )

        if bound_alert.alert_id != alert.alert_id:
            raise FoundationError(
                "alert does not belong to "
                "the supplied alert docket"
            )
        if bound_alert.digest() != alert.digest():
            raise FoundationError(
                "alert digest does not match "
                "the supplied alert docket"
            )
        if response_ledger.docket_id != docket.docket_id:
            raise FoundationError(
                "response ledger references "
                "a different alert docket"
            )
        if response_ledger.docket_digest != docket.digest():
            raise FoundationError(
                "response ledger is not bound to "
                "the supplied alert docket"
            )
        if (
            response_ledger.current_snapshot_digest
            != docket.current_snapshot_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket posture snapshot"
            )
        if (
            response_ledger.delta_snapshot_digest
            != docket.delta_snapshot_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket delta snapshot"
            )
        if (
            response_ledger.claim_catalog_digest
            != docket.claim_catalog_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket claim catalog"
            )
        if (
            response_ledger.actor_registry_digest
            != docket.actor_registry_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket actor registry"
            )
        if assessed_at.value < docket.generated_at.value:
            raise FoundationError(
                "follow-up assessment must not predate "
                "the alert docket"
            )
        if assessed_at.value < response_ledger.created_at.value:
            raise FoundationError(
                "follow-up assessment must not predate "
                "the response ledger"
            )

    @property
    def alert_remains_active(self) -> bool:
        """Return true because response state does not clear the alert."""

        return True

    @property
    def has_response(self) -> bool:
        """Return whether at least one human response exists."""

        return self.status.has_response

    @property
    def has_assignment(self) -> bool:
        """Return whether a human is assigned to the latest response."""

        return self.assigned_to_id is not None

    @property
    def requires_response(self) -> bool:
        """Return whether the alert has no human response."""

        return not self.has_response

    @property
    def requires_escalation(self) -> bool:
        """Return whether a critical alert lacks explicit escalation."""

        return (
            self.alert_severity
            is ClaimPostureAlertSeverity.CRITICAL
            and self.status
            is not ClaimPostureAlertFollowUpStatus.ESCALATED
        )

    @property
    def is_overdue(self) -> bool:
        """Return whether a scheduled follow-up time has passed."""

        return (
            self.review_due_at is not None
            and self.assessed_at.value
            > self.review_due_at.value
        )

    @property
    def follow_up_required(self) -> bool:
        """Return whether immediate follow-up action is required."""

        return (
            self.requires_response
            or self.requires_escalation
            or self.is_overdue
        )

    @property
    def resolves_alert(self) -> bool:
        """Return false because only posture change clears an alert."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because follow-up assessment is reporting only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because follow-up assessment grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic alert follow-up representation."""

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "alert_digest": self.alert_digest.to_payload(),
            "alert_id": str(self.alert_id),
            "alert_remains_active": self.alert_remains_active,
            "alert_severity": self.alert_severity.value,
            "assessed_at": self.assessed_at.isoformat(),
            "assigned_to_id": (
                str(self.assigned_to_id)
                if self.assigned_to_id is not None
                else None
            ),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "current_posture_digest": (
                self.current_posture_digest.to_payload()
            ),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
                if self.delta_snapshot_digest is not None
                else None
            ),
            "docket_digest": self.docket_digest.to_payload(),
            "follow_up_id": str(self.follow_up_id),
            "follow_up_required": self.follow_up_required,
            "grants_authority": self.grants_authority,
            "has_assignment": self.has_assignment,
            "has_response": self.has_response,
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
            "resolves_alert": self.resolves_alert,
            "response_count": self.response_count,
            "response_ledger_digest": (
                self.response_ledger_digest.to_payload()
            ),
            "review_due_at": (
                self.review_due_at.isoformat()
                if self.review_due_at is not None
                else None
            ),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "requires_escalation": self.requires_escalation,
            "requires_response": self.requires_response,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical follow-up document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete follow-up assessment."""

        return self.to_document().digest(
            domain="claim-posture-alert-follow-up"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertFollowUpSnapshot:
    """Current follow-up state for every alert on one immutable docket."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-follow-up-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    assessed_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertFollowUpSnapshotStatus
    docket_id: ScopedIdentifier
    response_ledger_id: ScopedIdentifier
    follow_ups: tuple[ClaimPostureAlertFollowUp, ...]
    docket_digest: ContentDigest
    response_ledger_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        follow_ups = tuple(
            self.follow_ups
        )
        self._validate_follow_ups(
            follow_ups
        )

        ordered = tuple(
            sorted(
                follow_ups,
                key=lambda follow_up: str(
                    follow_up.claim_id
                ),
            )
        )
        object.__setattr__(
            self,
            "follow_ups",
            ordered,
        )

        expected_status = self._status_for(
            ordered
        )

        if self.status is not expected_status:
            raise FoundationError(
                "alert follow-up snapshot status does not match "
                "its follow-up records"
            )

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                "claim-posture-alert-follow-up-snapshot",
            ),
            (
                "docket_id",
                self.docket_id,
                "claim-posture-alert-docket",
            ),
            (
                "response_ledger_id",
                self.response_ledger_id,
                "claim-posture-alert-response-ledger",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
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
        if self.producer_kind not in _FOLLOW_UP_PRODUCER_KINDS:
            raise FoundationError(
                "alert follow-up producer must be "
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
            ClaimPostureAlertFollowUpSnapshotStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertFollowUpSnapshotStatus"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "docket_digest",
                self.docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "response_ledger_digest",
                self.response_ledger_digest,
                "claim-posture-alert-response-ledger",
            ),
            (
                "current_snapshot_digest",
                self.current_snapshot_digest,
                "claim-posture-snapshot",
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
            self.delta_snapshot_digest,
            field_name="delta_snapshot_digest",
            domain="claim-posture-delta-snapshot",
        )

    def _validate_follow_ups(
        self,
        follow_ups: tuple[
            ClaimPostureAlertFollowUp,
            ...,
        ],
    ) -> None:
        for index, follow_up in enumerate(
            follow_ups
        ):
            if not isinstance(
                follow_up,
                ClaimPostureAlertFollowUp,
            ):
                raise FoundationError(
                    f"follow_ups[{index}] must be a "
                    "ClaimPostureAlertFollowUp"
                )
            if follow_up.assessed_at != self.assessed_at:
                raise FoundationError(
                    "every follow-up must use "
                    "the snapshot assessment time"
                )
            if follow_up.docket_digest != self.docket_digest:
                raise FoundationError(
                    "every follow-up must bind "
                    "the alert docket"
                )
            if (
                follow_up.response_ledger_digest
                != self.response_ledger_digest
            ):
                raise FoundationError(
                    "every follow-up must bind "
                    "the response ledger"
                )
            if (
                follow_up.current_snapshot_digest
                != self.current_snapshot_digest
            ):
                raise FoundationError(
                    "every follow-up must bind "
                    "the current posture snapshot"
                )
            if (
                follow_up.delta_snapshot_digest
                != self.delta_snapshot_digest
            ):
                raise FoundationError(
                    "every follow-up must bind "
                    "the posture-delta snapshot"
                )
            if (
                follow_up.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every follow-up must bind "
                    "the claim catalog"
                )
            if (
                follow_up.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every follow-up must bind "
                    "the actor registry"
                )

        follow_up_ids = tuple(
            follow_up.follow_up_id
            for follow_up in follow_ups
        )

        if len(follow_up_ids) != len(
            set(follow_up_ids)
        ):
            raise FoundationError(
                "alert follow-up snapshot must contain "
                "unique follow-up IDs"
            )

        alert_ids = tuple(
            follow_up.alert_id
            for follow_up in follow_ups
        )

        if len(alert_ids) != len(
            set(alert_ids)
        ):
            raise FoundationError(
                "alert follow-up snapshot must contain "
                "one follow-up per alert"
            )

        claim_ids = tuple(
            follow_up.claim_id
            for follow_up in follow_ups
        )

        if len(claim_ids) != len(
            set(claim_ids)
        ):
            raise FoundationError(
                "alert follow-up snapshot must contain "
                "one follow-up per claim"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        assessed_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        docket: ClaimPostureAlertDocket,
        response_ledger: ClaimPostureAlertResponseLedger,
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertFollowUpSnapshot:
        """Assess every alert without allowing responses to clear it."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = _validate_follow_up_producer(
            producer
        )

        cls._validate_bindings(
            assessed_at=assessed_at,
            docket=docket,
            response_ledger=response_ledger,
            actor_registry=actor_registry,
        )

        follow_ups = tuple(
            ClaimPostureAlertFollowUp.assess(
                key=(
                    f"{key}-"
                    f"{str(alert.claim_id)}"
                ),
                assessed_at=assessed_at,
                alert=alert,
                docket=docket,
                response_ledger=response_ledger,
            )
            for alert in docket.alerts
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-follow-up-snapshot"
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
            status=cls._status_for(
                follow_ups
            ),
            docket_id=docket.docket_id,
            response_ledger_id=response_ledger.ledger_id,
            follow_ups=follow_ups,
            docket_digest=docket.digest(),
            response_ledger_digest=response_ledger.digest(),
            current_snapshot_digest=(
                docket.current_snapshot_digest
            ),
            delta_snapshot_digest=(
                docket.delta_snapshot_digest
            ),
            claim_catalog_digest=(
                docket.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        assessed_at: UtcTimestamp,
        docket: ClaimPostureAlertDocket,
        response_ledger: ClaimPostureAlertResponseLedger,
        actor_registry: ActorRegistry,
    ) -> None:
        actor_registry_digest = actor_registry.digest()

        if (
            docket.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "alert docket is not bound to "
                "the supplied actor registry"
            )
        if (
            response_ledger.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the supplied actor registry"
            )
        if response_ledger.docket_id != docket.docket_id:
            raise FoundationError(
                "response ledger references "
                "a different alert docket"
            )
        if response_ledger.docket_digest != docket.digest():
            raise FoundationError(
                "response ledger is not bound to "
                "the supplied alert docket"
            )
        if (
            response_ledger.current_snapshot_digest
            != docket.current_snapshot_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket posture snapshot"
            )
        if (
            response_ledger.delta_snapshot_digest
            != docket.delta_snapshot_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket delta snapshot"
            )
        if (
            response_ledger.claim_catalog_digest
            != docket.claim_catalog_digest
        ):
            raise FoundationError(
                "response ledger is not bound to "
                "the docket claim catalog"
            )
        if assessed_at.value < docket.generated_at.value:
            raise FoundationError(
                "follow-up snapshot must not predate "
                "the alert docket"
            )
        if assessed_at.value < response_ledger.created_at.value:
            raise FoundationError(
                "follow-up snapshot must not predate "
                "the response ledger"
            )

    @staticmethod
    def _status_for(
        follow_ups: tuple[
            ClaimPostureAlertFollowUp,
            ...,
        ],
    ) -> ClaimPostureAlertFollowUpSnapshotStatus:
        if any(
            follow_up.requires_escalation
            for follow_up in follow_ups
        ):
            return (
                ClaimPostureAlertFollowUpSnapshotStatus
                .ESCALATION_REQUIRED
            )

        if any(
            follow_up.is_overdue
            for follow_up in follow_ups
        ):
            return (
                ClaimPostureAlertFollowUpSnapshotStatus
                .OVERDUE
            )

        if any(
            follow_up.requires_response
            for follow_up in follow_ups
        ):
            return (
                ClaimPostureAlertFollowUpSnapshotStatus
                .ACTION_REQUIRED
            )

        if follow_ups:
            return (
                ClaimPostureAlertFollowUpSnapshotStatus
                .TRACKED
            )

        return (
            ClaimPostureAlertFollowUpSnapshotStatus
            .NO_ACTIVE_ALERTS
        )

    @property
    def active_alert_count(self) -> int:
        """Return the number of still-active docket alerts."""

        return len(
            self.follow_ups
        )

    @property
    def responded_count(self) -> int:
        """Return the number of alerts with human responses."""

        return sum(
            follow_up.has_response
            for follow_up in self.follow_ups
        )

    @property
    def unresponded_count(self) -> int:
        """Return the number of alerts without human responses."""

        return sum(
            follow_up.requires_response
            for follow_up in self.follow_ups
        )

    @property
    def assigned_count(self) -> int:
        """Return the number of alerts with human assignments."""

        return sum(
            follow_up.has_assignment
            for follow_up in self.follow_ups
        )

    @property
    def overdue_count(self) -> int:
        """Return the number of overdue alert follow-ups."""

        return sum(
            follow_up.is_overdue
            for follow_up in self.follow_ups
        )

    @property
    def escalation_required_count(self) -> int:
        """Return critical alerts lacking explicit escalation."""

        return sum(
            follow_up.requires_escalation
            for follow_up in self.follow_ups
        )

    @property
    def follow_up_required_count(self) -> int:
        """Return alerts requiring immediate follow-up action."""

        return sum(
            follow_up.follow_up_required
            for follow_up in self.follow_ups
        )

    @property
    def all_active_alerts_responded(self) -> bool:
        """Return whether every active alert has a human response."""

        return all(
            follow_up.has_response
            for follow_up in self.follow_ups
        )

    @property
    def active_alerts_remain(self) -> bool:
        """Return whether the underlying docket still contains alerts."""

        return bool(
            self.follow_ups
        )

    @property
    def requires_human_action(self) -> bool:
        """Return whether immediate human action is required."""

        return self.status.requires_human_action

    @property
    def resolves_alerts(self) -> bool:
        """Return false because follow-up state does not clear alerts."""

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

    def follow_up_for_alert(
        self,
        alert_id: ScopedIdentifier,
    ) -> ClaimPostureAlertFollowUp | None:
        """Return the follow-up state for one exact alert."""

        for follow_up in self.follow_ups:
            if follow_up.alert_id == alert_id:
                return follow_up

        return None

    def follow_up_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureAlertFollowUp | None:
        """Return the follow-up state for one claim."""

        for follow_up in self.follow_ups:
            if follow_up.claim_id == claim_id:
                return follow_up

        return None

    def require_follow_up_for_alert(
        self,
        alert_id: ScopedIdentifier,
    ) -> ClaimPostureAlertFollowUp:
        """Return an alert follow-up or fail when absent."""

        follow_up = self.follow_up_for_alert(
            alert_id
        )

        if follow_up is None:
            raise FoundationError(
                "alert follow-up snapshot does not contain "
                f"alert: {alert_id}"
            )

        return follow_up

    def unresponded_follow_ups(
        self,
    ) -> tuple[ClaimPostureAlertFollowUp, ...]:
        """Return active alerts without a human response."""

        return tuple(
            follow_up
            for follow_up in self.follow_ups
            if follow_up.requires_response
        )

    def overdue_follow_ups(
        self,
    ) -> tuple[ClaimPostureAlertFollowUp, ...]:
        """Return overdue active alert follow-ups."""

        return tuple(
            follow_up
            for follow_up in self.follow_ups
            if follow_up.is_overdue
        )

    def escalation_required_follow_ups(
        self,
    ) -> tuple[ClaimPostureAlertFollowUp, ...]:
        """Return critical alerts lacking explicit escalation."""

        return tuple(
            follow_up
            for follow_up in self.follow_ups
            if follow_up.requires_escalation
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic follow-up snapshot representation."""

        follow_up_payloads: JsonArray = [
            follow_up.to_payload()
            for follow_up in self.follow_ups
        ]

        return {
            "active_alert_count": self.active_alert_count,
            "active_alerts_remain": self.active_alerts_remain,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "all_active_alerts_responded": (
                self.all_active_alerts_responded
            ),
            "assessed_at": self.assessed_at.isoformat(),
            "assigned_count": self.assigned_count,
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
                if self.delta_snapshot_digest is not None
                else None
            ),
            "docket_digest": self.docket_digest.to_payload(),
            "docket_id": str(self.docket_id),
            "escalation_required_count": (
                self.escalation_required_count
            ),
            "follow_up_required_count": (
                self.follow_up_required_count
            ),
            "follow_ups": follow_up_payloads,
            "grants_authority": self.grants_authority,
            "overdue_count": self.overdue_count,
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "requires_human_action": self.requires_human_action,
            "resolves_alerts": self.resolves_alerts,
            "responded_count": self.responded_count,
            "response_ledger_digest": (
                self.response_ledger_digest.to_payload()
            ),
            "response_ledger_id": str(
                self.response_ledger_id
            ),
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "status": self.status.value,
            "unresponded_count": self.unresponded_count,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical follow-up snapshot."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete follow-up snapshot."""

        return self.to_document().digest(
            domain="claim-posture-alert-follow-up-snapshot"
        )
