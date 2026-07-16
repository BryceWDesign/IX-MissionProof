"""Tests for lifecycle-review resolution snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlertLifecycleChain,
    ClaimPostureAlertLifecycleChainEntry,
    ClaimPostureAlertLifecycleCheckpoint,
    ClaimPostureAlertLifecycleCheckpointCurrencySnapshot,
    ClaimPostureAlertLifecycleCheckpointLedger,
    ClaimPostureAlertLifecycleCheckpointStatus,
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
    ClaimPostureAlertLifecycleReviewFollowUpSnapshot,
    ClaimPostureAlertLifecycleReviewResolutionSnapshot,
    ClaimPostureAlertLifecycleReviewResolutionStatus,
    ClaimPostureAlertLifecycleReviewResponse,
    ClaimPostureAlertLifecycleReviewResponseAction,
    ClaimPostureAlertLifecycleReviewResponseLedger,
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
    responder: ActorIdentity
    assignee: ActorIdentity
    lifecycle_service: ActorIdentity
    chain_system: ActorIdentity
    checkpoint_ledger_service: ActorIdentity
    currency_system: ActorIdentity
    review_docket_system: ActorIdentity
    response_service: ActorIdentity
    follow_up_system: ActorIdentity
    resolution_system: ActorIdentity
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
        key="review-resolution-owner",
        display_name="Review Resolution Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-resolution-reviewer",
        display_name="Review Resolution Reviewer",
    )
    responder = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-resolution-responder",
        display_name="Review Resolution Responder",
    )
    assignee = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-resolution-assignee",
        display_name="Review Resolution Assignee",
    )
    lifecycle_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-resolution-lifecycle-service",
        display_name="Review Resolution Lifecycle Service",
        accountability_owner_id=owner.actor_id,
    )
    chain_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-resolution-chain-system",
        display_name="Review Resolution Chain System",
        accountability_owner_id=owner.actor_id,
    )
    checkpoint_ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-resolution-checkpoint-ledger-service",
        display_name="Review Resolution Checkpoint Ledger Service",
        accountability_owner_id=reviewer.actor_id,
    )
    currency_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-resolution-currency-system",
        display_name="Review Resolution Currency System",
        accountability_owner_id=reviewer.actor_id,
    )
    review_docket_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-resolution-docket-system",
        display_name="Review Resolution Docket System",
        accountability_owner_id=reviewer.actor_id,
    )
    response_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-resolution-response-service",
        display_name="Review Resolution Response Service",
        accountability_owner_id=owner.actor_id,
    )
    follow_up_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-resolution-follow-up-system",
        display_name="Review Resolution Follow-Up System",
        accountability_owner_id=owner.actor_id,
    )
    resolution_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-resolution-system",
        display_name="Review Resolution System",
        accountability_owner_id=owner.actor_id,
    )
    registry = ActorRegistry.create(
        key="review-resolution-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T20:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            reviewer,
            responder,
            assignee,
            lifecycle_service,
            chain_system,
            checkpoint_ledger_service,
            currency_system,
            review_docket_system,
            response_service,
            follow_up_system,
            resolution_system,
        ),
    )
    catalog_digest = _digest(
        "claim-catalog",
        "review-resolution-catalog",
    )

    first_snapshot = _lifecycle_snapshot(
        key="review-resolution-generation-one",
        compared_at="2026-07-16T20:10:00Z",
        prior_docket_key="review-resolution-docket-zero",
        current_docket_key="review-resolution-docket-one",
        lifecycle_service=lifecycle_service,
        owner=owner,
        registry=registry,
        catalog_digest=catalog_digest,
    )
    first_entry = ClaimPostureAlertLifecycleChainEntry.link(
        key="review-resolution-entry-one",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T20:11:00Z"
        ),
        snapshot=first_snapshot,
    )
    first_chain = ClaimPostureAlertLifecycleChain.create(
        key="review-resolution-chain",
        created_at=UtcTimestamp.parse(
            "2026-07-16T20:12:00Z"
        ),
        producer_id=chain_system.actor_id,
        claim_catalog_digest=catalog_digest,
        actor_registry=registry,
        entries=(
            first_entry,
        ),
    )

    second_snapshot = _lifecycle_snapshot(
        key="review-resolution-generation-two",
        compared_at="2026-07-16T20:30:00Z",
        prior_docket_key="review-resolution-docket-one",
        current_docket_key="review-resolution-docket-two",
        lifecycle_service=lifecycle_service,
        owner=owner,
        registry=registry,
        catalog_digest=catalog_digest,
    )
    second_chain = first_chain.append(
        key="review-resolution-entry-two",
        linked_at=UtcTimestamp.parse(
            "2026-07-16T20:31:00Z"
        ),
        created_at=UtcTimestamp.parse(
            "2026-07-16T20:32:00Z"
        ),
        snapshot=second_snapshot,
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        responder=responder,
        assignee=assignee,
        lifecycle_service=lifecycle_service,
        chain_system=chain_system,
        checkpoint_ledger_service=checkpoint_ledger_service,
        currency_system=currency_system,
        review_docket_system=review_docket_system,
        response_service=response_service,
        follow_up_system=follow_up_system,
        resolution_system=resolution_system,
        registry=registry,
        catalog_digest=catalog_digest,
        first_chain=first_chain,
        second_chain=second_chain,
    )


def _checkpoint(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    status: ClaimPostureAlertLifecycleCheckpointStatus,
    key: str,
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


def _review_state(
    runtime: _Runtime,
    *,
    chain: ClaimPostureAlertLifecycleChain,
    checkpoint_status: (
        ClaimPostureAlertLifecycleCheckpointStatus | None
    ),
    key: str,
    checkpoint_time: str = "2026-07-16T20:13:00Z",
    ledger_time: str = "2026-07-16T20:14:00Z",
    currency_time: str = "2026-07-16T20:15:00Z",
    docket_time: str = "2026-07-16T20:16:00Z",
) -> tuple[
    ClaimPostureAlertLifecycleCheckpointCurrencySnapshot,
    ClaimPostureAlertLifecycleReviewDocket,
]:
    checkpoints: tuple[
        ClaimPostureAlertLifecycleCheckpoint,
        ...,
    ]

    if checkpoint_status is None:
        checkpoints = ()
    else:
        checkpoints = (
            _checkpoint(
                runtime,
                chain=chain,
                status=checkpoint_status,
                key=f"{key}-checkpoint",
                decided_at=checkpoint_time,
            ),
        )

    ledger = ClaimPostureAlertLifecycleCheckpointLedger.create(
        key=f"{key}-checkpoint-ledger",
        created_at=UtcTimestamp.parse(
            ledger_time
        ),
        producer_id=runtime.checkpoint_ledger_service.actor_id,
        chain=chain,
        actor_registry=runtime.registry,
        checkpoints=checkpoints,
    )
    currency = (
        ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
        .assess(
            key=f"{key}-currency",
            assessed_at=UtcTimestamp.parse(
                currency_time
            ),
            produced_by_id=runtime.currency_system.actor_id,
            chain=chain,
            checkpoint_ledger=ledger,
            actor_registry=runtime.registry,
        )
    )
    docket = ClaimPostureAlertLifecycleReviewDocket.create(
        key=f"{key}-review-docket",
        generated_at=UtcTimestamp.parse(
            docket_time
        ),
        produced_by_id=runtime.review_docket_system.actor_id,
        chain=chain,
        currency_snapshot=currency,
        actor_registry=runtime.registry,
    )

    return currency, docket


def _response(
    runtime: _Runtime,
    *,
    docket: ClaimPostureAlertLifecycleReviewDocket,
    key: str,
    responded_at: str,
    due_at: str,
) -> ClaimPostureAlertLifecycleReviewResponse:
    return ClaimPostureAlertLifecycleReviewResponse.respond(
        key=key,
        responded_at=UtcTimestamp.parse(
            responded_at
        ),
        responded_by_id=runtime.responder.actor_id,
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        rationale="Assign independent continuity review.",
        review_docket=docket,
        actor_registry=runtime.registry,
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at=UtcTimestamp.parse(
            due_at
        ),
    )


def _follow_up(
    runtime: _Runtime,
    *,
    docket: ClaimPostureAlertLifecycleReviewDocket,
    responses: tuple[
        ClaimPostureAlertLifecycleReviewResponse,
        ...,
    ] = (),
    ledger_time: str = "2026-07-16T20:18:00Z",
    assessed_at: str = "2026-07-16T20:19:00Z",
    key: str = "previous-review-follow-up",
) -> ClaimPostureAlertLifecycleReviewFollowUpSnapshot:
    ledger = ClaimPostureAlertLifecycleReviewResponseLedger.create(
        key=f"{key}-responses",
        created_at=UtcTimestamp.parse(
            ledger_time
        ),
        producer_id=runtime.response_service.actor_id,
        review_docket=docket,
        actor_registry=runtime.registry,
        responses=responses,
    )

    return (
        ClaimPostureAlertLifecycleReviewFollowUpSnapshot
        .assess(
            key=key,
            assessed_at=UtcTimestamp.parse(
                assessed_at
            ),
            produced_by_id=runtime.follow_up_system.actor_id,
            review_docket=docket,
            response_ledger=ledger,
            actor_registry=runtime.registry,
        )
    )


def _resolution(
    runtime: _Runtime,
    *,
    previous_docket: ClaimPostureAlertLifecycleReviewDocket,
    previous_follow_up: (
        ClaimPostureAlertLifecycleReviewFollowUpSnapshot
    ),
    current_chain: ClaimPostureAlertLifecycleChain,
    current_currency: (
        ClaimPostureAlertLifecycleCheckpointCurrencySnapshot
    ),
    current_docket: ClaimPostureAlertLifecycleReviewDocket,
    reconciled_at: str = "2026-07-16T20:40:00Z",
) -> ClaimPostureAlertLifecycleReviewResolutionSnapshot:
    return (
        ClaimPostureAlertLifecycleReviewResolutionSnapshot
        .reconcile(
            key="current-review-resolution",
            reconciled_at=UtcTimestamp.parse(
                reconciled_at
            ),
            produced_by_id=runtime.resolution_system.actor_id,
            previous_review_docket=previous_docket,
            previous_follow_up=previous_follow_up,
            current_chain=current_chain,
            current_currency_snapshot=current_currency,
            current_review_docket=current_docket,
            actor_registry=runtime.registry,
        )
    )


def test_unresponded_same_docket_remains_open() -> None:
    runtime = _runtime()
    currency, docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="unresponded-state",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
    )
    resolution = _resolution(
        runtime,
        previous_docket=docket,
        previous_follow_up=follow_up,
        current_chain=runtime.first_chain,
        current_currency=currency,
        current_docket=docket,
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .OPEN_UNRESPONDED
    )
    assert resolution.previous_review_docket_is_current is True
    assert resolution.previous_response_count == 0
    assert resolution.current_obligation_open is True
    assert resolution.requires_immediate_attention is True
    assert resolution.resolved_by_response_activity is False


def test_current_response_is_tracked_but_does_not_resolve() -> None:
    runtime = _runtime()
    currency, docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="tracked-state",
    )
    response = _response(
        runtime,
        docket=docket,
        key="tracked-review-response",
        responded_at="2026-07-16T20:17:00Z",
        due_at="2026-07-17T20:17:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        responses=(
            response,
        ),
    )
    resolution = _resolution(
        runtime,
        previous_docket=docket,
        previous_follow_up=follow_up,
        current_chain=runtime.first_chain,
        current_currency=currency,
        current_docket=docket,
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .OPEN_TRACKED
    )
    assert resolution.previous_response_carries_forward is True
    assert resolution.previous_assigned_to_id == (
        runtime.assignee.actor_id
    )
    assert resolution.prior_obligation_resolved is False
    assert resolution.resolved_by_response_activity is False


def test_overdue_current_response_requires_immediate_attention() -> None:
    runtime = _runtime()
    currency, docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="overdue-state",
    )
    response = _response(
        runtime,
        docket=docket,
        key="overdue-review-response",
        responded_at="2026-07-16T20:17:00Z",
        due_at="2026-07-16T20:30:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        responses=(
            response,
        ),
    )
    resolution = _resolution(
        runtime,
        previous_docket=docket,
        previous_follow_up=follow_up,
        current_chain=runtime.first_chain,
        current_currency=currency,
        current_docket=docket,
        reconciled_at="2026-07-16T20:40:00Z",
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .OPEN_OVERDUE
    )
    assert resolution.previous_follow_up_overdue is True
    assert resolution.requires_immediate_attention is True
    assert resolution.current_obligation_open is True


def test_accepted_current_checkpoint_resolves_prior_open_obligation() -> None:
    runtime = _runtime()
    _, previous_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="prior-open-state",
    )
    response = _response(
        runtime,
        docket=previous_docket,
        key="prior-open-response",
        responded_at="2026-07-16T20:17:00Z",
        due_at="2026-07-17T20:17:00Z",
    )
    previous_follow_up = _follow_up(
        runtime,
        docket=previous_docket,
        responses=(
            response,
        ),
    )
    current_currency, current_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        key="accepted-current-state",
        checkpoint_time="2026-07-16T20:20:00Z",
        ledger_time="2026-07-16T20:21:00Z",
        currency_time="2026-07-16T20:22:00Z",
        docket_time="2026-07-16T20:23:00Z",
    )
    resolution = _resolution(
        runtime,
        previous_docket=previous_docket,
        previous_follow_up=previous_follow_up,
        current_chain=runtime.first_chain,
        current_currency=current_currency,
        current_docket=current_docket,
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .RESOLVED_BY_ACCEPTED_CHECKPOINT
    )
    assert resolution.resolved_by_current_checkpoint is True
    assert resolution.resolved_by_response_activity is False
    assert resolution.prior_obligation_resolved is True
    assert resolution.current_obligation_open is False
    assert resolution.continuity_reliance_allowed is True
    assert (
        resolution.previous_response_applies_to_current_obligation
        is False
    )


def test_rejected_current_checkpoint_requires_corrective_action() -> None:
    runtime = _runtime()
    _, previous_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="prior-rejected-state",
    )
    previous_follow_up = _follow_up(
        runtime,
        docket=previous_docket,
    )
    current_currency, current_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=(
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED
        ),
        key="rejected-current-state",
        checkpoint_time="2026-07-16T20:20:00Z",
        ledger_time="2026-07-16T20:21:00Z",
        currency_time="2026-07-16T20:22:00Z",
        docket_time="2026-07-16T20:23:00Z",
    )
    resolution = _resolution(
        runtime,
        previous_docket=previous_docket,
        previous_follow_up=previous_follow_up,
        current_chain=runtime.first_chain,
        current_currency=current_currency,
        current_docket=current_docket,
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .CORRECTIVE_ACTION_REQUIRED
    )
    assert resolution.current_obligation_open is True
    assert resolution.requires_human_action is True
    assert resolution.requires_immediate_attention is True
    assert resolution.continuity_reliance_allowed is False


def test_new_chain_head_supersedes_prior_review_and_responses() -> None:
    runtime = _runtime()
    _, previous_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="prior-generation-state",
    )
    response = _response(
        runtime,
        docket=previous_docket,
        key="prior-generation-response",
        responded_at="2026-07-16T20:17:00Z",
        due_at="2026-07-17T20:17:00Z",
    )
    previous_follow_up = _follow_up(
        runtime,
        docket=previous_docket,
        responses=(
            response,
        ),
    )
    current_currency, current_docket = _review_state(
        runtime,
        chain=runtime.second_chain,
        checkpoint_status=None,
        key="new-generation-state",
        ledger_time="2026-07-16T20:33:00Z",
        currency_time="2026-07-16T20:34:00Z",
        docket_time="2026-07-16T20:35:00Z",
    )
    resolution = _resolution(
        runtime,
        previous_docket=previous_docket,
        previous_follow_up=previous_follow_up,
        current_chain=runtime.second_chain,
        current_currency=current_currency,
        current_docket=current_docket,
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .SUPERSEDED_BY_NEW_HEAD
    )
    assert resolution.generation_advanced is True
    assert resolution.same_chain_head is False
    assert resolution.prior_obligation_resolved is True
    assert resolution.current_obligation_open is True
    assert resolution.previous_response_carries_forward is False
    assert (
        resolution.previous_response_applies_to_current_obligation
        is False
    )
    assert resolution.requires_immediate_attention is True


def test_clear_to_clear_has_no_open_obligation() -> None:
    runtime = _runtime()
    previous_currency, previous_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=(
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        ),
        key="previous-clear-state",
    )
    previous_follow_up = _follow_up(
        runtime,
        docket=previous_docket,
    )
    resolution = _resolution(
        runtime,
        previous_docket=previous_docket,
        previous_follow_up=previous_follow_up,
        current_chain=runtime.first_chain,
        current_currency=previous_currency,
        current_docket=previous_docket,
    )

    assert resolution.status is (
        ClaimPostureAlertLifecycleReviewResolutionStatus
        .NO_OPEN_OBLIGATION
    )
    assert resolution.prior_obligation_resolved is True
    assert resolution.current_obligation_open is False
    assert resolution.continuity_reliance_allowed is True


def test_resolution_rejects_follow_up_from_different_docket() -> None:
    runtime = _runtime()
    currency, first_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="binding-first-state",
    )
    _, second_docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="binding-second-state",
        ledger_time="2026-07-16T20:17:00Z",
        currency_time="2026-07-16T20:18:00Z",
        docket_time="2026-07-16T20:19:00Z",
    )
    foreign_follow_up = _follow_up(
        runtime,
        docket=second_docket,
        ledger_time="2026-07-16T20:20:00Z",
        assessed_at="2026-07-16T20:21:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="different lifecycle-review docket",
    ):
        _resolution(
            runtime,
            previous_docket=first_docket,
            previous_follow_up=foreign_follow_up,
            current_chain=runtime.first_chain,
            current_currency=currency,
            current_docket=first_docket,
        )


def test_resolution_rejects_rewritten_prior_chain_head() -> None:
    runtime = _runtime()
    currency, docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="rewritten-prior-head-state",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
    )
    rewritten_docket = replace(
        docket,
        head_entry_id=_identifier(
            "claim-posture-alert-lifecycle-chain-entry",
            "rewritten-prior-head",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="head identity does not match",
    ):
        _resolution(
            runtime,
            previous_docket=rewritten_docket,
            previous_follow_up=replace(
                follow_up,
                review_docket_id=rewritten_docket.docket_id,
                review_docket_digest=rewritten_docket.digest(),
                head_entry_id=rewritten_docket.head_entry_id,
            ),
            current_chain=runtime.first_chain,
            current_currency=currency,
            current_docket=docket,
        )


def test_resolution_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    currency, docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="producer-validation-state",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        (
            ClaimPostureAlertLifecycleReviewResolutionSnapshot
            .reconcile(
                key="human-produced-resolution",
                reconciled_at=UtcTimestamp.parse(
                    "2026-07-16T20:40:00Z"
                ),
                produced_by_id=runtime.responder.actor_id,
                previous_review_docket=docket,
                previous_follow_up=follow_up,
                current_chain=runtime.first_chain,
                current_currency_snapshot=currency,
                current_review_docket=docket,
                actor_registry=runtime.registry,
            )
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-review-resolution-service",
        display_name="Unowned Review Resolution Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-review-resolution-actors",
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
            ClaimPostureAlertLifecycleReviewResolutionSnapshot
            .reconcile(
                key="unowned-produced-resolution",
                reconciled_at=UtcTimestamp.parse(
                    "2026-07-16T20:40:00Z"
                ),
                produced_by_id=unowned_service.actor_id,
                previous_review_docket=docket,
                previous_follow_up=follow_up,
                current_chain=runtime.first_chain,
                current_currency_snapshot=currency,
                current_review_docket=docket,
                actor_registry=expanded_registry,
            )
        )


def test_resolution_is_reporting_only_and_deterministic() -> None:
    runtime = _runtime()
    currency, docket = _review_state(
        runtime,
        chain=runtime.first_chain,
        checkpoint_status=None,
        key="stable-resolution-state",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        key="stable-resolution-follow-up",
    )

    first = _resolution(
        runtime,
        previous_docket=docket,
        previous_follow_up=follow_up,
        current_chain=runtime.first_chain,
        current_currency=currency,
        current_docket=docket,
    )
    second = _resolution(
        runtime,
        previous_docket=docket,
        previous_follow_up=follow_up,
        current_chain=runtime.first_chain,
        current_currency=currency,
        current_docket=docket,
    )

    assert first.resolved_by_response_activity is False
    assert first.approves_underlying_claims is False
    assert first.clears_claim_alerts is False
    assert first.changes_claim_state is False
    assert first.grants_authority is False
    assert first.claims_certification is False
    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()
    assert first.digest().verifies(
        first.to_payload()
    ) is True
