"""Tests for immutable claim-posture alerts and attention dockets."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPosture,
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertDocketStatus,
    ClaimPostureAlertReason,
    ClaimPostureAlertSeverity,
    ClaimPostureDeltaSnapshot,
    ClaimPostureSnapshot,
    ClaimPostureSource,
    ClaimPostureStatus,
    ClaimPostureTransition,
)
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    ContentDigest,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _identifier(
    namespace: str,
    key: str,
) -> ScopedIdentifier:
    return ScopedIdentifier.create(
        namespace=namespace,
        key=key,
    )


def _digest(
    domain: str,
    key: str,
) -> ContentDigest:
    return ContentDigest.from_payload(
        {
            "key": key,
        },
        domain=domain,
    )


@dataclass(frozen=True, slots=True)
class _Runtime:
    human: ActorIdentity
    posture_system: ActorIdentity
    delta_service: ActorIdentity
    alert_system: ActorIdentity
    registry: ActorRegistry
    claim_catalog_id: ScopedIdentifier
    claim_catalog_digest: ContentDigest
    claim_ids: tuple[ScopedIdentifier, ...]


def _runtime() -> _Runtime:
    human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="claim-reviewer",
        display_name="Claim Reviewer",
    )
    posture_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-posture-system",
        display_name="Claim Posture System",
        accountability_owner_id=human.actor_id,
    )
    delta_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-delta-service",
        display_name="Claim Delta Service",
        accountability_owner_id=human.actor_id,
    )
    alert_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-alert-system",
        display_name="Claim Alert System",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-alert-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T09:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            posture_system,
            delta_service,
            alert_system,
        ),
    )

    return _Runtime(
        human=human,
        posture_system=posture_system,
        delta_service=delta_service,
        alert_system=alert_system,
        registry=registry,
        claim_catalog_id=_identifier(
            "claim-catalog",
            "claim-alert-catalog",
        ),
        claim_catalog_digest=_digest(
            "claim-catalog",
            "claim-alert-catalog",
        ),
        claim_ids=(
            _identifier(
                "claim",
                "stable-supported",
            ),
            _identifier(
                "claim",
                "support-lost",
            ),
            _identifier(
                "claim",
                "falsification",
            ),
            _identifier(
                "claim",
                "not-supported",
            ),
            _identifier(
                "claim",
                "unevaluated",
            ),
        ),
    )


def _posture(
    runtime: _Runtime,
    *,
    claim_id: ScopedIdentifier,
    key: str,
    captured_at: str,
    status: ClaimPostureStatus,
    history_key: str,
) -> ClaimPosture:
    captured = UtcTimestamp.parse(
        captured_at
    )

    if status is ClaimPostureStatus.UNEVALUATED:
        return ClaimPosture(
            posture_id=_identifier(
                "claim-posture",
                key,
            ),
            captured_at=captured,
            claim_id=claim_id,
            status=status,
            source=ClaimPostureSource.NO_RESOLUTION,
            current_history_entry_id=None,
            current_evaluation_id=None,
            current_resolution_id=None,
            current_evaluated_at=None,
            current_resolved_at=None,
            claim_digest=_digest(
                "claim-specification",
                str(claim_id),
            ),
            current_history_entry_digest=None,
            claim_catalog_digest=runtime.claim_catalog_digest,
            history_digest=_digest(
                "claim-resolution-history",
                history_key,
            ),
        )

    old_snapshot = (
        captured_at
        == "2026-07-16T09:10:00Z"
    )

    return ClaimPosture(
        posture_id=_identifier(
            "claim-posture",
            key,
        ),
        captured_at=captured,
        claim_id=claim_id,
        status=status,
        source=ClaimPostureSource.RESOLUTION_HISTORY,
        current_history_entry_id=_identifier(
            "claim-resolution-history-entry",
            f"{key}-history-entry",
        ),
        current_evaluation_id=_identifier(
            "claim-evidence-evaluation",
            f"{key}-evaluation",
        ),
        current_resolution_id=_identifier(
            "claim-resolution",
            f"{key}-resolution",
        ),
        current_evaluated_at=UtcTimestamp.parse(
            (
                "2026-07-16T09:05:00Z"
                if old_snapshot
                else "2026-07-16T09:15:00Z"
            )
        ),
        current_resolved_at=UtcTimestamp.parse(
            (
                "2026-07-16T09:06:00Z"
                if old_snapshot
                else "2026-07-16T09:16:00Z"
            )
        ),
        claim_digest=_digest(
            "claim-specification",
            str(claim_id),
        ),
        current_history_entry_digest=_digest(
            "claim-resolution-history-entry",
            f"{key}-history-entry",
        ),
        claim_catalog_digest=runtime.claim_catalog_digest,
        history_digest=_digest(
            "claim-resolution-history",
            history_key,
        ),
    )


def _snapshot(
    runtime: _Runtime,
    *,
    key: str,
    captured_at: str,
    statuses: tuple[ClaimPostureStatus, ...],
    history_key: str,
) -> ClaimPostureSnapshot:
    postures = tuple(
        _posture(
            runtime,
            claim_id=claim_id,
            key=(
                f"{key}-"
                f"{str(claim_id)}"
            ),
            captured_at=captured_at,
            status=status,
            history_key=history_key,
        )
        for claim_id, status in zip(
            runtime.claim_ids,
            statuses,
            strict=True,
        )
    )

    return ClaimPostureSnapshot(
        snapshot_id=_identifier(
            "claim-posture-snapshot",
            key,
        ),
        captured_at=UtcTimestamp.parse(
            captured_at
        ),
        produced_by_id=runtime.posture_system.actor_id,
        producer_kind=runtime.posture_system.kind,
        producer_accountability_owner_id=runtime.human.actor_id,
        claim_catalog_id=runtime.claim_catalog_id,
        history_id=_identifier(
            "claim-resolution-history",
            history_key,
        ),
        postures=postures,
        claim_catalog_digest=runtime.claim_catalog_digest,
        history_digest=_digest(
            "claim-resolution-history",
            history_key,
        ),
        actor_registry_digest=runtime.registry.digest(),
    )


def _snapshots(
    runtime: _Runtime,
) -> tuple[
    ClaimPostureSnapshot,
    ClaimPostureSnapshot,
]:
    previous = _snapshot(
        runtime,
        key="previous-claim-alert-postures",
        captured_at="2026-07-16T09:10:00Z",
        history_key="previous-claim-alert-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.AWAITING_ADJUDICATION,
            ClaimPostureStatus.UNEVALUATED,
        ),
    )
    current = _snapshot(
        runtime,
        key="current-claim-alert-postures",
        captured_at="2026-07-16T09:20:00Z",
        history_key="current-claim-alert-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.NOT_SUPPORTED,
            ClaimPostureStatus.UNEVALUATED,
        ),
    )

    return previous, current


def _delta_snapshot(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
    current: ClaimPostureSnapshot,
) -> ClaimPostureDeltaSnapshot:
    return ClaimPostureDeltaSnapshot.create(
        key="claim-alert-deltas",
        compared_at=UtcTimestamp.parse(
            "2026-07-16T09:21:00Z"
        ),
        produced_by_id=runtime.delta_service.actor_id,
        previous_snapshot=previous,
        current_snapshot=current,
        actor_registry=runtime.registry,
    )


def _docket(
    runtime: _Runtime,
    current: ClaimPostureSnapshot,
    *,
    delta_snapshot: ClaimPostureDeltaSnapshot | None,
) -> ClaimPostureAlertDocket:
    return ClaimPostureAlertDocket.create(
        key="current-claim-alerts",
        generated_at=UtcTimestamp.parse(
            "2026-07-16T09:22:00Z"
        ),
        produced_by_id=runtime.alert_system.actor_id,
        current_snapshot=current,
        delta_snapshot=delta_snapshot,
        actor_registry=runtime.registry,
    )


def test_docket_captures_current_risk_and_material_transitions() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    delta_snapshot = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=delta_snapshot,
    )

    assert docket.status is (
        ClaimPostureAlertDocketStatus.CRITICAL
    )
    assert docket.requires_human_attention is True
    assert docket.total_count == 4
    assert docket.critical_count == 1
    assert docket.high_count == 2
    assert docket.moderate_count == 0
    assert docket.low_count == 1
    assert docket.support_lost_count == 1
    assert docket.adverse_count == 2

    assert docket.alert_for(
        runtime.claim_ids[0]
    ) is None


def test_support_loss_is_high_severity_and_preserves_attention_flags() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=_delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[1]
    )

    assert alert.severity is ClaimPostureAlertSeverity.HIGH
    assert alert.transition is ClaimPostureTransition.SUPPORT_LOST
    assert set(alert.reasons) == {
        ClaimPostureAlertReason.ATTENTION_OPENED,
        ClaimPostureAlertReason.CURRENT_INCOMPLETE_EVIDENCE,
        ClaimPostureAlertReason.SUPPORT_LOST,
    }
    assert alert.support_lost is True
    assert alert.has_adverse_signal is False
    assert alert.requires_immediate_attention is False


def test_falsification_alert_is_critical_and_cites_new_adverse_signal() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=_delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[2]
    )

    assert alert.severity is (
        ClaimPostureAlertSeverity.CRITICAL
    )
    assert alert.transition is (
        ClaimPostureTransition.NEW_ADVERSE_SIGNAL
    )
    assert set(alert.reasons) == {
        ClaimPostureAlertReason
        .CURRENT_FALSIFICATION_SIGNAL,
        ClaimPostureAlertReason.NEW_ADVERSE_SIGNAL,
    }
    assert alert.has_adverse_signal is True
    assert alert.requires_immediate_attention is True


def test_not_supported_posture_remains_alerted_after_attention_closes() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=_delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[3]
    )

    assert alert.severity is ClaimPostureAlertSeverity.HIGH
    assert alert.current_status is ClaimPostureStatus.NOT_SUPPORTED
    assert alert.has_adverse_signal is True
    assert alert.reasons == (
        ClaimPostureAlertReason.CURRENT_NOT_SUPPORTED,
        ClaimPostureAlertReason.NEW_ADVERSE_SIGNAL,
    )


def test_unchanged_adverse_posture_remains_on_current_docket() -> None:
    runtime = _runtime()
    previous = _snapshot(
        runtime,
        key="unchanged-adverse-previous",
        captured_at="2026-07-16T09:10:00Z",
        history_key="unchanged-adverse-history-one",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.NOT_SUPPORTED,
            ClaimPostureStatus.UNEVALUATED,
        ),
    )
    current = _snapshot(
        runtime,
        key="unchanged-adverse-current",
        captured_at="2026-07-16T09:20:00Z",
        history_key="unchanged-adverse-history-two",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.NOT_SUPPORTED,
            ClaimPostureStatus.UNEVALUATED,
        ),
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=_delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[2]
    )

    assert alert.transition is ClaimPostureTransition.UNCHANGED
    assert alert.reasons == (
        ClaimPostureAlertReason
        .CURRENT_FALSIFICATION_SIGNAL,
    )
    assert alert.severity is (
        ClaimPostureAlertSeverity.CRITICAL
    )


def test_docket_without_delta_still_surfaces_current_attention() -> None:
    runtime = _runtime()
    _, current = _snapshots(
        runtime
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=None,
    )

    assert docket.total_count == 4
    assert docket.delta_snapshot_id is None
    assert docket.delta_snapshot_digest is None

    alert = docket.require_alert(
        runtime.claim_ids[1]
    )
    assert alert.transition is None
    assert alert.delta_id is None
    assert alert.reasons == (
        ClaimPostureAlertReason
        .CURRENT_INCOMPLETE_EVIDENCE,
    )


def test_all_supported_snapshot_produces_clear_empty_docket() -> None:
    runtime = _runtime()
    current = _snapshot(
        runtime,
        key="all-supported-postures",
        captured_at="2026-07-16T09:20:00Z",
        history_key="all-supported-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
        ),
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=None,
    )

    assert docket.status is (
        ClaimPostureAlertDocketStatus.CLEAR
    )
    assert docket.requires_human_attention is False
    assert docket.total_count == 0
    assert docket.alerts == ()


def test_alert_creation_rejects_supported_clear_posture() -> None:
    runtime = _runtime()
    _, current = _snapshots(
        runtime
    )
    posture = current.require_posture(
        runtime.claim_ids[0]
    )

    with pytest.raises(
        FoundationError,
        match="does not require an alert",
    ):
        ClaimPostureAlert.create(
            key="clear-posture-alert",
            generated_at=UtcTimestamp.parse(
                "2026-07-16T09:22:00Z"
            ),
            current=posture,
            current_snapshot=current,
        )


def test_docket_rejects_delta_bound_to_different_current_snapshot() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    delta_snapshot = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    different_current = replace(
        current,
        snapshot_id=_identifier(
            "claim-posture-snapshot",
            "different-current-snapshot",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="different current posture snapshot",
    ):
        _docket(
            runtime,
            different_current,
            delta_snapshot=delta_snapshot,
        )


def test_docket_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    _, current = _snapshots(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertDocket.create(
            key="human-produced-alert-docket",
            generated_at=UtcTimestamp.parse(
                "2026-07-16T09:22:00Z"
            ),
            produced_by_id=runtime.human.actor_id,
            current_snapshot=current,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-alert-service",
        display_name="Unowned Alert Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-claim-alert-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.human.actor_id,
        actors=(
            *runtime.registry.actors,
            unowned_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must identify an accountable human owner",
    ):
        ClaimPostureAlertDocket.create(
            key="unowned-produced-alert-docket",
            generated_at=UtcTimestamp.parse(
                "2026-07-16T09:22:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            current_snapshot=current,
            actor_registry=expanded_registry,
        )


def test_alert_docket_is_reporting_only() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    docket = _docket(
        runtime,
        current,
        delta_snapshot=_delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )

    assert docket.grants_authority is False
    assert docket.changes_claim_state is False
    assert docket.claims_certification is False
    assert docket.digest().verifies(
        docket.canonical_payload()
    ) is True

    for alert in docket.alerts:
        assert alert.grants_authority is False
        assert alert.changes_claim_state is False
        assert alert.claims_certification is False


def test_alert_docket_is_deterministic_across_posture_order() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    first_delta = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    reordered_previous = replace(
        previous,
        postures=tuple(
            reversed(
                previous.postures
            )
        ),
    )
    reordered_current = replace(
        current,
        postures=tuple(
            reversed(
                current.postures
            )
        ),
    )
    second_delta = _delta_snapshot(
        runtime,
        reordered_previous,
        reordered_current,
    )

    first = _docket(
        runtime,
        current,
        delta_snapshot=first_delta,
    )
    second = _docket(
        runtime,
        reordered_current,
        delta_snapshot=second_delta,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
