"""Tests for human responses to immutable claim-posture alerts."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertDocketStatus,
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
    ActorStatus,
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
    ledger_service: ActorIdentity
    registry: ActorRegistry
    moderate_alert: ClaimPostureAlert
    critical_alert: ClaimPostureAlert
    docket: ClaimPostureAlertDocket


def _runtime() -> _Runtime:
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
    ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="alert-response-ledger-service",
        display_name="Alert Response Ledger Service",
        accountability_owner_id=owner.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-alert-response-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T10:00:00Z"
        ),
        producer_id=owner.actor_id,
        actors=(
            responder,
            assignee,
            owner,
            alert_system,
            ledger_service,
        ),
    )

    generated_at = UtcTimestamp.parse(
        "2026-07-16T10:10:00Z"
    )
    current_snapshot_digest = _digest(
        "claim-posture-snapshot",
        "current-claim-postures",
    )
    claim_catalog_digest = _digest(
        "claim-catalog",
        "claim-alert-response-catalog",
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
            "claim-alert-response-docket",
        ),
        generated_at=generated_at,
        produced_by_id=alert_system.actor_id,
        producer_kind=alert_system.kind,
        producer_accountability_owner_id=owner.actor_id,
        status=ClaimPostureAlertDocketStatus.CRITICAL,
        current_snapshot_id=_identifier(
            "claim-posture-snapshot",
            "current-claim-postures",
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
        ledger_service=ledger_service,
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
    responded_at: str = "2026-07-16T10:11:00Z",
    responded_by_id: ScopedIdentifier | None = None,
    assigned_to_id: ScopedIdentifier | None = None,
    review_due_at: str | None = None,
) -> ClaimPostureAlertResponse:
    return ClaimPostureAlertResponse.respond(
        key=key,
        responded_at=UtcTimestamp.parse(
            responded_at
        ),
        responded_by_id=(
            responded_by_id
            or runtime.responder.actor_id
        ),
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
    key: str = "claim-alert-responses",
    created_at: str = "2026-07-16T10:20:00Z",
) -> ClaimPostureAlertResponseLedger:
    return ClaimPostureAlertResponseLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.ledger_service.actor_id,
        docket=runtime.docket,
        actor_registry=runtime.registry,
        responses=responses,
    )


def test_human_can_acknowledge_alert_without_clearing_it() -> None:
    runtime = _runtime()
    response = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="acknowledge-incomplete-evidence",
    )

    assert response.acknowledges_alert is True
    assert response.opens_investigation is False
    assert response.escalates_alert is False
    assert response.defers_response is False
    assert response.resolves_alert is False
    assert response.changes_claim_state is False
    assert response.grants_authority is False
    assert response.claims_certification is False
    assert response.digest().verifies(
        response.to_payload()
    ) is True


def test_open_investigation_requires_human_assignment_and_due_time() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="requires an assigned human",
    ):
        _response(
            runtime,
            alert=runtime.moderate_alert,
            action=(
                ClaimPostureAlertResponseAction
                .OPEN_INVESTIGATION
            ),
            key="unassigned-investigation",
            review_due_at="2026-07-17T10:11:00Z",
        )

    with pytest.raises(
        FoundationError,
        match="requires review_due_at",
    ):
        _response(
            runtime,
            alert=runtime.moderate_alert,
            action=(
                ClaimPostureAlertResponseAction
                .OPEN_INVESTIGATION
            ),
            key="undated-investigation",
            assigned_to_id=runtime.assignee.actor_id,
        )

    response = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="open-investigation",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T10:11:00Z",
    )

    assert response.opens_investigation is True
    assert response.assigned_to_id == runtime.assignee.actor_id
    assert response.review_due_at == UtcTimestamp.parse(
        "2026-07-17T10:11:00Z"
    )
    assert response.resolves_alert is False


def test_critical_alert_must_not_be_deferred() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="must not be deferred",
    ):
        _response(
            runtime,
            alert=runtime.critical_alert,
            action=ClaimPostureAlertResponseAction.DEFER,
            key="defer-critical-alert",
            review_due_at="2026-07-17T10:11:00Z",
        )


def test_critical_alert_can_be_explicitly_escalated() -> None:
    runtime = _runtime()
    response = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="escalate-critical-alert",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T12:00:00Z",
    )

    assert response.escalates_alert is True
    assert response.alert_severity is (
        ClaimPostureAlertSeverity.CRITICAL
    )
    assert response.resolves_alert is False


def test_response_due_time_must_follow_response_time() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="later than responded_at",
    ):
        _response(
            runtime,
            alert=runtime.moderate_alert,
            action=ClaimPostureAlertResponseAction.DEFER,
            key="invalid-deferral-time",
            responded_at="2026-07-16T10:11:00Z",
            review_due_at="2026-07-16T10:11:00Z",
        )


def test_machine_or_inactive_human_cannot_respond() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="active human actor",
    ):
        _response(
            runtime,
            alert=runtime.moderate_alert,
            action=(
                ClaimPostureAlertResponseAction.ACKNOWLEDGE
            ),
            key="machine-response",
            responded_by_id=runtime.alert_system.actor_id,
        )

    inactive = replace(
        runtime.responder,
        status=ActorStatus.SUSPENDED,
    )
    inactive_registry = ActorRegistry.create(
        key="inactive-alert-response-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.owner.actor_id,
        actors=(
            inactive,
            runtime.assignee,
            runtime.owner,
            runtime.alert_system,
            runtime.ledger_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="active human actor",
    ):
        ClaimPostureAlertResponse.respond(
            key="inactive-human-response",
            responded_at=UtcTimestamp.parse(
                "2026-07-16T10:11:00Z"
            ),
            responded_by_id=inactive.actor_id,
            action=(
                ClaimPostureAlertResponseAction.ACKNOWLEDGE
            ),
            rationale="Suspended human attempted response.",
            alert=runtime.moderate_alert,
            docket=runtime.docket,
            actor_registry=inactive_registry,
        )


def test_response_rejects_alert_from_different_docket() -> None:
    runtime = _runtime()
    foreign_alert = replace(
        runtime.moderate_alert,
        alert_id=_identifier(
            "claim-posture-alert",
            "foreign-alert",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="does not belong to the supplied docket",
    ):
        _response(
            runtime,
            alert=foreign_alert,
            action=(
                ClaimPostureAlertResponseAction.ACKNOWLEDGE
            ),
            key="foreign-alert-response",
        )


def test_ledger_tracks_unresponded_and_escalation_required_alerts() -> None:
    runtime = _runtime()
    acknowledgment = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="acknowledge-moderate-alert",
    )
    ledger = _ledger(
        runtime,
        acknowledgment,
    )

    assert ledger.response_count == 1
    assert ledger.unresponded_alerts(
        docket=runtime.docket
    ) == (
        runtime.critical_alert,
    )
    assert ledger.alerts_requiring_escalation(
        docket=runtime.docket
    ) == (
        runtime.critical_alert,
    )
    assert ledger.active_alerts(
        docket=runtime.docket
    ) == runtime.docket.alerts
    assert ledger.resolves_alerts is False
    assert ledger.changes_claim_state is False


def test_acknowledging_critical_alert_does_not_satisfy_escalation() -> None:
    runtime = _runtime()
    acknowledgment = _response(
        runtime,
        alert=runtime.critical_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="acknowledge-critical-alert",
    )
    ledger = _ledger(
        runtime,
        acknowledgment,
    )

    assert ledger.unresponded_alerts(
        docket=runtime.docket
    ) == (
        runtime.moderate_alert,
    )
    assert ledger.alerts_requiring_escalation(
        docket=runtime.docket
    ) == (
        runtime.critical_alert,
    )


def test_explicit_escalation_clears_escalation_requirement_not_alert() -> None:
    runtime = _runtime()
    escalation = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="explicit-critical-escalation",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T12:00:00Z",
    )
    ledger = _ledger(
        runtime,
        escalation,
    )

    assert ledger.alerts_requiring_escalation(
        docket=runtime.docket
    ) == ()
    assert runtime.critical_alert in ledger.active_alerts(
        docket=runtime.docket
    )


def test_escalated_alert_cannot_later_be_deferred() -> None:
    runtime = _runtime()
    escalation = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="moderate-escalation",
        responded_at="2026-07-16T10:11:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T12:00:00Z",
    )
    deferral = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=ClaimPostureAlertResponseAction.DEFER,
        key="post-escalation-deferral",
        responded_at="2026-07-16T10:12:00Z",
        review_due_at="2026-07-17T10:12:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not later be deferred",
    ):
        _ledger(
            runtime,
            escalation,
            deferral,
        )


def test_responses_for_one_alert_require_strictly_increasing_times() -> None:
    runtime = _runtime()
    acknowledgment = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="same-time-acknowledgment",
    )
    investigation = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="same-time-investigation",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T10:11:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="strictly increasing response times",
    ):
        _ledger(
            runtime,
            acknowledgment,
            investigation,
        )


def test_ledger_append_preserves_identity_and_history() -> None:
    runtime = _runtime()
    acknowledgment = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="append-acknowledgment",
        responded_at="2026-07-16T10:11:00Z",
    )
    investigation = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction
            .OPEN_INVESTIGATION
        ),
        key="append-investigation",
        responded_at="2026-07-16T10:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-17T10:12:00Z",
    )
    ledger = _ledger(
        runtime,
        acknowledgment,
        created_at="2026-07-16T10:11:00Z",
    )
    next_ledger = ledger.append(
        investigation,
        created_at=UtcTimestamp.parse(
            "2026-07-16T10:12:00Z"
        ),
        docket=runtime.docket,
    )

    assert next_ledger.ledger_id == ledger.ledger_id
    assert next_ledger.producer_id == ledger.producer_id
    assert next_ledger.responses_for_alert(
        runtime.moderate_alert.alert_id
    ) == (
        acknowledgment,
        investigation,
    )
    assert next_ledger.latest_for_alert(
        runtime.moderate_alert.alert_id
    ) == investigation


def test_ledger_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureAlertResponseLedger.create(
            key="human-produced-response-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-16T10:20:00Z"
            ),
            producer_id=runtime.responder.actor_id,
            docket=runtime.docket,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-response-ledger-service",
        display_name="Unowned Response Ledger Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-alert-response-actors",
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
        ClaimPostureAlertResponseLedger.create(
            key="unowned-produced-response-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-16T10:20:00Z"
            ),
            producer_id=unowned_service.actor_id,
            docket=runtime.docket,
            actor_registry=expanded_registry,
        )


def test_response_ledger_is_reporting_only_and_deterministic() -> None:
    runtime = _runtime()
    moderate = _response(
        runtime,
        alert=runtime.moderate_alert,
        action=(
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        ),
        key="stable-moderate-response",
        responded_at="2026-07-16T10:11:00Z",
    )
    critical = _response(
        runtime,
        alert=runtime.critical_alert,
        action=ClaimPostureAlertResponseAction.ESCALATE,
        key="stable-critical-response",
        responded_at="2026-07-16T10:12:00Z",
        assigned_to_id=runtime.assignee.actor_id,
        review_due_at="2026-07-16T12:00:00Z",
    )

    first = _ledger(
        runtime,
        moderate,
        critical,
        key="stable-response-ledger",
    )
    second = _ledger(
        runtime,
        critical,
        moderate,
        key="stable-response-ledger",
    )

    assert first.resolves_alerts is False
    assert first.changes_claim_state is False
    assert first.grants_authority is False
    assert first.claims_certification is False
    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
    assert first.digest().verifies(
        first.canonical_payload()
    ) is True
