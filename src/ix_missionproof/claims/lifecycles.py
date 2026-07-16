"""Lifecycle continuity between successive claim-posture alert dockets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.alerts import (
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertSeverity,
)
from ix_missionproof.claims.deltas import (
    ClaimPostureDelta,
    ClaimPostureDeltaSnapshot,
    ClaimPostureTransition,
)
from ix_missionproof.claims.postures import ClaimPostureStatus
from ix_missionproof.claims.reconciliations import (
    ClaimPostureAlertReconciliation,
    ClaimPostureAlertReconciliationSnapshot,
    ClaimPostureAlertReconciliationStatus,
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

_LIFECYCLE_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleStatus(StrEnum):
    """Continuity state of one claim alert across docket generations."""

    RETAINED_UNCHANGED = "retained-unchanged"
    RETAINED_CHANGED = "retained-changed"
    CLEARED = "cleared"
    NEW = "new"

    @property
    def is_active(self) -> bool:
        """Return whether the current docket contains the alert."""

        return self in {
            ClaimPostureAlertLifecycleStatus.RETAINED_UNCHANGED,
            ClaimPostureAlertLifecycleStatus.RETAINED_CHANGED,
            ClaimPostureAlertLifecycleStatus.NEW,
        }

    @property
    def is_retained(self) -> bool:
        """Return whether the alert exists in both dockets."""

        return self in {
            ClaimPostureAlertLifecycleStatus.RETAINED_UNCHANGED,
            ClaimPostureAlertLifecycleStatus.RETAINED_CHANGED,
        }

    @property
    def is_cleared(self) -> bool:
        """Return whether posture change removed the prior alert."""

        return self is ClaimPostureAlertLifecycleStatus.CLEARED

    @property
    def is_new(self) -> bool:
        """Return whether the current docket newly opened the alert."""

        return self is ClaimPostureAlertLifecycleStatus.NEW


class ClaimPostureAlertLifecycleSnapshotStatus(StrEnum):
    """Aggregate continuity state between two alert dockets."""

    CLEAR = "clear"
    ACTIVE_UNCHANGED = "active-unchanged"
    CHANGED = "changed"

    @property
    def has_active_alerts(self) -> bool:
        """Return whether the current docket contains active alerts."""

        return self is not ClaimPostureAlertLifecycleSnapshotStatus.CLEAR


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


def _validate_lifecycle_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "claim-alert lifecycle producer must be active"
        )
    if producer.kind not in _LIFECYCLE_PRODUCER_KINDS:
        raise FoundationError(
            "claim-alert lifecycle producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "claim-alert lifecycle producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycle:
    """Continuity record for one claim across two alert dockets."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-v1"
    )

    lifecycle_id: ScopedIdentifier
    compared_at: UtcTimestamp
    claim_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleStatus
    transition: ClaimPostureTransition
    previous_posture_status: ClaimPostureStatus
    current_posture_status: ClaimPostureStatus
    previous_alert_id: ScopedIdentifier | None
    current_alert_id: ScopedIdentifier | None
    reconciliation_id: ScopedIdentifier | None
    delta_id: ScopedIdentifier
    previous_severity: ClaimPostureAlertSeverity | None
    current_severity: ClaimPostureAlertSeverity | None
    reconciliation_status: ClaimPostureAlertReconciliationStatus | None
    previous_alert_digest: ContentDigest | None
    current_alert_digest: ContentDigest | None
    reconciliation_digest: ContentDigest | None
    delta_digest: ContentDigest
    prior_docket_digest: ContentDigest
    current_docket_digest: ContentDigest
    reconciliation_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_lifecycle_semantics()

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.lifecycle_id,
            field_name="lifecycle_id",
            namespace="claim-posture-alert-lifecycle",
        )
        _require_identifier(
            self.claim_id,
            field_name="claim_id",
            namespace="claim",
        )
        _require_identifier(
            self.delta_id,
            field_name="delta_id",
            namespace="claim-posture-delta",
        )
        _require_optional_identifier(
            self.previous_alert_id,
            field_name="previous_alert_id",
            namespace="claim-posture-alert",
        )
        _require_optional_identifier(
            self.current_alert_id,
            field_name="current_alert_id",
            namespace="claim-posture-alert",
        )
        _require_optional_identifier(
            self.reconciliation_id,
            field_name="reconciliation_id",
            namespace="claim-posture-alert-reconciliation",
        )

        if not isinstance(
            self.compared_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "compared_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.status,
            ClaimPostureAlertLifecycleStatus,
        ):
            raise FoundationError(
                "status must be a ClaimPostureAlertLifecycleStatus"
            )
        if not isinstance(
            self.transition,
            ClaimPostureTransition,
        ):
            raise FoundationError(
                "transition must be a ClaimPostureTransition"
            )
        if not isinstance(
            self.previous_posture_status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "previous_posture_status must be "
                "a ClaimPostureStatus"
            )
        if not isinstance(
            self.current_posture_status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "current_posture_status must be "
                "a ClaimPostureStatus"
            )
        if (
            self.previous_severity is not None
            and not isinstance(
                self.previous_severity,
                ClaimPostureAlertSeverity,
            )
        ):
            raise FoundationError(
                "previous_severity must be "
                "a ClaimPostureAlertSeverity or None"
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
        if (
            self.reconciliation_status is not None
            and not isinstance(
                self.reconciliation_status,
                ClaimPostureAlertReconciliationStatus,
            )
        ):
            raise FoundationError(
                "reconciliation_status must be a "
                "ClaimPostureAlertReconciliationStatus or None"
            )

    def _validate_digests(self) -> None:
        _require_optional_digest(
            self.previous_alert_digest,
            field_name="previous_alert_digest",
            domain="claim-posture-alert",
        )
        _require_optional_digest(
            self.current_alert_digest,
            field_name="current_alert_digest",
            domain="claim-posture-alert",
        )
        _require_optional_digest(
            self.reconciliation_digest,
            field_name="reconciliation_digest",
            domain="claim-posture-alert-reconciliation",
        )

        for field_name, value, domain in (
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
                "current_docket_digest",
                self.current_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "reconciliation_snapshot_digest",
                self.reconciliation_snapshot_digest,
                "claim-posture-alert-reconciliation-snapshot",
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

    def _validate_lifecycle_semantics(self) -> None:
        previous_present = (
            self.previous_alert_id is not None
            and self.previous_alert_digest is not None
            and self.previous_severity is not None
        )
        previous_absent = (
            self.previous_alert_id is None
            and self.previous_alert_digest is None
            and self.previous_severity is None
        )
        current_present = (
            self.current_alert_id is not None
            and self.current_alert_digest is not None
            and self.current_severity is not None
        )
        current_absent = (
            self.current_alert_id is None
            and self.current_alert_digest is None
            and self.current_severity is None
        )
        reconciliation_present = (
            self.reconciliation_id is not None
            and self.reconciliation_digest is not None
            and self.reconciliation_status is not None
        )
        reconciliation_absent = (
            self.reconciliation_id is None
            and self.reconciliation_digest is None
            and self.reconciliation_status is None
        )

        if not previous_present and not previous_absent:
            raise FoundationError(
                "previous alert identity, digest, and severity "
                "must be present or absent together"
            )
        if not current_present and not current_absent:
            raise FoundationError(
                "current alert identity, digest, and severity "
                "must be present or absent together"
            )
        if not reconciliation_present and not reconciliation_absent:
            raise FoundationError(
                "reconciliation identity, digest, and status "
                "must be present or absent together"
            )

        if self.status is ClaimPostureAlertLifecycleStatus.NEW:
            if not previous_absent or not current_present:
                raise FoundationError(
                    "new alert lifecycle requires only "
                    "a current alert"
                )
            if not reconciliation_absent:
                raise FoundationError(
                    "new alert lifecycle must not contain "
                    "a prior-alert reconciliation"
                )
            return

        if self.status is ClaimPostureAlertLifecycleStatus.CLEARED:
            if not previous_present or not current_absent:
                raise FoundationError(
                    "cleared alert lifecycle requires only "
                    "a previous alert"
                )
            if not reconciliation_present:
                raise FoundationError(
                    "cleared alert lifecycle requires "
                    "a reconciliation"
                )
            if self.reconciliation_status is not (
                ClaimPostureAlertReconciliationStatus.CLEARED
            ):
                raise FoundationError(
                    "cleared alert lifecycle requires "
                    "a cleared reconciliation"
                )
            return

        if not previous_present or not current_present:
            raise FoundationError(
                "retained alert lifecycle requires both "
                "previous and current alerts"
            )
        if not reconciliation_present:
            raise FoundationError(
                "retained alert lifecycle requires "
                "a reconciliation"
            )

        expected_reconciliation = {
            ClaimPostureAlertLifecycleStatus.RETAINED_UNCHANGED: (
                ClaimPostureAlertReconciliationStatus
                .ACTIVE_UNCHANGED
            ),
            ClaimPostureAlertLifecycleStatus.RETAINED_CHANGED: (
                ClaimPostureAlertReconciliationStatus
                .ACTIVE_CHANGED
            ),
        }[self.status]

        if self.reconciliation_status is not expected_reconciliation:
            raise FoundationError(
                "retained alert lifecycle status does not match "
                "its reconciliation"
            )

    @classmethod
    def compare(
        cls,
        *,
        key: str,
        compared_at: UtcTimestamp,
        claim_id: ScopedIdentifier,
        delta: ClaimPostureDelta,
        prior_docket: ClaimPostureAlertDocket,
        current_docket: ClaimPostureAlertDocket,
        reconciliation_snapshot: (
            ClaimPostureAlertReconciliationSnapshot
        ),
        delta_snapshot: ClaimPostureDeltaSnapshot,
    ) -> ClaimPostureAlertLifecycle:
        """Account for one claim across successive alert dockets."""

        previous_alert = prior_docket.alert_for(
            claim_id
        )
        current_alert = current_docket.alert_for(
            claim_id
        )
        reconciliation = (
            reconciliation_snapshot.reconciliation_for_claim(
                claim_id
            )
        )

        cls._validate_bindings(
            compared_at=compared_at,
            claim_id=claim_id,
            delta=delta,
            previous_alert=previous_alert,
            current_alert=current_alert,
            reconciliation=reconciliation,
            prior_docket=prior_docket,
            current_docket=current_docket,
            reconciliation_snapshot=reconciliation_snapshot,
            delta_snapshot=delta_snapshot,
        )

        status = cls.classify(
            previous_alert=previous_alert,
            current_alert=current_alert,
            reconciliation=reconciliation,
        )

        return cls(
            lifecycle_id=ScopedIdentifier.create(
                namespace="claim-posture-alert-lifecycle",
                key=key,
                namespace_field="lifecycle namespace",
                key_field="lifecycle key",
            ),
            compared_at=compared_at,
            claim_id=claim_id,
            status=status,
            transition=delta.transition,
            previous_posture_status=delta.previous_status,
            current_posture_status=delta.current_status,
            previous_alert_id=(
                previous_alert.alert_id
                if previous_alert is not None
                else None
            ),
            current_alert_id=(
                current_alert.alert_id
                if current_alert is not None
                else None
            ),
            reconciliation_id=(
                reconciliation.reconciliation_id
                if reconciliation is not None
                else None
            ),
            delta_id=delta.delta_id,
            previous_severity=(
                previous_alert.severity
                if previous_alert is not None
                else None
            ),
            current_severity=(
                current_alert.severity
                if current_alert is not None
                else None
            ),
            reconciliation_status=(
                reconciliation.status
                if reconciliation is not None
                else None
            ),
            previous_alert_digest=(
                previous_alert.digest()
                if previous_alert is not None
                else None
            ),
            current_alert_digest=(
                current_alert.digest()
                if current_alert is not None
                else None
            ),
            reconciliation_digest=(
                reconciliation.digest()
                if reconciliation is not None
                else None
            ),
            delta_digest=delta.digest(),
            prior_docket_digest=prior_docket.digest(),
            current_docket_digest=current_docket.digest(),
            reconciliation_snapshot_digest=(
                reconciliation_snapshot.digest()
            ),
            delta_snapshot_digest=delta_snapshot.digest(),
            claim_catalog_digest=(
                current_docket.claim_catalog_digest
            ),
            actor_registry_digest=(
                current_docket.actor_registry_digest
            ),
        )

    @staticmethod
    def _validate_bindings(
        *,
        compared_at: UtcTimestamp,
        claim_id: ScopedIdentifier,
        delta: ClaimPostureDelta,
        previous_alert: ClaimPostureAlert | None,
        current_alert: ClaimPostureAlert | None,
        reconciliation: ClaimPostureAlertReconciliation | None,
        prior_docket: ClaimPostureAlertDocket,
        current_docket: ClaimPostureAlertDocket,
        reconciliation_snapshot: (
            ClaimPostureAlertReconciliationSnapshot
        ),
        delta_snapshot: ClaimPostureDeltaSnapshot,
    ) -> None:
        bound_delta = delta_snapshot.require_delta(
            claim_id
        )

        if bound_delta.digest() != delta.digest():
            raise FoundationError(
                "claim-posture delta does not match "
                "the posture-delta snapshot"
            )

        if previous_alert is not None:
            bound_previous = prior_docket.require_alert(
                claim_id
            )

            if bound_previous.digest() != previous_alert.digest():
                raise FoundationError(
                    "previous alert does not match "
                    "the prior alert docket"
                )

        if current_alert is not None:
            bound_current = current_docket.require_alert(
                claim_id
            )

            if bound_current.digest() != current_alert.digest():
                raise FoundationError(
                    "current alert does not match "
                    "the current alert docket"
                )
            if current_alert.transition is not delta.transition:
                raise FoundationError(
                    "current alert transition does not match "
                    "the posture delta"
                )
            if (
                current_alert.current_status
                is not delta.current_status
            ):
                raise FoundationError(
                    "current alert posture status does not match "
                    "the posture delta"
                )

        if reconciliation is not None:
            bound_reconciliation = (
                reconciliation_snapshot
                .require_reconciliation_for_alert(
                    reconciliation.alert_id
                )
            )

            if (
                bound_reconciliation.digest()
                != reconciliation.digest()
            ):
                raise FoundationError(
                    "alert reconciliation does not match "
                    "the reconciliation snapshot"
                )
            if reconciliation.claim_id != claim_id:
                raise FoundationError(
                    "alert reconciliation references "
                    "a different claim"
                )

        if previous_alert is None and reconciliation is not None:
            raise FoundationError(
                "claim without a prior alert must not contain "
                "a reconciliation"
            )
        if previous_alert is not None and reconciliation is None:
            raise FoundationError(
                "every prior alert must have "
                "a reconciliation"
            )

        if reconciliation is not None:
            if current_alert is None and not reconciliation.alert_cleared:
                raise FoundationError(
                    "active reconciliation requires "
                    "a current alert"
                )
            if current_alert is not None and not (
                reconciliation.alert_remains_active
            ):
                raise FoundationError(
                    "cleared reconciliation must not have "
                    "a current alert"
                )
            if current_alert is not None:
                if (
                    reconciliation.current_severity
                    is not current_alert.severity
                ):
                    raise FoundationError(
                        "current alert severity does not match "
                        "the reconciliation"
                    )
                if (
                    reconciliation.current_status
                    is not current_alert.current_status
                ):
                    raise FoundationError(
                        "current alert posture does not match "
                        "the reconciliation"
                    )
                if (
                    reconciliation.current_reasons
                    != current_alert.reasons
                ):
                    raise FoundationError(
                        "current alert reasons do not match "
                        "the reconciliation"
                    )

        if compared_at.value < current_docket.generated_at.value:
            raise FoundationError(
                "alert lifecycle comparison must not predate "
                "the current alert docket"
            )
        if (
            compared_at.value
            < reconciliation_snapshot.reconciled_at.value
        ):
            raise FoundationError(
                "alert lifecycle comparison must not predate "
                "the reconciliation snapshot"
            )

    @staticmethod
    def classify(
        *,
        previous_alert: ClaimPostureAlert | None,
        current_alert: ClaimPostureAlert | None,
        reconciliation: ClaimPostureAlertReconciliation | None,
    ) -> ClaimPostureAlertLifecycleStatus:
        """Classify one claim's alert lifecycle."""

        if previous_alert is None:
            if current_alert is None:
                raise FoundationError(
                    "alert lifecycle requires a prior "
                    "or current alert"
                )
            if reconciliation is not None:
                raise FoundationError(
                    "new alert must not contain "
                    "a prior-alert reconciliation"
                )
            return ClaimPostureAlertLifecycleStatus.NEW

        if reconciliation is None:
            raise FoundationError(
                "prior alert requires a reconciliation"
            )

        if current_alert is None:
            if not reconciliation.alert_cleared:
                raise FoundationError(
                    "missing current alert requires "
                    "a cleared reconciliation"
                )
            return ClaimPostureAlertLifecycleStatus.CLEARED

        if reconciliation.status is (
            ClaimPostureAlertReconciliationStatus
            .ACTIVE_UNCHANGED
        ):
            return (
                ClaimPostureAlertLifecycleStatus
                .RETAINED_UNCHANGED
            )

        if reconciliation.status is (
            ClaimPostureAlertReconciliationStatus
            .ACTIVE_CHANGED
        ):
            return (
                ClaimPostureAlertLifecycleStatus
                .RETAINED_CHANGED
            )

        raise FoundationError(
            "cleared reconciliation must not retain "
            "a current alert"
        )

    @property
    def alert_is_active(self) -> bool:
        """Return whether the current docket contains the alert."""

        return self.status.is_active

    @property
    def alert_was_retained(self) -> bool:
        """Return whether the alert continued across dockets."""

        return self.status.is_retained

    @property
    def alert_was_cleared(self) -> bool:
        """Return whether newer posture cleared the prior alert."""

        return self.status.is_cleared

    @property
    def alert_is_new(self) -> bool:
        """Return whether the current docket newly opened the alert."""

        return self.status.is_new

    @property
    def disappeared_without_reconciliation(self) -> bool:
        """Return false because every prior alert is accounted for."""

        return False

    @property
    def response_can_clear_alert(self) -> bool:
        """Return false because responses cannot clear posture alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because lifecycle records are reporting only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because lifecycle continuity grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic alert-lifecycle representation."""

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "alert_is_active": self.alert_is_active,
            "alert_is_new": self.alert_is_new,
            "alert_was_cleared": self.alert_was_cleared,
            "alert_was_retained": self.alert_was_retained,
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "compared_at": self.compared_at.isoformat(),
            "current_alert_digest": (
                self.current_alert_digest.to_payload()
                if self.current_alert_digest is not None
                else None
            ),
            "current_alert_id": (
                str(self.current_alert_id)
                if self.current_alert_id is not None
                else None
            ),
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
            ),
            "current_posture_status": (
                self.current_posture_status.value
            ),
            "current_severity": (
                self.current_severity.value
                if self.current_severity is not None
                else None
            ),
            "delta_digest": self.delta_digest.to_payload(),
            "delta_id": str(self.delta_id),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
            ),
            "disappeared_without_reconciliation": (
                self.disappeared_without_reconciliation
            ),
            "grants_authority": self.grants_authority,
            "lifecycle_id": str(self.lifecycle_id),
            "previous_alert_digest": (
                self.previous_alert_digest.to_payload()
                if self.previous_alert_digest is not None
                else None
            ),
            "previous_alert_id": (
                str(self.previous_alert_id)
                if self.previous_alert_id is not None
                else None
            ),
            "previous_posture_status": (
                self.previous_posture_status.value
            ),
            "previous_severity": (
                self.previous_severity.value
                if self.previous_severity is not None
                else None
            ),
            "prior_docket_digest": (
                self.prior_docket_digest.to_payload()
            ),
            "reconciliation_digest": (
                self.reconciliation_digest.to_payload()
                if self.reconciliation_digest is not None
                else None
            ),
            "reconciliation_id": (
                str(self.reconciliation_id)
                if self.reconciliation_id is not None
                else None
            ),
            "reconciliation_snapshot_digest": (
                self.reconciliation_snapshot_digest.to_payload()
            ),
            "reconciliation_status": (
                self.reconciliation_status.value
                if self.reconciliation_status is not None
                else None
            ),
            "response_can_clear_alert": (
                self.response_can_clear_alert
            ),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "transition": self.transition.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical lifecycle document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete alert lifecycle."""

        return self.to_document().digest(
            domain="claim-posture-alert-lifecycle"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleSnapshot:
    """Complete continuity proof across successive alert dockets."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    compared_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertLifecycleSnapshotStatus
    prior_docket_id: ScopedIdentifier
    current_docket_id: ScopedIdentifier
    reconciliation_snapshot_id: ScopedIdentifier
    delta_snapshot_id: ScopedIdentifier
    lifecycles: tuple[ClaimPostureAlertLifecycle, ...]
    prior_docket_digest: ContentDigest
    current_docket_digest: ContentDigest
    reconciliation_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        lifecycles = tuple(
            self.lifecycles
        )
        self._validate_lifecycles(
            lifecycles
        )

        ordered = tuple(
            sorted(
                lifecycles,
                key=lambda lifecycle: str(
                    lifecycle.claim_id
                ),
            )
        )
        object.__setattr__(
            self,
            "lifecycles",
            ordered,
        )

        expected_status = self._status_for(
            ordered
        )

        if self.status is not expected_status:
            raise FoundationError(
                "claim-alert lifecycle snapshot status does not "
                "match its lifecycle records"
            )

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                "claim-posture-alert-lifecycle-snapshot",
            ),
            (
                "prior_docket_id",
                self.prior_docket_id,
                "claim-posture-alert-docket",
            ),
            (
                "current_docket_id",
                self.current_docket_id,
                "claim-posture-alert-docket",
            ),
            (
                "reconciliation_snapshot_id",
                self.reconciliation_snapshot_id,
                "claim-posture-alert-reconciliation-snapshot",
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
            self.compared_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "compared_at must be a UtcTimestamp"
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
        if self.producer_kind not in _LIFECYCLE_PRODUCER_KINDS:
            raise FoundationError(
                "claim-alert lifecycle producer must be "
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
            ClaimPostureAlertLifecycleSnapshotStatus,
        ):
            raise FoundationError(
                "status must be a "
                "ClaimPostureAlertLifecycleSnapshotStatus"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "prior_docket_digest",
                self.prior_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "current_docket_digest",
                self.current_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "reconciliation_snapshot_digest",
                self.reconciliation_snapshot_digest,
                "claim-posture-alert-reconciliation-snapshot",
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

    def _validate_lifecycles(
        self,
        lifecycles: tuple[
            ClaimPostureAlertLifecycle,
            ...,
        ],
    ) -> None:
        for index, lifecycle in enumerate(
            lifecycles
        ):
            if not isinstance(
                lifecycle,
                ClaimPostureAlertLifecycle,
            ):
                raise FoundationError(
                    f"lifecycles[{index}] must be a "
                    "ClaimPostureAlertLifecycle"
                )
            if lifecycle.compared_at != self.compared_at:
                raise FoundationError(
                    "every alert lifecycle must use "
                    "the snapshot comparison time"
                )
            if (
                lifecycle.prior_docket_digest
                != self.prior_docket_digest
            ):
                raise FoundationError(
                    "every alert lifecycle must bind "
                    "the prior alert docket"
                )
            if (
                lifecycle.current_docket_digest
                != self.current_docket_digest
            ):
                raise FoundationError(
                    "every alert lifecycle must bind "
                    "the current alert docket"
                )
            if (
                lifecycle.reconciliation_snapshot_digest
                != self.reconciliation_snapshot_digest
            ):
                raise FoundationError(
                    "every alert lifecycle must bind "
                    "the reconciliation snapshot"
                )
            if (
                lifecycle.delta_snapshot_digest
                != self.delta_snapshot_digest
            ):
                raise FoundationError(
                    "every alert lifecycle must bind "
                    "the posture-delta snapshot"
                )
            if (
                lifecycle.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every alert lifecycle must bind "
                    "the claim catalog"
                )
            if (
                lifecycle.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every alert lifecycle must bind "
                    "the actor registry"
                )

        lifecycle_ids = tuple(
            lifecycle.lifecycle_id
            for lifecycle in lifecycles
        )

        if len(lifecycle_ids) != len(
            set(lifecycle_ids)
        ):
            raise FoundationError(
                "claim-alert lifecycle snapshot must contain "
                "unique lifecycle IDs"
            )

        claim_ids = tuple(
            lifecycle.claim_id
            for lifecycle in lifecycles
        )

        if len(claim_ids) != len(
            set(claim_ids)
        ):
            raise FoundationError(
                "claim-alert lifecycle snapshot must contain "
                "one lifecycle per claim"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        compared_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        prior_docket: ClaimPostureAlertDocket,
        current_docket: ClaimPostureAlertDocket,
        reconciliation_snapshot: (
            ClaimPostureAlertReconciliationSnapshot
        ),
        delta_snapshot: ClaimPostureDeltaSnapshot,
        actor_registry: ActorRegistry,
    ) -> ClaimPostureAlertLifecycleSnapshot:
        """Prove continuity for every prior or current alert."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = _validate_lifecycle_producer(
            producer
        )

        cls._validate_bindings(
            compared_at=compared_at,
            prior_docket=prior_docket,
            current_docket=current_docket,
            reconciliation_snapshot=reconciliation_snapshot,
            delta_snapshot=delta_snapshot,
            actor_registry=actor_registry,
        )

        claim_ids = {
            alert.claim_id
            for alert in prior_docket.alerts
        }
        claim_ids.update(
            alert.claim_id
            for alert in current_docket.alerts
        )

        lifecycles = tuple(
            ClaimPostureAlertLifecycle.compare(
                key=(
                    f"{key}-"
                    f"{str(claim_id)}"
                ),
                compared_at=compared_at,
                claim_id=claim_id,
                delta=delta_snapshot.require_delta(
                    claim_id
                ),
                prior_docket=prior_docket,
                current_docket=current_docket,
                reconciliation_snapshot=(
                    reconciliation_snapshot
                ),
                delta_snapshot=delta_snapshot,
            )
            for claim_id in sorted(
                claim_ids,
                key=str,
            )
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-snapshot"
                ),
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            compared_at=compared_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            status=cls._status_for(
                lifecycles
            ),
            prior_docket_id=prior_docket.docket_id,
            current_docket_id=current_docket.docket_id,
            reconciliation_snapshot_id=(
                reconciliation_snapshot.snapshot_id
            ),
            delta_snapshot_id=delta_snapshot.snapshot_id,
            lifecycles=lifecycles,
            prior_docket_digest=prior_docket.digest(),
            current_docket_digest=current_docket.digest(),
            reconciliation_snapshot_digest=(
                reconciliation_snapshot.digest()
            ),
            delta_snapshot_digest=delta_snapshot.digest(),
            claim_catalog_digest=(
                current_docket.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        compared_at: UtcTimestamp,
        prior_docket: ClaimPostureAlertDocket,
        current_docket: ClaimPostureAlertDocket,
        reconciliation_snapshot: (
            ClaimPostureAlertReconciliationSnapshot
        ),
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
                "current alert docket",
                current_docket.actor_registry_digest,
            ),
            (
                "reconciliation snapshot",
                reconciliation_snapshot.actor_registry_digest,
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
            reconciliation_snapshot.prior_docket_id
            != prior_docket.docket_id
        ):
            raise FoundationError(
                "reconciliation snapshot references "
                "a different prior alert docket"
            )
        if (
            reconciliation_snapshot.prior_docket_digest
            != prior_docket.digest()
        ):
            raise FoundationError(
                "reconciliation snapshot is not bound to "
                "the prior alert docket"
            )
        if (
            reconciliation_snapshot.delta_snapshot_id
            != delta_snapshot.snapshot_id
        ):
            raise FoundationError(
                "reconciliation snapshot references "
                "a different posture-delta snapshot"
            )
        if (
            reconciliation_snapshot.delta_snapshot_digest
            != delta_snapshot.digest()
        ):
            raise FoundationError(
                "reconciliation snapshot is not bound to "
                "the posture-delta snapshot"
            )

        if (
            current_docket.current_snapshot_id
            != reconciliation_snapshot.current_snapshot_id
        ):
            raise FoundationError(
                "current alert docket references a different "
                "current posture snapshot"
            )
        if (
            current_docket.current_snapshot_digest
            != reconciliation_snapshot.current_snapshot_digest
        ):
            raise FoundationError(
                "current alert docket is not bound to "
                "the reconciled current posture snapshot"
            )
        if (
            current_docket.delta_snapshot_id
            != delta_snapshot.snapshot_id
        ):
            raise FoundationError(
                "current alert docket references a different "
                "posture-delta snapshot"
            )
        if (
            current_docket.delta_snapshot_digest
            != delta_snapshot.digest()
        ):
            raise FoundationError(
                "current alert docket is not bound to "
                "the posture-delta snapshot"
            )

        for role, digest in (
            (
                "prior alert docket",
                prior_docket.claim_catalog_digest,
            ),
            (
                "current alert docket",
                current_docket.claim_catalog_digest,
            ),
            (
                "reconciliation snapshot",
                reconciliation_snapshot.claim_catalog_digest,
            ),
            (
                "posture-delta snapshot",
                delta_snapshot.claim_catalog_digest,
            ),
        ):
            if digest != current_docket.claim_catalog_digest:
                raise FoundationError(
                    f"{role} is not bound to "
                    "the current claim catalog"
                )

        if (
            current_docket.generated_at.value
            <= prior_docket.generated_at.value
        ):
            raise FoundationError(
                "current alert docket must be newer "
                "than the prior alert docket"
            )
        if (
            current_docket.generated_at.value
            < reconciliation_snapshot.reconciled_at.value
        ):
            raise FoundationError(
                "current alert docket must not predate "
                "the reconciliation snapshot"
            )
        if compared_at.value < current_docket.generated_at.value:
            raise FoundationError(
                "alert lifecycle snapshot must not predate "
                "the current alert docket"
            )

        prior_alert_ids = {
            reconciliation.alert_id
            for reconciliation
            in reconciliation_snapshot.reconciliations
        }
        expected_prior_alert_ids = {
            alert.alert_id
            for alert in prior_docket.alerts
        }

        if prior_alert_ids != expected_prior_alert_ids:
            raise FoundationError(
                "reconciliation snapshot must account for "
                "every prior alert exactly once"
            )

    @staticmethod
    def _status_for(
        lifecycles: tuple[
            ClaimPostureAlertLifecycle,
            ...,
        ],
    ) -> ClaimPostureAlertLifecycleSnapshotStatus:
        active = tuple(
            lifecycle
            for lifecycle in lifecycles
            if lifecycle.alert_is_active
        )

        if not active:
            return (
                ClaimPostureAlertLifecycleSnapshotStatus.CLEAR
            )

        if all(
            lifecycle.status
            is ClaimPostureAlertLifecycleStatus.RETAINED_UNCHANGED
            for lifecycle in active
        ) and not any(
            lifecycle.alert_was_cleared
            for lifecycle in lifecycles
        ):
            return (
                ClaimPostureAlertLifecycleSnapshotStatus
                .ACTIVE_UNCHANGED
            )

        return (
            ClaimPostureAlertLifecycleSnapshotStatus.CHANGED
        )

    @property
    def total_count(self) -> int:
        """Return the total number of alert lifecycle records."""

        return len(
            self.lifecycles
        )

    @property
    def active_count(self) -> int:
        """Return the number of alerts on the current docket."""

        return sum(
            lifecycle.alert_is_active
            for lifecycle in self.lifecycles
        )

    @property
    def retained_count(self) -> int:
        """Return the number of alerts retained across dockets."""

        return sum(
            lifecycle.alert_was_retained
            for lifecycle in self.lifecycles
        )

    @property
    def retained_unchanged_count(self) -> int:
        """Return retained alerts whose condition is unchanged."""

        return sum(
            lifecycle.status
            is ClaimPostureAlertLifecycleStatus.RETAINED_UNCHANGED
            for lifecycle in self.lifecycles
        )

    @property
    def retained_changed_count(self) -> int:
        """Return retained alerts whose condition changed."""

        return sum(
            lifecycle.status
            is ClaimPostureAlertLifecycleStatus.RETAINED_CHANGED
            for lifecycle in self.lifecycles
        )

    @property
    def cleared_count(self) -> int:
        """Return prior alerts cleared by posture change."""

        return sum(
            lifecycle.alert_was_cleared
            for lifecycle in self.lifecycles
        )

    @property
    def new_count(self) -> int:
        """Return alerts newly opened on the current docket."""

        return sum(
            lifecycle.alert_is_new
            for lifecycle in self.lifecycles
        )

    @property
    def all_prior_alerts_accounted_for(self) -> bool:
        """Return true because construction enforces complete continuity."""

        return True

    @property
    def silent_drop_count(self) -> int:
        """Return zero because alerts cannot disappear silently."""

        return 0

    @property
    def has_active_alerts(self) -> bool:
        """Return whether the current docket contains active alerts."""

        return self.status.has_active_alerts

    @property
    def response_can_clear_alerts(self) -> bool:
        """Return false because response history cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because lifecycle continuity is reporting only."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because lifecycle continuity grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def lifecycle_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureAlertLifecycle | None:
        """Return the lifecycle record for one claim."""

        for lifecycle in self.lifecycles:
            if lifecycle.claim_id == claim_id:
                return lifecycle

        return None

    def require_lifecycle_for_claim(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureAlertLifecycle:
        """Return one claim lifecycle or fail when absent."""

        lifecycle = self.lifecycle_for_claim(
            claim_id
        )

        if lifecycle is None:
            raise FoundationError(
                "claim-alert lifecycle snapshot does not contain "
                f"claim: {claim_id}"
            )

        return lifecycle

    def active_lifecycles(
        self,
    ) -> tuple[ClaimPostureAlertLifecycle, ...]:
        """Return alerts present on the current docket."""

        return tuple(
            lifecycle
            for lifecycle in self.lifecycles
            if lifecycle.alert_is_active
        )

    def cleared_lifecycles(
        self,
    ) -> tuple[ClaimPostureAlertLifecycle, ...]:
        """Return prior alerts cleared through posture change."""

        return tuple(
            lifecycle
            for lifecycle in self.lifecycles
            if lifecycle.alert_was_cleared
        )

    def new_lifecycles(
        self,
    ) -> tuple[ClaimPostureAlertLifecycle, ...]:
        """Return alerts newly opened on the current docket."""

        return tuple(
            lifecycle
            for lifecycle in self.lifecycles
            if lifecycle.alert_is_new
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic lifecycle-snapshot representation."""

        lifecycle_payloads: JsonArray = [
            lifecycle.to_payload()
            for lifecycle in self.lifecycles
        ]

        return {
            "active_count": self.active_count,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "all_prior_alerts_accounted_for": (
                self.all_prior_alerts_accounted_for
            ),
            "changed_count": (
                self.retained_changed_count
                + self.cleared_count
                + self.new_count
            ),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "cleared_count": self.cleared_count,
            "compared_at": self.compared_at.isoformat(),
            "current_docket_digest": (
                self.current_docket_digest.to_payload()
            ),
            "current_docket_id": str(
                self.current_docket_id
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
            ),
            "delta_snapshot_id": str(
                self.delta_snapshot_id
            ),
            "grants_authority": self.grants_authority,
            "has_active_alerts": self.has_active_alerts,
            "lifecycles": lifecycle_payloads,
            "new_count": self.new_count,
            "prior_docket_digest": (
                self.prior_docket_digest.to_payload()
            ),
            "prior_docket_id": str(
                self.prior_docket_id
            ),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "reconciliation_snapshot_digest": (
                self.reconciliation_snapshot_digest.to_payload()
            ),
            "reconciliation_snapshot_id": str(
                self.reconciliation_snapshot_id
            ),
            "response_can_clear_alerts": (
                self.response_can_clear_alerts
            ),
            "retained_changed_count": (
                self.retained_changed_count
            ),
            "retained_count": self.retained_count,
            "retained_unchanged_count": (
                self.retained_unchanged_count
            ),
            "schema": self.SCHEMA.value,
            "silent_drop_count": self.silent_drop_count,
            "snapshot_id": str(self.snapshot_id),
            "status": self.status.value,
            "total_count": self.total_count,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical lifecycle snapshot."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering complete alert continuity."""

        return self.to_document().digest(
            domain="claim-posture-alert-lifecycle-snapshot"
        )
