"""Tests for lifecycle checkpoint currency snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
    ClaimPostureAlertLifecycleCheckpoint,
    ClaimPostureAlertLifecycleCheckpointCurrencySnapshot,
    ClaimPostureAlertLifecycleCheckpointCurrencyStatus,
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
    currency_system: ActorIdentity
    registry: ActorRegistry
    catalog_digest: ContentDigest
    first_chain: ClaimPostureAlertLifecycleChain
    second_chain: ClaimPostureAlertLifecycleChain


def _lifecycle_snapshot(
    *,
    key: str,
    compared_at: str,
    prior_docket_key: str,
    current_docket_key: str,
    lifecycle_service: ActorIdentity,
    owner: ActorIdentity,
    registry: ActorRegistry,
    catalog_digest: ContentDigest,
) -> ClaimPostureAlertLifecycleSnapshot:
    return ClaimPostureAlertLifecycleSnapshot(
        snapshot_id=_identifier(
            "claim-posture-alert-lifecycle-snapshot",
            key,
        ),
        compared_at=UtcTimestamp.parse(
            compared_at
        ),
        produced_by_id=lifecycle_service.actor_id,
        producer_kind=lifecycle_service.kind,
        producer_accountability_owner_id=owner.actor_id,
        status=ClaimPostureAlertLifecycleSnapshotStatus.CLEAR,
        prior_docket_id=_identifier(
            "claim-posture-alert-docket",
            prior_docket_key,
        ),
        current_docket_id=_identifier(
            "claim-posture-alert-docket",
            current_docket_key,
        ),
        reconciliation_snapshot_id=_identifier(
            "claim-posture-alert-reconciliation-snapshot",
            f"{key}-reconciliation",
        ),
        delta_snapshot_id=_identifier(
            "claim-posture-delta-snapshot",
            f"{key}-delta",
        ),
        lifecycles=(),
        prior_docket_digest=_digest(
            "claim-posture-alert-docket",
            prior_docket_key,
        ),
        current_docket_digest=_digest(
            "claim-posture-alert-docket",
            current_docket_key,
        ),
        reconciliation_snapshot_digest=_digest(
            "claim-posture-alert-reconciliation-snapshot",
            f"{key}-reconciliation",
        ),
        delta_snapshot_digest=_digest(
            "claim-posture-delta-snapshot",
            f"{key}-delta",
        ),
        claim_catalog_digest=catalog_digest,
        actor_registry_digest=registry.digest(),
    )


def _runtime() -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="checkpoint-currency-owner",
        display_name="Checkpoint Currency Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="checkpoint-currency-reviewer",
        display_name="Checkpoint Currency Reviewer",
    )
    lifecycle_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="checkpoint-currency-lifecycle-service",
        display_name="Checkpoint Currency Lifecycle Service",
        accountability_owner_id=owner.actor_id,
    )
    chain_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="checkpoint-currency-chain-system",
        display_name="Checkpoint Currency Chain System",
        accountability_owner_id=owner.actor_id,
    )
    ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="checkpoint-currency-ledger-service",
        display_name="Checkpoint Currency Ledger Service",
        accountability_owner_id=reviewer.actor_id,
    )
    currency_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="checkpoint-currency-system",
        display_name="Checkpoint Currency System",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="checkpoint-currency-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T16:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            reviewer,
            lifecycle_service,
            chain_system,
            ledger_service,
            currency_system,
        ),
    )
    catalog_digest = _digest(
        "claim-catalog",
        "checkpoint-currency-catalog",
    )

    first_snapshot = _lifecycle_snapshot(
        key="checkpoint-currency-generation-one",
        compared_at="2026-07-16T16:10:00Z",
        prior_docket_key="checkpoint-currency-docket-zero",
        current_docket_key="checkpoint-currency-docket-one",
        lifecycle_service=lifecycle_service,
        owner=owner,
        registry=registry,
        catalog_digest=catalog_digest,
    )
    first_entry = ClaimPostureAlertLifecycleChainEntry.link(
        key="checkpoint-currency-entry-one",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T16:11:00Z"
        ),
        snapshot=first_snapshot,
    )
    first_chain = ClaimPostureAlertLifecycleChain.create(
        key="checkpoint-currency-chain",
        created_at=UtcTimestamp.parse(
            "2026-07-16T16:12:00Z"
        ),
        producer_id=chain_system.actor_id,
        claim_catalog_digest=catalog_digest,
        actor_registry=registry,
        entries=(
            first_entry,
        ),
    )

    second_snapshot = _lifecycle_snapshot(
        key="checkpoint-currency-generation-two",
        compared_at="2026-07-16T16:20:00Z",
        prior_docket_key="checkpoint-currency-docket-one",
        current_docket_key="checkpoint-currency-docket-two",
        lifecycle_service=lifecycle_service,
        owner=owner,
        registry=registry,
        catalog_digest=catalog_digest,
    )
    second_chain = first_chain.append(
        key="checkpoint-currency-entry-two",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T16:21:00Z"
        ),
        created_at=UtcTimestamp.parse(
            "2026-07-16T16:22:00Z"
        ),
        snapshot=second_snapshot,
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        lifecycle_service=lifecycle_service,
        chain_system=chain_system,
        ledger_service=ledger_service,
        currency_system=currency_system,
        registry=registry,
        catalog_digest=catalog_digest,
        first_chain=first_chain,
        second_chain=second_chain,
    )


def _checkpoint(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    key: str,
    status: ClaimPostureAlertLifecycleCheckpointStatus,
    decided_at: str,
) -> ClaimPostureAlertLifecycleCheckpoint:
    return ClaimPostureAlertLifecycleCheckpoint.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=runtime.reviewer.actor_id,
        status=status,
        rationale=f"Independent continuity review: {status.value}.",
        chain=chain,
        actor_registry=runtime.registry,
    )


def _ledger(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    checkpoints: tuple[
        ClaimPostureAlertLifecycleCheckpoint,
        ...,
    ] = (),
    key: str = "checkpoint-currency-ledger",
    created_at: str = "2026-07-16T16:14:00Z",
) -> ClaimPostureAlertLifecycleCheckpointLedger:
    return ClaimPostureAlertLifecycleCheckpointLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.ledger_service.actor_id,
        chain=chain,
        actor_registry=runtime.registry,
        checkpoints=checkpoints,
    )


def _currency(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    ledger: ClaimPostureAlertLifecycleCheckpointLedger,
    assessed_at: str = "2026-07-16T16:23:00Z",
) -> ClaimPostureAlertLifecycleCheckpointCurrencySnapshot:
    return (
        ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        .assess(
            key="current-checkpoint-currency",
            assessed_at=UtcTimestamp.parse(
                assessed_at
            ),
            produced_by_id=runtime.currency_system.actor_id,
            chain=chain,
            checkpoint_ledger=ledger,
            actor_registry=runtime.registry,
        )
    )


def test_accepted_checkpoint_applies_to_exact_current_head() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="accept-current-chain-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T16:13:00Z",
    )
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            accepted,
        ),
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        ledger=ledger,
        assessed_at="2026-07-16T16:15:00Z",
    )

    assert currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.ACCEPTED
    )
    assert currency.applies_to_current_head is True
    assert currency.continuity_accepted_for_current_head is True
    assert currency.continuity_rejected_for_current_head is False
    assert currency.review_required is False
    assert currency.stale_review_cannot_cover_current_head is False
    assert currency.current_head_entry_id == (
        currency.reviewed_head_entry_id
    )
    assert currency.chain_digest == currency.reviewed_chain_digest


def test_rejected_checkpoint_applies_only_to_exact_current_head() -> None:
    runtime = _runtime()
    rejected = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="reject-current-chain-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED
        ),
        decided_at="2026-07-16T16:13:00Z",
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        ledger=_ledger(
            runtime,
            chain=runtime.first_chain,
            checkpoints=(
                rejected,
            ),
        ),
        assessed_at="2026-07-16T16:15:00Z",
    )

    assert currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.REJECTED
    )
    assert currency.applies_to_current_head is True
    assert currency.continuity_rejected_for_current_head is True
    assert currency.continuity_accepted_for_current_head is False
    assert currency.review_required is False


def test_empty_checkpoint_ledger_reports_no_review() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        ledger=ledger,
        assessed_at="2026-07-16T16:15:00Z",
    )

    assert currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.NO_REVIEW
    )
    assert currency.latest_checkpoint_id is None
    assert currency.latest_checkpoint_status is None
    assert currency.latest_checkpoint_digest is None
    assert currency.applies_to_current_head is True
    assert currency.review_required is True


def test_deferred_checkpoint_keeps_current_review_open() -> None:
    runtime = _runtime()
    deferred = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="defer-current-chain-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
        decided_at="2026-07-16T16:13:00Z",
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        ledger=_ledger(
            runtime,
            chain=runtime.first_chain,
            checkpoints=(
                deferred,
            ),
        ),
        assessed_at="2026-07-16T16:15:00Z",
    )

    assert currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.DEFERRED
    )
    assert currency.applies_to_current_head is True
    assert currency.review_required is True
    assert currency.continuity_accepted_for_current_head is False


def test_checkpoint_becomes_stale_when_chain_advances() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="accept-old-chain-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T16:13:00Z",
    )
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            accepted,
        ),
    )
    currency = _currency(
        runtime,
        chain=runtime.second_chain,
        ledger=ledger,
    )

    assert currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE
    )
    assert currency.current_generation_count == 2
    assert currency.reviewed_generation_count == 1
    assert currency.applies_to_current_head is False
    assert currency.continuity_accepted_for_current_head is False
    assert currency.review_required is True
    assert currency.stale_review_cannot_cover_current_head is True
    assert (
        currency.current_head_entry_id
        != currency.reviewed_head_entry_id
    )


def test_stale_reviewed_head_must_remain_in_current_chain_history() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="accept-history-bound-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T16:13:00Z",
    )
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            accepted,
        ),
    )
    tampered_first_entry = replace(
        runtime.second_chain.entries[0],
        entry_id=_identifier(
            "claim-posture-alert-lifecycle-chain-entry",
            "rewritten-first-entry",
        ),
    )
    tampered_second_entry = replace(
        runtime.second_chain.entries[1],
        predecessor_entry_id=tampered_first_entry.entry_id,
        predecessor_entry_digest=tampered_first_entry.digest(),
    )
    tampered_chain = replace(
        runtime.second_chain,
        entries=(
            tampered_first_entry,
            tampered_second_entry,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="head identity does not match",
    ):
        _currency(
            runtime,
            chain=tampered_chain,
            ledger=ledger,
        )


def test_same_generation_requires_exact_reviewed_chain_digest() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
    )
    altered_chain = replace(
        runtime.first_chain,
        created_at=UtcTimestamp.parse(
            "2026-07-16T16:12:01Z"
        ),
    )

    with pytest.raises(
        FoundationError,
        match="chain digest does not match",
    ):
        _currency(
            runtime,
            chain=altered_chain,
            ledger=ledger,
            assessed_at="2026-07-16T16:15:00Z",
        )


def test_checkpoint_ledger_cannot_reference_newer_generation() -> None:
    runtime = _runtime()
    second_accepted = _checkpoint(
        runtime,
        chain=runtime.second_chain,
        key="accept-second-generation",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T16:23:00Z",
    )
    second_ledger = _ledger(
        runtime,
        chain=runtime.second_chain,
        checkpoints=(
            second_accepted,
        ),
        key="second-generation-ledger",
        created_at="2026-07-16T16:24:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="newer than the current lifecycle chain",
    ):
        _currency(
            runtime,
            chain=runtime.first_chain,
            ledger=second_ledger,
            assessed_at="2026-07-16T16:25:00Z",
        )


def test_checkpoint_ledger_must_reference_same_chain_identity() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
    )
    different_chain = replace(
        runtime.first_chain,
        chain_id=_identifier(
            "claim-posture-alert-lifecycle-chain",
            "different-currency-chain",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="different lifecycle chain",
    ):
        _currency(
            runtime,
            chain=different_chain,
            ledger=ledger,
            assessed_at="2026-07-16T16:15:00Z",
        )


def test_currency_assessment_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        (
            ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
            .assess(
                key="human-produced-checkpoint-currency",
                assessed_at=UtcTimestamp.parse(
                    "2026-07-16T16:15:00Z"
                ),
                produced_by_id=runtime.reviewer.actor_id,
                chain=runtime.first_chain,
                checkpoint_ledger=ledger,
                actor_registry=runtime.registry,
            )
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-checkpoint-currency-service",
        display_name="Unowned Checkpoint Currency Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-checkpoint-currency-actors",
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
        (
            ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
            .assess(
                key="unowned-produced-checkpoint-currency",
                assessed_at=UtcTimestamp.parse(
                    "2026-07-16T16:15:00Z"
                ),
                produced_by_id=unowned_service.actor_id,
                chain=runtime.first_chain,
                checkpoint_ledger=ledger,
                actor_registry=expanded_registry,
            )
        )


def test_currency_assessment_must_not_predate_checkpoint_ledger() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
        created_at="2026-07-16T16:16:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the checkpoint ledger",
    ):
        _currency(
            runtime,
            chain=runtime.first_chain,
            ledger=ledger,
            assessed_at="2026-07-16T16:15:00Z",
        )


def test_checkpoint_currency_is_reporting_only_and_deterministic() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="stable-checkpoint-currency-review",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T16:13:00Z",
    )
    ledger = _ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            accepted,
        ),
        key="stable-checkpoint-currency-ledger",
    )

    first = _currency(
        runtime,
        chain=runtime.first_chain,
        ledger=ledger,
        assessed_at="2026-07-16T16:15:00Z",
    )
    second = _currency(
        runtime,
        chain=runtime.first_chain,
        ledger=ledger,
        assessed_at="2026-07-16T16:15:00Z",
    )

    assert first.approves_underlying_claims is False
    assert first.clears_alerts is False
    assert first.changes_claim_state is False
    assert first.grants_authority is False
    assert first.claims_certification is False
    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()
    assert first.digest().verifies(
        first.to_payload()
    ) is True
