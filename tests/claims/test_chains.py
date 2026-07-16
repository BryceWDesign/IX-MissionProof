"""Tests for chained claim-alert lifecycle generations."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlertLifecycle,
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
    ClaimPostureAlertLifecycleChainStatus,
    ClaimPostureAlertLifecycleSnapshot,
    ClaimPostureAlertLifecycleSnapshotStatus,
    ClaimPostureAlertLifecycleStatus,
    ClaimPostureAlertReconciliationStatus,
    ClaimPostureAlertSeverity,
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
    owner: ActorIdentity
    lifecycle_service: ActorIdentity
    chain_system: ActorIdentity
    registry: ActorRegistry
    claim_catalog_digest: ContentDigest
    first_claim_id: ScopedIdentifier
    second_claim_id: ScopedIdentifier


def _runtime() -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="claim-chain-owner",
        display_name="Claim Chain Owner",
    )
    lifecycle_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-lifecycle-service",
        display_name="Claim Lifecycle Service",
        accountability_owner_id=owner.actor_id,
    )
    chain_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-lifecycle-chain-system",
        display_name="Claim Lifecycle Chain System",
        accountability_owner_id=owner.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-lifecycle-chain-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T14:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            lifecycle_service,
            chain_system,
        ),
    )

    return _Runtime(
        owner=owner,
        lifecycle_service=lifecycle_service,
        chain_system=chain_system,
        registry=registry,
        claim_catalog_digest=_digest(
            "claim-catalog",
            "claim-lifecycle-chain-catalog",
        ),
        first_claim_id=_identifier(
            "claim",
            "first-alerted-claim",
        ),
        second_claim_id=_identifier(
            "claim",
            "second-alerted-claim",
        ),
    )


def _new_lifecycle(
    runtime: _Runtime,
    *,
    key: str,
    compared_at: str,
    claim_id: ScopedIdentifier,
    prior_docket_digest: ContentDigest,
    current_docket_digest: ContentDigest,
    reconciliation_snapshot_digest: ContentDigest,
    delta_snapshot_digest: ContentDigest,
) -> ClaimPostureAlertLifecycle:
    return ClaimPostureAlertLifecycle(
        lifecycle_id=_identifier(
            "claim-posture-alert-lifecycle",
            key,
        ),
        compared_at=UtcTimestamp.parse(
            compared_at
        ),
        claim_id=claim_id,
        status=ClaimPostureAlertLifecycleStatus.NEW,
        transition=ClaimPostureTransition.ATTENTION_OPENED,
        previous_posture_status=ClaimPostureStatus.SUPPORTED,
        current_posture_status=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE
        ),
        previous_alert_id=None,
        current_alert_id=_identifier(
            "claim-posture-alert",
            f"{key}-current-alert",
        ),
        reconciliation_id=None,
        delta_id=_identifier(
            "claim-posture-delta",
            f"{key}-delta",
        ),
        previous_severity=None,
        current_severity=ClaimPostureAlertSeverity.MODERATE,
        reconciliation_status=None,
        previous_alert_digest=None,
        current_alert_digest=_digest(
            "claim-posture-alert",
            f"{key}-current-alert",
        ),
        reconciliation_digest=None,
        delta_digest=_digest(
            "claim-posture-delta",
            f"{key}-delta",
        ),
        prior_docket_digest=prior_docket_digest,
        current_docket_digest=current_docket_digest,
        reconciliation_snapshot_digest=(
            reconciliation_snapshot_digest
        ),
        delta_snapshot_digest=delta_snapshot_digest,
        claim_catalog_digest=runtime.claim_catalog_digest,
        actor_registry_digest=runtime.registry.digest(),
    )


def _cleared_lifecycle(
    runtime: _Runtime,
    *,
    key: str,
    compared_at: str,
    claim_id: ScopedIdentifier,
    prior_docket_digest: ContentDigest,
    current_docket_digest: ContentDigest,
    reconciliation_snapshot_digest: ContentDigest,
    delta_snapshot_digest: ContentDigest,
) -> ClaimPostureAlertLifecycle:
    return ClaimPostureAlertLifecycle(
        lifecycle_id=_identifier(
            "claim-posture-alert-lifecycle",
            key,
        ),
        compared_at=UtcTimestamp.parse(
            compared_at
        ),
        claim_id=claim_id,
        status=ClaimPostureAlertLifecycleStatus.CLEARED,
        transition=ClaimPostureTransition.ATTENTION_CLEARED,
        previous_posture_status=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE
        ),
        current_posture_status=ClaimPostureStatus.SUPPORTED,
        previous_alert_id=_identifier(
            "claim-posture-alert",
            f"{key}-previous-alert",
        ),
        current_alert_id=None,
        reconciliation_id=_identifier(
            "claim-posture-alert-reconciliation",
            f"{key}-reconciliation",
        ),
        delta_id=_identifier(
            "claim-posture-delta",
            f"{key}-delta",
        ),
        previous_severity=ClaimPostureAlertSeverity.MODERATE,
        current_severity=None,
        reconciliation_status=(
            ClaimPostureAlertReconciliationStatus.CLEARED
        ),
        previous_alert_digest=_digest(
            "claim-posture-alert",
            f"{key}-previous-alert",
        ),
        current_alert_digest=None,
        reconciliation_digest=_digest(
            "claim-posture-alert-reconciliation",
            f"{key}-reconciliation",
        ),
        delta_digest=_digest(
            "claim-posture-delta",
            f"{key}-delta",
        ),
        prior_docket_digest=prior_docket_digest,
        current_docket_digest=current_docket_digest,
        reconciliation_snapshot_digest=(
            reconciliation_snapshot_digest
        ),
        delta_snapshot_digest=delta_snapshot_digest,
        claim_catalog_digest=runtime.claim_catalog_digest,
        actor_registry_digest=runtime.registry.digest(),
    )


def _active_snapshot(
    runtime: _Runtime,
    *,
    key: str,
    compared_at: str,
    prior_docket_id: ScopedIdentifier,
    current_docket_id: ScopedIdentifier,
    prior_docket_digest: ContentDigest,
    current_docket_digest: ContentDigest,
    claim_id: ScopedIdentifier,
) -> ClaimPostureAlertLifecycleSnapshot:
    reconciliation_snapshot_id = _identifier(
        "claim-posture-alert-reconciliation-snapshot",
        f"{key}-reconciliation",
    )
    delta_snapshot_id = _identifier(
        "claim-posture-delta-snapshot",
        f"{key}-delta",
    )
    reconciliation_snapshot_digest = _digest(
        "claim-posture-alert-reconciliation-snapshot",
        f"{key}-reconciliation",
    )
    delta_snapshot_digest = _digest(
        "claim-posture-delta-snapshot",
        f"{key}-delta",
    )
    lifecycle = _new_lifecycle(
        runtime,
        key=f"{key}-new-alert",
        compared_at=compared_at,
        claim_id=claim_id,
        prior_docket_digest=prior_docket_digest,
        current_docket_digest=current_docket_digest,
        reconciliation_snapshot_digest=(
            reconciliation_snapshot_digest
        ),
        delta_snapshot_digest=delta_snapshot_digest,
    )

    return ClaimPostureAlertLifecycleSnapshot(
        snapshot_id=_identifier(
            "claim-posture-alert-lifecycle-snapshot",
            key,
        ),
        compared_at=UtcTimestamp.parse(
            compared_at
        ),
        produced_by_id=runtime.lifecycle_service.actor_id,
        producer_kind=runtime.lifecycle_service.kind,
        producer_accountability_owner_id=runtime.owner.actor_id,
        status=ClaimPostureAlertLifecycleSnapshotStatus.CHANGED,
        prior_docket_id=prior_docket_id,
        current_docket_id=current_docket_id,
        reconciliation_snapshot_id=(
            reconciliation_snapshot_id
        ),
        delta_snapshot_id=delta_snapshot_id,
        lifecycles=(
            lifecycle,
        ),
        prior_docket_digest=prior_docket_digest,
        current_docket_digest=current_docket_digest,
        reconciliation_snapshot_digest=(
            reconciliation_snapshot_digest
        ),
        delta_snapshot_digest=delta_snapshot_digest,
        claim_catalog_digest=runtime.claim_catalog_digest,
        actor_registry_digest=runtime.registry.digest(),
    )


def _clear_snapshot(
    runtime: _Runtime,
    *,
    key: str,
    compared_at: str,
    prior_docket_id: ScopedIdentifier,
    current_docket_id: ScopedIdentifier,
    prior_docket_digest: ContentDigest,
    current_docket_digest: ContentDigest,
    claim_id: ScopedIdentifier,
) -> ClaimPostureAlertLifecycleSnapshot:
    reconciliation_snapshot_id = _identifier(
        "claim-posture-alert-reconciliation-snapshot",
        f"{key}-reconciliation",
    )
    delta_snapshot_id = _identifier(
        "claim-posture-delta-snapshot",
        f"{key}-delta",
    )
    reconciliation_snapshot_digest = _digest(
        "claim-posture-alert-reconciliation-snapshot",
        f"{key}-reconciliation",
    )
    delta_snapshot_digest = _digest(
        "claim-posture-delta-snapshot",
        f"{key}-delta",
    )
    lifecycle = _cleared_lifecycle(
        runtime,
        key=f"{key}-cleared-alert",
        compared_at=compared_at,
        claim_id=claim_id,
        prior_docket_digest=prior_docket_digest,
        current_docket_digest=current_docket_digest,
        reconciliation_snapshot_digest=(
            reconciliation_snapshot_digest
        ),
        delta_snapshot_digest=delta_snapshot_digest,
    )

    return ClaimPostureAlertLifecycleSnapshot(
        snapshot_id=_identifier(
            "claim-posture-alert-lifecycle-snapshot",
            key,
        ),
        compared_at=UtcTimestamp.parse(
            compared_at
        ),
        produced_by_id=runtime.lifecycle_service.actor_id,
        producer_kind=runtime.lifecycle_service.kind,
        producer_accountability_owner_id=runtime.owner.actor_id,
        status=ClaimPostureAlertLifecycleSnapshotStatus.CLEAR,
        prior_docket_id=prior_docket_id,
        current_docket_id=current_docket_id,
        reconciliation_snapshot_id=(
            reconciliation_snapshot_id
        ),
        delta_snapshot_id=delta_snapshot_id,
        lifecycles=(
            lifecycle,
        ),
        prior_docket_digest=prior_docket_digest,
        current_docket_digest=current_docket_digest,
        reconciliation_snapshot_digest=(
            reconciliation_snapshot_digest
        ),
        delta_snapshot_digest=delta_snapshot_digest,
        claim_catalog_digest=runtime.claim_catalog_digest,
        actor_registry_digest=runtime.registry.digest(),
    )


def _snapshots(
    runtime: _Runtime,
) -> tuple[
    ClaimPostureAlertLifecycleSnapshot,
    ClaimPostureAlertLifecycleSnapshot,
    ClaimPostureAlertLifecycleSnapshot,
]:
    docket_zero_id = _identifier(
        "claim-posture-alert-docket",
        "chain-docket-zero",
    )
    docket_one_id = _identifier(
        "claim-posture-alert-docket",
        "chain-docket-one",
    )
    docket_two_id = _identifier(
        "claim-posture-alert-docket",
        "chain-docket-two",
    )
    docket_three_id = _identifier(
        "claim-posture-alert-docket",
        "chain-docket-three",
    )

    docket_zero_digest = _digest(
        "claim-posture-alert-docket",
        "chain-docket-zero",
    )
    docket_one_digest = _digest(
        "claim-posture-alert-docket",
        "chain-docket-one",
    )
    docket_two_digest = _digest(
        "claim-posture-alert-docket",
        "chain-docket-two",
    )
    docket_three_digest = _digest(
        "claim-posture-alert-docket",
        "chain-docket-three",
    )

    first = _active_snapshot(
        runtime,
        key="chain-generation-one",
        compared_at="2026-07-16T14:10:00Z",
        prior_docket_id=docket_zero_id,
        current_docket_id=docket_one_id,
        prior_docket_digest=docket_zero_digest,
        current_docket_digest=docket_one_digest,
        claim_id=runtime.first_claim_id,
    )
    second = _clear_snapshot(
        runtime,
        key="chain-generation-two",
        compared_at="2026-07-16T14:20:00Z",
        prior_docket_id=docket_one_id,
        current_docket_id=docket_two_id,
        prior_docket_digest=docket_one_digest,
        current_docket_digest=docket_two_digest,
        claim_id=runtime.first_claim_id,
    )
    third = _active_snapshot(
        runtime,
        key="chain-generation-three",
        compared_at="2026-07-16T14:30:00Z",
        prior_docket_id=docket_two_id,
        current_docket_id=docket_three_id,
        prior_docket_digest=docket_two_digest,
        current_docket_digest=docket_three_digest,
        claim_id=runtime.second_claim_id,
    )

    return first, second, third


def _entry(
    *,
    key: str,
    linked_at: str,
    snapshot: ClaimPostureAlertLifecycleSnapshot,
    previous: ClaimPostureAlertLifecycleChainEntry | None = None,
) -> ClaimPostureAlertLifecycleChainEntry:
    return ClaimPostureAlertLifecycleChainEntry.link(
        key=key,
        linked_at=UtcTimestamp.parse(
            linked_at
        ),
        snapshot=snapshot,
        previous=previous,
    )


def _chain(
    runtime: _Runtime,
    *entries: ClaimPostureAlertLifecycleChainEntry,
    key: str = "claim-alert-lifecycle-chain",
    created_at: str = "2026-07-16T14:40:00Z",
) -> ClaimPostureAlertLifecycleChain:
    return ClaimPostureAlertLifecycleChain.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.chain_system.actor_id,
        claim_catalog_digest=runtime.claim_catalog_digest,
        actor_registry=runtime.registry,
        entries=entries,
    )


def test_chain_preserves_linear_multi_generation_continuity() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, third_snapshot = _snapshots(
        runtime
    )
    first = _entry(
        key="chain-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="chain-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )
    third = _entry(
        key="chain-entry-three",
        linked_at="2026-07-16T14:31:00Z",
        snapshot=third_snapshot,
        previous=second,
    )
    chain = _chain(
        runtime,
        first,
        second,
        third,
    )

    assert chain.generation_count == 3
    assert chain.latest_entry == third
    assert chain.latest_snapshot == third_snapshot
    assert chain.status is (
        ClaimPostureAlertLifecycleChainStatus.ACTIVE
    )
    assert chain.has_active_alerts is True
    assert chain.current_active_alert_count == 1
    assert chain.current_docket_id == (
        third_snapshot.current_docket_id
    )
    assert chain.current_docket_digest == (
        third_snapshot.current_docket_digest
    )
    assert chain.active_claim_ids() == (
        runtime.second_claim_id,
    )
    assert chain.silent_drop_count == 0


def test_clear_latest_generation_produces_clear_chain_status() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="clear-chain-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="clear-chain-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )
    chain = _chain(
        runtime,
        first,
        second,
    )

    assert chain.status is (
        ClaimPostureAlertLifecycleChainStatus.CLEAR
    )
    assert chain.has_active_alerts is False
    assert chain.current_active_alert_count == 0
    assert chain.active_claim_ids() == ()


def test_empty_chain_has_no_current_docket_or_active_alerts() -> None:
    runtime = _runtime()
    chain = _chain(
        runtime
    )

    assert chain.status is (
        ClaimPostureAlertLifecycleChainStatus.EMPTY
    )
    assert chain.generation_count == 0
    assert chain.latest_entry is None
    assert chain.latest_snapshot is None
    assert chain.current_docket_id is None
    assert chain.current_docket_digest is None
    assert chain.current_active_alert_count == 0
    assert chain.active_claim_ids() == ()


def test_entry_predecessor_digest_binds_exact_previous_entry() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="digest-chain-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="digest-chain-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )

    assert second.predecessor_entry_id == first.entry_id
    assert second.predecessor_entry_digest == first.digest()

    tampered = replace(
        second,
        predecessor_entry_digest=_digest(
            "claim-posture-alert-lifecycle-chain-entry",
            "different-predecessor",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="predecessor digest",
    ):
        _chain(
            runtime,
            first,
            tampered,
        )


def test_chain_rejects_docket_continuity_gap_or_fork() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="fork-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    forked_snapshot = replace(
        second_snapshot,
        prior_docket_id=_identifier(
            "claim-posture-alert-docket",
            "unrelated-prior-docket",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="previous current alert docket",
    ):
        _entry(
            key="fork-entry-two",
            linked_at="2026-07-16T14:21:00Z",
            snapshot=forked_snapshot,
            previous=first,
        )


def test_chain_rejects_prior_docket_digest_mismatch() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="digest-gap-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    mismatched_snapshot = replace(
        second_snapshot,
        prior_docket_digest=_digest(
            "claim-posture-alert-docket",
            "mismatched-prior-docket",
        ),
        lifecycles=tuple(
            replace(
                lifecycle,
                prior_docket_digest=_digest(
                    "claim-posture-alert-docket",
                    "mismatched-prior-docket",
                ),
            )
            for lifecycle in second_snapshot.lifecycles
        ),
    )

    with pytest.raises(
        FoundationError,
        match="prior-docket digest",
    ):
        _entry(
            key="digest-gap-entry-two",
            linked_at="2026-07-16T14:21:00Z",
            snapshot=mismatched_snapshot,
            previous=first,
        )


def test_chain_rejects_noncontiguous_sequence_numbers() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="sequence-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="sequence-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )
    gap = replace(
        second,
        sequence_number=3,
    )

    with pytest.raises(
        FoundationError,
        match="contiguous and begin at one",
    ):
        _chain(
            runtime,
            first,
            gap,
        )


def test_chain_rejects_docket_cycles() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, third_snapshot = _snapshots(
        runtime
    )
    first = _entry(
        key="cycle-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="cycle-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )
    cyclic_snapshot = replace(
        third_snapshot,
        current_docket_id=first_snapshot.prior_docket_id,
    )
    third = _entry(
        key="cycle-entry-three",
        linked_at="2026-07-16T14:31:00Z",
        snapshot=cyclic_snapshot,
        previous=second,
    )

    with pytest.raises(
        FoundationError,
        match="must not contain a docket cycle",
    ):
        _chain(
            runtime,
            first,
            second,
            third,
        )


def test_chain_append_preserves_identity_and_adds_next_generation() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="append-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    chain = _chain(
        runtime,
        first,
        created_at="2026-07-16T14:12:00Z",
    )
    next_chain = chain.append(
        key="append-entry-two",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T14:21:00Z"
        ),
        created_at=UtcTimestamp.parse(
            "2026-07-16T14:22:00Z"
        ),
        snapshot=second_snapshot,
    )

    assert next_chain.chain_id == chain.chain_id
    assert next_chain.producer_id == chain.producer_id
    assert next_chain.generation_count == 2
    assert next_chain.require_entry_for_sequence(
        1
    ) == first
    assert next_chain.require_entry_for_sequence(
        2
    ).snapshot == second_snapshot


def test_chain_rejects_different_catalog_generation() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="catalog-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    different_catalog = _digest(
        "claim-catalog",
        "different-claim-catalog",
    )
    mismatched_snapshot = replace(
        second_snapshot,
        claim_catalog_digest=different_catalog,
        lifecycles=tuple(
            replace(
                lifecycle,
                claim_catalog_digest=different_catalog,
            )
            for lifecycle in second_snapshot.lifecycles
        ),
    )

    with pytest.raises(
        FoundationError,
        match="same claim catalog",
    ):
        _entry(
            key="catalog-entry-two",
            linked_at="2026-07-16T14:21:00Z",
            snapshot=mismatched_snapshot,
            previous=first,
        )


def test_chain_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertLifecycleChain.create(
            key="human-produced-chain",
            created_at=UtcTimestamp.parse(
                "2026-07-16T14:40:00Z"
            ),
            producer_id=runtime.owner.actor_id,
            claim_catalog_digest=runtime.claim_catalog_digest,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-chain-service",
        display_name="Unowned Chain Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-lifecycle-chain-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.owner.actor_id,
        actors=(
            *runtime.registry.actors,
            unowned_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must identify an accountable human owner",
    ):
        ClaimPostureAlertLifecycleChain.create(
            key="unowned-produced-chain",
            created_at=UtcTimestamp.parse(
                "2026-07-16T14:40:00Z"
            ),
            producer_id=unowned_service.actor_id,
            claim_catalog_digest=runtime.claim_catalog_digest,
            actor_registry=expanded_registry,
        )


def test_chain_is_reporting_only_and_tamper_evident() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, _ = _snapshots(
        runtime
    )
    first = _entry(
        key="reporting-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="reporting-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )
    chain = _chain(
        runtime,
        first,
        second,
    )

    assert chain.all_generations_accounted_for is True
    assert chain.changes_claim_state is False
    assert chain.grants_authority is False
    assert chain.claims_certification is False
    assert chain.digest().verifies(
        chain.canonical_payload()
    ) is True

    for entry in chain.entries:
        assert entry.changes_claim_state is False
        assert entry.grants_authority is False
        assert entry.claims_certification is False
        assert entry.digest().verifies(
            entry.to_payload()
        ) is True


def test_chain_is_deterministic_across_entry_input_order() -> None:
    runtime = _runtime()
    first_snapshot, second_snapshot, third_snapshot = _snapshots(
        runtime
    )
    first = _entry(
        key="stable-entry-one",
        linked_at="2026-07-16T14:11:00Z",
        snapshot=first_snapshot,
    )
    second = _entry(
        key="stable-entry-two",
        linked_at="2026-07-16T14:21:00Z",
        snapshot=second_snapshot,
        previous=first,
    )
    third = _entry(
        key="stable-entry-three",
        linked_at="2026-07-16T14:31:00Z",
        snapshot=third_snapshot,
        previous=second,
    )

    ordered = _chain(
        runtime,
        first,
        second,
        third,
        key="stable-lifecycle-chain",
    )
    reordered = _chain(
        runtime,
        third,
        first,
        second,
        key="stable-lifecycle-chain",
    )

    assert (
        ordered.canonical_payload()
        == reordered.canonical_payload()
    )
    assert ordered.digest() == reordered.digest()
