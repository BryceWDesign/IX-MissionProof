"""Tests for lifecycle-review follow-up snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlertLifecycleCheckpointStatus,
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
    ClaimPostureAlertLifecycleReviewFollowUpSnapshot,
    ClaimPostureAlertLifecycleReviewFollowUpStatus,
    ClaimPostureAlertLifecycleReviewPriority,
    ClaimPostureAlertLifecycleReviewReason,
    ClaimPostureAlertLifecycleReviewResponse,
    ClaimPostureAlertLifecycleReviewResponseAction,
    ClaimPostureAlertLifecycleReviewResponseLedger,
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
    responder: ActorIdentity
    assignee: ActorIdentity
    review_system: ActorIdentity
    response_service: ActorIdentity
    follow_up_system: ActorIdentity
    registry: ActorRegistry


def _runtime() -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-follow-up-owner",
        display_name="Review Follow-Up Owner",
    )
    responder = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-follow-up-responder",
        display_name="Review Follow-Up Responder",
    )
    assignee = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-follow-up-assignee",
        display_name="Review Follow-Up Assignee",
    )
    review_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-follow-up-docket-system",
        display_name="Review Follow-Up Docket System",
        accountability_owner_id=owner.actor_id,
    )
    response_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-follow-up-response-service",
        display_name="Review Follow-Up Response Service",
        accountability_owner_id=owner.actor_id,
    )
    follow_up_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-follow-up-system",
        display_name="Review Follow-Up System",
        accountability_owner_id=owner.actor_id,
    )
    registry = ActorRegistry.create(
        key="review-follow-up-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T19:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            responder,
            assignee,
            review_system,
            response_service,
            follow_up_system,
        ),
    )

    return _Runtime(
        owner=owner,
        responder=responder,
        assignee=assignee,
        review_system=review_system,
        response_service=response_service,
        follow_up_system=follow_up_system,
        registry=registry,
    )


def _review_docket(
    runtime: _Runtime,
    *,
    key: str,
    status: ClaimPostureAlertLifecycleReviewDocketStatus,
) -> ClaimPostureAlertLifecycleReviewDocket:
    reason: ClaimPostureAlertLifecycleReviewReason | None
    priority: ClaimPostureAlertLifecycleReviewPriority
    checkpoint_status: (
        ClaimPostureAlertLifecycleCheckpointStatus | None
    )

    if status is (
        ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
    ):
        reason = None
        priority = ClaimPostureAlertLifecycleReviewPriority.NONE
        checkpoint_status = (
            ClaimPostureAlertLifecycleCheckpointStatus.ACCEPTED
        )
    elif status is (
        ClaimPostureAlertLifecycleReviewDocketStatus
        .REVIEW_REQUIRED
    ):
        reason = (
            ClaimPostureAlertLifecycleReviewReason
            .CURRENT_HEAD_UNREVIEWED
        )
        priority = ClaimPostureAlertLifecycleReviewPriority.HIGH
        checkpoint_status = None
    elif status is (
        ClaimPostureAlertLifecycleReviewDocketStatus
        .REVIEW_DEFERRED
    ):
        reason = (
            ClaimPostureAlertLifecycleReviewReason
            .CURRENT_REVIEW_DEFERRED
        )
        priority = ClaimPostureAlertLifecycleReviewPriority.HIGH
        checkpoint_status = (
            ClaimPostureAlertLifecycleCheckpointStatus.DEFERRED
        )
    else:
        reason = (
            ClaimPostureAlertLifecycleReviewReason
            .CURRENT_CONTINUITY_REJECTED
        )
        priority = (
            ClaimPostureAlertLifecycleReviewPriority.CRITICAL
        )
        checkpoint_status = (
            ClaimPostureAlertLifecycleCheckpointStatus.REJECTED
        )

    checkpoint_id = (
        _identifier(
            "claim-posture-alert-lifecycle-checkpoint",
            f"{key}-checkpoint",
        )
        if checkpoint_status is not None
        else None
    )
    checkpoint_digest = (
        _digest(
            "claim-posture-alert-lifecycle-checkpoint",
            f"{key}-checkpoint",
        )
        if checkpoint_status is not None
        else None
    )

    return ClaimPostureAlertLifecycleReviewDocket(
        docket_id=_identifier(
            "claim-posture-alert-lifecycle-review-docket",
            key,
        ),
        generated_at=UtcTimestamp.parse(
            "2026-07-16T19:10:00Z"
        ),
        produced_by_id=runtime.review_system.actor_id,
        producer_kind=runtime.review_system.kind,
        producer_accountability_owner_id=runtime.owner.actor_id,
        status=status,
        reason=reason,
        priority=priority,
        chain_id=_identifier(
            "claim-posture-alert-lifecycle-chain",
            f"{key}-chain",
        ),
        generation_count=3,
        head_entry_id=_identifier(
            "claim-posture-alert-lifecycle-chain-entry",
            f"{key}-head",
        ),
        current_docket_id=_identifier(
            "claim-posture-alert-docket",
            f"{key}-current-alerts",
        ),
        active_alert_count=1,
        checkpoint_currency_snapshot_id=_identifier(
            (
                "claim-posture-alert-lifecycle-"
                "checkpoint-currency-snapshot"
            ),
            f"{key}-currency",
        ),
        latest_checkpoint_id=checkpoint_id,
        latest_checkpoint_status=checkpoint_status,
        chain_digest=_digest(
            "claim-posture-alert-lifecycle-chain",
            f"{key}-chain",
        ),
        head_entry_digest=_digest(
            "claim-posture-alert-lifecycle-chain-entry",
            f"{key}-head",
        ),
        current_alert_docket_digest=_digest(
            "claim-posture-alert-docket",
            f"{key}-current-alerts",
        ),
        checkpoint_currency_snapshot_digest=_digest(
            (
                "claim-posture-alert-lifecycle-"
                "checkpoint-currency-snapshot"
            ),
            f"{key}-currency",
        ),
        latest_checkpoint_digest=checkpoint_digest,
        claim_catalog_digest=_digest(
            "claim-catalog",
            "review-follow-up-catalog",
        ),
        actor_registry_digest=runtime.registry.digest(),
    )


def _response(
    runtime: _Runtime,
    *,
    docket: ClaimPostureAlertLifecycleReviewDocket,
    key: str,
    action: ClaimPostureAlertLifecycleReviewResponseAction,
    responded_at: str,
    assigned_to_id: ScopedIdentifier | None = None,
    action_due_at: str | None = None,
) -> ClaimPostureAlertLifecycleReviewResponse:
    return ClaimPostureAlertLifecycleReviewResponse.respond(
        key=key,
        responded_at=UtcTimestamp.parse(
            responded_at
        ),
        responded_by_id=runtime.responder.actor_id,
        action=action,
        rationale=f"Operational response: {action.value}.",
        review_docket=docket,
        actor_registry=runtime.registry,
        assigned_to_id=assigned_to_id,
        action_due_at=(
            UtcTimestamp.parse(
                action_due_at
            )
            if action_due_at is not None
            else None
        ),
    )


def _ledger(
    runtime: _Runtime,
    *,
    docket: ClaimPostureAlertLifecycleReviewDocket,
    responses: tuple[
        ClaimPostureAlertLifecycleReviewResponse,
        ...,
    ] = (),
    key: str = "review-follow-up-responses",
    created_at: str = "2026-07-16T19:20:00Z",
) -> ClaimPostureAlertLifecycleReviewResponseLedger:
    return ClaimPostureAlertLifecycleReviewResponseLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.response_service.actor_id,
        review_docket=docket,
        actor_registry=runtime.registry,
        responses=responses,
    )


def _follow_up(
    runtime: _Runtime,
    *,
    docket: ClaimPostureAlertLifecycleReviewDocket,
    ledger: ClaimPostureAlertLifecycleReviewResponseLedger,
    assessed_at: str = "2026-07-16T19:21:00Z",
) -> ClaimPostureAlertLifecycleReviewFollowUpSnapshot:
    return (
        ClaimPostureAlertLifecycleReviewFollowUpSnapshot
        .assess(
            key="current-review-follow-up",
            assessed_at=UtcTimestamp.parse(
                assessed_at
            ),
            produced_by_id=runtime.follow_up_system.actor_id,
            review_docket=docket,
            response_ledger=ledger,
            actor_registry=runtime.registry,
        )
    )


def test_clear_review_docket_produces_clear_follow_up() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="clear-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ),
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
        ),
    )

    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus.CLEAR
    )
    assert follow_up.obligation_remains_open is False
    assert follow_up.has_response is False
    assert follow_up.requires_human_action is False
    assert follow_up.immediate_follow_up_required is False
    assert follow_up.response_resolves_obligation is False


def test_unresponded_review_obligation_requires_follow_up() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="unresponded-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
        ),
    )

    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus
        .UNRESPONDED
    )
    assert follow_up.obligation_remains_open is True
    assert follow_up.has_response is False
    assert follow_up.response_count == 0
    assert follow_up.requires_human_action is True
    assert follow_up.immediate_follow_up_required is True
    assert follow_up.response_tracks_obligation is False


def test_acknowledgment_tracks_but_does_not_resolve_review() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="acknowledged-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    acknowledgment = _response(
        runtime,
        docket=docket,
        key="acknowledge-review-follow-up",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ACKNOWLEDGE
        ),
        responded_at="2026-07-16T19:11:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
            responses=(
                acknowledgment,
            ),
        ),
    )

    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus
        .ACKNOWLEDGED
    )
    assert follow_up.has_response is True
    assert follow_up.has_assignment is False
    assert follow_up.response_tracks_obligation is True
    assert follow_up.immediate_follow_up_required is False
    assert follow_up.obligation_remains_open is True
    assert follow_up.response_resolves_obligation is False
    assert follow_up.accepts_continuity is False


def test_assigned_review_is_tracked_until_due() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="assigned-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="assign-review-follow-up",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T19:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T19:11:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
            responses=(
                assignment,
            ),
        ),
    )

    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus
        .REVIEW_ASSIGNED
    )
    assert follow_up.has_response is True
    assert follow_up.has_assignment is True
    assert follow_up.assigned_to_id == runtime.assignee.actor_id
    assert follow_up.is_overdue is False
    assert follow_up.immediate_follow_up_required is False
    assert follow_up.requires_human_action is True


def test_overdue_assignment_requires_immediate_follow_up() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="overdue-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="overdue-review-assignment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T19:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-16T20:00:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
            responses=(
                assignment,
            ),
        ),
        assessed_at="2026-07-16T20:00:01Z",
    )

    assert follow_up.is_overdue is True
    assert follow_up.immediate_follow_up_required is True
    assert follow_up.obligation_remains_open is True
    assert follow_up.response_resolves_obligation is False


def test_latest_response_controls_follow_up_status() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="latest-response-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    acknowledgment = _response(
        runtime,
        docket=docket,
        key="first-follow-up-acknowledgment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ACKNOWLEDGE
        ),
        responded_at="2026-07-16T19:11:00Z",
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="later-follow-up-assignment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T19:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T19:12:00Z",
    )
    ledger = _ledger(
        runtime,
        docket=docket,
        responses=(
            acknowledgment,
            assignment,
        ),
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=ledger,
    )

    assert follow_up.response_count == 2
    assert follow_up.latest_response_id == assignment.response_id
    assert follow_up.latest_response_action is (
        ClaimPostureAlertLifecycleReviewResponseAction
        .ASSIGN_REVIEW
    )
    assert follow_up.latest_response_digest == assignment.digest()
    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus
        .REVIEW_ASSIGNED
    )


def test_escalation_is_explicit_but_does_not_close_obligation() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="escalated-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    escalation = _response(
        runtime,
        docket=docket,
        key="escalate-review-follow-up",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ESCALATE
        ),
        responded_at="2026-07-16T19:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-16T21:00:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
            responses=(
                escalation,
            ),
        ),
    )

    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus.ESCALATED
    )
    assert follow_up.escalated is True
    assert follow_up.has_assignment is True
    assert follow_up.obligation_remains_open is True
    assert follow_up.response_resolves_obligation is False


def test_corrective_action_is_tracked_for_rejected_continuity() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="corrective-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .CORRECTIVE_ACTION_REQUIRED
        ),
    )
    corrective_action = _response(
        runtime,
        docket=docket,
        key="open-corrective-review-follow-up",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .OPEN_CORRECTIVE_ACTION
        ),
        responded_at="2026-07-16T19:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T19:11:00Z",
    )
    follow_up = _follow_up(
        runtime,
        docket=docket,
        ledger=_ledger(
            runtime,
            docket=docket,
            responses=(
                corrective_action,
            ),
        ),
    )

    assert follow_up.status is (
        ClaimPostureAlertLifecycleReviewFollowUpStatus
        .CORRECTIVE_ACTION_OPEN
    )
    assert follow_up.corrective_action_open is True
    assert follow_up.has_assignment is True
    assert follow_up.obligation_remains_open is True
    assert follow_up.accepts_continuity is False


def test_follow_up_rejects_ledger_for_different_review_docket() -> None:
    runtime = _runtime()
    first_docket = _review_docket(
        runtime,
        key="first-follow-up-docket",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    second_docket = _review_docket(
        runtime,
        key="second-follow-up-docket",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    foreign_ledger = _ledger(
        runtime,
        docket=first_docket,
    )

    with pytest.raises(
        FoundationError,
        match="different lifecycle-review docket",
    ):
        _follow_up(
            runtime,
            docket=second_docket,
            ledger=foreign_ledger,
        )


def test_follow_up_rejects_rewritten_response_ledger_binding() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="rewritten-follow-up-binding",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    ledger = _ledger(
        runtime,
        docket=docket,
    )
    rewritten = replace(
        ledger,
        chain_digest=_digest(
            "claim-posture-alert-lifecycle-chain",
            "different-follow-up-chain",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="lifecycle chain",
    ):
        _follow_up(
            runtime,
            docket=docket,
            ledger=rewritten,
        )


def test_follow_up_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="follow-up-producer-validation",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    ledger = _ledger(
        runtime,
        docket=docket,
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        (
            ClaimPostureAlertLifecycleReviewFollowUpSnapshot
            .assess(
                key="human-produced-review-follow-up",
                assessed_at=UtcTimestamp.parse(
                    "2026-07-16T19:21:00Z"
                ),
                produced_by_id=runtime.responder.actor_id,
                review_docket=docket,
                response_ledger=ledger,
                actor_registry=runtime.registry,
            )
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-review-follow-up-service",
        display_name="Unowned Review Follow-Up Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-review-follow-up-actors",
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
            ClaimPostureAlertLifecycleReviewFollowUpSnapshot
            .assess(
                key="unowned-produced-review-follow-up",
                assessed_at=UtcTimestamp.parse(
                    "2026-07-16T19:21:00Z"
                ),
                produced_by_id=unowned_service.actor_id,
                review_docket=docket,
                response_ledger=ledger,
                actor_registry=expanded_registry,
            )
        )


def test_follow_up_must_not_predate_response_ledger() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="follow-up-time-validation",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    ledger = _ledger(
        runtime,
        docket=docket,
        created_at="2026-07-16T19:22:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the review-response ledger",
    ):
        _follow_up(
            runtime,
            docket=docket,
            ledger=ledger,
            assessed_at="2026-07-16T19:21:00Z",
        )


def test_follow_up_is_reporting_only_and_deterministic() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="stable-review-follow-up",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="stable-review-follow-up-assignment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T19:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T19:11:00Z",
    )
    ledger = _ledger(
        runtime,
        docket=docket,
        responses=(
            assignment,
        ),
        key="stable-review-follow-up-ledger",
    )

    first = _follow_up(
        runtime,
        docket=docket,
        ledger=ledger,
    )
    second = _follow_up(
        runtime,
        docket=docket,
        ledger=ledger,
    )

    assert first.response_resolves_obligation is False
    assert first.accepts_continuity is False
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
