"""Tests for revocation-aware per-action authorization preflight."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.authority import (
    ActionAuthorizationEvaluator,
    ActionAuthorizationOutcome,
    ActionAuthorizationReason,
    ActionAuthorizationRequest,
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
    ActorStatus,
    FoundationError,
    JsonArray,
    JsonObject,
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
class _Runtime:
    human: ActorIdentity
    agent: ActorIdentity
    actor_registry: ActorRegistry
    capability: CapabilityDefinition
    capability_catalog: CapabilityCatalog
    grant: AuthorityGrant
    grant_ledger: AuthorityGrantLedger
    revocation_ledger: AuthorityRevocationLedger
    authority_state: AuthorityStateSnapshot


def _runtime(
    *,
    requires_human_review: bool = False,
    revoked: bool = False,
) -> _Runtime:
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
        roles=("bounded tool executor",),
        accountability_owner_id=human.actor_id,
    )
    actor_registry = ActorRegistry.create(
        key="action-authorization-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-15T18:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(human, agent),
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
        permitted_actor_kinds=(ActorKind.AGENT,),
        requires_separate_human_authorization=(
            requires_human_review
        ),
    )
    capability_catalog = CapabilityCatalog.create(
        key="action-authorization-capabilities",
        created_at=UtcTimestamp.parse(
            "2026-07-15T18:00:00Z"
        ),
        producer_id=human.actor_id,
        capabilities=(capability,),
    )
    grant = AuthorityGrant.issue(
        key="bounded-agent-tool-grant",
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=human.actor_id,
        issued_at=UtcTimestamp.parse(
            "2026-07-15T18:05:00Z"
        ),
        valid_from=UtcTimestamp.parse(
            "2026-07-15T18:10:00Z"
        ),
        expires_at=UtcTimestamp.parse(
            "2026-07-15T19:00:00Z"
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
        constraints={
            "allowed_arguments": [
                "tests/unit",
            ]
        },
    )
    grant_ledger = AuthorityGrantLedger.create(
        key="action-authorization-grants",
        created_at=UtcTimestamp.parse(
            "2026-07-15T18:05:00Z"
        ),
        producer_id=human.actor_id,
        grants=(grant,),
    )

    revocations: tuple[AuthorityRevocation, ...] = ()
    revocation_created_at = "2026-07-15T18:05:00Z"

    if revoked:
        revocation = AuthorityRevocation.revoke(
            key="bounded-agent-tool-revocation",
            grant_id=grant.grant_id,
            revoked_by_id=human.actor_id,
            revoked_at=UtcTimestamp.parse(
                "2026-07-15T18:20:00Z"
            ),
            reason_code=(
                AuthorityRevocationReason.HUMAN_WITHDRAWAL
            ),
            reason=(
                "The human grantor withdrew the "
                "execution authority."
            ),
            supporting_record_ids=(
                _identifier(
                    "record",
                    "revocation-evidence",
                ),
            ),
            grant_ledger=grant_ledger,
            actor_registry=actor_registry,
        )
        revocations = (revocation,)
        revocation_created_at = "2026-07-15T18:20:00Z"

    revocation_ledger = AuthorityRevocationLedger.create(
        key="action-authorization-revocations",
        created_at=UtcTimestamp.parse(
            revocation_created_at
        ),
        producer_id=human.actor_id,
        grant_ledger=grant_ledger,
        revocations=revocations,
    )
    authority_state = AuthorityStateSnapshot.create(
        key="action-authorization-state",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-15T18:30:00Z"
        ),
        producer_id=human.actor_id,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
    )

    return _Runtime(
        human=human,
        agent=agent,
        actor_registry=actor_registry,
        capability=capability,
        capability_catalog=capability_catalog,
        grant=grant,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
        authority_state=authority_state,
    )


def _request(
    runtime: _Runtime,
    *,
    key: str = "run-unit-tests",
    requester_id: ScopedIdentifier | None = None,
    capability_id: ScopedIdentifier | None = None,
    grant_id: ScopedIdentifier | None = None,
    target_id: ScopedIdentifier | None = None,
    evidence_record_ids: (
        tuple[ScopedIdentifier, ...] | None
    ) = None,
    requested_at: str = "2026-07-15T18:25:00Z",
) -> ActionAuthorizationRequest:
    return ActionAuthorizationRequest.create(
        key=key,
        requested_at=UtcTimestamp.parse(requested_at),
        requester_id=(
            requester_id
            or runtime.agent.actor_id
        ),
        grant_id=(
            grant_id
            or runtime.grant.grant_id
        ),
        capability_id=(
            capability_id
            or runtime.capability.capability_id
        ),
        target_id=(
            target_id
            or _identifier(
                "bounded-tool",
                "test-runner",
            )
        ),
        action={
            "arguments": [
                "tests/unit",
            ],
            "operation": "run-tests",
            "tool_id": "test-runner",
        },
        evidence_record_ids=(
            evidence_record_ids
            if evidence_record_ids is not None
            else (
                _identifier(
                    "record",
                    "request-evidence",
                ),
            )
        ),
        justification=(
            "Run the bounded unit-test target."
        ),
        metadata={
            "correlation_id": "run:unit-tests-0001",
        },
    )


def _evaluator(
    runtime: _Runtime,
    *,
    actor_registry: ActorRegistry | None = None,
    capability_catalog: CapabilityCatalog | None = None,
    grant_ledger: AuthorityGrantLedger | None = None,
    authority_state: AuthorityStateSnapshot | None = None,
) -> ActionAuthorizationEvaluator:
    return ActionAuthorizationEvaluator(
        actor_registry=(
            actor_registry
            or runtime.actor_registry
        ),
        capability_catalog=(
            capability_catalog
            or runtime.capability_catalog
        ),
        grant_ledger=(
            grant_ledger
            or runtime.grant_ledger
        ),
        authority_state=(
            authority_state
            or runtime.authority_state
        ),
    )


def test_request_captures_action_without_retaining_input() -> None:
    runtime = _runtime()
    arguments: JsonArray = ["tests/unit"]
    action: JsonObject = {
        "arguments": arguments,
        "operation": "run-tests",
    }
    request = ActionAuthorizationRequest.create(
        key="immutable-action",
        requested_at=UtcTimestamp.parse(
            "2026-07-15T18:25:00Z"
        ),
        requester_id=runtime.agent.actor_id,
        grant_id=runtime.grant.grant_id,
        capability_id=runtime.capability.capability_id,
        target_id=_identifier(
            "bounded-tool",
            "test-runner",
        ),
        action=action,
        evidence_record_ids=(
            _identifier(
                "record",
                "request-evidence",
            ),
        ),
        justification=(
            "Run the bounded unit-test target."
        ),
    )

    arguments.append("tests/integration")

    assert request.action.require_object() == {
        "arguments": ["tests/unit"],
        "operation": "run-tests",
    }
    assert request.action_digest.verifies(
        request.action.to_value()
    ) is True
    assert request.digest().verifies(
        request.to_payload()
    ) is True


def test_active_grant_allows_action_without_human_boundary() -> None:
    runtime = _runtime()
    evaluation = _evaluator(runtime).evaluate(
        _request(runtime),
        key="allow-unit-tests",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.ALLOW
    )
    assert evaluation.reasons == (
        ActionAuthorizationReason.ACTIVE_GRANT,
    )
    assert evaluation.permits_execution is True
    assert evaluation.requires_human_review is False
    assert evaluation.blocked is False
    assert evaluation.grant_digest == runtime.grant.digest()


def test_active_grant_preserves_human_authorization() -> None:
    runtime = _runtime(
        requires_human_review=True
    )
    evaluation = _evaluator(runtime).evaluate(
        _request(runtime),
        key="review-unit-tests",
    )

    assert evaluation.outcome is (
        ActionAuthorizationOutcome
        .REQUIRE_HUMAN_REVIEW
    )
    assert set(evaluation.reasons) == {
        ActionAuthorizationReason.ACTIVE_GRANT,
        ActionAuthorizationReason
        .SEPARATE_HUMAN_AUTHORIZATION_REQUIRED,
    }
    assert evaluation.permits_execution is False
    assert evaluation.requires_human_review is True
    assert evaluation.blocked is False


def test_revoked_grant_blocks_action() -> None:
    runtime = _runtime(revoked=True)
    evaluation = _evaluator(runtime).evaluate(
        _request(runtime),
        key="block-revoked-grant",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.BLOCK
    )
    assert (
        ActionAuthorizationReason.GRANT_NOT_ACTIVE
        in evaluation.reasons
    )
    assert evaluation.permits_execution is False
    assert evaluation.blocked is True


def test_target_must_match_capability_and_grant_scope() -> None:
    runtime = _runtime()

    wrong_type = _evaluator(runtime).evaluate(
        _request(
            runtime,
            key="wrong-target-type",
            target_id=_identifier(
                "workspace",
                "test-runner",
            ),
        ),
        key="block-wrong-target-type",
    )
    uncovered_target = _evaluator(runtime).evaluate(
        _request(
            runtime,
            key="uncovered-target",
            target_id=_identifier(
                "bounded-tool",
                "deployment-runner",
            ),
        ),
        key="block-uncovered-target",
    )

    assert (
        ActionAuthorizationReason.TARGET_TYPE_MISMATCH
        in wrong_type.reasons
    )
    assert (
        ActionAuthorizationReason.TARGET_NOT_COVERED
        in wrong_type.reasons
    )
    assert uncovered_target.reasons == (
        ActionAuthorizationReason.TARGET_NOT_COVERED,
    )


def test_evidence_bound_capability_blocks_missing_evidence() -> None:
    runtime = _runtime()
    evaluation = _evaluator(runtime).evaluate(
        _request(
            runtime,
            evidence_record_ids=(),
        ),
        key="block-missing-evidence",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.BLOCK
    )
    assert evaluation.reasons == (
        ActionAuthorizationReason
        .REQUIRED_EVIDENCE_MISSING,
    )


def test_unknown_requester_cannot_reuse_actor_grant() -> None:
    runtime = _runtime()
    evaluation = _evaluator(runtime).evaluate(
        _request(
            runtime,
            requester_id=_identifier(
                "agent",
                "unknown-agent",
            ),
        ),
        key="block-unknown-requester",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.BLOCK
    )
    assert set(evaluation.reasons) == {
        ActionAuthorizationReason
        .GRANT_REQUESTER_MISMATCH,
        ActionAuthorizationReason
        .REQUESTER_NOT_REGISTERED,
    }


def test_inactive_requester_is_blocked_by_old_grant() -> None:
    runtime = _runtime()
    suspended_agent = replace(
        runtime.agent,
        status=ActorStatus.SUSPENDED,
    )
    updated_registry = ActorRegistry.create(
        key="suspended-action-authorization-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-15T18:25:00Z"
        ),
        producer_id=runtime.human.actor_id,
        actors=(
            runtime.human,
            suspended_agent,
        ),
    )
    evaluation = _evaluator(
        runtime,
        actor_registry=updated_registry,
    ).evaluate(
        _request(runtime),
        key="block-suspended-requester",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.BLOCK
    )
    assert set(evaluation.reasons) == {
        ActionAuthorizationReason
        .ACTOR_REGISTRY_BINDING_MISMATCH,
        ActionAuthorizationReason
        .REQUESTER_NOT_ACTIVE,
    }


def test_grant_binding_blocks_changed_capability_catalog() -> None:
    runtime = _runtime()
    changed_capability = replace(
        runtime.capability,
        summary=(
            "Changed capability text after grant issuance."
        ),
    )
    changed_catalog = CapabilityCatalog.create(
        key="changed-action-authorization-capabilities",
        created_at=UtcTimestamp.parse(
            "2026-07-15T18:25:00Z"
        ),
        producer_id=runtime.human.actor_id,
        capabilities=(changed_capability,),
    )
    evaluation = _evaluator(
        runtime,
        capability_catalog=changed_catalog,
    ).evaluate(
        _request(runtime),
        key="block-changed-capability",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.BLOCK
    )
    assert set(evaluation.reasons) == {
        ActionAuthorizationReason
        .CAPABILITY_BINDING_MISMATCH,
        ActionAuthorizationReason
        .CAPABILITY_CATALOG_BINDING_MISMATCH,
    }


def test_unknown_grant_and_capability_are_reported() -> None:
    runtime = _runtime()
    evaluation = _evaluator(runtime).evaluate(
        _request(
            runtime,
            grant_id=_identifier(
                "authority-grant",
                "unknown-grant",
            ),
            capability_id=_identifier(
                "capability",
                "unknown-capability",
            ),
        ),
        key="block-unknown-authority",
    )

    assert (
        evaluation.outcome
        is ActionAuthorizationOutcome.BLOCK
    )
    assert set(evaluation.reasons) == {
        ActionAuthorizationReason
        .CAPABILITY_NOT_FOUND,
        ActionAuthorizationReason
        .GRANT_NOT_FOUND,
    }
    assert evaluation.grant_digest is None


def test_authority_state_must_not_predate_request() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match=(
            "authority state must not predate "
            "the action request"
        ),
    ):
        _evaluator(runtime).evaluate(
            _request(
                runtime,
                requested_at="2026-07-15T18:31:00Z",
            ),
            key="future-request",
        )


def test_evaluator_rejects_different_grant_ledger() -> None:
    runtime = _runtime()
    different_ledger = AuthorityGrantLedger.create(
        key="different-action-authorization-grants",
        created_at=runtime.grant_ledger.created_at,
        producer_id=runtime.human.actor_id,
        grants=(),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "authority state is not bound to "
            "the supplied grant ledger"
        ),
    ):
        _evaluator(
            runtime,
            grant_ledger=different_ledger,
        )


def test_evaluation_binds_all_authority_inputs() -> None:
    runtime = _runtime(
        requires_human_review=True
    )
    request = _request(runtime)
    evaluation = _evaluator(runtime).evaluate(
        request,
        key="bound-evaluation",
    )
    payload = evaluation.to_payload()

    assert payload["request_digest"] == (
        request.digest().to_payload()
    )
    assert payload["authority_state_digest"] == (
        runtime.authority_state.digest().to_payload()
    )
    assert payload["actor_registry_digest"] == (
        runtime.actor_registry.digest().to_payload()
    )
    assert payload["capability_catalog_digest"] == (
        runtime.capability_catalog.digest().to_payload()
    )
    assert evaluation.digest().verifies(payload) is True
