"""Reconcile prior claim alerts against newer claim posture."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.alerts import (
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertReason,
    ClaimPostureAlertSeverity,
)
from ix_missionproof.claims.deltas import (
    ClaimPostureDelta,
    ClaimPostureDeltaSnapshot,
    ClaimPostureTransition,
)
from ix_missionproof.claims.postures import (
    ClaimPosture,
    ClaimPostureSnapshot,
    ClaimPostureStatus,
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

_RECONCILIATION_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertReconciliationStatus(StrEnum):
    """Result of reconciling one prior alert with newer posture."""

    ACTIVE_UNCHANGED = "active-unchanged"
    ACTIVE_CHANGED = "active-changed"
    CLEARED = "cleared"

    @property
    def is_active(self) -> bool:
        """Return whether the prior alert condition remains active."""

        return self in {
            ClaimPostureAlertReconciliationStatus.ACTIVE_UNCHANGED,
            ClaimPostureAlertReconciliationStatus.ACTIVE_CHANGED,
        }

    @property
    def is_cleared(self) -> bool:
        """Return whether newer posture no longer requires an alert."""

        return self is ClaimPostureAlertReconciliationStatus.CLEARED


class ClaimPostureAlertReconciliationSnapshotStatus(StrEnum):
    """Aggregate reconciliation state for one prior alert docket."""

    CLEAR = "clear"
    PARTIALLY_CLEARED = "partially-cleared"
    ACTIVE = "active"

    @property
    def has_active_alerts(self) -> bool:
        """Return whether at least one prior alert remains active."""

        return self is not ClaimPostureAlertReconciliationSnapshotStatus.CLEAR


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


def _validate_reconciliation_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "claim-alert reconciliation producer must be active"
        )
    if producer.kind not in _RECONCILIATION_PRODUCER_KINDS:
        raise FoundationError(
            "claim-alert reconciliation producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "claim-alert reconciliation producer must identify "
            "an accountable human owner"
        )

    return owner_id


def _normalize_reasons(
    values: tuple[ClaimPostureAlertReason, ...],
    *,
    field_name: str,
    required: bool,
) -> tuple[ClaimPostureAlertReason, ...]:
    normalized: set[ClaimPostureAlertReason] = set()

    for index, value in enumerate(values):
        if not isinstance(
            value,
            ClaimPostureAlertReason,
        ):
            raise FoundationError(
                f"{field_name}[{index}] must be "
                "a ClaimPostureAlertReason"
            )
        normalized.add(value)

    if required and not normalized:
        raise FoundationError(
            f"{field_name} must not be empty"
        )

    return tuple(
        sorted(
            normalized,
            key=lambda reason: reason.value,
        )
    )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertReconciliation:
    """Reconciliation of one prior alert with one newer claim posture."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-reconciliation-v1"
    )

    reconciliation_id: ScopedIdentifier
    reconciled_at: UtcTimestamp
    alert_id: ScopedIdentifier
    claim_id: ScopedIdentifier
    status: ClaimPostureAlertReconciliationStatus
    transition: ClaimPostureTransition
    previous_status: ClaimPostureStatus
    current_status: ClaimPostureStatus
    previous_severity: ClaimPostureAlertSeverity
    current_severity: ClaimPostureAlertSeverity | None
    previous_reasons: tuple[ClaimPostureAlertReason, ...]
    current_reasons: tuple[ClaimPostureAlertReason, ...]
    previous_posture_id: ScopedIdentifier
    current_posture_id: ScopedIdentifier
    delta_id: ScopedIdentifier
    alert_digest: ContentDigest
    previous_posture_digest: ContentDigest
    current_posture_digest: ContentDigest
    delta_digest: ContentDigest
    prior_docket_digest: ContentDigest
    previous_snapshot_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        previous_reasons = _normalize_reasons(
            self.previous_reasons,
            field_name="previous_reasons",
            required=True,
        )
        current_reasons = _normalize_reasons(
            self.current_reasons,
            field_name="current_reasons",
            required=False,
        )

        object.__setattr__(
            self,
            "previous_reasons",
            previous_reasons,
        )
        object.__setattr__(
            self,
            "current_reasons",
            current_reasons,
        )

        self._validate_reconciliation_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "reconciliation_id",
                self.reconciliation_id,
                "claim-posture-alert-reconciliation",
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
            (
                "previous_posture_id",
                self.previous_posture_id,
                "claim-posture",
            ),
            (
                "current_posture_id",
                self.current_posture_id,
                "claim-posture",
            ),
            (
                "delta_id",
                self.delta_id,
                "claim-posture-delta",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        if not isinstance(
            self.reconciled_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "reconciled_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.status,
            ClaimPostureAlertReconciliationStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertReconciliationStatus"
            )
        if not isinstance(
            self.transition,
            ClaimPostureTransition,
        ):
            raise FoundationError(
                "transition must be a ClaimPostureTransition"
            )
        if not isinstance(
            self.previous_status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "previous_status must be a ClaimPostureStatus"
            )
        if not isinstance(
            self.current_status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "current_status must be a ClaimPostureStatus"
            )
        if not isinstance(
            self.previous_severity,
            ClaimPostureAlertSeverity,
        ):
            raise FoundationError(
                "previous_severity must be "
                "a ClaimPostureAlertSeverity"
            )
        if (
            self.current_severity is not None
            and not isinstance(
                self.current_severity,
                ClaimPostureAlertSeverity,
            )
        ):
            raise FoundationError(
                "current_severity must be "
                "a ClaimPostureAlertSeverity or None"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "alert_digest",
                self.alert_digest,
                "claim-posture-alert",
            ),
            (
                "previous_posture_digest",
                self.previous_posture_digest,
                "claim-posture",
            ),
            (
                "current_posture_digest",
                self.current_posture_digest,
                "claim-posture",
            ),
            (
                "delta_digest",
                self.delta_digest,
                "claim-posture-delta",
            ),
            (
                "prior_docket_digest",
                self.prior_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "previous_snapshot_digest",
                self.previous_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "current_snapshot_digest",
                self.current_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "delta_snapshot_digest",
                self.delta_snapshot_digest,
                "claim-posture-delta-snapshot",
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

    def _validate_reconciliation_semantics(self) -> None:
        expected_status = self.classify(
            previous_status=self.previous_status,
            current_status=self.current_status,
            previous_severity=self.previous_severity,
            current_severity=self.current_severity,
            previous_reasons=self.previous_reasons,
            current_reasons=self.current_reasons,
        )

        if self.status is not expected_status:
            raise FoundationError(
                "claim-alert reconciliation status does not "
                "match the previous alert and current posture"
            )

        if self.status.is_cleared:
            if self.current_severity is not None:
                raise FoundationError(
                    "cleared alert reconciliation must not "
                    "contain a current severity"
                )
            if self.current_reasons:
                raise FoundationError(
                    "cleared alert reconciliation must not "
                    "contain current alert reasons"
                )
            return

        if self.current_severity is None:
            raise FoundationError(
                "active alert reconciliation requires "
                "a current alert severity"
            )
        if not self.current_reasons:
            raise FoundationError(
                "active alert reconciliation requires "
                "current alert reasons"
            )

    @classmethod
    def reconcile(
        cls,
        *,
        key: str,
        reconciled_at: UtcTimestamp,
        alert: ClaimPostureAlert,
        prior_docket: ClaimPostureAlertDocket,
        previous_posture: ClaimPosture,
        current_posture: ClaimPosture,
        delta: ClaimPostureDelta,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
        delta_snapshot: ClaimPostureDeltaSnapshot,
    ) -> ClaimPostureAlertReconciliation:
        """Reconcile an alert only through newer bound claim posture."""

        cls._validate_bindings(
            reconciled_at=reconciled_at,
            alert=alert,
            prior_docket=prior_docket,
            previous_posture=previous_posture,
            current_posture=current_posture,
            delta=delta,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            delta_snapshot=delta_snapshot,
        )

        current_severity = ClaimPostureAlert.severity_for(
            current_status=current_posture.status,
            transition=delta.transition,
        )
        current_reasons = (
            ClaimPostureAlert.reasons_for(
                current_status=current_posture.status,
                transition=delta.transition,
            )
            if current_severity is not None
            else ()
        )
        status = cls.classify(
            previous_status=previous_posture.status,
            current_status=current_posture.status,
            previous_severity=alert.severity,
            current_severity=current_severity,
            previous_reasons=alert.reasons,
            current_reasons=current_reasons,
        )

        return cls(
            reconciliation_id=ScopedIdentifier.create(
                namespace="claim-posture-alert-reconciliation",
                key=key,
                namespace_field="reconciliation namespace",
                key_field="reconciliation key",
            ),
            reconciled_at=reconciled_at,
            alert_id=alert.alert_id,
            claim_id=alert.claim_id,
            status=status,
            transition=delta.transition,
            previous_status=previous_posture.status,
            current_status=current_posture.status,
            previous_severity=alert.severity,
            current_severity=current_severity,
            previous_reasons=alert.reasons,
            current_reasons=current_reasons,
            previous_posture_id=previous_posture.posture_id,
            current_posture_id=current_posture.posture_id,
            delta_id=delta.delta_id,
            alert_digest=alert.digest(),
            previous_posture_digest=previous_posture.digest(),
            current_posture_digest=current_posture.digest(),
            delta_digest=delta.digest(),
            prior_docket_digest=prior_docket.digest(),
            previous_snapshot_digest=previous_snapshot.digest(),
            current_snapshot_digest=current_snapshot.digest(),
            delta_snapshot_digest=delta_snapshot.digest(),
            claim_catalog_digest=current_snapshot.claim_catalog_digest,
            actor_registry_digest=current_snapshot.actor_registry_digest,
        )

    @staticmethod
    def _validate_bindings(
        *,
        reconciled_at: UtcTimestamp,
        alert: ClaimPostureAlert,
        prior_docket: ClaimPostureAlertDocket,
        previous_posture: ClaimPosture,
        current_posture: ClaimPosture,
        delta: ClaimPostureDelta,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
        delta_snapshot: ClaimPostureDeltaSnapshot,
    ) -> None:
        bound_alert = prior_docket.require_alert(
            alert.claim_id
        )

        if bound_alert.alert_id != alert.alert_id:
            raise FoundationError(
                "alert does not belong to the prior alert docket"
            )
        if bound_alert.digest() != alert.digest():
            raise FoundationError(
                "alert digest does not match the prior alert docket"
            )

        if (
            prior_docket.current_snapshot_id
            != previous_snapshot.snapshot_id
        ):
            raise FoundationError(
                "prior alert docket references a different "
                "previous posture snapshot"
            )
        if (
            prior_docket.current_snapshot_digest
            != previous_snapshot.digest()
        ):
            raise FoundationError(
                "prior alert docket is not bound to "
                "the previous posture snapshot"
            )

        bound_previous = previous_snapshot.require_posture(
            alert.claim_id
        )
        bound_current = current_snapshot.require_posture(
            alert.claim_id
        )
        bound_delta = delta_snapshot.require_delta(
            alert.claim_id
        )

        if bound_previous.digest() != previous_posture.digest():
            raise FoundationError(
                "previous posture does not match "
                "the previous posture snapshot"
            )
        if bound_current.digest() != current_posture.digest():
            raise FoundationError(
                "current posture does not match "
                "the current posture snapshot"
            )
        if bound_delta.digest() != delta.digest():
            raise FoundationError(
                "claim-posture delta does not match "
                "the posture-delta snapshot"
            )

        if alert.current_posture_id != previous_posture.posture_id:
            raise FoundationError(
                "prior alert references a different "
                "previous claim posture"
            )
        if (
            alert.current_posture_digest
            != previous_posture.digest()
        ):
            raise FoundationError(
                "prior alert posture digest does not match"
            )
        if delta.previous_posture_id != previous_posture.posture_id:
            raise FoundationError(
                "claim-posture delta references a different "
                "previous posture"
            )
        if delta.current_posture_id != current_posture.posture_id:
            raise FoundationError(
                "claim-posture delta references a different "
                "current posture"
            )
        if delta.claim_id != alert.claim_id:
            raise FoundationError(
                "claim-posture delta references a different claim"
            )

        if (
            delta_snapshot.previous_snapshot_id
            != previous_snapshot.snapshot_id
        ):
            raise FoundationError(
                "posture-delta snapshot references a different "
                "previous posture snapshot"
            )
        if (
            delta_snapshot.current_snapshot_id
            != current_snapshot.snapshot_id
        ):
            raise FoundationError(
                "posture-delta snapshot references a different "
                "current posture snapshot"
            )
        if (
            delta_snapshot.previous_snapshot_digest
            != previous_snapshot.digest()
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound to "
                "the previous posture snapshot"
            )
        if (
            delta_snapshot.current_snapshot_digest
            != current_snapshot.digest()
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound to "
                "the current posture snapshot"
            )

        if (
            current_snapshot.captured_at.value
            <= previous_snapshot.captured_at.value
        ):
            raise FoundationError(
                "current posture snapshot must be newer "
                "than the previous posture snapshot"
            )
        if (
            current_snapshot.captured_at.value
            <= prior_docket.generated_at.value
        ):
            raise FoundationError(
                "alert reconciliation requires posture captured "
                "after the prior alert docket"
            )
        if reconciled_at.value < delta_snapshot.compared_at.value:
            raise FoundationError(
                "alert reconciliation must not predate "
                "the posture-delta snapshot"
            )

        if (
            prior_docket.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "prior alert docket and current posture snapshot "
                "must bind the same claim catalog"
            )
        if (
            prior_docket.actor_registry_digest
            != current_snapshot.actor_registry_digest
        ):
            raise FoundationError(
                "prior alert docket and current posture snapshot "
                "must bind the same actor registry"
            )

    @staticmethod
    def classify(
        *,
        previous_status: ClaimPostureStatus,
        current_status: ClaimPostureStatus,
        previous_severity: ClaimPostureAlertSeverity,
        current_severity: ClaimPostureAlertSeverity | None,
        previous_reasons: tuple[ClaimPostureAlertReason, ...],
        current_reasons: tuple[ClaimPostureAlertReason, ...],
    ) -> ClaimPostureAlertReconciliationStatus:
        """Classify whether a prior alert remains active."""

        if current_severity is None:
            return ClaimPostureAlertReconciliationStatus.CLEARED

        if (
            previous_status is current_status
            and previous_severity is current_severity
            and previous_reasons == current_reasons
        ):
            return (
                ClaimPostureAlertReconciliationStatus
                .ACTIVE_UNCHANGED
            )

        return (
            ClaimPostureAlertReconciliationStatus
            .ACTIVE_CHANGED
        )

    @property
    def alert_remains_active(self) -> bool:
        """Return whether the underlying posture still requires an alert."""

        return self.status.is_active

    @property
    def alert_cleared(self) -> bool:
        """Return whether newer posture no longer requires an alert."""

        return self.status.is_cleared

    @property
    def cleared_by_posture_change(self) -> bool:
        """Return whether claim posture itself cleared the alert."""

        return self.alert_cleared

    @property
    def response_can_clear_alert(self) -> bool:
        """Return false because response history cannot clear an alert."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because reconciliation reports existing posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because alert reconciliation grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic reconciliation representation."""

        previous_reasons: JsonArray = [
            reason.value
            for reason in self.previous_reasons
        ]
        current_reasons: JsonArray = [
            reason.value
            for reason in self.current_reasons
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "alert_cleared": self.alert_cleared,
            "alert_digest": self.alert_digest.to_payload(),
            "alert_id": str(self.alert_id),
            "alert_remains_active": self.alert_remains_active,
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "cleared_by_posture_change": (
                self.cleared_by_posture_change
            ),
            "current_posture_digest": (
                self.current_posture_digest.to_payload()
            ),
            "current_posture_id": str(
                self.current_posture_id
            ),
            "current_reasons": current_reasons,
            "current_severity": (
                self.current_severity.value
                if self.current_severity is not None
                else None
            ),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "current_status": self.current_status.value,
            "delta_digest": self.delta_digest.to_payload(),
            "delta_id": str(self.delta_id),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
            ),
            "grants_authority": self.grants_authority,
            "previous_posture_digest": (
                self.previous_posture_digest.to_payload()
            ),
            "previous_posture_id": str(
                self.previous_posture_id
            ),
            "previous_reasons": previous_reasons,
            "previous_severity": self.previous_severity.value,
            "previous_snapshot_digest": (
                self.previous_snapshot_digest.to_payload()
            ),
            "previous_status": self.previous_status.value,
            "prior_docket_digest": (
                self.prior_docket_digest.to_payload()
            ),
            "reconciled_at": self.reconciled_at.isoformat(),
            "reconciliation_id": str(self.reconciliation_id),
            "response_can_clear_alert": (
                self.response_can_clear_alert
            ),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "transition": self.transition.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical reconciliation document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete alert reconciliation."""

        return self.to_document().digest(
            domain="claim-posture-alert-reconciliation"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertReconciliationSnapshot:
    """Reconcile every alert from a prior docket against newer posture."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-reconciliation-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    reconciled_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertReconciliationSnapshotStatus
    prior_docket_id: ScopedIdentifier
    previous_snapshot_id: ScopedIdentifier
    current_snapshot_id: ScopedIdentifier
    delta_snapshot_id: ScopedIdentifier
    reconciliations: tuple[ClaimPostureAlertReconciliation, ...]
    prior_docket_digest: ContentDigest
    previous_snapshot_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        reconciliations = tuple(
            self.reconciliations
        )
        self._validate_reconciliations(
            reconciliations
        )

        ordered = tuple(
            sorted(
                reconciliations,
                key=lambda reconciliation: str(
                    reconciliation.claim_id
                ),
            )
        )
        object.__setattr__(
            self,
            "reconciliations",
            ordered,
        )

        expected_status = self._status_for(
            ordered
        )

        if self.status is not expected_status:
            raise FoundationError(
                "claim-alert reconciliation snapshot status "
                "does not match its reconciliations"
            )

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                "claim-posture-alert-reconciliation-snapshot",
            ),
            (
                "prior_docket_id",
                self.prior_docket_id,
                "claim-posture-alert-docket",
            ),
            (
                "previous_snapshot_id",
                self.previous_snapshot_id,
                "claim-posture-snapshot",
            ),
            (
                "current_snapshot_id",
                self.current_snapshot_id,
                "claim-posture-snapshot",
            ),
            (
                "delta_snapshot_id",
                self.delta_snapshot_id,
                "claim-posture-delta-snapshot",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
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
            _RECONCILIATION_PRODUCER_KINDS
        ):
            raise FoundationError(
                "claim-alert reconciliation producer must be "
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
            ClaimPostureAlertReconciliationSnapshotStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertReconciliationSnapshotStatus"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "prior_docket_digest",
                self.prior_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "previous_snapshot_digest",
                self.previous_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "current_snapshot_digest",
                self.current_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "delta_snapshot_digest",
                self.delta_snapshot_digest,
                "claim-posture-delta-snapshot",
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

    def _validate_reconciliations(
        self,
        reconciliations: tuple[
            ClaimPostureAlertReconciliation,
            ...,
        ],
    ) -> None:
        for index, reconciliation in enumerate(
            reconciliations
        ):
            if not isinstance(
                reconciliation,
                ClaimPostureAlertReconciliation,
            ):
                raise FoundationError(
                    f"reconciliations[{index}] must be a "
                    "ClaimPostureAlertReconciliation"
                )
            if reconciliation.reconciled_at != self.reconciled_at:
                raise FoundationError(
                    "every reconciliation must use "
                    "the snapshot reconciliation time"
                )
            if (
                reconciliation.prior_docket_digest
                != self.prior_docket_digest
            ):
                raise FoundationError(
                    "every reconciliation must bind "
                    "the prior alert docket"
                )
            if (
                reconciliation.previous_snapshot_digest
                != self.previous_snapshot_digest
            ):
                raise FoundationError(
                    "every reconciliation must bind "
                    "the previous posture snapshot"
                )
            if (
                reconciliation.current_snapshot_digest
                != self.current_snapshot_digest
            ):
                raise FoundationError(
                    "every reconciliation must bind "
                    "the current posture snapshot"
                )
            if (
                reconciliation.delta_snapshot_digest
                != self.delta_snapshot_digest
            ):
                raise FoundationError(
                    "every reconciliation must bind "
                    "the posture-delta snapshot"
                )
            if (
                reconciliation.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every reconciliation must bind "
                    "the claim catalog"
                )
            if (
                reconciliation.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every reconciliation must bind "
                    "the actor registry"
                )

        reconciliation_ids = tuple(
            reconciliation.reconciliation_id
            for reconciliation in reconciliations
        )
        if len(reconciliation_ids) != len(
            set(reconciliation_ids)
        ):
            raise FoundationError(
                "claim-alert reconciliation snapshot must "
                "contain unique reconciliation IDs"
            )

        alert_ids = tuple(
            reconciliation.alert_id
            for reconciliation in reconciliations
        )
        if len(alert_ids) != len(
            set(alert_ids)
        ):
            raise FoundationError(
                "claim-alert reconciliation snapshot must "
                "contain one reconciliation per alert"
            )

        claim_ids = tuple(
            reconciliation.claim_id
            for reconciliation in reconciliations
        )
        if len(claim_ids) != len(
            set(claim_ids)
        ):
            raise FoundationError(
                "claim-alert reconciliation snapshot must "
                "contain one reconciliation per claim"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        reconciled_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        prior_docket: ClaimPostureAlertDocket,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
        delta_snapshot: ClaimPostureDeltaSnapshot,
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertReconciliationSnapshot:
        """Reconcile every prior alert through newer posture only."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = (
            _validate_reconciliation_producer(
                producer
            )
        )

        cls._validate_bindings(
            reconciled_at=reconciled_at,
            prior_docket=prior_docket,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            delta_snapshot=delta_snapshot,
            actor_registry=actor_registry,
        )

        reconciliations = tuple(
            ClaimPostureAlertReconciliation.reconcile(
                key=(
                    f"{key}-"
                    f"{str(alert.claim_id)}"
                ),
                reconciled_at=reconciled_at,
                alert=alert,
                prior_docket=prior_docket,
                previous_posture=(
                    previous_snapshot.require_posture(
                        alert.claim_id
                    )
                ),
                current_posture=(
                    current_snapshot.require_posture(
                        alert.claim_id
                    )
                ),
                delta=delta_snapshot.require_delta(
                    alert.claim_id
                ),
                previous_snapshot=previous_snapshot,
                current_snapshot=current_snapshot,
                delta_snapshot=delta_snapshot,
            )
            for alert in prior_docket.alerts
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-reconciliation-snapshot"
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
            status=cls._status_for(
                reconciliations
            ),
            prior_docket_id=prior_docket.docket_id,
            previous_snapshot_id=previous_snapshot.snapshot_id,
            current_snapshot_id=current_snapshot.snapshot_id,
            delta_snapshot_id=delta_snapshot.snapshot_id,
            reconciliations=reconciliations,
            prior_docket_digest=prior_docket.digest(),
            previous_snapshot_digest=previous_snapshot.digest(),
            current_snapshot_digest=current_snapshot.digest(),
            delta_snapshot_digest=delta_snapshot.digest(),
            claim_catalog_digest=(
                current_snapshot.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        reconciled_at: UtcTimestamp,
        prior_docket: ClaimPostureAlertDocket,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
        delta_snapshot: ClaimPostureDeltaSnapshot,
        actor_registry: ActorRegistry,
    ) -> None:
        actor_registry_digest = actor_registry.digest()

        for role, digest in (
            (
                "prior alert docket",
                prior_docket.actor_registry_digest,
            ),
            (
                "previous posture snapshot",
                previous_snapshot.actor_registry_digest,
            ),
            (
                "current posture snapshot",
                current_snapshot.actor_registry_digest,
            ),
            (
                "posture-delta snapshot",
                delta_snapshot.actor_registry_digest,
            ),
        ):
            if digest != actor_registry_digest:
                raise FoundationError(
                    f"{role} is not bound to "
                    "the supplied actor registry"
                )

        if (
            prior_docket.current_snapshot_id
            != previous_snapshot.snapshot_id
        ):
            raise FoundationError(
                "prior alert docket references a different "
                "previous posture snapshot"
            )
        if (
            prior_docket.current_snapshot_digest
            != previous_snapshot.digest()
        ):
            raise FoundationError(
                "prior alert docket is not bound to "
                "the previous posture snapshot"
            )

        if (
            delta_snapshot.previous_snapshot_id
            != previous_snapshot.snapshot_id
        ):
            raise FoundationError(
                "posture-delta snapshot references a different "
                "previous posture snapshot"
            )
        if (
            delta_snapshot.current_snapshot_id
            != current_snapshot.snapshot_id
        ):
            raise FoundationError(
                "posture-delta snapshot references a different "
                "current posture snapshot"
            )
        if (
            delta_snapshot.previous_snapshot_digest
            != previous_snapshot.digest()
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound to "
                "the previous posture snapshot"
            )
        if (
            delta_snapshot.current_snapshot_digest
            != current_snapshot.digest()
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound to "
                "the current posture snapshot"
            )

        if (
            prior_docket.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "prior alert docket and current posture snapshot "
                "must bind the same claim catalog"
            )
        if (
            previous_snapshot.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "posture snapshots must bind "
                "the same claim catalog"
            )
        if (
            delta_snapshot.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "posture-delta snapshot must bind "
                "the current claim catalog"
            )

        if (
            current_snapshot.captured_at.value
            <= prior_docket.generated_at.value
        ):
            raise FoundationError(
                "alert reconciliation requires posture captured "
                "after the prior alert docket"
            )
        if reconciled_at.value < delta_snapshot.compared_at.value:
            raise FoundationError(
                "alert reconciliation snapshot must not predate "
                "the posture-delta snapshot"
            )

        current_claim_ids = {
            posture.claim_id
            for posture in current_snapshot.postures
        }

        for alert in prior_docket.alerts:
            if alert.claim_id not in current_claim_ids:
                raise FoundationError(
                    "current posture snapshot is missing "
                    "a previously alerted claim"
                )

    @staticmethod
    def _status_for(
        reconciliations: tuple[
            ClaimPostureAlertReconciliation,
            ...,
        ],
    ) -> ClaimPostureAlertReconciliationSnapshotStatus:
        active_count = sum(
            reconciliation.alert_remains_active
            for reconciliation in reconciliations
        )
        cleared_count = sum(
            reconciliation.alert_cleared
            for reconciliation in reconciliations
        )

        if active_count == 0:
            return (
                ClaimPostureAlertReconciliationSnapshotStatus
                .CLEAR
            )

        if cleared_count > 0:
            return (
                ClaimPostureAlertReconciliationSnapshotStatus
                .PARTIALLY_CLEARED
            )

        return (
            ClaimPostureAlertReconciliationSnapshotStatus
            .ACTIVE
        )

    @property
    def total_count(self) -> int:
        """Return the number of prior alerts reconciled."""

        return len(
            self.reconciliations
        )

    @property
    def active_count(self) -> int:
        """Return the number of prior alerts still active."""

        return sum(
            reconciliation.alert_remains_active
            for reconciliation in self.reconciliations
        )

    @property
    def cleared_count(self) -> int:
        """Return the number of prior alerts cleared by posture change."""

        return sum(
            reconciliation.alert_cleared
            for reconciliation in self.reconciliations
        )

    @property
    def changed_active_count(self) -> int:
        """Return active alerts whose severity, reasons, or posture changed."""

        return sum(
            reconciliation.status
            is ClaimPostureAlertReconciliationStatus.ACTIVE_CHANGED
            for reconciliation in self.reconciliations
        )

    @property
    def unchanged_active_count(self) -> int:
        """Return active alerts whose alert condition is unchanged."""

        return sum(
            reconciliation.status
            is ClaimPostureAlertReconciliationStatus.ACTIVE_UNCHANGED
            for reconciliation in self.reconciliations
        )

    @property
    def all_prior_alerts_cleared(self) -> bool:
        """Return whether no prior alert condition remains active."""

        return self.active_count == 0

    @property
    def has_active_alerts(self) -> bool:
        """Return whether at least one prior alert remains active."""

        return self.status.has_active_alerts

    @property
    def response_can_clear_alerts(self) -> bool:
        """Return false because response history cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because reconciliation reports newer posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because reconciliation grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def reconciliation_for_alert(
        self,
        alert_id: ScopedIdentifier,
    ) -> ClaimPostureAlertReconciliation | None:
        """Return reconciliation state for one prior alert."""

        for reconciliation in self.reconciliations:
            if reconciliation.alert_id == alert_id:
                return reconciliation

        return None

    def reconciliation_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureAlertReconciliation | None:
        """Return reconciliation state for one claim."""

        for reconciliation in self.reconciliations:
            if reconciliation.claim_id == claim_id:
                return reconciliation

        return None

    def require_reconciliation_for_alert(
        self,
        alert_id: ScopedIdentifier,
    ) -> ClaimPostureAlertReconciliation:
        """Return an alert reconciliation or fail when absent."""

        reconciliation = self.reconciliation_for_alert(
            alert_id
        )

        if reconciliation is None:
            raise FoundationError(
                "claim-alert reconciliation snapshot does not "
                f"contain alert: {alert_id}"
            )

        return reconciliation

    def active_reconciliations(
        self,
    ) -> tuple[ClaimPostureAlertReconciliation, ...]:
        """Return prior alerts that remain active."""

        return tuple(
            reconciliation
            for reconciliation in self.reconciliations
            if reconciliation.alert_remains_active
        )

    def cleared_reconciliations(
        self,
    ) -> tuple[ClaimPostureAlertReconciliation, ...]:
        """Return prior alerts cleared by newer claim posture."""

        return tuple(
            reconciliation
            for reconciliation in self.reconciliations
            if reconciliation.alert_cleared
        )

    def changed_active_reconciliations(
        self,
    ) -> tuple[ClaimPostureAlertReconciliation, ...]:
        """Return still-active alerts whose condition changed."""

        return tuple(
            reconciliation
            for reconciliation in self.reconciliations
            if reconciliation.status
            is ClaimPostureAlertReconciliationStatus.ACTIVE_CHANGED
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic reconciliation snapshot."""

        reconciliation_payloads: JsonArray = [
            reconciliation.to_payload()
            for reconciliation in self.reconciliations
        ]

        return {
            "active_count": self.active_count,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "all_prior_alerts_cleared": (
                self.all_prior_alerts_cleared
            ),
            "changed_active_count": self.changed_active_count,
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "cleared_count": self.cleared_count,
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "current_snapshot_id": str(
                self.current_snapshot_id
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
            ),
            "delta_snapshot_id": str(
                self.delta_snapshot_id
            ),
            "grants_authority": self.grants_authority,
            "has_active_alerts": self.has_active_alerts,
            "previous_snapshot_digest": (
                self.previous_snapshot_digest.to_payload()
            ),
            "previous_snapshot_id": str(
                self.previous_snapshot_id
            ),
            "prior_docket_digest": (
                self.prior_docket_digest.to_payload()
            ),
            "prior_docket_id": str(self.prior_docket_id),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "reconciled_at": self.reconciled_at.isoformat(),
            "reconciliations": reconciliation_payloads,
            "response_can_clear_alerts": (
                self.response_can_clear_alerts
            ),
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "status": self.status.value,
            "total_count": self.total_count,
            "unchanged_active_count": (
                self.unchanged_active_count
            ),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical reconciliation snapshot."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete reconciliation snapshot."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-reconciliation-snapshot"
            )
        )
