"""Tests for lifecycle-review docket responses."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlertLifecycleCheckpointStatus,
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
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
    ledger_service: ActorIdentity
    registry: ActorRegistry


def _runtime() -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-response-owner",
        display_name="Review Response Owner",
    )
    responder = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-response-human",
        display_name="Review Response Human",
    )
    assignee = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="review-response-assignee",
        display_name="Review Response Assignee",
    )
    review_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="review-response-system",
        display_name="Review Response System",
        accountability_owner_id=owner.actor_id,
    )
    ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="review-response-ledger-service",
        display_name="Review Response Ledger Service",
        accountability_owner_id=owner.actor_id,
    )
    registry = ActorRegistry.create(
        key="review-response-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T18:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            owner,
            responder,
            assignee,
            review_system,
            ledger_service,
        ),
    )

    return _Runtime(
        owner=owner,
        responder=responder,
        assignee=assignee,
        review_system=review_system,
        ledger_service=ledger_service,
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
            "2026-07-16T18:10:00Z"
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
        generation_count=2,
        head_entry_id=_identifier(
            "claim-posture-alert-lifecycle-chain-entry",
            f"{key}-head",
        ),
        current_docket_id=_identifier(
            "claim-posture-alert-docket",
            f"{key}-alert-docket",
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
            f"{key}-alert-docket",
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
            "review-response-catalog",
        ),
        actor_registry_digest=runtime.registry.digest(),
    )


def _response(
    runtime: _Runtime,
    *,
    docket: ClaimPostureAlertLifecycleReviewDocket,
    key: str,
    action: ClaimPostureAlertLifecycleReviewResponseAction,
    responded_at: str = "2026-07-16T18:11:00Z",
    responded_by_id: ScopedIdentifier | None = None,
    assigned_to_id: ScopedIdentifier | None = None,
    action_due_at: str | None = None,
) -> ClaimPostureAlertLifecycleReviewResponse:
    return ClaimPostureAlertLifecycleReviewResponse.respond(
        key=key,
        responded_at=UtcTimestamp.parse(
            responded_at
        ),
        responded_by_id=(
            responded_by_id
            or runtime.responder.actor_id
        ),
        action=action,
        rationale=f"Human review response: {action.value}.",
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
    key: str = "review-response-ledger",
    created_at: str = "2026-07-16T18:20:00Z",
) -> ClaimPostureAlertLifecycleReviewResponseLedger:
    return ClaimPostureAlertLifecycleReviewResponseLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.ledger_service.actor_id,
        review_docket=docket,
        actor_registry=runtime.registry,
        responses=responses,
    )


def test_open_review_can_be_acknowledged_without_resolution() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="unreviewed-head",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    response = _response(
        runtime,
        docket=docket,
        key="acknowledge-unreviewed-head",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ACKNOWLEDGE
        ),
    )

    assert response.assigns_human is False
    assert response.escalates_review is False
    assert response.opens_corrective_action is False
    assert response.resolves_review_obligation is False
    assert response.accepts_continuity is False
    assert response.approves_underlying_claims is False
    assert response.clears_alerts is False
    assert response.grants_authority is False


def test_clear_review_docket_cannot_receive_response() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="clear-head",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus.CLEAR
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must not receive a response",
    ):
        _response(
            runtime,
            docket=docket,
            key="respond-to-clear-head",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .ACKNOWLEDGE
            ),
        )


def test_assign_review_requires_human_and_due_time() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="assign-review-head",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="requires an assigned human",
    ):
        _response(
            runtime,
            docket=docket,
            key="unassigned-review",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .ASSIGN_REVIEW
            ),
            action_due_at="2026-07-17T18:11:00Z",
        )

    with pytest.raises(
        FoundationError,
        match="requires action_due_at",
    ):
        _response(
            runtime,
            docket=docket,
            key="undated-review",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .ASSIGN_REVIEW
            ),
            assigned_to_id=runtime.assignee.actor_id,
        )

    response = _response(
        runtime,
        docket=docket,
        key="assigned-review",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T18:11:00Z",
    )

    assert response.assigns_human is True
    assert response.assigned_to_id == runtime.assignee.actor_id


def test_corrective_docket_requires_corrective_plan_or_escalation() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="rejected-continuity",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .CORRECTIVE_ACTION_REQUIRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="requires escalation or a corrective-action plan",
    ):
        _response(
            runtime,
            docket=docket,
            key="acknowledge-rejection",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .ACKNOWLEDGE
            ),
        )

    response = _response(
        runtime,
        docket=docket,
        key="open-corrective-action",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .OPEN_CORRECTIVE_ACTION
        ),
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T18:11:00Z",
    )

    assert response.opens_corrective_action is True
    assert response.resolves_review_obligation is False


def test_corrective_plan_is_rejected_for_noncorrective_docket() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="ordinary-review",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="only valid for a rejected continuity review",
    ):
        _response(
            runtime,
            docket=docket,
            key="invalid-corrective-plan",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .OPEN_CORRECTIVE_ACTION
            ),
            assigned_to_id=runtime.assignee.actor_id,
            action_due_at="2026-07-17T18:11:00Z",
        )


def test_action_due_time_must_follow_response_time() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="invalid-due-time",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="later than responded_at",
    ):
        _response(
            runtime,
            docket=docket,
            key="past-due-review",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .ASSIGN_REVIEW
            ),
            assigned_to_id=runtime.assignee.actor_id,
            action_due_at="2026-07-16T18:11:00Z",
        )


def test_machine_cannot_issue_human_review_response() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="machine-response",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="active human actor",
    ):
        _response(
            runtime,
            docket=docket,
            key="machine-review-response",
            action=(
                ClaimPostureAlertLifecycleReviewResponseAction
                .ACKNOWLEDGE
            ),
            responded_by_id=runtime.review_system.actor_id,
        )


def test_ledger_tracks_latest_assignment_without_closing_review() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="tracked-review",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    acknowledgment = _response(
        runtime,
        docket=docket,
        key="tracked-acknowledgment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ACKNOWLEDGE
        ),
        responded_at="2026-07-16T18:11:00Z",
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="tracked-assignment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T18:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T18:12:00Z",
    )
    ledger = _ledger(
        runtime,
        docket=docket,
        responses=(
            assignment,
            acknowledgment,
        ),
    )

    assert ledger.responses == (
        acknowledgment,
        assignment,
    )
    assert ledger.response_count == 2
    assert ledger.latest_response == assignment
    assert ledger.current_assignee_id == (
        runtime.assignee.actor_id
    )
    assert ledger.response_recorded is True
    assert ledger.resolves_review_obligation is False
    assert ledger.accepts_continuity is False


def test_response_sequence_cannot_regress_after_escalation() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="response-regression",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    escalation = _response(
        runtime,
        docket=docket,
        key="escalate-review",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ESCALATE
        ),
        responded_at="2026-07-16T18:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-16T20:00:00Z",
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="regressive-assignment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T18:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T18:12:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not regress",
    ):
        _ledger(
            runtime,
            docket=docket,
            responses=(
                escalation,
                assignment,
            ),
        )


def test_ledger_rejects_response_from_different_docket() -> None:
    runtime = _runtime()
    first_docket = _review_docket(
        runtime,
        key="first-review-docket",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    second_docket = _review_docket(
        runtime,
        key="second-review-docket",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    response = _response(
        runtime,
        docket=first_docket,
        key="first-docket-response",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ACKNOWLEDGE
        ),
    )

    with pytest.raises(
        FoundationError,
        match="same review docket",
    ):
        _ledger(
            runtime,
            docket=second_docket,
            responses=(
                response,
            ),
        )


def test_ledger_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="producer-validation",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertLifecycleReviewResponseLedger.create(
            key="human-produced-review-response-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-16T18:20:00Z"
            ),
            producer_id=runtime.responder.actor_id,
            review_docket=docket,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-review-response-service",
        display_name="Unowned Review Response Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-review-response-actors",
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
        ClaimPostureAlertLifecycleReviewResponseLedger.create(
            key="unowned-review-response-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-16T18:20:00Z"
            ),
            producer_id=unowned_service.actor_id,
            review_docket=docket,
            actor_registry=expanded_registry,
        )


def test_review_response_ledger_is_reporting_only_and_deterministic() -> None:
    runtime = _runtime()
    docket = _review_docket(
        runtime,
        key="stable-review-response",
        status=(
            ClaimPostureAlertLifecycleReviewDocketStatus
            .REVIEW_REQUIRED
        ),
    )
    acknowledgment = _response(
        runtime,
        docket=docket,
        key="stable-acknowledgment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ACKNOWLEDGE
        ),
        responded_at="2026-07-16T18:11:00Z",
    )
    assignment = _response(
        runtime,
        docket=docket,
        key="stable-assignment",
        action=(
            ClaimPostureAlertLifecycleReviewResponseAction
            .ASSIGN_REVIEW
        ),
        responded_at="2026-07-16T18:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        action_due_at="2026-07-17T18:12:00Z",
    )

    ordered = _ledger(
        runtime,
        docket=docket,
        responses=(
            acknowledgment,
            assignment,
        ),
        key="stable-review-response-ledger",
    )
    reordered = _ledger(
        runtime,
        docket=docket,
        responses=(
            assignment,
            acknowledgment,
        ),
        key="stable-review-response-ledger",
    )

    assert ordered.resolves_review_obligation is False
    assert ordered.accepts_continuity is False
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
