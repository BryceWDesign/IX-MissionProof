"""Immutable claim-posture alerts and attention dockets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

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

_ALERT_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertSeverity(StrEnum):
    """Operational severity of one current claim-posture alert."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def requires_immediate_attention(self) -> bool:
        """Return whether this alert represents a critical posture."""

        return self is ClaimPostureAlertSeverity.CRITICAL


class ClaimPostureAlertReason(StrEnum):
    """Stable reasons that place a current claim posture on the docket."""

    SUPPORT_LOST = "support-lost"
    NEW_ADVERSE_SIGNAL = "new-adverse-signal"
    ATTENTION_OPENED = "attention-opened"
    CURRENT_UNEVALUATED = "current-unevaluated"
    CURRENT_DEFERRED = "current-deferred"
    CURRENT_AWAITING_ADJUDICATION = "current-awaiting-adjudication"
    CURRENT_INCOMPLETE_EVIDENCE = "current-incomplete-evidence"
    CURRENT_EVIDENCE_REVIEW_OPEN = "current-evidence-review-open"
    CURRENT_NOT_SUPPORTED = "current-not-supported"
    CURRENT_FALSIFICATION_SIGNAL = "current-falsification-signal"


class ClaimPostureAlertDocketStatus(StrEnum):
    """Aggregate operational state of a claim-posture alert docket."""

    CLEAR = "clear"
    ACTION_REQUIRED = "action-required"
    CRITICAL = "critical"

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the docket contains any active alert."""

        return self is not ClaimPostureAlertDocketStatus.CLEAR


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
        raise FoundationError(f"{field_name} must be a ContentDigest")
    if value.domain != CanonicalKey(domain):
        raise FoundationError(f"{field_name} domain must be {domain}")


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


def _validate_alert_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError("claim-posture alert producer must be active")
    if producer.kind not in _ALERT_PRODUCER_KINDS:
        raise FoundationError(
            "claim-posture alert producer must be a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "claim-posture alert producer must identify an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlert:
    """One immutable alert over a current claim posture."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("claim-posture-alert-v1")

    alert_id: ScopedIdentifier
    generated_at: UtcTimestamp
    claim_id: ScopedIdentifier
    severity: ClaimPostureAlertSeverity
    reasons: tuple[ClaimPostureAlertReason, ...]
    current_status: ClaimPostureStatus
    transition: ClaimPostureTransition | None
    current_posture_id: ScopedIdentifier
    delta_id: ScopedIdentifier | None
    claim_digest: ContentDigest
    current_posture_digest: ContentDigest
    delta_digest: ContentDigest | None
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        reasons = self._normalize_reasons(self.reasons)
        object.__setattr__(
            self,
            "reasons",
            reasons,
        )

        expected_reasons = self.reasons_for(
            current_status=self.current_status,
            transition=self.transition,
        )
        if reasons != expected_reasons:
            raise FoundationError(
                "claim-posture alert reasons do not match "
                "the current status and transition"
            )

        expected_severity = self.severity_for(
            current_status=self.current_status,
            transition=self.transition,
        )
        if expected_severity is None:
            raise FoundationError("claim posture does not require an alert")
        if self.severity is not expected_severity:
            raise FoundationError(
                "claim-posture alert severity does not match "
                "the current status and transition"
            )

        self._validate_delta_presence()

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.alert_id,
            field_name="alert_id",
            namespace="claim-posture-alert",
        )
        _require_identifier(
            self.claim_id,
            field_name="claim_id",
            namespace="claim",
        )
        _require_identifier(
            self.current_posture_id,
            field_name="current_posture_id",
            namespace="claim-posture",
        )
        _require_optional_identifier(
            self.delta_id,
            field_name="delta_id",
            namespace="claim-posture-delta",
        )

        if not isinstance(
            self.generated_at,
            UtcTimestamp,
        ):
            raise FoundationError("generated_at must be a UtcTimestamp")
        if not isinstance(
            self.severity,
            ClaimPostureAlertSeverity,
        ):
            raise FoundationError("severity must be a ClaimPostureAlertSeverity")
        if not isinstance(
            self.current_status,
            ClaimPostureStatus,
        ):
            raise FoundationError("current_status must be a ClaimPostureStatus")
        if self.transition is not None and not isinstance(
            self.transition,
            ClaimPostureTransition,
        ):
            raise FoundationError("transition must be a ClaimPostureTransition or None")

    def _validate_digests(self) -> None:
        _require_digest(
            self.claim_digest,
            field_name="claim_digest",
            domain="claim-specification",
        )
        _require_digest(
            self.current_posture_digest,
            field_name="current_posture_digest",
            domain="claim-posture",
        )
        _require_optional_digest(
            self.delta_digest,
            field_name="delta_digest",
            domain="claim-posture-delta",
        )
        _require_digest(
            self.current_snapshot_digest,
            field_name="current_snapshot_digest",
            domain="claim-posture-snapshot",
        )
        _require_optional_digest(
            self.delta_snapshot_digest,
            field_name="delta_snapshot_digest",
            domain="claim-posture-delta-snapshot",
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

    @staticmethod
    def _normalize_reasons(
        values: tuple[ClaimPostureAlertReason, ...],
    ) -> tuple[ClaimPostureAlertReason, ...]:
        normalized: set[ClaimPostureAlertReason] = set()

        for index, value in enumerate(values):
            if not isinstance(
                value,
                ClaimPostureAlertReason,
            ):
                raise FoundationError(
                    f"reasons[{index}] must be a ClaimPostureAlertReason"
                )
            normalized.add(value)

        if not normalized:
            raise FoundationError("claim-posture alert reasons must not be empty")

        return tuple(
            sorted(
                normalized,
                key=lambda reason: reason.value,
            )
        )

    def _validate_delta_presence(self) -> None:
        delta_values_present = (
            self.delta_id is not None,
            self.delta_digest is not None,
            self.delta_snapshot_digest is not None,
            self.transition is not None,
        )

        if len(set(delta_values_present)) != 1:
            raise FoundationError(
                "delta_id, delta_digest, delta_snapshot_digest, "
                "and transition must be present or absent together"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        generated_at: UtcTimestamp,
        current: ClaimPosture,
        current_snapshot: ClaimPostureSnapshot,
        delta: ClaimPostureDelta | None = None,
        delta_snapshot: ClaimPostureDeltaSnapshot | None = None,
    ) -> ClaimPostureAlert:
        """Create an alert only when the current posture requires one."""

        cls._validate_bindings(
            generated_at=generated_at,
            current=current,
            current_snapshot=current_snapshot,
            delta=delta,
            delta_snapshot=delta_snapshot,
        )

        transition = delta.transition if delta is not None else None
        reasons = cls.reasons_for(
            current_status=current.status,
            transition=transition,
        )
        severity = cls.severity_for(
            current_status=current.status,
            transition=transition,
        )

        if severity is None or not reasons:
            raise FoundationError("claim posture does not require an alert")

        return cls(
            alert_id=ScopedIdentifier.create(
                namespace="claim-posture-alert",
                key=key,
                namespace_field="alert namespace",
                key_field="alert key",
            ),
            generated_at=generated_at,
            claim_id=current.claim_id,
            severity=severity,
            reasons=reasons,
            current_status=current.status,
            transition=transition,
            current_posture_id=current.posture_id,
            delta_id=(
                delta.delta_id
                if delta is not None
                else None
            ),
            claim_digest=current.claim_digest,
            current_posture_digest=current.digest(),
            delta_digest=(
                delta.digest()
                if delta is not None
                else None
            ),
            current_snapshot_digest=current_snapshot.digest(),
            delta_snapshot_digest=(
                delta_snapshot.digest()
                if delta_snapshot is not None
                else None
            ),
            claim_catalog_digest=(
                current_snapshot.claim_catalog_digest
            ),
            actor_registry_digest=(
                current_snapshot.actor_registry_digest
            ),
        )

    @staticmethod
    def _validate_bindings(
        *,
        generated_at: UtcTimestamp,
        current: ClaimPosture,
        current_snapshot: ClaimPostureSnapshot,
        delta: ClaimPostureDelta | None,
        delta_snapshot: ClaimPostureDeltaSnapshot | None,
    ) -> None:
        bound_current = current_snapshot.require_posture(
            current.claim_id
        )

        if bound_current.digest() != current.digest():
            raise FoundationError(
                "current posture does not match "
                "the current posture snapshot"
            )
        if generated_at.value < current_snapshot.captured_at.value:
            raise FoundationError(
                "claim-posture alert must not predate "
                "the current posture snapshot"
            )

        if (delta is None) != (delta_snapshot is None):
            raise FoundationError(
                "delta and delta_snapshot must be supplied together"
            )
        if delta is None or delta_snapshot is None:
            return

        bound_delta = delta_snapshot.require_delta(
            current.claim_id
        )

        if bound_delta.digest() != delta.digest():
            raise FoundationError(
                "claim-posture delta does not match "
                "the delta snapshot"
            )
        if delta.current_posture_id != current.posture_id:
            raise FoundationError(
                "claim-posture delta references a different "
                "current posture"
            )
        if delta.current_posture_digest != current.digest():
            raise FoundationError(
                "claim-posture delta current digest does not match"
            )
        if generated_at.value < delta_snapshot.compared_at.value:
            raise FoundationError(
                "claim-posture alert must not predate "
                "the posture-delta snapshot"
            )
        if (
            delta_snapshot.current_snapshot_id
            != current_snapshot.snapshot_id
        ):
            raise FoundationError(
                "delta snapshot references a different "
                "current posture snapshot"
            )
        if (
            delta_snapshot.current_snapshot_digest
            != current_snapshot.digest()
        ):
            raise FoundationError(
                "delta snapshot is not bound to "
                "the current posture snapshot"
            )

    @staticmethod
    def reasons_for(
        *,
        current_status: ClaimPostureStatus,
        transition: ClaimPostureTransition | None,
    ) -> tuple[ClaimPostureAlertReason, ...]:
        """Return deterministic alert reasons for one current posture."""

        reasons: set[ClaimPostureAlertReason] = set()

        status_reasons = {
            ClaimPostureStatus.UNEVALUATED: (
                ClaimPostureAlertReason.CURRENT_UNEVALUATED
            ),
            ClaimPostureStatus.DEFERRED: (
                ClaimPostureAlertReason.CURRENT_DEFERRED
            ),
            ClaimPostureStatus.AWAITING_ADJUDICATION: (
                ClaimPostureAlertReason
                .CURRENT_AWAITING_ADJUDICATION
            ),
            ClaimPostureStatus.INCOMPLETE_EVIDENCE: (
                ClaimPostureAlertReason
                .CURRENT_INCOMPLETE_EVIDENCE
            ),
            ClaimPostureStatus.EVIDENCE_REVIEW_OPEN: (
                ClaimPostureAlertReason
                .CURRENT_EVIDENCE_REVIEW_OPEN
            ),
            ClaimPostureStatus.NOT_SUPPORTED: (
                ClaimPostureAlertReason.CURRENT_NOT_SUPPORTED
            ),
            ClaimPostureStatus.FALSIFICATION_SIGNAL: (
                ClaimPostureAlertReason
                .CURRENT_FALSIFICATION_SIGNAL
            ),
        }
        status_reason = status_reasons.get(
            current_status
        )

        if status_reason is not None:
            reasons.add(
                status_reason
            )

        if transition is ClaimPostureTransition.SUPPORT_LOST:
            reasons.add(
                ClaimPostureAlertReason.SUPPORT_LOST
            )

        if (
            transition
            in {
                ClaimPostureTransition.SUPPORT_LOST,
                ClaimPostureTransition.NEW_ADVERSE_SIGNAL,
            }
            and current_status.has_adverse_signal
        ):
            reasons.add(
                ClaimPostureAlertReason.NEW_ADVERSE_SIGNAL
            )

        if (
            transition
            in {
                ClaimPostureTransition.SUPPORT_LOST,
                ClaimPostureTransition.ATTENTION_OPENED,
            }
            and current_status.requires_human_attention
        ):
            reasons.add(
                ClaimPostureAlertReason.ATTENTION_OPENED
            )

        return tuple(
            sorted(
                reasons,
                key=lambda reason: reason.value,
            )
        )

    @staticmethod
    def severity_for(
        *,
        current_status: ClaimPostureStatus,
        transition: ClaimPostureTransition | None,
    ) -> ClaimPostureAlertSeverity | None:
        """Return deterministic alert severity, or None when clear."""

        if current_status is ClaimPostureStatus.FALSIFICATION_SIGNAL:
            return ClaimPostureAlertSeverity.CRITICAL

        if (
            current_status is ClaimPostureStatus.NOT_SUPPORTED
            or transition
            in {
                ClaimPostureTransition.SUPPORT_LOST,
                ClaimPostureTransition.NEW_ADVERSE_SIGNAL,
            }
        ):
            return ClaimPostureAlertSeverity.HIGH

        if current_status in {
            ClaimPostureStatus.DEFERRED,
            ClaimPostureStatus.AWAITING_ADJUDICATION,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.EVIDENCE_REVIEW_OPEN,
        }:
            return ClaimPostureAlertSeverity.MODERATE

        if current_status is ClaimPostureStatus.UNEVALUATED:
            return ClaimPostureAlertSeverity.LOW

        return None

    @property
    def requires_immediate_attention(self) -> bool:
        """Return whether this is a critical alert."""

        return self.severity.requires_immediate_attention

    @property
    def support_lost(self) -> bool:
        """Return whether this alert records loss of current support."""

        return ClaimPostureAlertReason.SUPPORT_LOST in self.reasons

    @property
    def has_adverse_signal(self) -> bool:
        """Return whether the current posture is adverse."""

        return self.current_status.has_adverse_signal

    @property
    def grants_authority(self) -> bool:
        """Return false because alerts never grant authority."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because alerts report rather than mutate posture."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic alert representation."""

        reasons: JsonArray = [
            reason.value
            for reason in self.reasons
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "alert_id": str(self.alert_id),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "current_posture_digest": (
                self.current_posture_digest.to_payload()
            ),
            "current_posture_id": str(
                self.current_posture_id
            ),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "current_status": self.current_status.value,
            "delta_digest": (
                self.delta_digest.to_payload()
                if self.delta_digest is not None
                else None
            ),
            "delta_id": (
                str(self.delta_id)
                if self.delta_id is not None
                else None
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
                if self.delta_snapshot_digest is not None
                else None
            ),
            "generated_at": self.generated_at.isoformat(),
            "grants_authority": self.grants_authority,
            "has_adverse_signal": self.has_adverse_signal,
            "reasons": reasons,
            "requires_immediate_attention": (
                self.requires_immediate_attention
            ),
            "schema": self.SCHEMA.value,
            "severity": self.severity.value,
            "support_lost": self.support_lost,
            "transition": (
                self.transition.value
                if self.transition is not None
                else None
            ),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical alert document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete claim alert."""

        return self.to_document().digest(
            domain="claim-posture-alert"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertDocket:
    """Catalog-wide immutable docket of current claim-posture alerts."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-docket-v1"
    )

    docket_id: ScopedIdentifier
    generated_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: ClaimPostureAlertDocketStatus
    current_snapshot_id: ScopedIdentifier
    delta_snapshot_id: ScopedIdentifier | None
    alerts: tuple[ClaimPostureAlert, ...]
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        alerts = tuple(
            self.alerts
        )
        self._validate_alerts(
            alerts
        )

        ordered = tuple(
            sorted(
                alerts,
                key=lambda alert: str(
                    alert.claim_id
                ),
            )
        )
        object.__setattr__(
            self,
            "alerts",
            ordered,
        )

        expected_status = self._status_for(
            ordered
        )

        if self.status is not expected_status:
            raise FoundationError(
                "claim-posture alert docket status does not match "
                "its alerts"
            )

        self._validate_delta_presence()

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.docket_id,
            field_name="docket_id",
            namespace="claim-posture-alert-docket",
        )
        _require_identifier(
            self.current_snapshot_id,
            field_name="current_snapshot_id",
            namespace="claim-posture-snapshot",
        )
        _require_optional_identifier(
            self.delta_snapshot_id,
            field_name="delta_snapshot_id",
            namespace="claim-posture-delta-snapshot",
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
        if self.producer_kind not in _ALERT_PRODUCER_KINDS:
            raise FoundationError(
                "claim-posture alert producer must be "
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
            ClaimPostureAlertDocketStatus,
        ):
            raise FoundationError(
                "status must be a ClaimPostureAlertDocketStatus"
            )

    def _validate_digests(self) -> None:
        _require_digest(
            self.current_snapshot_digest,
            field_name="current_snapshot_digest",
            domain="claim-posture-snapshot",
        )
        _require_optional_digest(
            self.delta_snapshot_digest,
            field_name="delta_snapshot_digest",
            domain="claim-posture-delta-snapshot",
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

    def _validate_alerts(
        self,
        alerts: tuple[ClaimPostureAlert, ...],
    ) -> None:
        for index, alert in enumerate(
            alerts
        ):
            if not isinstance(
                alert,
                ClaimPostureAlert,
            ):
                raise FoundationError(
                    f"alerts[{index}] must be a ClaimPostureAlert"
                )
            if alert.generated_at != self.generated_at:
                raise FoundationError(
                    "every alert must use "
                    "the docket generation time"
                )
            if (
                alert.current_snapshot_digest
                != self.current_snapshot_digest
            ):
                raise FoundationError(
                    "every alert must bind "
                    "the current posture snapshot"
                )
            if (
                alert.delta_snapshot_digest
                != self.delta_snapshot_digest
            ):
                raise FoundationError(
                    "every alert must bind "
                    "the same delta snapshot"
                )
            if (
                alert.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every alert must bind the claim catalog"
                )
            if (
                alert.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every alert must bind the actor registry"
                )

        alert_ids = tuple(
            alert.alert_id
            for alert in alerts
        )

        if len(alert_ids) != len(
            set(alert_ids)
        ):
            raise FoundationError(
                "claim-posture alert docket must contain "
                "unique alert IDs"
            )

        claim_ids = tuple(
            alert.claim_id
            for alert in alerts
        )

        if len(claim_ids) != len(
            set(claim_ids)
        ):
            raise FoundationError(
                "claim-posture alert docket must contain "
                "one alert per claim"
            )

    def _validate_delta_presence(self) -> None:
        has_delta_id = self.delta_snapshot_id is not None
        has_delta_digest = self.delta_snapshot_digest is not None

        if has_delta_id != has_delta_digest:
            raise FoundationError(
                "delta_snapshot_id and delta_snapshot_digest "
                "must be present or absent together"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        generated_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        current_snapshot: ClaimPostureSnapshot,
        actor_registry: ActorRegistry,
        delta_snapshot: ClaimPostureDeltaSnapshot | None = None,
    ) -> ClaimPostureAlertDocket:
        """Create a deterministic docket for all actionable current claims."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = _validate_alert_producer(
            producer
        )

        cls._validate_bindings(
            generated_at=generated_at,
            current_snapshot=current_snapshot,
            delta_snapshot=delta_snapshot,
            actor_registry=actor_registry,
        )

        alerts: list[ClaimPostureAlert] = []

        for current in current_snapshot.postures:
            delta = (
                delta_snapshot.require_delta(
                    current.claim_id
                )
                if delta_snapshot is not None
                else None
            )
            transition = (
                delta.transition
                if delta is not None
                else None
            )
            severity = ClaimPostureAlert.severity_for(
                current_status=current.status,
                transition=transition,
            )

            if severity is None:
                continue

            alerts.append(
                ClaimPostureAlert.create(
                    key=(
                        f"{key}-"
                        f"{str(current.claim_id)}"
                    ),
                    generated_at=generated_at,
                    current=current,
                    current_snapshot=current_snapshot,
                    delta=delta,
                    delta_snapshot=delta_snapshot,
                )
            )

        alert_tuple = tuple(
            alerts
        )

        return cls(
            docket_id=ScopedIdentifier.create(
                namespace="claim-posture-alert-docket",
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
            status=cls._status_for(
                alert_tuple
            ),
            current_snapshot_id=current_snapshot.snapshot_id,
            delta_snapshot_id=(
                delta_snapshot.snapshot_id
                if delta_snapshot is not None
                else None
            ),
            alerts=alert_tuple,
            current_snapshot_digest=current_snapshot.digest(),
            delta_snapshot_digest=(
                delta_snapshot.digest()
                if delta_snapshot is not None
                else None
            ),
            claim_catalog_digest=(
                current_snapshot.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        generated_at: UtcTimestamp,
        current_snapshot: ClaimPostureSnapshot,
        delta_snapshot: ClaimPostureDeltaSnapshot | None,
        actor_registry: ActorRegistry,
    ) -> None:
        actor_registry_digest = actor_registry.digest()

        if (
            current_snapshot.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "current posture snapshot is not bound "
                "to the supplied actor registry"
            )
        if generated_at.value < current_snapshot.captured_at.value:
            raise FoundationError(
                "claim-posture alert docket must not predate "
                "the current posture snapshot"
            )

        if delta_snapshot is None:
            return

        if generated_at.value < delta_snapshot.compared_at.value:
            raise FoundationError(
                "claim-posture alert docket must not predate "
                "the posture-delta snapshot"
            )
        if (
            delta_snapshot.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound "
                "to the supplied actor registry"
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
            delta_snapshot.current_snapshot_digest
            != current_snapshot.digest()
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound "
                "to the current posture snapshot"
            )
        if (
            delta_snapshot.claim_catalog_id
            != current_snapshot.claim_catalog_id
        ):
            raise FoundationError(
                "posture-delta snapshot references a different "
                "claim catalog"
            )
        if (
            delta_snapshot.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "posture-delta snapshot is not bound "
                "to the current claim catalog"
            )

    @staticmethod
    def _status_for(
        alerts: tuple[ClaimPostureAlert, ...],
    ) -> ClaimPostureAlertDocketStatus:
        if any(
            alert.requires_immediate_attention
            for alert in alerts
        ):
            return ClaimPostureAlertDocketStatus.CRITICAL

        if alerts:
            return ClaimPostureAlertDocketStatus.ACTION_REQUIRED

        return ClaimPostureAlertDocketStatus.CLEAR

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the docket contains active alerts."""

        return self.status.requires_human_attention

    @property
    def total_count(self) -> int:
        """Return the number of current claim alerts."""

        return len(
            self.alerts
        )

    @property
    def critical_count(self) -> int:
        """Return the number of critical claim alerts."""

        return sum(
            alert.severity
            is ClaimPostureAlertSeverity.CRITICAL
            for alert in self.alerts
        )

    @property
    def high_count(self) -> int:
        """Return the number of high-severity claim alerts."""

        return sum(
            alert.severity
            is ClaimPostureAlertSeverity.HIGH
            for alert in self.alerts
        )

    @property
    def moderate_count(self) -> int:
        """Return the number of moderate claim alerts."""

        return sum(
            alert.severity
            is ClaimPostureAlertSeverity.MODERATE
            for alert in self.alerts
        )

    @property
    def low_count(self) -> int:
        """Return the number of low-severity claim alerts."""

        return sum(
            alert.severity
            is ClaimPostureAlertSeverity.LOW
            for alert in self.alerts
        )

    @property
    def support_lost_count(self) -> int:
        """Return the number of alerts reporting lost support."""

        return sum(
            alert.support_lost
            for alert in self.alerts
        )

    @property
    def adverse_count(self) -> int:
        """Return the number of alerts with current adverse posture."""

        return sum(
            alert.has_adverse_signal
            for alert in self.alerts
        )

    @property
    def grants_authority(self) -> bool:
        """Return false because alert dockets never grant authority."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because alert dockets do not mutate claims."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def alert_for(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureAlert | None:
        """Return the current alert for one claim, when present."""

        for alert in self.alerts:
            if alert.claim_id == claim_id:
                return alert

        return None

    def require_alert(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureAlert:
        """Return a claim alert or fail when absent."""

        alert = self.alert_for(
            claim_id
        )

        if alert is None:
            raise FoundationError(
                "claim-posture alert docket does not contain "
                f"claim: {claim_id}"
            )

        return alert

    def alerts_by_severity(
        self,
        severity: ClaimPostureAlertSeverity,
    ) -> tuple[ClaimPostureAlert, ...]:
        """Return alerts at one severity level."""

        if not isinstance(
            severity,
            ClaimPostureAlertSeverity,
        ):
            raise FoundationError(
                "severity must be a ClaimPostureAlertSeverity"
            )

        return tuple(
            alert
            for alert in self.alerts
            if alert.severity is severity
        )

    def critical_alerts(
        self,
    ) -> tuple[ClaimPostureAlert, ...]:
        """Return all critical current claim alerts."""

        return self.alerts_by_severity(
            ClaimPostureAlertSeverity.CRITICAL
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic alert-docket representation."""

        alert_payloads: JsonArray = [
            alert.to_payload()
            for alert in self.alerts
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "adverse_count": self.adverse_count,
            "alerts": alert_payloads,
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "critical_count": self.critical_count,
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "current_snapshot_id": str(
                self.current_snapshot_id
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
                if self.delta_snapshot_digest is not None
                else None
            ),
            "delta_snapshot_id": (
                str(self.delta_snapshot_id)
                if self.delta_snapshot_id is not None
                else None
            ),
            "docket_id": str(self.docket_id),
            "generated_at": self.generated_at.isoformat(),
            "grants_authority": self.grants_authority,
            "high_count": self.high_count,
            "low_count": self.low_count,
            "moderate_count": self.moderate_count,
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "requires_human_attention": (
                self.requires_human_attention
            ),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "support_lost_count": self.support_lost_count,
            "total_count": self.total_count,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical alert-docket document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete alert docket."""

        return self.to_document().digest(
            domain="claim-posture-alert-docket"
        )
