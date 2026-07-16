"""Tests for operational claim-alert follow-up status."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertDocketStatus,
    ClaimPostureAlertFollowUpSnapshot,
    ClaimPostureAlertFollowUpSnapshotStatus,
    ClaimPostureAlertFollowUpStatus,
    ClaimPostureAlertReason,
    ClaimPostureAlertResponse,
    ClaimPostureAlertResponseAction,
    ClaimPostureAlertResponseLedger,
    ClaimPostureAlertSeverity,
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
    responder: ActorIdentity
    assignee: ActorIdentity
    owner: ActorIdentity
    alert_system: ActorIdentity
    response_service: ActorIdentity
    follow_up_system: ActorIdentity
    registry: ActorRegistry
    moderate_alert: ClaimPostureAlert
    critical_alert: ClaimPostureAlert
    docket: ClaimPostureAlertDocket


def _runtime(
    *,
    docket_key: str = "claim-follow-up-docket",
) -> _Runtime:
    responder = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="alert-responder",
        display_name="Alert Responder",
    )
    assignee = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="alert-assignee",
        display_name="Alert Assignee",
    )
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="control-owner",
        display_name="Control Owner",
    )
    alert_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-alert-system",
        display_name="Claim Alert System",
        accountability_owner_id=owner.actor_id,
    )
    response_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="alert-response-service",
        display_name="Alert Response Service",
        accountability_owner_id=owner.actor_id,
    )
    follow_up_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="alert-follow-up-system",
        display_name="Alert Follow-Up System",
        accountability_owner_id=owner.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-follow-up-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T11:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            responder,
            assignee,
            owner,
            alert_system,
            response_service,
            follow_up_system,
        ),
    )

    generated_at = UtcTimestamp.parse(
        "2026-07-16T11:10:00Z"
    )
    current_snapshot_digest = _digest(
        "claim-posture-snapshot",
        "current-posture-snapshot",
    )
    claim_catalog_digest = _digest(
        "claim-catalog",
        "claim-follow-up-catalog",
    )

    moderate_alert = ClaimPostureAlert(
        alert_id=_identifier(
            "claim-posture-alert",
            "incomplete-evidence-alert",
        ),
        generated_at=generated_at,
        claim_id=_identifier(
            "claim",
            "incomplete-runtime",
        ),
        severity=ClaimPostureAlertSeverity.MODERATE,
        reasons=(
            ClaimPostureAlertReason
            .CURRENT_INCOMPLETE_EVIDENCE,
        ),
        current_status=(
            ClaimPostureStatus.INCOMPLETE_EVIDENCE
        ),
        transition=None,
        current_posture_id=_identifier(
            "claim-posture",
            "incomplete-runtime-posture",
        ),
        delta_id=None,
        claim_digest=_digest(
            "claim-specification",
            "incomplete-runtime",
        ),
        current_posture_digest=_digest(
            "claim-posture",
            "incomplete-runtime-posture",
        ),
        delta_digest=None,
        current_snapshot_digest=current_snapshot_digest,
        delta_snapshot_digest=None,
        claim_catalog_digest=claim_catalog_digest,
        actor_registry_digest=registry.digest(),
    )
    critical_alert = ClaimPostureAlert(
        alert_id=_identifier(
            "claim-posture-alert",
            "falsification-alert",
        ),
        generated_at=generated_at,
        claim_id=_identifier(
            "claim",
            "falsified-runtime",
        ),
        severity=ClaimPostureAlertSeverity.CRITICAL,
        reasons=(
            ClaimPostureAlertReason
            .CURRENT_FALSIFICATION_SIGNAL,
        ),
        current_status=(
            ClaimPostureStatus.FALSIFICATION_SIGNAL
        ),
        transition=None,
        current_posture_id=_identifier(
            "claim-posture",
            "falsified-runtime-posture",
        ),
        delta_id=None,
        claim_digest=_digest(
            "claim-specification",
            "falsified-runtime",
        ),
        current_posture_digest=_digest(
            "claim-posture",
            "falsified-runtime-posture",
        ),
        delta_digest=None,
        current_snapshot_digest=current_snapshot_digest,
        delta_snapshot_digest=None,
        claim_catalog_digest=claim_catalog_digest,
        actor_registry_digest=registry.digest(),
    )
    docket = ClaimPostureAlertDocket(
        docket_id=_identifier(
            "claim-posture-alert-docket",
            docket_key,
        ),
        generated_at=generated_at,
        produced_by_id=alert_system.actor_id,
        producer_kind=alert_system.kind,
        producer_accountability_owner_id=owner.actor_id,
        status=ClaimPostureAlertDocketStatus.CRITICAL,
        current_snapshot_id=_identifier(
            "claim-posture-snapshot",
            "current-posture-snapshot",
        ),
        delta_snapshot_id=None,
        alerts=(
            moderate_alert,
            critical_alert,
        ),
        current_snapshot_digest=current_snapshot_digest,
        delta_snapshot_digest=None,
        claim_catalog_digest=claim_catalog_digest,
        actor_registry_digest=registry.digest(),
    )

    return _Runtime(
        responder=responder,
        assignee=assignee,
        owner=owner,
        alert_system=alert_system,
        response_service=response_service,
        follow_up_system=follow_up_system,
        registry=registry,
        moderate_alert=moderate_alert,
        critical_alert=critical_alert,
        docket=docket,
    )


def _response(
    runtime: _Runtime,
    *,
    alert: ClaimPostureAlert,
    action: ClaimPostureAlertResponseAction,
    key: str,
    responded_at: str,
    assigned_to_id: ScopedIdentifier | None = None,
    review_due_at: str | None = None,
) -> ClaimPostureAlertResponse:
    return ClaimPostureAlertResponse.respond(
        key=key,
        responded_at=UtcTimestamp.parse(
            responded_at
        ),
        responded_by_id=runtime.responder.actor_id,
        action=action,
        rationale=f"Human response: {action.value}.",
        alert=alert,
        docket=runtime.docket,
        actor_registry=runtime.registry,
        assigned_to_id=assigned_to_id,
        review_due_at=(
            UtcTimestamp.parse(
                review_due_at
            )
            if review_due_at is not None
            else None
        ),
    )


def _ledger(
    runtime: _Runtime,
    *responses: ClaimPostureAlertResponse,
    key: str = "claim-follow-up-responses",
    created_at: str = "2026-07-16T11:20:00Z",
) -> ClaimPostureAlertResponseLedger:
    return ClaimPostureAlertResponseLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.response_service.actor_id,
        docket=runtime.docket,
        actor_registry=runtime.registry,
        responses=responses,
    )


def _snapshot(
    runtime: _Runtime,
    ledger: ClaimPostureAlertResponseLedger,
    *,
    assessed_at: str = "2026-07-16T11:21:00Z",
) -> ClaimPostureAlertFollowUpSnapshot:
    return ClaimPostureAlertFollowUpSnapshot.create(
        key="current-alert-follow-up",
        assessed_at=UtcTimestamp.parse(
            assessed_at
        ),
        produced_by_id=runtime.follow_up_system.actor_id,
        docket=runtime.docket,
        response_ledger=ledger,
        actor_registry=runtime.registry,
    )


def test_unresponded_alerts_remain_active_and_require_action() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _ledger(runtime),
    )
    moderate = snapshot.require_follow_up_for_alert(
        runtime.moderate_alert.alert_id
    )
    critical = snapshot.require_follow_up_for_alert(
        runtime.critical_alert.alert_id
    )

    assert snapshot.status is (
        ClaimPostureAlertFollowUpSnapshotStatus
        .ESCALATION_REQUIRED
    )
    assert snapshot.active_alert_count == 2
    assert snapshot.responded_count == 0
    assert snapshot.unresponded_count == 2
    assert snapshot.escalation_required_count == 1
    assert snapshot.follow_up_required_count == 2
    assert snapshot.active_alerts_remain is True
    assert snapshot.all_active_alerts_responded is False

    assert moderate.status is (
        ClaimPostureAlertFollowUpStatus.UNRESPONDED
    )
    assert moderate.requires_response is True
    assert moderate.alert_remains_active is True

    assert critical.status is (
        ClaimPostureAlertFollowUpStatus.UNRESPONDED
    )
    assert critical.requires_escalation is True
    assert critical.follow_up_required is True


def test_acknowledged_critical_alert_still_requires_escalation() -> None:
    runtime = _runtime()
    acknowledgment = _response(
        runtime,
        alert=runtime.critical_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="acknowledge-critical-alert",
        responded_at="2026-07-16T11:11:00Z",
    )
    snapshot = _snapshot(
        runtime,
        _ledger(
            runtime,
            acknowledgment,
        ),
    )
    follow_up = snapshot.require_follow_up_for_alert(
        runtime.critical_alert.alert_id
    )

    assert follow_up.status is (
        ClaimPostureAlertFollowUpStatus.ACKNOWLEDGED
    )
    assert follow_up.has_response is True
    assert follow_up.requires_response is False
    assert follow_up.requires_escalation is True
    assert follow_up.alert_remains_active is True
    assert snapshot.escalation_required_count == 1


def test_explicit_escalation_clears_requirement_not_alert() -> None:
    runtime = _runtime()
    escalation = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="escalate-critical-alert",
        responded_at="2026-07-16T11:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T13:00:00Z",
    )
    snapshot = _snapshot(
        runtime,
        _ledger(
            runtime,
            escalation,
        ),
    )
    follow_up = snapshot.require_follow_up_for_alert(
        runtime.critical_alert.alert_id
    )

    assert follow_up.status is (
        ClaimPostureAlertFollowUpStatus.ESCALATED
    )
    assert follow_up.requires_escalation is False
    assert follow_up.has_assignment is True
    assert follow_up.is_overdue is False
    assert follow_up.alert_remains_active is True
    assert follow_up.resolves_alert is False

    assert snapshot.escalation_required_count == 0
    assert snapshot.unresponded_count == 1
    assert snapshot.status is (
        ClaimPostureAlertFollowUpSnapshotStatus
        .ACTION_REQUIRED
    )


def test_open_investigation_is_tracked_until_due() -> None:
    runtime = _runtime()
    investigation = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="open-moderate-investigation",
        responded_at="2026-07-16T11:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T11:11:00Z",
    )
    escalation = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="escalate-critical-for-tracking",
        responded_at="2026-07-16T11:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T13:00:00Z",
    )
    snapshot = _snapshot(
        runtime,
        _ledger(
            runtime,
            investigation,
            escalation,
        ),
    )
    follow_up = snapshot.require_follow_up_for_alert(
        runtime.moderate_alert.alert_id
    )

    assert snapshot.status is (
        ClaimPostureAlertFollowUpSnapshotStatus.TRACKED
    )
    assert snapshot.responded_count == 2
    assert snapshot.unresponded_count == 0
    assert snapshot.assigned_count == 2
    assert snapshot.overdue_count == 0
    assert snapshot.all_active_alerts_responded is True
    assert snapshot.active_alerts_remain is True
    assert snapshot.requires_human_action is False

    assert follow_up.status is (
        ClaimPostureAlertFollowUpStatus
        .INVESTIGATION_OPEN
    )
    assert follow_up.has_assignment is True
    assert follow_up.is_overdue is False
    assert follow_up.follow_up_required is False


def test_overdue_investigation_is_detected() -> None:
    runtime = _runtime()
    investigation = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="overdue-investigation",
        responded_at="2026-07-16T11:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T12:00:00Z",
    )
    escalation = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="current-critical-escalation",
        responded_at="2026-07-16T11:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T11:12:00Z",
    )
    snapshot = _snapshot(
        runtime,
        _ledger(
            runtime,
            investigation,
            escalation,
        ),
        assessed_at="2026-07-16T12:00:01Z",
    )
    follow_up = snapshot.require_follow_up_for_alert(
        runtime.moderate_alert.alert_id
    )

    assert snapshot.status is (
        ClaimPostureAlertFollowUpSnapshotStatus.OVERDUE
    )
    assert snapshot.overdue_count == 1
    assert snapshot.follow_up_required_count == 1
    assert snapshot.requires_human_action is True
    assert follow_up.is_overdue is True
    assert follow_up.follow_up_required is True
    assert snapshot.overdue_follow_ups() == (
        follow_up,
    )


def test_latest_response_controls_current_follow_up_status() -> None:
    runtime = _runtime()
    acknowledgment = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="first-acknowledgment",
        responded_at="2026-07-16T11:11:00Z",
    )
    investigation = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="later-investigation",
        responded_at="2026-07-16T11:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T11:12:00Z",
    )
    snapshot = _snapshot(
        runtime,
        _ledger(
            runtime,
            acknowledgment,
            investigation,
        ),
    )
    follow_up = snapshot.require_follow_up_for_alert(
        runtime.moderate_alert.alert_id
    )

    assert follow_up.response_count == 2
    assert follow_up.status is (
        ClaimPostureAlertFollowUpStatus
        .INVESTIGATION_OPEN
    )
    assert follow_up.latest_response_id == (
        investigation.response_id
    )
    assert follow_up.latest_response_digest == (
        investigation.digest()
    )
    assert follow_up.assigned_to_id == (
        runtime.assignee.actor_id
    )


def test_empty_docket_has_no_active_alerts() -> None:
    runtime = _runtime()
    empty_docket = ClaimPostureAlertDocket(
        docket_id=_identifier(
            "claim-posture-alert-docket",
            "empty-follow-up-docket",
        ),
        generated_at=runtime.docket.generated_at,
        produced_by_id=runtime.alert_system.actor_id,
        producer_kind=runtime.alert_system.kind,
        producer_accountability_owner_id=runtime.owner.actor_id,
        status=ClaimPostureAlertDocketStatus.CLEAR,
        current_snapshot_id=runtime.docket.current_snapshot_id,
        delta_snapshot_id=None,
        alerts=(),
        current_snapshot_digest=(
            runtime.docket.current_snapshot_digest
        ),
        delta_snapshot_digest=None,
        claim_catalog_digest=(
            runtime.docket.claim_catalog_digest
        ),
        actor_registry_digest=runtime.registry.digest(),
    )
    ledger = ClaimPostureAlertResponseLedger.create(
        key="empty-follow-up-responses",
        created_at=UtcTimestamp.parse(
            "2026-07-16T11:20:00Z"
        ),
        producer_id=runtime.response_service.actor_id,
        docket=empty_docket,
        actor_registry=runtime.registry,
    )
    snapshot = ClaimPostureAlertFollowUpSnapshot.create(
        key="empty-alert-follow-up",
        assessed_at=UtcTimestamp.parse(
            "2026-07-16T11:21:00Z"
        ),
        produced_by_id=runtime.follow_up_system.actor_id,
        docket=empty_docket,
        response_ledger=ledger,
        actor_registry=runtime.registry,
    )

    assert snapshot.status is (
        ClaimPostureAlertFollowUpSnapshotStatus
        .NO_ACTIVE_ALERTS
    )
    assert snapshot.active_alert_count == 0
    assert snapshot.active_alerts_remain is False
    assert snapshot.all_active_alerts_responded is True
    assert snapshot.requires_human_action is False


def test_snapshot_rejects_response_ledger_from_different_docket() -> None:
    runtime = _runtime()
    different_runtime = _runtime(
        docket_key="different-follow-up-docket"
    )
    foreign_ledger = _ledger(
        different_runtime,
    )

    with pytest.raises(
        FoundationError,
        match="different alert docket",
    ):
        ClaimPostureAlertFollowUpSnapshot.create(
            key="mismatched-follow-up",
            assessed_at=UtcTimestamp.parse(
                "2026-07-16T11:21:00Z"
            ),
            produced_by_id=runtime.follow_up_system.actor_id,
            docket=runtime.docket,
            response_ledger=foreign_ledger,
            actor_registry=runtime.registry,
        )


def test_snapshot_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertFollowUpSnapshot.create(
            key="human-produced-follow-up",
            assessed_at=UtcTimestamp.parse(
                "2026-07-16T11:21:00Z"
            ),
            produced_by_id=runtime.responder.actor_id,
            docket=runtime.docket,
            response_ledger=ledger,
            actor_registry=runtime.registry,
        )

    unowned_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="unowned-follow-up-system",
        display_name="Unowned Follow-Up System",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-claim-follow-up-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.owner.actor_id,
        actors=(
            *runtime.registry.actors,
            unowned_system,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must identify an accountable human owner",
    ):
        ClaimPostureAlertFollowUpSnapshot.create(
            key="unowned-produced-follow-up",
            assessed_at=UtcTimestamp.parse(
                "2026-07-16T11:21:00Z"
            ),
            produced_by_id=unowned_system.actor_id,
            docket=runtime.docket,
            response_ledger=ledger,
            actor_registry=expanded_registry,
        )


def test_snapshot_must_not_predate_response_ledger() -> None:
    runtime = _runtime()
    ledger = _ledger(
        runtime,
        created_at="2026-07-16T11:22:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the response ledger",
    ):
        _snapshot(
            runtime,
            ledger,
            assessed_at="2026-07-16T11:21:00Z",
        )


def test_follow_up_snapshot_is_reporting_only() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _ledger(runtime),
    )

    assert snapshot.resolves_alerts is False
    assert snapshot.changes_claim_state is False
    assert snapshot.grants_authority is False
    assert snapshot.claims_certification is False
    assert snapshot.digest().verifies(
        snapshot.canonical_payload()
    ) is True

    for follow_up in snapshot.follow_ups:
        assert follow_up.alert_remains_active is True
        assert follow_up.resolves_alert is False
        assert follow_up.changes_claim_state is False
        assert follow_up.grants_authority is False
        assert follow_up.claims_certification is False


def test_follow_up_snapshot_is_deterministic_across_response_order() -> None:
    runtime = _runtime()
    moderate = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="stable-moderate-investigation",
        responded_at="2026-07-16T11:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T11:11:00Z",
    )
    critical = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="stable-critical-escalation",
        responded_at="2026-07-16T11:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T11:12:00Z",
    )
    first_ledger = _ledger(
        runtime,
        moderate,
        critical,
        key="stable-follow-up-responses",
    )
    second_ledger = _ledger(
        runtime,
        critical,
        moderate,
        key="stable-follow-up-responses",
    )

    first = _snapshot(
        runtime,
        first_ledger,
    )
    second = _snapshot(
        runtime,
        second_ledger,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()


def test_snapshot_rejects_duplicate_follow_up_claim() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _ledger(runtime),
    )
    duplicate = replace(
        snapshot.follow_ups[0],
        follow_up_id=_identifier(
            "claim-posture-alert-follow-up",
            "duplicate-follow-up",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="one follow-up per alert",
    ):
        replace(
            snapshot,
            follow_ups=(
                *snapshot.follow_ups,
                duplicate,
            ),
        )
