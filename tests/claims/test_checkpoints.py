"""Tests for independent lifecycle-chain checkpoints."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
    ClaimPostureAlertLifecycleCheckpoint,
    ClaimPostureAlertLifecycleCheckpointLedger,
    ClaimPostureAlertLifecycleCheckpointStatus,
    ClaimPostureAlertLifecycleSnapshot,
    ClaimPostureAlertLifecycleSnapshotStatus,
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
    reviewer: ActorIdentity
    lifecycle_service: ActorIdentity
    chain_system: ActorIdentity
    ledger_service: ActorIdentity
    registry: ActorRegistry
    catalog_digest: ContentDigest
    chain: ClaimPostureAlertLifecycleChain


def _runtime() -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="checkpoint-chain-owner",
        display_name="Checkpoint Chain Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-checkpoint-reviewer",
        display_name="Independent Checkpoint Reviewer",
    )
    lifecycle_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="checkpoint-lifecycle-service",
        display_name="Checkpoint Lifecycle Service",
        accountability_owner_id=owner.actor_id,
    )
    chain_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="checkpoint-chain-system",
        display_name="Checkpoint Chain System",
        accountability_owner_id=owner.actor_id,
    )
    ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="checkpoint-ledger-service",
        display_name="Checkpoint Ledger Service",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-lifecycle-checkpoint-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T15:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            reviewer,
            lifecycle_service,
            chain_system,
            ledger_service,
        ),
    )
    catalog_digest = _digest(
        "claim-catalog",
        "claim-lifecycle-checkpoint-catalog",
    )
    snapshot = ClaimPostureAlertLifecycleSnapshot(
        snapshot_id=_identifier(
            "claim-posture-alert-lifecycle-snapshot",
            "checkpoint-lifecycle-snapshot",
        ),
        compared_at=UtcTimestamp.parse(
            "2026-07-16T15:10:00Z"
        ),
        produced_by_id=lifecycle_service.actor_id,
        producer_kind=lifecycle_service.kind,
        producer_accountability_owner_id=owner.actor_id,
        status=ClaimPostureAlertLifecycleSnapshotStatus.CLEAR,
        prior_docket_id=_identifier(
            "claim-posture-alert-docket",
            "checkpoint-prior-docket",
        ),
        current_docket_id=_identifier(
            "claim-posture-alert-docket",
            "checkpoint-current-docket",
        ),
        reconciliation_snapshot_id=_identifier(
            "claim-posture-alert-reconciliation-snapshot",
            "checkpoint-reconciliation",
        ),
        delta_snapshot_id=_identifier(
            "claim-posture-delta-snapshot",
            "checkpoint-delta",
        ),
        lifecycles=(),
        prior_docket_digest=_digest(
            "claim-posture-alert-docket",
            "checkpoint-prior-docket",
        ),
        current_docket_digest=_digest(
            "claim-posture-alert-docket",
            "checkpoint-current-docket",
        ),
        reconciliation_snapshot_digest=_digest(
            "claim-posture-alert-reconciliation-snapshot",
            "checkpoint-reconciliation",
        ),
        delta_snapshot_digest=_digest(
            "claim-posture-delta-snapshot",
            "checkpoint-delta",
        ),
        claim_catalog_digest=catalog_digest,
        actor_registry_digest=registry.digest(),
    )
    entry = ClaimPostureAlertLifecycleChainEntry.link(
        key="checkpoint-chain-entry",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T15:11:00Z"
        ),
        snapshot=snapshot,
    )
    chain = ClaimPostureAlertLifecycleChain.create(
        key="checkpoint-lifecycle-chain",
        created_at=UtcTimestamp.parse(
            "2026-07-16T15:12:00Z"
        ),
        producer_id=chain_system.actor_id,
        claim_catalog_digest=catalog_digest,
        actor_registry=registry,
        entries=(
            entry,
        ),
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        lifecycle_service=lifecycle_service,
        chain_system=chain_system,
        ledger_service=ledger_service,
        registry=registry,
        catalog_digest=catalog_digest,
        chain=chain,
    )


def _checkpoint(
    runtime: _Runtime,
    *,
    key: str,
    status: ClaimPostureAlertLifecycleCheckpointStatus,
    decided_at: str = "2026-07-16T15:13:00Z",
    decided_by_id: ScopedIdentifier | None = None,
    chain: ClaimPostureAlertLifecycleChain | None = None,
) -> ClaimPostureAlertLifecycleCheckpoint:
    return ClaimPostureAlertLifecycleCheckpoint.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=(
            decided_by_id
            or runtime.reviewer.actor_id
        ),
        status=status,
        rationale=f"Independent continuity review: {status.value}.",
        chain=(
            chain
            or runtime.chain
        ),
        actor_registry=runtime.registry,
    )


def _ledger(
    runtime: _Runtime,
    *checkpoints: ClaimPostureAlertLifecycleCheckpoint,
    key: str = "claim-lifecycle-checkpoints",
    created_at: str = "2026-07-16T15:20:00Z",
    chain: ClaimPostureAlertLifecycleChain | None = None,
) -> ClaimPostureAlertLifecycleCheckpointLedger:
    return ClaimPostureAlertLifecycleCheckpointLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.ledger_service.actor_id,
        chain=(
            chain
            or runtime.chain
        ),
        actor_registry=runtime.registry,
        checkpoints=checkpoints,
    )


def test_independent_human_accepts_exact_chain_head() -> None:
    runtime = _runtime()
    checkpoint = _checkpoint(
        runtime,
        key="accept-chain-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
    )
    head = runtime.chain.latest_entry

    assert head is not None
    assert checkpoint.chain_id == runtime.chain.chain_id
    assert checkpoint.chain_digest == runtime.chain.digest()
    assert checkpoint.head_entry_id == head.entry_id
    assert checkpoint.head_entry_digest == head.digest()
    assert checkpoint.current_docket_id == (
        runtime.chain.current_docket_id
    )
    assert checkpoint.current_docket_digest == (
        runtime.chain.current_docket_digest
    )
    assert checkpoint.generation_count == 1
    assert checkpoint.accepts_continuity is True
    assert checkpoint.is_terminal is True


def test_checkpoint_does_not_approve_claims_clear_alerts_or_grant_authority() -> None:
    runtime = _runtime()
    checkpoint = _checkpoint(
        runtime,
        key="bounded-checkpoint",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
    )

    assert checkpoint.approves_underlying_claims is False
    assert checkpoint.clears_alerts is False
    assert checkpoint.changes_claim_state is False
    assert checkpoint.grants_authority is False
    assert checkpoint.claims_certification is False
    assert checkpoint.digest().verifies(
        checkpoint.to_payload()
    ) is True


def test_chain_producer_owner_cannot_review_own_chain() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="independent of the chain producer",
    ):
        _checkpoint(
            runtime,
            key="self-reviewed-chain",
            status=(
                ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
            ),
            decided_by_id=runtime.owner.actor_id,
        )


def test_machine_cannot_issue_human_checkpoint() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="active human actor",
    ):
        _checkpoint(
            runtime,
            key="machine-reviewed-chain",
            status=(
                ClaimPostureAlertLifecycleCheckpointStatus.REJECTED
            ),
            decided_by_id=runtime.chain_system.actor_id,
        )


def test_empty_chain_cannot_be_checkpointed() -> None:
    runtime = _runtime()
    empty_chain = ClaimPostureAlertLifecycleChain.create(
        key="empty-checkpoint-chain",
        created_at=runtime.chain.created_at,
        producer_id=runtime.chain_system.actor_id,
        claim_catalog_digest=runtime.catalog_digest,
        actor_registry=runtime.registry,
    )

    with pytest.raises(
        FoundationError,
        match="requires at least one generation",
    ):
        _checkpoint(
            runtime,
            key="empty-chain-checkpoint",
            status=(
                ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
            ),
            chain=empty_chain,
        )


def test_deferred_then_terminal_checkpoint_is_allowed() -> None:
    runtime = _runtime()
    deferred = _checkpoint(
        runtime,
        key="defer-chain-review",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
        decided_at="2026-07-16T15:13:00Z",
    )
    accepted = _checkpoint(
        runtime,
        key="accept-after-deferral",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T15:14:00Z",
    )
    ledger = _ledger(
        runtime,
        accepted,
        deferred,
    )

    assert ledger.checkpoints == (
        deferred,
        accepted,
    )
    assert ledger.latest_checkpoint == accepted
    assert ledger.terminal_checkpoint == accepted
    assert ledger.continuity_accepted is True
    assert ledger.review_open is False
    assert ledger.require_terminal_checkpoint() == accepted


def test_terminal_checkpoint_cannot_be_followed() -> None:
    runtime = _runtime()
    rejected = _checkpoint(
        runtime,
        key="reject-chain-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED
        ),
        decided_at="2026-07-16T15:13:00Z",
    )
    later = _checkpoint(
        runtime,
        key="later-chain-decision",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T15:14:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="terminal lifecycle-chain checkpoint",
    ):
        _ledger(
            runtime,
            rejected,
            later,
        )


def test_checkpoint_times_must_strictly_increase() -> None:
    runtime = _runtime()
    first = _checkpoint(
        runtime,
        key="same-time-defer-one",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
    )
    second = _checkpoint(
        runtime,
        key="same-time-defer-two",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="strictly increasing decision times",
    ):
        _ledger(
            runtime,
            first,
            second,
        )


def test_checkpoint_from_different_chain_head_is_rejected() -> None:
    runtime = _runtime()
    checkpoint = _checkpoint(
        runtime,
        key="old-head-checkpoint",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
    )
    altered_chain = replace(
        runtime.chain,
        chain_id=_identifier(
            "claim-posture-alert-lifecycle-chain",
            "different-checkpoint-chain",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="same lifecycle chain",
    ):
        _ledger(
            runtime,
            checkpoint,
            chain=altered_chain,
        )


def test_empty_checkpoint_ledger_keeps_review_open() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime
    )

    assert ledger.checkpoint_count == 0
    assert ledger.latest_checkpoint is None
    assert ledger.terminal_checkpoint is None
    assert ledger.continuity_accepted is False
    assert ledger.review_open is True

    with pytest.raises(
        FoundationError,
        match="does not have a terminal decision",
    ):
        ledger.require_terminal_checkpoint()


def test_checkpoint_ledger_append_preserves_identity() -> None:
    runtime = _runtime()
    deferred = _checkpoint(
        runtime,
        key="append-deferred-checkpoint",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
        decided_at="2026-07-16T15:13:00Z",
    )
    accepted = _checkpoint(
        runtime,
        key="append-accepted-checkpoint",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T15:14:00Z",
    )
    ledger = _ledger(
        runtime,
        deferred,
        created_at="2026-07-16T15:13:00Z",
    )
    next_ledger = ledger.append(
        accepted,
        created_at=UtcTimestamp.parse(
            "2026-07-16T15:14:00Z"
        ),
    )

    assert next_ledger.ledger_id == ledger.ledger_id
    assert next_ledger.producer_id == ledger.producer_id
    assert next_ledger.checkpoints == (
        deferred,
        accepted,
    )
    assert next_ledger.continuity_accepted is True


def test_checkpoint_ledger_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertLifecycleCheckpointLedger.create(
            key="human-produced-checkpoint-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-16T15:20:00Z"
            ),
            producer_id=runtime.reviewer.actor_id,
            chain=runtime.chain,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-checkpoint-ledger-service",
        display_name="Unowned Checkpoint Ledger Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-checkpoint-ledger-actors",
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
        ClaimPostureAlertLifecycleCheckpointLedger.create(
            key="unowned-produced-checkpoint-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-16T15:20:00Z"
            ),
            producer_id=unowned_service.actor_id,
            chain=runtime.chain,
            actor_registry=expanded_registry,
        )


def test_checkpoint_ledger_is_reporting_only_and_deterministic() -> None:
    runtime = _runtime()
    first = _checkpoint(
        runtime,
        key="stable-checkpoint-one",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
        decided_at="2026-07-16T15:13:00Z",
    )
    second = _checkpoint(
        runtime,
        key="stable-checkpoint-two",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T15:14:00Z",
    )

    ordered = _ledger(
        runtime,
        first,
        second,
        key="stable-checkpoint-ledger",
    )
    reordered = _ledger(
        runtime,
        second,
        first,
        key="stable-checkpoint-ledger",
    )

    assert ordered.approves_underlying_claims is False
    assert ordered.clears_alerts is False
    assert ordered.changes_claim_state is False
    assert ordered.grants_authority is False
    assert ordered.claims_certification is False
    assert (
        ordered.canonical_payload()
        == reordered.canonical_payload()
    )
    assert ordered.digest() == reordered.digest()
    assert ordered.digest().verifies(
        ordered.canonical_payload()
    ) is True
