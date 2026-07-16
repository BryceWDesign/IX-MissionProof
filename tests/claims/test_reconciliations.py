"""Tests for claim-posture alert reconciliation snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPosture,
    ClaimPostureAlertDocket,
    ClaimPostureAlertReconciliationSnapshot,
    ClaimPostureAlertReconciliationSnapshotStatus,
    ClaimPostureAlertReconciliationStatus,
    ClaimPostureDeltaSnapshot,
    ClaimPostureSnapshot,
    ClaimPostureSource,
    ClaimPostureStatus,
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
    reconciliation_system: ActorIdentity
    registry: ActorRegistry
    catalog_id: ScopedIdentifier
    catalog_digest: ContentDigest
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
    reconciliation_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-alert-reconciliation-system",
        display_name="Claim Alert Reconciliation System",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-alert-reconciliation-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T12:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            posture_system,
            delta_service,
            alert_system,
            reconciliation_system,
        ),
    )

    return _Runtime(
        human=human,
        posture_system=posture_system,
        delta_service=delta_service,
        alert_system=alert_system,
        reconciliation_system=reconciliation_system,
        registry=registry,
        catalog_id=_identifier(
            "claim-catalog",
            "claim-reconciliation-catalog",
        ),
        catalog_digest=_digest(
            "claim-catalog",
            "claim-reconciliation-catalog",
        ),
        claim_ids=(
            _identifier(
                "claim",
                "restored-claim",
            ),
            _identifier(
                "claim",
                "persistent-falsification",
            ),
            _identifier(
                "claim",
                "changed-adverse-claim",
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
            claim_catalog_digest=runtime.catalog_digest,
            history_digest=_digest(
                "claim-resolution-history",
                history_key,
            ),
        )

    previous = (
        captured_at
        == "2026-07-16T12:10:00Z"
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
                "2026-07-16T12:05:00Z"
                if previous
                else "2026-07-16T12:20:00Z"
            )
        ),
        current_resolved_at=UtcTimestamp.parse(
            (
                "2026-07-16T12:06:00Z"
                if previous
                else "2026-07-16T12:21:00Z"
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
        claim_catalog_digest=runtime.catalog_digest,
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
    history_key: str,
    statuses: tuple[ClaimPostureStatus, ...],
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
        claim_catalog_id=runtime.catalog_id,
        history_id=_identifier(
            "claim-resolution-history",
            history_key,
        ),
        postures=postures,
        claim_catalog_digest=runtime.catalog_digest,
        history_digest=_digest(
            "claim-resolution-history",
            history_key,
        ),
        actor_registry_digest=runtime.registry.digest(),
    )


def _previous_snapshot(
    runtime: _Runtime,
) -> ClaimPostureSnapshot:
    return _snapshot(
        runtime,
        key="previous-reconciliation-postures",
        captured_at="2026-07-16T12:10:00Z",
        history_key="previous-reconciliation-history",
        statuses=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
        ),
    )


def _current_snapshot(
    runtime: _Runtime,
) -> ClaimPostureSnapshot:
    return _snapshot(
        runtime,
        key="current-reconciliation-postures",
        captured_at="2026-07-16T12:25:00Z",
        history_key="current-reconciliation-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.NOT_SUPPORTED,
        ),
    )


def _prior_docket(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
) -> ClaimPostureAlertDocket:
    return ClaimPostureAlertDocket.create(
        key="prior-claim-alerts",
        generated_at=UtcTimestamp.parse(
            "2026-07-16T12:11:00Z"
        ),
        produced_by_id=runtime.alert_system.actor_id,
        current_snapshot=previous,
        actor_registry=runtime.registry,
    )


def _delta_snapshot(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
    current: ClaimPostureSnapshot,
) -> ClaimPostureDeltaSnapshot:
    return ClaimPostureDeltaSnapshot.create(
        key="claim-reconciliation-deltas",
        compared_at=UtcTimestamp.parse(
            "2026-07-16T12:26:00Z"
        ),
        produced_by_id=runtime.delta_service.actor_id,
        previous_snapshot=previous,
        current_snapshot=current,
        actor_registry=runtime.registry,
    )


def _reconciliation_snapshot(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
    current: ClaimPostureSnapshot,
    docket: ClaimPostureAlertDocket,
    delta: ClaimPostureDeltaSnapshot,
) -> ClaimPostureAlertReconciliationSnapshot:
    return ClaimPostureAlertReconciliationSnapshot.create(
        key="claim-alert-reconciliation",
        reconciled_at=UtcTimestamp.parse(
            "2026-07-16T12:27:00Z"
        ),
        produced_by_id=(
            runtime.reconciliation_system.actor_id
        ),
        prior_docket=docket,
        previous_snapshot=previous,
        current_snapshot=current,
        delta_snapshot=delta,
        actor_registry=runtime.registry,
    )


def test_reconciliation_clears_alert_only_after_posture_supports_claim() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[0]
    )
    reconciliation = (
        snapshot.require_reconciliation_for_alert(
            alert.alert_id
        )
    )

    assert reconciliation.status is (
        ClaimPostureAlertReconciliationStatus.CLEARED
    )
    assert reconciliation.alert_cleared is True
    assert reconciliation.alert_remains_active is False
    assert reconciliation.cleared_by_posture_change is True
    assert reconciliation.current_severity is None
    assert reconciliation.current_reasons == ()
    assert reconciliation.response_can_clear_alert is False


def test_unchanged_falsification_alert_remains_active() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[1]
    )
    reconciliation = (
        snapshot.require_reconciliation_for_alert(
            alert.alert_id
        )
    )

    assert reconciliation.status is (
        ClaimPostureAlertReconciliationStatus
        .ACTIVE_UNCHANGED
    )
    assert reconciliation.alert_remains_active is True
    assert reconciliation.alert_cleared is False
    assert reconciliation.current_severity == alert.severity
    assert reconciliation.current_reasons == alert.reasons


def test_changed_adverse_alert_remains_active_with_new_condition() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )
    alert = docket.require_alert(
        runtime.claim_ids[2]
    )
    reconciliation = (
        snapshot.require_reconciliation_for_alert(
            alert.alert_id
        )
    )

    assert reconciliation.status is (
        ClaimPostureAlertReconciliationStatus
        .ACTIVE_CHANGED
    )
    assert reconciliation.alert_remains_active is True
    assert reconciliation.previous_status is (
        ClaimPostureStatus.INCOMPLETE_EVIDENCE
    )
    assert reconciliation.current_status is (
        ClaimPostureStatus.NOT_SUPPORTED
    )
    assert reconciliation.current_severity is not None
    assert reconciliation.current_severity.value == "high"


def test_snapshot_reports_partial_clearance_without_hiding_active_alerts() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )

    assert snapshot.status is (
        ClaimPostureAlertReconciliationSnapshotStatus
        .PARTIALLY_CLEARED
    )
    assert snapshot.total_count == 3
    assert snapshot.active_count == 2
    assert snapshot.cleared_count == 1
    assert snapshot.changed_active_count == 1
    assert snapshot.unchanged_active_count == 1
    assert snapshot.all_prior_alerts_cleared is False
    assert snapshot.has_active_alerts is True
    assert len(snapshot.active_reconciliations()) == 2
    assert len(snapshot.cleared_reconciliations()) == 1


def test_all_supported_new_posture_clears_all_prior_alerts() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _snapshot(
        runtime,
        key="all-supported-current-postures",
        captured_at="2026-07-16T12:25:00Z",
        history_key="all-supported-current-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
        ),
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )

    assert snapshot.status is (
        ClaimPostureAlertReconciliationSnapshotStatus.CLEAR
    )
    assert snapshot.active_count == 0
    assert snapshot.cleared_count == 3
    assert snapshot.all_prior_alerts_cleared is True
    assert snapshot.has_active_alerts is False


def test_unchanged_alerting_posture_keeps_snapshot_active() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _snapshot(
        runtime,
        key="all-active-current-postures",
        captured_at="2026-07-16T12:25:00Z",
        history_key="all-active-current-history",
        statuses=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
        ),
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )

    assert snapshot.status is (
        ClaimPostureAlertReconciliationSnapshotStatus.ACTIVE
    )
    assert snapshot.active_count == 3
    assert snapshot.cleared_count == 0
    assert snapshot.all_prior_alerts_cleared is False


def test_clear_prior_docket_produces_clear_empty_reconciliation() -> None:
    runtime = _runtime()
    previous = _snapshot(
        runtime,
        key="clear-previous-postures",
        captured_at="2026-07-16T12:10:00Z",
        history_key="clear-previous-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
        ),
    )
    current = _snapshot(
        runtime,
        key="clear-current-postures",
        captured_at="2026-07-16T12:25:00Z",
        history_key="clear-current-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
        ),
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )

    assert docket.alerts == ()
    assert snapshot.reconciliations == ()
    assert snapshot.status is (
        ClaimPostureAlertReconciliationSnapshotStatus.CLEAR
    )
    assert snapshot.all_prior_alerts_cleared is True


def test_reconciliation_requires_delta_from_prior_docket_snapshot() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    unrelated_previous = replace(
        previous,
        snapshot_id=_identifier(
            "claim-posture-snapshot",
            "unrelated-previous-snapshot",
        ),
    )
    unrelated_delta = _delta_snapshot(
        runtime,
        unrelated_previous,
        current,
    )

    with pytest.raises(
        FoundationError,
        match="different previous posture snapshot",
    ):
        _reconciliation_snapshot(
            runtime,
            previous,
            current,
            docket,
            unrelated_delta,
        )


def test_reconciliation_requires_posture_captured_after_docket() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    current = _snapshot(
        runtime,
        key="premature-current-postures",
        captured_at="2026-07-16T12:10:30Z",
        history_key="premature-current-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.NOT_SUPPORTED,
        ),
    )
    delta = ClaimPostureDeltaSnapshot.create(
        key="premature-reconciliation-deltas",
        compared_at=UtcTimestamp.parse(
            "2026-07-16T12:12:00Z"
        ),
        produced_by_id=runtime.delta_service.actor_id,
        previous_snapshot=previous,
        current_snapshot=current,
        actor_registry=runtime.registry,
    )

    with pytest.raises(
        FoundationError,
        match="captured after the prior alert docket",
    ):
        _reconciliation_snapshot(
            runtime,
            previous,
            current,
            docket,
            delta,
        )


def test_reconciliation_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    delta = _delta_snapshot(
        runtime,
        previous,
        current,
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertReconciliationSnapshot.create(
            key="human-produced-reconciliation",
            reconciled_at=UtcTimestamp.parse(
                "2026-07-16T12:27:00Z"
            ),
            produced_by_id=runtime.human.actor_id,
            prior_docket=docket,
            previous_snapshot=previous,
            current_snapshot=current,
            delta_snapshot=delta,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-reconciliation-service",
        display_name="Unowned Reconciliation Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-reconciliation-actors",
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
        ClaimPostureAlertReconciliationSnapshot.create(
            key="unowned-produced-reconciliation",
            reconciled_at=UtcTimestamp.parse(
                "2026-07-16T12:27:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            prior_docket=docket,
            previous_snapshot=previous,
            current_snapshot=current,
            delta_snapshot=delta,
            actor_registry=expanded_registry,
        )


def test_reconciliation_is_reporting_only() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
    )
    snapshot = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        _delta_snapshot(
            runtime,
            previous,
            current,
        ),
    )

    assert snapshot.response_can_clear_alerts is False
    assert snapshot.changes_claim_state is False
    assert snapshot.grants_authority is False
    assert snapshot.claims_certification is False
    assert snapshot.digest().verifies(
        snapshot.canonical_payload()
    ) is True

    for reconciliation in snapshot.reconciliations:
        assert reconciliation.response_can_clear_alert is False
        assert reconciliation.changes_claim_state is False
        assert reconciliation.grants_authority is False
        assert reconciliation.claims_certification is False


def test_reconciliation_is_deterministic_across_posture_order() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    docket = _prior_docket(
        runtime,
        previous,
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

    first = _reconciliation_snapshot(
        runtime,
        previous,
        current,
        docket,
        first_delta,
    )
    second = _reconciliation_snapshot(
        runtime,
        reordered_previous,
        reordered_current,
        docket,
        second_delta,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
