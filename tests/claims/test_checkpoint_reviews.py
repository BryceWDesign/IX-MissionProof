"""Tests for lifecycle checkpoint review dockets."""

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
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
    ClaimPostureAlertLifecycleReviewPriority,
    ClaimPostureAlertLifecycleReviewReason,
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
    checkpoint_ledger_service: ActorIdentity
    currency_system: ActorIdentity
    review_docket_system: ActorIdentity
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
        key="review-docket-owner",
        display_name="Review Docket Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-review-docket-reviewer",
        display_name="Independent Review Docket Reviewer",
    )
    lifecycle_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-docket-lifecycle-service",
        display_name="Review Docket Lifecycle Service",
        accountability_owner_id=owner.actor_id,
    )
    chain_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-docket-chain-system",
        display_name="Review Docket Chain System",
        accountability_owner_id=owner.actor_id,
    )
    checkpoint_ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-docket-checkpoint-ledger-service",
        display_name="Review Docket Checkpoint Ledger Service",
        accountability_owner_id=reviewer.actor_id,
    )
    currency_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-docket-currency-system",
        display_name="Review Docket Currency System",
        accountability_owner_id=reviewer.actor_id,
    )
    review_docket_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="lifecycle-review-docket-system",
        display_name="Lifecycle Review Docket System",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="lifecycle-review-docket-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T17:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            reviewer,
            lifecycle_service,
            chain_system,
            checkpoint_ledger_service,
            currency_system,
            review_docket_system,
        ),
    )
    catalog_digest = _digest(
        "claim-catalog",
        "lifecycle-review-docket-catalog",
    )

    first_snapshot = _lifecycle_snapshot(
        key="review-docket-generation-one",
        compared_at="2026-07-16T17:10:00Z",
        prior_docket_key="review-docket-zero",
        current_docket_key="review-docket-one",
        lifecycle_service=lifecycle_service,
        owner=owner,
        registry=registry,
        catalog_digest=catalog_digest,
    )
    first_entry = ClaimPostureAlertLifecycleChainEntry.link(
        key="review-docket-entry-one",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T17:11:00Z"
        ),
        snapshot=first_snapshot,
    )
    first_chain = ClaimPostureAlertLifecycleChain.create(
        key="lifecycle-review-chain",
        created_at=UtcTimestamp.parse(
            "2026-07-16T17:12:00Z"
        ),
        producer_id=chain_system.actor_id,
        claim_catalog_digest=catalog_digest,
        actor_registry=registry,
        entries=(
            first_entry,
        ),
    )

    second_snapshot = _lifecycle_snapshot(
        key="review-docket-generation-two",
        compared_at="2026-07-16T17:20:00Z",
        prior_docket_key="review-docket-one",
        current_docket_key="review-docket-two",
        lifecycle_service=lifecycle_service,
        owner=owner,
        registry=registry,
        catalog_digest=catalog_digest,
    )
    second_chain = first_chain.append(
        key="review-docket-entry-two",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T17:21:00Z"
        ),
        created_at=UtcTimestamp.parse(
            "2026-07-16T17:22:00Z"
        ),
        snapshot=second_snapshot,
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        lifecycle_service=lifecycle_service,
        chain_system=chain_system,
        checkpoint_ledger_service=checkpoint_ledger_service,
        currency_system=currency_system,
        review_docket_system=review_docket_system,
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


def _checkpoint_ledger(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    checkpoints: tuple[
        ClaimPostureAlertLifecycleCheckpoint,
        ...,
    ] = (),
    key: str = "lifecycle-review-checkpoint-ledger",
    created_at: str = "2026-07-16T17:14:00Z",
) -> ClaimPostureAlertLifecycleCheckpointLedger:
    return ClaimPostureAlertLifecycleCheckpointLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.checkpoint_ledger_service.actor_id,
        chain=chain,
        actor_registry=runtime.registry,
        checkpoints=checkpoints,
    )


def _currency(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    checkpoint_ledger: (
        ClaimPostureAlertLifecycleCheckpointLedger
    ),
    assessed_at: str,
) -> ClaimPostureAlertLifecycleCheckpointCurrencySnapshot:
    return (
        ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        .assess(
            key="lifecycle-review-currency",
            assessed_at=UtcTimestamp.parse(
                assessed_at
            ),
            produced_by_id=runtime.currency_system.actor_id,
            chain=chain,
            checkpoint_ledger=checkpoint_ledger,
            actor_registry=runtime.registry,
        )
    )


def _review_docket(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    currency: (
        ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
    ),
    generated_at: str,
) -> ClaimPostureAlertLifecycleReviewDocket:
    return ClaimPostureAlertLifecycleReviewDocket.create(
        key="current-lifecycle-review-docket",
        generated_at=UtcTimestamp.parse(
            generated_at
        ),
        produced_by_id=runtime.review_docket_system.actor_id,
        chain=chain,
        currency_snapshot=currency,
        actor_registry=runtime.registry,
    )


def test_accepted_current_head_produces_clear_review_docket() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="accept-current-review-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T17:13:00Z",
    )
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            accepted,
        ),
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    assert docket.status is (
        ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
    )
    assert docket.reason is None
    assert docket.priority is (
        ClaimPostureAlertLifecycleReviewPriority.NONE
    )
    assert docket.requires_human_action is False
    assert docket.requires_human_review is False
    assert docket.requires_corrective_action is False
    assert docket.continuity_reliance_allowed is True
    assert docket.accepted_review_covers_current_head is True


def test_unreviewed_current_head_opens_review_requirement() -> None:
    runtime = _runtime()
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    assert currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.NO_REVIEW
    )
    assert docket.status is (
        ClaimPostureAlertLifecycleReviewDocketStatus
        .REVIEW_REQUIRED
    )
    assert docket.reason is (
        ClaimPostureAlertLifecycleReviewReason
        .CURRENT_HEAD_UNREVIEWED
    )
    assert docket.priority is (
        ClaimPostureAlertLifecycleReviewPriority.HIGH
    )
    assert docket.requires_human_action is True
    assert docket.requires_human_review is True
    assert docket.continuity_reliance_allowed is False
    assert docket.latest_checkpoint_id is None


def test_deferred_current_review_remains_explicitly_open() -> None:
    runtime = _runtime()
    deferred = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="defer-current-review-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
        decided_at="2026-07-16T17:13:00Z",
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=_checkpoint_ledger(
            runtime,
            chain=runtime.first_chain,
            checkpoints=(
                deferred,
            ),
        ),
        assessed_at="2026-07-16T17:15:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    assert docket.status is (
        ClaimPostureAlertLifecycleReviewDocketStatus
        .REVIEW_DEFERRED
    )
    assert docket.reason is (
        ClaimPostureAlertLifecycleReviewReason
        .CURRENT_REVIEW_DEFERRED
    )
    assert docket.priority is (
        ClaimPostureAlertLifecycleReviewPriority.ROUTINE
    )
    assert docket.requires_human_review is True
    assert docket.continuity_reliance_allowed is False
    assert docket.latest_checkpoint_id == deferred.checkpoint_id


def test_rejected_current_review_requires_corrective_action() -> None:
    runtime = _runtime()
    rejected = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="reject-current-review-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED
        ),
        decided_at="2026-07-16T17:13:00Z",
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=_checkpoint_ledger(
            runtime,
            chain=runtime.first_chain,
            checkpoints=(
                rejected,
            ),
        ),
        assessed_at="2026-07-16T17:15:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    assert docket.status is (
        ClaimPostureAlertLifecycleReviewDocketStatus
        .CORRECTIVE_ACTION_REQUIRED
    )
    assert docket.reason is (
        ClaimPostureAlertLifecycleReviewReason
        .CURRENT_CONTINUITY_REJECTED
    )
    assert docket.priority is (
        ClaimPostureAlertLifecycleReviewPriority.CRITICAL
    )
    assert docket.requires_corrective_action is True
    assert docket.requires_human_review is False
    assert docket.is_urgent is True
    assert docket.continuity_reliance_allowed is False


def test_accepted_prior_review_becomes_stale_after_chain_advances() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="accept-prior-review-head",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T17:13:00Z",
    )
    prior_ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            accepted,
        ),
    )
    stale_currency = _currency(
        runtime,
        chain=runtime.second_chain,
        checkpoint_ledger=prior_ledger,
        assessed_at="2026-07-16T17:23:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.second_chain,
        currency=stale_currency,
        generated_at="2026-07-16T17:24:00Z",
    )

    assert stale_currency.status is (
        ClaimPostureAlertLifecycleCheckpointCurrencyStatus.STALE
    )
    assert docket.status is (
        ClaimPostureAlertLifecycleReviewDocketStatus
        .REVIEW_REQUIRED
    )
    assert docket.reason is (
        ClaimPostureAlertLifecycleReviewReason
        .PRIOR_REVIEW_STALE
    )
    assert docket.priority is (
        ClaimPostureAlertLifecycleReviewPriority.HIGH
    )
    assert docket.generation_count == 2
    assert docket.continuity_reliance_allowed is False
    assert docket.accepted_review_covers_current_head is False
    assert docket.latest_checkpoint_id == accepted.checkpoint_id


def test_review_docket_requires_currency_for_exact_current_chain() -> None:
    runtime = _runtime()
    first_ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
    )
    first_currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=first_ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="current lifecycle-chain digest",
    ):
        _review_docket(
            runtime,
            chain=runtime.second_chain,
            currency=first_currency,
            generated_at="2026-07-16T17:24:00Z",
        )


def test_review_docket_rejects_rewritten_current_head() -> None:
    runtime = _runtime()
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )
    rewritten_head = replace(
        runtime.first_chain.entries[0],
        entry_id=_identifier(
            "claim-posture-alert-lifecycle-chain-entry",
            "rewritten-review-head",
        ),
    )
    rewritten_chain = replace(
        runtime.first_chain,
        entries=(
            rewritten_head,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="current lifecycle-chain digest",
    ):
        _review_docket(
            runtime,
            chain=rewritten_chain,
            currency=currency,
            generated_at="2026-07-16T17:16:00Z",
        )


def test_review_docket_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertLifecycleReviewDocket.create(
            key="human-produced-review-docket",
            generated_at=UtcTimestamp.parse(
                "2026-07-16T17:16:00Z"
            ),
            produced_by_id=runtime.reviewer.actor_id,
            chain=runtime.first_chain,
            currency_snapshot=currency,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-review-docket-service",
        display_name="Unowned Review Docket Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-review-docket-actors",
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
        ClaimPostureAlertLifecycleReviewDocket.create(
            key="unowned-produced-review-docket",
            generated_at=UtcTimestamp.parse(
                "2026-07-16T17:16:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            chain=runtime.first_chain,
            currency_snapshot=currency,
            actor_registry=expanded_registry,
        )


def test_review_docket_must_not_predate_currency_snapshot() -> None:
    runtime = _runtime()
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the checkpoint-currency snapshot",
    ):
        _review_docket(
            runtime,
            chain=runtime.first_chain,
            currency=currency,
            generated_at="2026-07-16T17:14:59Z",
        )


def test_review_docket_checkpoint_fields_must_be_complete() -> None:
    runtime = _runtime()
    accepted = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="complete-checkpoint-fields",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        decided_at="2026-07-16T17:13:00Z",
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=_checkpoint_ledger(
            runtime,
            chain=runtime.first_chain,
            checkpoints=(
                accepted,
            ),
        ),
        assessed_at="2026-07-16T17:15:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must be present or absent together",
    ):
        replace(
            docket,
            latest_checkpoint_digest=None,
        )


def test_review_docket_is_non_authorizing_and_non_certifying() -> None:
    runtime = _runtime()
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )
    docket = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    assert docket.approves_underlying_claims is False
    assert docket.clears_alerts is False
    assert docket.changes_claim_state is False
    assert docket.grants_authority is False
    assert docket.claims_certification is False
    assert docket.digest().verifies(
        docket.to_payload()
    ) is True


def test_review_docket_is_deterministic() -> None:
    runtime = _runtime()
    deferred = _checkpoint(
        runtime,
        chain=runtime.first_chain,
        key="stable-deferred-review",
        status=(
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        ),
        decided_at="2026-07-16T17:13:00Z",
    )
    ledger = _checkpoint_ledger(
        runtime,
        chain=runtime.first_chain,
        checkpoints=(
            deferred,
        ),
        key="stable-review-ledger",
    )
    currency = _currency(
        runtime,
        chain=runtime.first_chain,
        checkpoint_ledger=ledger,
        assessed_at="2026-07-16T17:15:00Z",
    )

    first = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )
    second = _review_docket(
        runtime,
        chain=runtime.first_chain,
        currency=currency,
        generated_at="2026-07-16T17:16:00Z",
    )

    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()
