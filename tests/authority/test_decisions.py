"""Tests for action-bound human authorization decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.authority import (
    ActionAuthorizationDecision,
    ActionAuthorizationDecisionLedger,
    ActionAuthorizationDecisionStatus,
    ActionAuthorizationEvaluation,
    ActionAuthorizationEvaluator,
    ActionAuthorizationOutcome,
    ActionAuthorizationRequest,
    AuthorityGrant,
    AuthorityGrantLedger,
    AuthorityRevocationLedger,
    AuthorityStateSnapshot,
    CapabilityCatalog,
    CapabilityDefinition,
    CapabilityOperation,
    CapabilityRiskTier,
)
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
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


@dataclass(frozen=True, slots=True)
class _ReviewRuntime:
    human: ActorIdentity
    second_human: ActorIdentity
    agent: ActorIdentity
    actor_registry: ActorRegistry
    capability: CapabilityDefinition
    capability_catalog: CapabilityCatalog
    grant: AuthorityGrant
    grant_ledger: AuthorityGrantLedger
    authority_state: AuthorityStateSnapshot
    request: ActionAuthorizationRequest


def _runtime(
    *,
    requires_human_review: bool = True,
    include_request_evidence: bool = True,
) -> _ReviewRuntime:
    human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-01",
        display_name="Mission Reviewer",
        roles=("authority grantor",),
    )
    second_human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-02",
        display_name="Second Reviewer",
        roles=("human reviewer",),
    )
    agent = ActorIdentity.create(
        kind=ActorKind.AGENT,
        key="bounded-agent",
        display_name="Bounded Agent",
        accountability_owner_id=human.actor_id,
    )
    actor_registry = ActorRegistry.create(
        key="human-action-decision-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-15T19:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            second_human,
            agent,
        ),
    )
    capability = CapabilityDefinition.create(
        key="execute-bounded-tool",
        operation=CapabilityOperation.EXECUTE,
        target_type="bounded tool",
        summary="Execute one exact bounded tool.",
        risk_tier=(
            CapabilityRiskTier.CRITICAL
            if requires_human_review
            else CapabilityRiskTier.HIGH
        ),
        permitted_actor_kinds=(
            ActorKind.AGENT,
        ),
        requires_separate_human_authorization=(
            requires_human_review
        ),
    )
    capability_catalog = CapabilityCatalog.create(
        key="human-action-decision-capabilities",
        created_at=UtcTimestamp.parse(
            "2026-07-15T19:00:00Z"
        ),
        producer_id=human.actor_id,
        capabilities=(
            capability,
        ),
    )
    grant = AuthorityGrant.issue(
        key="bounded-agent-tool-grant",
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=human.actor_id,
        issued_at=UtcTimestamp.parse(
            "2026-07-15T19:05:00Z"
        ),
        valid_from=UtcTimestamp.parse(
            "2026-07-15T19:10:00Z"
        ),
        expires_at=UtcTimestamp.parse(
            "2026-07-15T20:00:00Z"
        ),
        actor_registry=actor_registry,
        capability_catalog=capability_catalog,
        target_ids=(
            _identifier(
                "bounded-tool",
                "test-runner",
            ),
        ),
        supporting_record_ids=(
            _identifier(
                "record",
                "grant-evidence",
            ),
        ),
    )
    grant_ledger = AuthorityGrantLedger.create(
        key="human-action-decision-grants",
        created_at=UtcTimestamp.parse(
            "2026-07-15T19:05:00Z"
        ),
        producer_id=human.actor_id,
        grants=(
            grant,
        ),
    )
    revocation_ledger = (
        AuthorityRevocationLedger.create(
            key="human-action-decision-revocations",
            created_at=UtcTimestamp.parse(
                "2026-07-15T19:05:00Z"
            ),
            producer_id=human.actor_id,
            grant_ledger=grant_ledger,
            revocations=(),
        )
    )
    authority_state = AuthorityStateSnapshot.create(
        key="human-action-decision-state",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-15T19:30:00Z"
        ),
        producer_id=human.actor_id,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
    )
    request = ActionAuthorizationRequest.create(
        key="run-unit-tests",
        requested_at=UtcTimestamp.parse(
            "2026-07-15T19:25:00Z"
        ),
        requester_id=agent.actor_id,
        grant_id=grant.grant_id,
        capability_id=capability.capability_id,
        target_id=_identifier(
            "bounded-tool",
            "test-runner",
        ),
        action={
            "arguments": [
                "tests/unit",
            ],
            "operation": "run-tests",
            "tool_id": "test-runner",
        },
        evidence_record_ids=(
            (
                _identifier(
                    "record",
                    "request-evidence",
                ),
            )
            if include_request_evidence
            else ()
        ),
        justification=(
            "Run the bounded unit-test target."
        ),
    )

    return _ReviewRuntime(
        human=human,
        second_human=second_human,
        agent=agent,
        actor_registry=actor_registry,
        capability=capability,
        capability_catalog=capability_catalog,
        grant=grant,
        grant_ledger=grant_ledger,
        authority_state=authority_state,
        request=request,
    )


def _evaluation(
    runtime: _ReviewRuntime,
) -> ActionAuthorizationEvaluation:
    evaluator = ActionAuthorizationEvaluator(
        actor_registry=runtime.actor_registry,
        capability_catalog=runtime.capability_catalog,
        grant_ledger=runtime.grant_ledger,
        authority_state=runtime.authority_state,
    )
    return evaluator.evaluate(
        runtime.request,
        key="human-action-preflight",
    )


def _decision(
    runtime: _ReviewRuntime,
    *,
    status: ActionAuthorizationDecisionStatus,
    decided_at: str,
    key: str,
    decided_by_id: ScopedIdentifier | None = None,
) -> ActionAuthorizationDecision:
    return ActionAuthorizationDecision.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=(
            decided_by_id
            or runtime.human.actor_id
        ),
        status=status,
        rationale=(
            f"Human decision: {status.value}."
        ),
        supporting_record_ids=(
            _identifier(
                "record",
                f"{key}-evidence",
            ),
        ),
        request=runtime.request,
        evaluation=_evaluation(runtime),
        grant=runtime.grant,
        actor_registry=runtime.actor_registry,
    )


def test_approved_decision_is_bound_but_does_not_release_execution() -> None:
    runtime = _runtime()
    evaluation = _evaluation(runtime)
    decision = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.APPROVED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="approve-unit-tests",
    )

    assert evaluation.outcome is (
        ActionAuthorizationOutcome.REQUIRE_HUMAN_REVIEW
    )
    assert decision.approves_action is True
    assert decision.rejects_action is False
    assert decision.defers_action is False
    assert decision.releases_execution is False
    assert (
        decision.action_digest
        == runtime.request.action_digest
    )
    assert (
        decision.request_digest
        == runtime.request.digest()
    )
    assert (
        decision.evaluation_digest
        == evaluation.digest()
    )
    assert (
        decision.grant_digest
        == runtime.grant.digest()
    )
    assert decision.digest().verifies(
        decision.to_payload()
    ) is True


def test_rejected_and_deferred_decisions_preserve_distinct_status() -> None:
    runtime = _runtime()
    rejected = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.REJECTED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="reject-unit-tests",
    )
    deferred = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.DEFERRED
        ),
        decided_at="2026-07-15T19:36:00Z",
        key="defer-unit-tests",
    )

    assert rejected.rejects_action is True
    assert rejected.status.is_terminal is True
    assert deferred.defers_action is True
    assert deferred.status.is_terminal is False


def test_human_decision_cannot_override_blocked_preflight() -> None:
    runtime = _runtime(
        include_request_evidence=False
    )
    evaluation = _evaluation(runtime)

    assert evaluation.outcome is (
        ActionAuthorizationOutcome.BLOCK
    )

    with pytest.raises(
        FoundationError,
        match="blocked preflight cannot be overridden",
    ):
        ActionAuthorizationDecision.decide(
            key="override-blocked-preflight",
            decided_at=UtcTimestamp.parse(
                "2026-07-15T19:35:00Z"
            ),
            decided_by_id=runtime.human.actor_id,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            rationale=(
                "Attempted approval of a blocked action."
            ),
            supporting_record_ids=(
                _identifier(
                    "record",
                    "override-attempt",
                ),
            ),
            request=runtime.request,
            evaluation=evaluation,
            grant=runtime.grant,
            actor_registry=runtime.actor_registry,
        )


def test_human_decision_is_invalid_when_preflight_already_allows() -> None:
    runtime = _runtime(
        requires_human_review=False
    )

    with pytest.raises(
        FoundationError,
        match="require-human-review",
    ):
        _decision(
            runtime,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            decided_at="2026-07-15T19:35:00Z",
            key="unnecessary-human-decision",
        )


def test_only_original_active_human_grantor_may_decide() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="original human grantor",
    ):
        _decision(
            runtime,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            decided_at="2026-07-15T19:35:00Z",
            key="wrong-reviewer",
            decided_by_id=runtime.second_human.actor_id,
        )


def test_decision_must_occur_while_grant_remains_time_effective() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="must remain time-effective",
    ):
        _decision(
            runtime,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            decided_at="2026-07-15T20:00:00Z",
            key="late-approval",
        )


def test_decision_requires_supporting_record() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="require at least one supporting record",
    ):
        ActionAuthorizationDecision.decide(
            key="unsupported-approval",
            decided_at=UtcTimestamp.parse(
                "2026-07-15T19:35:00Z"
            ),
            decided_by_id=runtime.human.actor_id,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            rationale=(
                "Approval without supporting evidence."
            ),
            supporting_record_ids=(),
            request=runtime.request,
            evaluation=_evaluation(runtime),
            grant=runtime.grant,
            actor_registry=runtime.actor_registry,
        )


def test_decision_rejects_mismatched_request() -> None:
    runtime = _runtime()
    other_request = ActionAuthorizationRequest.create(
        key="different-request",
        requested_at=runtime.request.requested_at,
        requester_id=runtime.request.requester_id,
        grant_id=runtime.request.grant_id,
        capability_id=runtime.request.capability_id,
        target_id=runtime.request.target_id,
        action={
            "operation": "different-action",
        },
        evidence_record_ids=(
            runtime.request.evidence_record_ids
        ),
        justification=(
            "A different proposed action."
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "evaluation does not reference the supplied request"
        ),
    ):
        ActionAuthorizationDecision.decide(
            key="mismatched-request",
            decided_at=UtcTimestamp.parse(
                "2026-07-15T19:35:00Z"
            ),
            decided_by_id=runtime.human.actor_id,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            rationale=(
                "Attempted decision over a different request."
            ),
            supporting_record_ids=(
                _identifier(
                    "record",
                    "mismatch-evidence",
                ),
            ),
            request=other_request,
            evaluation=_evaluation(runtime),
            grant=runtime.grant,
            actor_registry=runtime.actor_registry,
        )


def test_ledger_allows_defer_then_terminal_decision() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.DEFERRED
        ),
        decided_at="2026-07-15T19:34:00Z",
        key="defer-for-more-evidence",
    )
    approved = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.APPROVED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="approve-after-evidence",
    )
    ledger = ActionAuthorizationDecisionLedger.create(
        key="unit-test-decisions",
        created_at=UtcTimestamp.parse(
            "2026-07-15T19:36:00Z"
        ),
        producer_id=runtime.human.actor_id,
        decisions=(
            approved,
            deferred,
        ),
    )

    assert ledger.decisions_for_evaluation(
        approved.evaluation_id
    ) == (
        deferred,
        approved,
    )
    assert ledger.latest_for_evaluation(
        approved.evaluation_id
    ) == approved
    assert ledger.require_terminal_decision(
        approved.evaluation_id
    ) == approved


def test_ledger_rejects_decision_after_terminal_disposition() -> None:
    runtime = _runtime()
    approved = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.APPROVED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="terminal-approval",
    )
    rejected = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.REJECTED
        ),
        decided_at="2026-07-15T19:36:00Z",
        key="replacement-rejection",
    )

    with pytest.raises(
        FoundationError,
        match=(
            "terminal action authorization decisions "
            "must not be replaced"
        ),
    ):
        ActionAuthorizationDecisionLedger.create(
            key="invalid-terminal-sequence",
            created_at=UtcTimestamp.parse(
                "2026-07-15T19:37:00Z"
            ),
            producer_id=runtime.human.actor_id,
            decisions=(
                approved,
                rejected,
            ),
        )


def test_ledger_rejects_ambiguous_same_time_decisions() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.DEFERRED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="same-time-defer",
    )
    approved = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.APPROVED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="same-time-approve",
    )

    with pytest.raises(
        FoundationError,
        match="strictly increasing decision times",
    ):
        ActionAuthorizationDecisionLedger.create(
            key="ambiguous-decision-order",
            created_at=UtcTimestamp.parse(
                "2026-07-15T19:36:00Z"
            ),
            producer_id=runtime.human.actor_id,
            decisions=(
                deferred,
                approved,
            ),
        )


def test_ledger_requires_terminal_decision_after_deferral() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.DEFERRED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="unresolved-deferral",
    )
    ledger = ActionAuthorizationDecisionLedger.create(
        key="deferred-decisions",
        created_at=UtcTimestamp.parse(
            "2026-07-15T19:36:00Z"
        ),
        producer_id=runtime.human.actor_id,
        decisions=(
            deferred,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="decision is deferred",
    ):
        ledger.require_terminal_decision(
            deferred.evaluation_id
        )


def test_ledger_rejects_mixed_binding_under_same_evaluation_id() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.DEFERRED
        ),
        decided_at="2026-07-15T19:34:00Z",
        key="bound-defer",
    )
    mixed = replace(
        _decision(
            runtime,
            status=(
                ActionAuthorizationDecisionStatus.APPROVED
            ),
            decided_at="2026-07-15T19:35:00Z",
            key="mixed-approve",
        ),
        request_id=_identifier(
            "action-authorization-request",
            "different-request",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="preserve one bound evaluation",
    ):
        ActionAuthorizationDecisionLedger.create(
            key="mixed-binding-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T19:36:00Z"
            ),
            producer_id=runtime.human.actor_id,
            decisions=(
                deferred,
                mixed,
            ),
        )


def test_ledger_digest_is_independent_of_input_order() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.DEFERRED
        ),
        decided_at="2026-07-15T19:34:00Z",
        key="stable-defer",
    )
    approved = _decision(
        runtime,
        status=(
            ActionAuthorizationDecisionStatus.APPROVED
        ),
        decided_at="2026-07-15T19:35:00Z",
        key="stable-approve",
    )
    created_at = UtcTimestamp.parse(
        "2026-07-15T19:36:00Z"
    )

    first = ActionAuthorizationDecisionLedger.create(
        key="stable-ledger",
        created_at=created_at,
        producer_id=runtime.human.actor_id,
        decisions=(
            deferred,
            approved,
        ),
    )
    second = ActionAuthorizationDecisionLedger.create(
        key="stable-ledger",
        created_at=created_at,
        producer_id=runtime.human.actor_id,
        decisions=(
            approved,
            deferred,
        ),
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
