"""Tests for deterministic claim-posture transition snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPosture,
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
    registry = ActorRegistry.create(
        key="claim-delta-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T08:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            posture_system,
            delta_service,
        ),
    )

    return _Runtime(
        human=human,
        posture_system=posture_system,
        delta_service=delta_service,
        registry=registry,
        claim_catalog_id=_identifier(
            "claim-catalog",
            "claim-delta-catalog",
        ),
        claim_catalog_digest=_digest(
            "claim-catalog",
            "claim-delta-catalog",
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
                "new-adverse",
            ),
            _identifier(
                "claim",
                "newly-supported",
            ),
            _identifier(
                "claim",
                "attention-cleared",
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
                "2026-07-16T08:05:00Z"
                if captured_at == "2026-07-16T08:10:00Z"
                else "2026-07-16T08:15:00Z"
            )
        ),
        current_resolved_at=UtcTimestamp.parse(
            (
                "2026-07-16T08:06:00Z"
                if captured_at == "2026-07-16T08:10:00Z"
                else "2026-07-16T08:16:00Z"
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
        key="previous-postures",
        captured_at="2026-07-16T08:10:00Z",
        history_key="previous-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.AWAITING_ADJUDICATION,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
        ),
    )
    current = _snapshot(
        runtime,
        key="current-postures",
        captured_at="2026-07-16T08:20:00Z",
        history_key="current-history",
        statuses=(
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
            ClaimPostureStatus.NOT_SUPPORTED,
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.NOT_SUPPORTED,
        ),
    )

    return previous, current


def _delta_snapshot(
    runtime: _Runtime,
    previous: ClaimPostureSnapshot,
    current: ClaimPostureSnapshot,
) -> ClaimPostureDeltaSnapshot:
    return ClaimPostureDeltaSnapshot.create(
        key="claim-posture-changes",
        compared_at=UtcTimestamp.parse(
            "2026-07-16T08:21:00Z"
        ),
        produced_by_id=runtime.delta_service.actor_id,
        previous_snapshot=previous,
        current_snapshot=current,
        actor_registry=runtime.registry,
    )


def test_snapshot_classifies_claim_posture_transitions() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    snapshot = _delta_snapshot(
        runtime,
        previous,
        current,
    )

    stable = snapshot.require_delta(
        runtime.claim_ids[0]
    )
    support_lost = snapshot.require_delta(
        runtime.claim_ids[1]
    )
    adverse = snapshot.require_delta(
        runtime.claim_ids[2]
    )
    supported = snapshot.require_delta(
        runtime.claim_ids[3]
    )
    attention_cleared = snapshot.require_delta(
        runtime.claim_ids[4]
    )

    assert stable.transition is (
        ClaimPostureTransition.UNCHANGED
    )
    assert stable.status_changed is False

    assert support_lost.transition is (
        ClaimPostureTransition.SUPPORT_LOST
    )
    assert support_lost.support_lost is True
    assert support_lost.new_adverse_signal is True
    assert support_lost.attention_opened is True

    assert adverse.transition is (
        ClaimPostureTransition.NEW_ADVERSE_SIGNAL
    )
    assert adverse.new_adverse_signal is True
    assert adverse.support_lost is False

    assert supported.transition is (
        ClaimPostureTransition.NEWLY_SUPPORTED
    )
    assert supported.newly_supported is True
    assert supported.attention_cleared is True

    assert attention_cleared.transition is (
        ClaimPostureTransition.ATTENTION_CLEARED
    )
    assert attention_cleared.attention_cleared is True


def test_snapshot_preserves_all_material_transition_counts() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    snapshot = _delta_snapshot(
        runtime,
        previous,
        current,
    )

    assert snapshot.total_count == 5
    assert snapshot.changed_count == 4
    assert snapshot.unchanged_count == 1
    assert snapshot.support_lost_count == 1
    assert snapshot.newly_supported_count == 1
    assert snapshot.new_adverse_signal_count == 2
    assert snapshot.adverse_signal_cleared_count == 0
    assert snapshot.attention_opened_count == 1
    assert snapshot.attention_cleared_count == 2
    assert snapshot.has_material_regression is True

    assert snapshot.support_lost_deltas() == (
        snapshot.require_delta(
            runtime.claim_ids[1]
        ),
    )
    assert set(
        delta.claim_id
        for delta in snapshot.new_adverse_signal_deltas()
    ) == {
        runtime.claim_ids[1],
        runtime.claim_ids[2],
    }


def test_support_loss_precedence_does_not_hide_other_flags() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    delta = _delta_snapshot(
        runtime,
        previous,
        current,
    ).require_delta(
        runtime.claim_ids[1]
    )

    assert delta.transition is (
        ClaimPostureTransition.SUPPORT_LOST
    )
    assert delta.support_lost is True
    assert delta.new_adverse_signal is True
    assert delta.attention_opened is True


def test_delta_snapshot_is_non_certifying_and_non_authorizing() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    snapshot = _delta_snapshot(
        runtime,
        previous,
        current,
    )

    assert snapshot.establishes_absolute_truth is False
    assert snapshot.grants_authority is False
    assert snapshot.claims_certification is False
    assert snapshot.digest().verifies(
        snapshot.canonical_payload()
    ) is True

    for delta in snapshot.deltas:
        assert delta.establishes_absolute_truth is False
        assert delta.grants_authority is False
        assert delta.claims_certification is False


def test_current_snapshot_must_be_strictly_newer() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    same_time = replace(
        current,
        captured_at=previous.captured_at,
        postures=tuple(
            replace(
                posture,
                captured_at=previous.captured_at,
            )
            for posture in current.postures
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must be newer",
    ):
        _delta_snapshot(
            runtime,
            previous,
            same_time,
        )


def test_snapshots_must_bind_same_claim_catalog() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    different_catalog = replace(
        current,
        claim_catalog_id=_identifier(
            "claim-catalog",
            "different-catalog",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="different claim catalogs",
    ):
        _delta_snapshot(
            runtime,
            previous,
            different_catalog,
        )


def test_snapshots_must_contain_same_claim_set() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    missing_claim = replace(
        current,
        postures=current.postures[:-1],
    )

    with pytest.raises(
        FoundationError,
        match="same catalog claim set",
    ):
        _delta_snapshot(
            runtime,
            previous,
            missing_claim,
        )


def test_comparison_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureDeltaSnapshot.create(
            key="human-produced-delta",
            compared_at=UtcTimestamp.parse(
                "2026-07-16T08:21:00Z"
            ),
            produced_by_id=runtime.human.actor_id,
            previous_snapshot=previous,
            current_snapshot=current,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-delta-service",
        display_name="Unowned Delta Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-claim-delta-actors",
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
        ClaimPostureDeltaSnapshot.create(
            key="unowned-produced-delta",
            compared_at=UtcTimestamp.parse(
                "2026-07-16T08:21:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            previous_snapshot=previous,
            current_snapshot=current,
            actor_registry=expanded_registry,
        )


def test_comparison_must_not_predate_current_snapshot() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="must not predate",
    ):
        ClaimPostureDeltaSnapshot.create(
            key="premature-comparison",
            compared_at=UtcTimestamp.parse(
                "2026-07-16T08:19:59Z"
            ),
            produced_by_id=runtime.delta_service.actor_id,
            previous_snapshot=previous,
            current_snapshot=current,
            actor_registry=runtime.registry,
        )


def test_delta_snapshot_is_deterministic_across_posture_order() -> None:
    runtime = _runtime()
    previous, current = _snapshots(
        runtime
    )
    reordered_previous = replace(
        previous,
        postures=tuple(
            reversed(previous.postures)
        ),
    )
    reordered_current = replace(
        current,
        postures=tuple(
            reversed(current.postures)
        ),
    )

    first = _delta_snapshot(
        runtime,
        previous,
        current,
    )
    second = _delta_snapshot(
        runtime,
        reordered_previous,
        reordered_current,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
