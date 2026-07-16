"""Tests for claim-alert lifecycle continuity snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPosture,
    ClaimPostureAlertDocket,
    ClaimPostureAlertLifecycleSnapshot,
    ClaimPostureAlertLifecycleSnapshotStatus,
    ClaimPostureAlertLifecycleStatus,
    ClaimPostureAlertReconciliationSnapshot,
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
    lifecycle_service: ActorIdentity
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
        key="claim-reconciliation-system",
        display_name="Claim Reconciliation System",
        accountability_owner_id=human.actor_id,
    )
    lifecycle_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-alert-lifecycle-service",
        display_name="Claim Alert Lifecycle Service",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-alert-lifecycle-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T13:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            posture_system,
            delta_service,
            alert_system,
            reconciliation_system,
            lifecycle_service,
        ),
    )

    return _Runtime(
        human=human,
        posture_system=posture_system,
        delta_service=delta_service,
        alert_system=alert_system,
        reconciliation_system=reconciliation_system,
        lifecycle_service=lifecycle_service,
        registry=registry,
        catalog_id=_identifier(
            "claim-catalog",
            "claim-alert-lifecycle-catalog",
        ),
        catalog_digest=_digest(
            "claim-catalog",
            "claim-alert-lifecycle-catalog",
        ),
        claim_ids=(
            _identifier(
                "claim",
                "cleared-alert",
            ),
            _identifier(
                "claim",
                "retained-changed-alert",
            ),
            _identifier(
                "claim",
                "retained-unchanged-alert",
            ),
            _identifier(
                "claim",
                "new-alert",
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
        == "2026-07-16T13:10:00Z"
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
                "2026-07-16T13:05:00Z"
                if previous
                else "2026-07-16T13:20:00Z"
            )
        ),
        current_resolved_at=UtcTimestamp.parse(
            (
                "2026-07-16T13:06:00Z"
                if previous
                else "2026-07-16T13:21:00Z"
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
        key="previous-lifecycle-postures",
        captured_at="2026-07-16T13:10:00Z",
        history_key="previous-lifecycle-history",
        statuses=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.SUPPORTED,
        ),
    )


def _current_snapshot(
    runtime: _Runtime,
) -> ClaimPostureSnapshot:
    return _snapshot(
        runtime,
        key="current-lifecycle-postures",
        captured_at="2026-07-16T13:25:00Z",
        history_key="current-lifecycle-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
        ),
    )


def _delta_snapshot(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
    current: ClaimPostureSnapshot,
) -> ClaimPostureDeltaSnapshot:
    return ClaimPostureDeltaSnapshot.create(
        key="claim-alert-lifecycle-deltas",
        compared_at=UtcTimestamp.parse(
            "2026-07-16T13:26:00Z"
        ),
        produced_by_id=runtime.delta_service.actor_id,
        previous_snapshot=previous,
        current_snapshot=current,
        actor_registry=runtime.registry,
    )


def _prior_docket(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
) -> ClaimPostureAlertDocket:
    return ClaimPostureAlertDocket.create(
        key="prior-claim-alert-docket",
        generated_at=UtcTimestamp.parse(
            "2026-07-16T13:11:00Z"
        ),
        produced_by_id=runtime.alert_system.actor_id,
        current_snapshot=previous,
        actor_registry=runtime.registry,
    )


def _reconciliation(
    runtime: _Runtime,
    prior_docket: ClaimPostureAlertDocket,
    previous: ClaimPostureSnapshot,
    current: ClaimPostureSnapshot,
    delta: ClaimPostureDeltaSnapshot,
) -> ClaimPostureAlertReconciliationSnapshot:
    return ClaimPostureAlertReconciliationSnapshot.create(
        key="claim-alert-lifecycle-reconciliation",
        reconciled_at=UtcTimestamp.parse(
            "2026-07-16T13:27:00Z"
        ),
        produced_by_id=(
            runtime.reconciliation_system.actor_id
        ),
        prior_docket=prior_docket,
        previous_snapshot=previous,
        current_snapshot=current,
        delta_snapshot=delta,
        actor_registry=runtime.registry,
    )


def _current_docket(
    runtime: _Runtime,
    current: ClaimPostureSnapshot,
    delta: ClaimPostureDeltaSnapshot,
) -> ClaimPostureAlertDocket:
    return ClaimPostureAlertDocket.create(
        key="current-claim-alert-docket",
        generated_at=UtcTimestamp.parse(
            "2026-07-16T13:28:00Z"
        ),
        produced_by_id=runtime.alert_system.actor_id,
        current_snapshot=current,
        delta_snapshot=delta,
        actor_registry=runtime.registry,
    )


def _lifecycle_snapshot(
    runtime: _Runtime,
    prior_docket: ClaimPostureAlertDocket,
    current_docket: ClaimPostureAlertDocket,
    reconciliation: ClaimPostureAlertReconciliationSnapshot,
    delta: ClaimPostureDeltaSnapshot,
) -> ClaimPostureAlertLifecycleSnapshot:
    return ClaimPostureAlertLifecycleSnapshot.create(
        key="claim-alert-lifecycle",
        compared_at=UtcTimestamp.parse(
            "2026-07-16T13:29:00Z"
        ),
        produced_by_id=runtime.lifecycle_service.actor_id,
        prior_docket=prior_docket,
        current_docket=current_docket,
        reconciliation_snapshot=reconciliation,
        delta_snapshot=delta,
        actor_registry=runtime.registry,
    )


def _complete_runtime(
    runtime: _Runtime,
) -> tuple[
    ClaimPostureAlertDocket,
    ClaimPostureAlertDocket,
    ClaimPostureAlertReconciliationSnapshot,
    ClaimPostureDeltaSnapshot,
]:
    previous = _previous_snapshot(
        runtime
    )
    current = _current_snapshot(
        runtime
    )
    delta = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    prior_docket = _prior_docket(
        runtime,
        previous,
    )
    reconciliation = _reconciliation(
        runtime,
        prior_docket,
        previous,
        current,
        delta,
    )
    current_docket = _current_docket(
        runtime,
        current,
        delta,
    )

    return (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )


def test_lifecycle_accounts_for_cleared_retained_and_new_alerts() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    snapshot = _lifecycle_snapshot(
        runtime,
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )

    cleared = snapshot.require_lifecycle_for_claim(
        runtime.claim_ids[0]
    )
    retained_changed = snapshot.require_lifecycle_for_claim(
        runtime.claim_ids[1]
    )
    retained_unchanged = (
        snapshot.require_lifecycle_for_claim(
            runtime.claim_ids[2]
        )
    )
    new = snapshot.require_lifecycle_for_claim(
        runtime.claim_ids[3]
    )

    assert cleared.status is (
        ClaimPostureAlertLifecycleStatus.CLEARED
    )
    assert cleared.alert_was_cleared is True
    assert cleared.current_alert_id is None

    assert retained_changed.status is (
        ClaimPostureAlertLifecycleStatus.RETAINED_CHANGED
    )
    assert retained_changed.alert_was_retained is True
    assert retained_changed.alert_is_active is True

    assert retained_unchanged.status is (
        ClaimPostureAlertLifecycleStatus
        .RETAINED_UNCHANGED
    )
    assert retained_unchanged.alert_was_retained is True

    assert new.status is ClaimPostureAlertLifecycleStatus.NEW
    assert new.alert_is_new is True
    assert new.previous_alert_id is None
    assert new.reconciliation_id is None


def test_lifecycle_snapshot_counts_complete_alert_continuity() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    snapshot = _lifecycle_snapshot(
        runtime,
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )

    assert snapshot.status is (
        ClaimPostureAlertLifecycleSnapshotStatus.CHANGED
    )
    assert snapshot.total_count == 4
    assert snapshot.active_count == 3
    assert snapshot.retained_count == 2
    assert snapshot.retained_unchanged_count == 1
    assert snapshot.retained_changed_count == 1
    assert snapshot.cleared_count == 1
    assert snapshot.new_count == 1
    assert snapshot.all_prior_alerts_accounted_for is True
    assert snapshot.silent_drop_count == 0
    assert snapshot.has_active_alerts is True


def test_cleared_alert_requires_reconciliation_and_no_current_alert() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    cleared_claim_id = runtime.claim_ids[0]
    unexpected_alert = replace(
        prior_docket.require_alert(
            cleared_claim_id
        ),
        alert_id=_identifier(
            "claim-posture-alert",
            "unexpected-current-alert",
        ),
        generated_at=current_docket.generated_at,
        current_posture_id=(
            delta.require_delta(
                cleared_claim_id
            ).current_posture_id
        ),
        current_posture_digest=(
            delta.require_delta(
                cleared_claim_id
            ).current_posture_digest
        ),
        current_snapshot_digest=(
            current_docket.current_snapshot_digest
        ),
        delta_snapshot_digest=delta.digest(),
        delta_id=(
            delta.require_delta(
                cleared_claim_id
            ).delta_id
        ),
        delta_digest=(
            delta.require_delta(
                cleared_claim_id
            ).digest()
        ),
        transition=(
            delta.require_delta(
                cleared_claim_id
            ).transition
        ),
        current_status=(
            delta.require_delta(
                cleared_claim_id
            ).current_status
        ),
    )
    malformed_current = replace(
        current_docket,
        alerts=(
            *current_docket.alerts,
            unexpected_alert,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="cleared reconciliation must not have",
    ):
        _lifecycle_snapshot(
            runtime,
            prior_docket,
            malformed_current,
            reconciliation,
            delta,
        )


def test_prior_alert_cannot_disappear_without_reconciliation() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    incomplete_reconciliation = replace(
        reconciliation,
        reconciliations=(
            reconciliation.reconciliations[:-1]
        ),
    )

    with pytest.raises(
        FoundationError,
        match="account for every prior alert exactly once",
    ):
        _lifecycle_snapshot(
            runtime,
            prior_docket,
            current_docket,
            incomplete_reconciliation,
            delta,
        )


def test_current_docket_must_bind_reconciled_posture_snapshot() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    different_current = replace(
        current_docket,
        current_snapshot_id=_identifier(
            "claim-posture-snapshot",
            "different-current-posture-snapshot",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="different current posture snapshot",
    ):
        _lifecycle_snapshot(
            runtime,
            prior_docket,
            different_current,
            reconciliation,
            delta,
        )


def test_lifecycle_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertLifecycleSnapshot.create(
            key="human-produced-lifecycle",
            compared_at=UtcTimestamp.parse(
                "2026-07-16T13:29:00Z"
            ),
            produced_by_id=runtime.human.actor_id,
            prior_docket=prior_docket,
            current_docket=current_docket,
            reconciliation_snapshot=reconciliation,
            delta_snapshot=delta,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-lifecycle-service",
        display_name="Unowned Lifecycle Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-lifecycle-actors",
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
        ClaimPostureAlertLifecycleSnapshot.create(
            key="unowned-produced-lifecycle",
            compared_at=UtcTimestamp.parse(
                "2026-07-16T13:29:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            prior_docket=prior_docket,
            current_docket=current_docket,
            reconciliation_snapshot=reconciliation,
            delta_snapshot=delta,
            actor_registry=expanded_registry,
        )


def test_all_cleared_current_docket_produces_clear_lifecycle() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _snapshot(
        runtime,
        key="all-cleared-current-postures",
        captured_at="2026-07-16T13:25:00Z",
        history_key="all-cleared-current-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
        ),
    )
    delta = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    prior_docket = _prior_docket(
        runtime,
        previous,
    )
    reconciliation = _reconciliation(
        runtime,
        prior_docket,
        previous,
        current,
        delta,
    )
    current_docket = _current_docket(
        runtime,
        current,
        delta,
    )
    snapshot = _lifecycle_snapshot(
        runtime,
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )

    assert current_docket.alerts == ()
    assert snapshot.status is (
        ClaimPostureAlertLifecycleSnapshotStatus.CLEAR
    )
    assert snapshot.active_count == 0
    assert snapshot.cleared_count == 3
    assert snapshot.new_count == 0
    assert snapshot.has_active_alerts is False


def test_unchanged_alert_docket_produces_active_unchanged_status() -> None:
    runtime = _runtime()
    previous = _previous_snapshot(
        runtime
    )
    current = _snapshot(
        runtime,
        key="unchanged-current-postures",
        captured_at="2026-07-16T13:25:00Z",
        history_key="unchanged-current-history",
        statuses=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.SUPPORTED,
        ),
    )
    delta = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    prior_docket = _prior_docket(
        runtime,
        previous,
    )
    reconciliation = _reconciliation(
        runtime,
        prior_docket,
        previous,
        current,
        delta,
    )
    current_docket = _current_docket(
        runtime,
        current,
        delta,
    )
    snapshot = _lifecycle_snapshot(
        runtime,
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )

    assert snapshot.status is (
        ClaimPostureAlertLifecycleSnapshotStatus
        .ACTIVE_UNCHANGED
    )
    assert snapshot.active_count == 3
    assert snapshot.retained_unchanged_count == 3
    assert snapshot.cleared_count == 0
    assert snapshot.new_count == 0


def test_lifecycle_snapshot_is_reporting_only() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    snapshot = _lifecycle_snapshot(
        runtime,
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )

    assert snapshot.response_can_clear_alerts is False
    assert snapshot.changes_claim_state is False
    assert snapshot.grants_authority is False
    assert snapshot.claims_certification is False
    assert snapshot.digest().verifies(
        snapshot.canonical_payload()
    ) is True

    for lifecycle in snapshot.lifecycles:
        assert (
            lifecycle.disappeared_without_reconciliation
            is False
        )
        assert lifecycle.response_can_clear_alert is False
        assert lifecycle.changes_claim_state is False
        assert lifecycle.grants_authority is False
        assert lifecycle.claims_certification is False


def test_lifecycle_snapshot_is_deterministic() -> None:
    runtime = _runtime()
    (
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    ) = _complete_runtime(
        runtime
    )
    reordered_prior = replace(
        prior_docket,
        alerts=tuple(
            reversed(
                prior_docket.alerts
            )
        ),
    )
    reordered_current = replace(
        current_docket,
        alerts=tuple(
            reversed(
                current_docket.alerts
            )
        ),
    )
    reordered_reconciliation = replace(
        reconciliation,
        reconciliations=tuple(
            reversed(
                reconciliation.reconciliations
            )
        ),
    )

    first = _lifecycle_snapshot(
        runtime,
        prior_docket,
        current_docket,
        reconciliation,
        delta,
    )
    second = _lifecycle_snapshot(
        runtime,
        reordered_prior,
        reordered_current,
        reordered_reconciliation,
        delta,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
