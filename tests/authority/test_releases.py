"""Tests for fresh-state execution release certificates."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ix_missionproof.authority import (
    ActionAuthorizationDecision,
    ActionAuthorizationDecisionStatus,
    ActionAuthorizationEvaluation,
    ActionAuthorizationEvaluator,
    ActionAuthorizationOutcome,
    ActionAuthorizationRequest,
    ActionExecutionRelease,
    ActionExecutionReleasePath,
    AuthorityGrant,
    AuthorityGrantLedger,
    AuthorityRevocation,
    AuthorityRevocationLedger,
    AuthorityRevocationReason,
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
class _ReleaseRuntime:
    human: ActorIdentity
    agent: ActorIdentity
    release_service: ActorIdentity
    actor_registry: ActorRegistry
    capability: CapabilityDefinition
    capability_catalog: CapabilityCatalog
    grant: AuthorityGrant
    grant_ledger: AuthorityGrantLedger
    request: ActionAuthorizationRequest
    evaluation: ActionAuthorizationEvaluation
    decision: ActionAuthorizationDecision | None
    authority_state: AuthorityStateSnapshot


def _runtime(
    *,
    requires_human_review: bool,
    revoked_after_decision: bool = False,
    include_request_evidence: bool = True,
) -> _ReleaseRuntime:
    human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-01",
        display_name="Mission Reviewer",
        roles=("authority grantor",),
    )
    agent = ActorIdentity.create(
        kind=ActorKind.AGENT,
        key="bounded-agent",
        display_name="Bounded Agent",
        accountability_owner_id=human.actor_id,
    )
    release_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="execution-release-gate",
        display_name="Execution Release Gate",
        roles=("execution release issuer",),
        accountability_owner_id=human.actor_id,
    )
    actor_registry = ActorRegistry.create(
        key="execution-release-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-15T20:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            agent,
            release_service,
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
        key="execution-release-capabilities",
        created_at=UtcTimestamp.parse(
            "2026-07-15T20:00:00Z"
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
            "2026-07-15T20:05:00Z"
        ),
        valid_from=UtcTimestamp.parse(
            "2026-07-15T20:10:00Z"
        ),
        expires_at=UtcTimestamp.parse(
            "2026-07-15T21:00:00Z"
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
        key="execution-release-grants",
        created_at=UtcTimestamp.parse(
            "2026-07-15T20:05:00Z"
        ),
        producer_id=human.actor_id,
        grants=(
            grant,
        ),
    )
    initial_revocations = AuthorityRevocationLedger.create(
        key="initial-execution-release-revocations",
        created_at=UtcTimestamp.parse(
            "2026-07-15T20:05:00Z"
        ),
        producer_id=human.actor_id,
        grant_ledger=grant_ledger,
        revocations=(),
    )
    initial_state = AuthorityStateSnapshot.create(
        key="execution-release-preflight-state",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-15T20:30:00Z"
        ),
        producer_id=release_service.actor_id,
        grant_ledger=grant_ledger,
        revocation_ledger=initial_revocations,
    )
    request = ActionAuthorizationRequest.create(
        key="run-unit-tests",
        requested_at=UtcTimestamp.parse(
            "2026-07-15T20:25:00Z"
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
        justification="Run the bounded unit-test target.",
    )
    evaluation = ActionAuthorizationEvaluator(
        actor_registry=actor_registry,
        capability_catalog=capability_catalog,
        grant_ledger=grant_ledger,
        authority_state=initial_state,
    ).evaluate(
        request,
        key="execution-release-preflight",
    )

    decision: ActionAuthorizationDecision | None = None
    if evaluation.outcome is (
        ActionAuthorizationOutcome.REQUIRE_HUMAN_REVIEW
    ):
        decision = ActionAuthorizationDecision.decide(
            key="approve-unit-tests",
            decided_at=UtcTimestamp.parse(
                "2026-07-15T20:35:00Z"
            ),
            decided_by_id=human.actor_id,
            status=ActionAuthorizationDecisionStatus.APPROVED,
            rationale=(
                "The bounded action and evidence were reviewed."
            ),
            supporting_record_ids=(
                _identifier(
                    "record",
                    "approval-evidence",
                ),
            ),
            request=request,
            evaluation=evaluation,
            grant=grant,
            actor_registry=actor_registry,
        )

    revocations: tuple[AuthorityRevocation, ...] = ()
    revocation_ledger_time = "2026-07-15T20:35:00Z"

    if revoked_after_decision:
        revocation = AuthorityRevocation.revoke(
            key="post-decision-revocation",
            grant_id=grant.grant_id,
            revoked_by_id=human.actor_id,
            revoked_at=UtcTimestamp.parse(
                "2026-07-15T20:36:00Z"
            ),
            reason_code=AuthorityRevocationReason.SAFETY_HOLD,
            reason=(
                "A fresh safety concern invalidated the authority."
            ),
            supporting_record_ids=(
                _identifier(
                    "record",
                    "post-decision-safety-hold",
                ),
            ),
            grant_ledger=grant_ledger,
            actor_registry=actor_registry,
        )
        revocations = (revocation,)
        revocation_ledger_time = "2026-07-15T20:36:00Z"

    current_revocations = AuthorityRevocationLedger.create(
        key="current-execution-release-revocations",
        created_at=UtcTimestamp.parse(
            revocation_ledger_time
        ),
        producer_id=human.actor_id,
        grant_ledger=grant_ledger,
        revocations=revocations,
    )
    authority_state = AuthorityStateSnapshot.create(
        key="fresh-execution-release-state",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-15T20:40:00Z"
        ),
        producer_id=release_service.actor_id,
        grant_ledger=grant_ledger,
        revocation_ledger=current_revocations,
    )

    return _ReleaseRuntime(
        human=human,
        agent=agent,
        release_service=release_service,
        actor_registry=actor_registry,
        capability=capability,
        capability_catalog=capability_catalog,
        grant=grant,
        grant_ledger=grant_ledger,
        request=request,
        evaluation=evaluation,
        decision=decision,
        authority_state=authority_state,
    )


def _issue_release(
    runtime: _ReleaseRuntime,
    *,
    decision: ActionAuthorizationDecision | None = None,
    released_at: str = "2026-07-15T20:41:00Z",
    valid_until: str = "2026-07-15T20:46:00Z",
) -> ActionExecutionRelease:
    return ActionExecutionRelease.issue(
        key="run-unit-tests-release",
        released_at=UtcTimestamp.parse(
            released_at
        ),
        valid_until=UtcTimestamp.parse(
            valid_until
        ),
        released_by_id=runtime.release_service.actor_id,
        request=runtime.request,
        evaluation=runtime.evaluation,
        decision=(
            decision
            if decision is not None
            else runtime.decision
        ),
        grant=runtime.grant,
        grant_ledger=runtime.grant_ledger,
        authority_state=runtime.authority_state,
        actor_registry=runtime.actor_registry,
        capability_catalog=runtime.capability_catalog,
    )


def test_automatic_preflight_release_binds_exact_action() -> None:
    runtime = _runtime(
        requires_human_review=False
    )
    release = _issue_release(runtime)

    assert release.release_path is (
        ActionExecutionReleasePath.AUTOMATIC_PREFLIGHT
    )
    assert release.required_human_approval is False
    assert release.decision_id is None
    assert release.decision_digest is None
    assert release.single_use is True
    assert release.matches_request(runtime.request) is True
    assert release.digest().verifies(
        release.to_payload()
    ) is True


def test_human_approved_release_requires_fresh_authority_state() -> None:
    runtime = _runtime(
        requires_human_review=True
    )
    release = _issue_release(runtime)
    decision = runtime.decision

    assert decision is not None
    assert release.release_path is (
        ActionExecutionReleasePath.HUMAN_APPROVAL
    )
    assert release.required_human_approval is True
    assert release.decision_id == decision.decision_id
    assert release.decision_digest == decision.digest()
    assert (
        release.authority_state_digest
        == runtime.authority_state.digest()
    )


def test_release_has_short_lived_exclusive_end_time() -> None:
    runtime = _runtime(
        requires_human_review=False
    )
    release = _issue_release(runtime)

    assert release.is_time_effective(
        UtcTimestamp.parse(
            "2026-07-15T20:40:59Z"
        )
    ) is False
    assert release.is_time_effective(
        UtcTimestamp.parse(
            "2026-07-15T20:41:00Z"
        )
    ) is True
    assert release.is_time_effective(
        UtcTimestamp.parse(
            "2026-07-15T20:45:59Z"
        )
    ) is True
    assert release.is_time_effective(
        UtcTimestamp.parse(
            "2026-07-15T20:46:00Z"
        )
    ) is False


def test_revocation_after_human_approval_blocks_release() -> None:
    runtime = _runtime(
        requires_human_review=True,
        revoked_after_decision=True,
    )

    with pytest.raises(
        FoundationError,
        match="authority grant is revoked",
    ):
        _issue_release(runtime)


def test_human_review_path_requires_decision() -> None:
    runtime = _runtime(
        requires_human_review=True
    )

    with pytest.raises(
        FoundationError,
        match="requires an approved human decision",
    ):
        ActionExecutionRelease.issue(
            key="missing-decision-release",
            released_at=UtcTimestamp.parse(
                "2026-07-15T20:41:00Z"
            ),
            valid_until=UtcTimestamp.parse(
                "2026-07-15T20:46:00Z"
            ),
            released_by_id=runtime.release_service.actor_id,
            request=runtime.request,
            evaluation=runtime.evaluation,
            decision=None,
            grant=runtime.grant,
            grant_ledger=runtime.grant_ledger,
            authority_state=runtime.authority_state,
            actor_registry=runtime.actor_registry,
            capability_catalog=runtime.capability_catalog,
        )


def test_rejected_decision_cannot_release_execution() -> None:
    runtime = _runtime(
        requires_human_review=True
    )
    rejected = ActionAuthorizationDecision.decide(
        key="reject-unit-tests",
        decided_at=UtcTimestamp.parse(
            "2026-07-15T20:35:00Z"
        ),
        decided_by_id=runtime.human.actor_id,
        status=ActionAuthorizationDecisionStatus.REJECTED,
        rationale="The bounded action was rejected.",
        supporting_record_ids=(
            _identifier(
                "record",
                "rejection-evidence",
            ),
        ),
        request=runtime.request,
        evaluation=runtime.evaluation,
        grant=runtime.grant,
        actor_registry=runtime.actor_registry,
    )

    with pytest.raises(
        FoundationError,
        match="requires an approved human decision",
    ):
        _issue_release(
            runtime,
            decision=rejected,
        )


def test_blocked_preflight_cannot_receive_release() -> None:
    runtime = _runtime(
        requires_human_review=False,
        include_request_evidence=False,
    )

    assert runtime.evaluation.outcome is (
        ActionAuthorizationOutcome.BLOCK
    )

    with pytest.raises(
        FoundationError,
        match="blocked authorization preflight",
    ):
        _issue_release(runtime)


def test_automatic_release_rejects_unnecessary_human_decision() -> None:
    automatic = _runtime(
        requires_human_review=False
    )
    reviewed = _runtime(
        requires_human_review=True
    )

    with pytest.raises(
        FoundationError,
        match="must not include a human decision",
    ):
        _issue_release(
            automatic,
            decision=reviewed.decision,
        )


def test_release_service_must_be_separate_accountable_machine() -> None:
    runtime = _runtime(
        requires_human_review=False
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ActionExecutionRelease.issue(
            key="human-issued-release",
            released_at=UtcTimestamp.parse(
                "2026-07-15T20:41:00Z"
            ),
            valid_until=UtcTimestamp.parse(
                "2026-07-15T20:46:00Z"
            ),
            released_by_id=runtime.human.actor_id,
            request=runtime.request,
            evaluation=runtime.evaluation,
            decision=None,
            grant=runtime.grant,
            grant_ledger=runtime.grant_ledger,
            authority_state=runtime.authority_state,
            actor_registry=runtime.actor_registry,
            capability_catalog=runtime.capability_catalog,
        )


def test_release_service_requires_accountable_human_owner() -> None:
    runtime = _runtime(
        requires_human_review=False
    )
    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-release-gate",
        display_name="Unowned Release Gate",
    )
    registry = ActorRegistry.create(
        key="unowned-release-actors",
        created_at=runtime.actor_registry.created_at,
        producer_id=runtime.human.actor_id,
        actors=(
            runtime.human,
            runtime.agent,
            unowned_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must identify an accountable human owner",
    ):
        ActionExecutionRelease.issue(
            key="unowned-service-release",
            released_at=UtcTimestamp.parse(
                "2026-07-15T20:41:00Z"
            ),
            valid_until=UtcTimestamp.parse(
                "2026-07-15T20:46:00Z"
            ),
            released_by_id=unowned_service.actor_id,
            request=runtime.request,
            evaluation=runtime.evaluation,
            decision=None,
            grant=runtime.grant,
            grant_ledger=runtime.grant_ledger,
            authority_state=runtime.authority_state,
            actor_registry=registry,
            capability_catalog=runtime.capability_catalog,
        )


def test_release_requires_state_newer_than_human_decision() -> None:
    runtime = _runtime(
        requires_human_review=True
    )
    stale_revocations = AuthorityRevocationLedger.create(
        key="stale-release-revocations",
        created_at=UtcTimestamp.parse(
            "2026-07-15T20:05:00Z"
        ),
        producer_id=runtime.human.actor_id,
        grant_ledger=runtime.grant_ledger,
        revocations=(),
    )
    stale_state = AuthorityStateSnapshot.create(
        key="stale-release-state",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-15T20:34:00Z"
        ),
        producer_id=runtime.release_service.actor_id,
        grant_ledger=runtime.grant_ledger,
        revocation_ledger=stale_revocations,
    )

    with pytest.raises(
        FoundationError,
        match="after the latest evaluation or human decision",
    ):
        ActionExecutionRelease.issue(
            key="stale-state-release",
            released_at=UtcTimestamp.parse(
                "2026-07-15T20:41:00Z"
            ),
            valid_until=UtcTimestamp.parse(
                "2026-07-15T20:46:00Z"
            ),
            released_by_id=runtime.release_service.actor_id,
            request=runtime.request,
            evaluation=runtime.evaluation,
            decision=runtime.decision,
            grant=runtime.grant,
            grant_ledger=runtime.grant_ledger,
            authority_state=stale_state,
            actor_registry=runtime.actor_registry,
            capability_catalog=runtime.capability_catalog,
        )


def test_release_cannot_outlive_authority_grant() -> None:
    runtime = _runtime(
        requires_human_review=False
    )

    with pytest.raises(
        FoundationError,
        match="must not outlive the authority grant",
    ):
        _issue_release(
            runtime,
            released_at="2026-07-15T20:50:00Z",
            valid_until="2026-07-15T21:01:00Z",
        )


def test_release_rejects_action_substitution() -> None:
    runtime = _runtime(
        requires_human_review=False
    )
    release = _issue_release(runtime)
    substituted_request = ActionAuthorizationRequest.create(
        key="run-deployment-tests",
        requested_at=runtime.request.requested_at,
        requester_id=runtime.request.requester_id,
        grant_id=runtime.request.grant_id,
        capability_id=runtime.request.capability_id,
        target_id=runtime.request.target_id,
        action={
            "arguments": [
                "tests/deployment",
            ],
            "operation": "run-tests",
            "tool_id": "test-runner",
        },
        evidence_record_ids=runtime.request.evidence_record_ids,
        justification="Run a different test target.",
    )

    assert release.matches_request(
        substituted_request
    ) is False
