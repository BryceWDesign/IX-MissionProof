"""Tests for single-use execution receipts and consumption ledger."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ix_missionproof.authority import (
    ActionAuthorizationEvaluation,
    ActionAuthorizationEvaluator,
    ActionAuthorizationRequest,
    ActionExecutionLedger,
    ActionExecutionReceipt,
    ActionExecutionRelease,
    ActionExecutionStatus,
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
    ContentDigest,
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
class _ExecutionRuntime:
    human: ActorIdentity
    agent: ActorIdentity
    release_service: ActorIdentity
    execution_service: ActorIdentity
    actor_registry: ActorRegistry
    capability: CapabilityDefinition
    capability_catalog: CapabilityCatalog
    grant: AuthorityGrant
    grant_ledger: AuthorityGrantLedger
    request: ActionAuthorizationRequest
    evaluation: ActionAuthorizationEvaluation
    authority_state: AuthorityStateSnapshot
    release: ActionExecutionRelease


def _runtime(
    *,
    suffix: str = "one",
    executor_owned: bool = True,
) -> _ExecutionRuntime:
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
        accountability_owner_id=human.actor_id,
    )
    execution_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="bounded-execution-service",
        display_name="Bounded Execution Service",
        accountability_owner_id=(
            human.actor_id
            if executor_owned
            else None
        ),
    )
    actor_registry = ActorRegistry.create(
        key=f"execution-actors-{suffix}",
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            agent,
            release_service,
            execution_service,
        ),
    )
    capability = CapabilityDefinition.create(
        key="execute-bounded-tool",
        operation=CapabilityOperation.EXECUTE,
        target_type="bounded tool",
        summary="Execute one exact bounded tool.",
        risk_tier=CapabilityRiskTier.HIGH,
        permitted_actor_kinds=(
            ActorKind.AGENT,
        ),
    )
    capability_catalog = CapabilityCatalog.create(
        key=f"execution-capabilities-{suffix}",
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:00:00Z"
        ),
        producer_id=human.actor_id,
        capabilities=(
            capability,
        ),
    )
    grant = AuthorityGrant.issue(
        key=f"bounded-agent-tool-grant-{suffix}",
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=human.actor_id,
        issued_at=UtcTimestamp.parse(
            "2026-07-15T21:05:00Z"
        ),
        valid_from=UtcTimestamp.parse(
            "2026-07-15T21:10:00Z"
        ),
        expires_at=UtcTimestamp.parse(
            "2026-07-15T22:00:00Z"
        ),
        actor_registry=actor_registry,
        capability_catalog=capability_catalog,
        target_ids=(
            _identifier(
                "bounded-tool",
                f"test-runner-{suffix}",
            ),
        ),
        supporting_record_ids=(
            _identifier(
                "record",
                f"grant-evidence-{suffix}",
            ),
        ),
    )
    grant_ledger = AuthorityGrantLedger.create(
        key=f"execution-grants-{suffix}",
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:05:00Z"
        ),
        producer_id=human.actor_id,
        grants=(
            grant,
        ),
    )
    revocation_ledger = AuthorityRevocationLedger.create(
        key=f"execution-revocations-{suffix}",
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:05:00Z"
        ),
        producer_id=human.actor_id,
        grant_ledger=grant_ledger,
        revocations=(),
    )
    authority_state = AuthorityStateSnapshot.create(
        key=f"execution-state-{suffix}",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-15T21:30:00Z"
        ),
        producer_id=release_service.actor_id,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
    )
    request = ActionAuthorizationRequest.create(
        key=f"run-unit-tests-{suffix}",
        requested_at=UtcTimestamp.parse(
            "2026-07-15T21:25:00Z"
        ),
        requester_id=agent.actor_id,
        grant_id=grant.grant_id,
        capability_id=capability.capability_id,
        target_id=_identifier(
            "bounded-tool",
            f"test-runner-{suffix}",
        ),
        action={
            "arguments": [
                "tests/unit",
            ],
            "operation": "run-tests",
            "tool_id": f"test-runner-{suffix}",
        },
        evidence_record_ids=(
            _identifier(
                "record",
                f"request-evidence-{suffix}",
            ),
        ),
        justification="Run the bounded unit-test target.",
    )
    evaluation = ActionAuthorizationEvaluator(
        actor_registry=actor_registry,
        capability_catalog=capability_catalog,
        grant_ledger=grant_ledger,
        authority_state=authority_state,
    ).evaluate(
        request,
        key=f"execution-preflight-{suffix}",
    )
    release = ActionExecutionRelease.issue(
        key=f"execution-release-{suffix}",
        released_at=UtcTimestamp.parse(
            "2026-07-15T21:31:00Z"
        ),
        valid_until=UtcTimestamp.parse(
            "2026-07-15T21:36:00Z"
        ),
        released_by_id=release_service.actor_id,
        request=request,
        evaluation=evaluation,
        decision=None,
        grant=grant,
        grant_ledger=grant_ledger,
        authority_state=authority_state,
        actor_registry=actor_registry,
        capability_catalog=capability_catalog,
    )

    return _ExecutionRuntime(
        human=human,
        agent=agent,
        release_service=release_service,
        execution_service=execution_service,
        actor_registry=actor_registry,
        capability=capability,
        capability_catalog=capability_catalog,
        grant=grant,
        grant_ledger=grant_ledger,
        request=request,
        evaluation=evaluation,
        authority_state=authority_state,
        release=release,
    )


def _receipt(
    runtime: _ExecutionRuntime,
    *,
    key: str = "unit-test-execution",
    status: ActionExecutionStatus = ActionExecutionStatus.SUCCEEDED,
    started_at: str = "2026-07-15T21:32:00Z",
    completed_at: str = "2026-07-15T21:33:00Z",
    exit_code: int | None = 0,
    boundary_note: str | None = None,
) -> ActionExecutionReceipt:
    return ActionExecutionReceipt.record(
        key=key,
        started_at=UtcTimestamp.parse(
            started_at
        ),
        completed_at=UtcTimestamp.parse(
            completed_at
        ),
        executed_by_id=runtime.execution_service.actor_id,
        status=status,
        summary="Bounded unit tests completed.",
        result={
            "passed": 42,
            "failed": 0,
            "target": "tests/unit",
        },
        exit_code=exit_code,
        release=runtime.release,
        request=runtime.request,
        actor_registry=runtime.actor_registry,
        stdout_digest=ContentDigest.from_payload(
            {
                "text": "42 passed",
            },
            domain="execution-stdout",
        ),
        stderr_digest=None,
        boundary_note=boundary_note,
        evidence_record_ids=(
            _identifier(
                "record",
                f"{key}-evidence",
            ),
        ),
    )


def test_successful_receipt_consumes_exact_release() -> None:
    runtime = _runtime()
    receipt = _receipt(runtime)

    assert receipt.succeeded is True
    assert receipt.blocks_progress is False
    assert receipt.consumes_release is True
    assert receipt.release_id == runtime.release.release_id
    assert receipt.request_id == runtime.request.request_id
    assert receipt.requester_id == runtime.agent.actor_id
    assert receipt.action_digest == runtime.request.action_digest
    assert receipt.release_digest == runtime.release.digest()
    assert receipt.request_digest == runtime.request.digest()
    assert (
        receipt.actor_registry_digest
        == runtime.actor_registry.digest()
    )
    assert receipt.digest().verifies(
        receipt.to_payload()
    ) is True


def test_execution_result_is_captured_immutably() -> None:
    runtime = _runtime()
    passed_tests: JsonArray = [
        "test_authority",
    ]
    result: JsonObject = {
        "passed_tests": passed_tests,
    }

    receipt = ActionExecutionReceipt.record(
        key="immutable-result",
        started_at=UtcTimestamp.parse(
            "2026-07-15T21:32:00Z"
        ),
        completed_at=UtcTimestamp.parse(
            "2026-07-15T21:33:00Z"
        ),
        executed_by_id=runtime.execution_service.actor_id,
        status=ActionExecutionStatus.SUCCEEDED,
        summary="Bounded unit tests completed.",
        result=result,
        exit_code=0,
        release=runtime.release,
        request=runtime.request,
        actor_registry=runtime.actor_registry,
    )

    passed_tests.append(
        "test_replay"
    )

    assert receipt.result.require_object() == {
        "passed_tests": [
            "test_authority",
        ],
    }
    assert receipt.result_digest.verifies(
        receipt.result.to_value()
    ) is True


def test_execution_must_start_inside_release_window() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="must start while the release is time-effective",
    ):
        _receipt(
            runtime,
            started_at="2026-07-15T21:36:00Z",
            completed_at="2026-07-15T21:37:00Z",
        )


def test_execution_may_finish_after_release_window() -> None:
    runtime = _runtime()
    receipt = _receipt(
        runtime,
        started_at="2026-07-15T21:35:59Z",
        completed_at="2026-07-15T21:40:00Z",
    )

    assert receipt.started_at.value < (
        runtime.release.valid_until.value
    )
    assert receipt.completed_at.value > (
        runtime.release.valid_until.value
    )


def test_action_substitution_is_rejected() -> None:
    runtime = _runtime()
    substituted_request = ActionAuthorizationRequest.create(
        key="substituted-request",
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
            "tool_id": "test-runner-one",
        },
        evidence_record_ids=(
            runtime.request.evidence_record_ids
        ),
        justification="Run a different test target.",
    )

    with pytest.raises(
        FoundationError,
        match="does not match the supplied request",
    ):
        ActionExecutionReceipt.record(
            key="substituted-execution",
            started_at=UtcTimestamp.parse(
                "2026-07-15T21:32:00Z"
            ),
            completed_at=UtcTimestamp.parse(
                "2026-07-15T21:33:00Z"
            ),
            executed_by_id=runtime.execution_service.actor_id,
            status=ActionExecutionStatus.SUCCEEDED,
            summary="Substituted action attempt.",
            result={
                "passed": 1,
            },
            exit_code=0,
            release=runtime.release,
            request=substituted_request,
            actor_registry=runtime.actor_registry,
        )


def test_executor_requires_accountable_human_owner() -> None:
    runtime = _runtime(
        executor_owned=False
    )

    with pytest.raises(
        FoundationError,
        match="must identify an accountable human owner",
    ):
        _receipt(runtime)


def test_human_actor_cannot_be_runtime_executor() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="requires an executable machine actor",
    ):
        ActionExecutionReceipt.record(
            key="human-execution",
            started_at=UtcTimestamp.parse(
                "2026-07-15T21:32:00Z"
            ),
            completed_at=UtcTimestamp.parse(
                "2026-07-15T21:33:00Z"
            ),
            executed_by_id=runtime.human.actor_id,
            status=ActionExecutionStatus.SUCCEEDED,
            summary="Invalid human runtime execution.",
            result={
                "passed": 1,
            },
            exit_code=0,
            release=runtime.release,
            request=runtime.request,
            actor_registry=runtime.actor_registry,
        )


def test_successful_execution_requires_zero_exit_code() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="requires exit_code 0",
    ):
        _receipt(
            runtime,
            exit_code=1,
        )


def test_failed_execution_requires_nonzero_exit_code() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="requires a non-zero exit_code",
    ):
        _receipt(
            runtime,
            status=ActionExecutionStatus.FAILED,
            exit_code=0,
        )


def test_blocked_execution_requires_boundary_note() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="require a boundary_note",
    ):
        _receipt(
            runtime,
            status=ActionExecutionStatus.BLOCKED,
            exit_code=None,
        )

    receipt = _receipt(
        runtime,
        key="sandbox-boundary-block",
        status=ActionExecutionStatus.BLOCKED,
        exit_code=None,
        boundary_note=(
            "Sandbox policy denied the requested operation."
        ),
    )

    assert receipt.blocks_progress is True
    assert receipt.succeeded is False


def test_execution_ledger_enforces_single_use_release() -> None:
    runtime = _runtime()
    receipt = _receipt(runtime)
    ledger = ActionExecutionLedger.create(
        key="runtime-executions",
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:34:00Z"
        ),
        producer_id=runtime.execution_service.actor_id,
        receipts=(
            receipt,
        ),
    )

    assert ledger.is_release_consumed(
        runtime.release.release_id
    ) is True
    assert ledger.receipt_for_release(
        runtime.release.release_id
    ) == receipt
    assert ledger.require_receipt(
        receipt.receipt_id
    ) == receipt

    with pytest.raises(
        FoundationError,
        match="may be consumed only once",
    ):
        ActionExecutionLedger.create(
            key="duplicate-release-consumption",
            created_at=UtcTimestamp.parse(
                "2026-07-15T21:34:00Z"
            ),
            producer_id=runtime.execution_service.actor_id,
            receipts=(
                receipt,
                receipt,
            ),
        )


def test_append_rejects_reused_release() -> None:
    runtime = _runtime()
    first = _receipt(
        runtime,
        key="first-consumption",
    )
    second = _receipt(
        runtime,
        key="second-consumption",
    )
    ledger = ActionExecutionLedger.create(
        key="append-only-executions",
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:31:00Z"
        ),
        producer_id=runtime.execution_service.actor_id,
    )
    ledger = ledger.append(
        first,
        created_at=UtcTimestamp.parse(
            "2026-07-15T21:34:00Z"
        ),
        producer_id=runtime.execution_service.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="was already consumed",
    ):
        ledger.append(
            second,
            created_at=UtcTimestamp.parse(
                "2026-07-15T21:35:00Z"
            ),
            producer_id=runtime.execution_service.actor_id,
        )


def test_execution_ledger_orders_receipts_deterministically() -> None:
    first_runtime = _runtime(
        suffix="first"
    )
    second_runtime = _runtime(
        suffix="second"
    )
    first = _receipt(
        first_runtime,
        key="later-receipt",
        started_at="2026-07-15T21:33:00Z",
        completed_at="2026-07-15T21:34:00Z",
    )
    second = _receipt(
        second_runtime,
        key="earlier-receipt",
        started_at="2026-07-15T21:32:00Z",
        completed_at="2026-07-15T21:33:00Z",
    )
    created_at = UtcTimestamp.parse(
        "2026-07-15T21:35:00Z"
    )

    first_ledger = ActionExecutionLedger.create(
        key="stable-executions",
        created_at=created_at,
        producer_id=first_runtime.execution_service.actor_id,
        receipts=(
            first,
            second,
        ),
    )
    second_ledger = ActionExecutionLedger.create(
        key="stable-executions",
        created_at=created_at,
        producer_id=first_runtime.execution_service.actor_id,
        receipts=(
            second,
            first,
        ),
    )

    assert (
        first_ledger.canonical_payload()
        == second_ledger.canonical_payload()
    )
    assert first_ledger.digest() == second_ledger.digest()


def test_execution_ledger_must_not_predate_receipt() -> None:
    runtime = _runtime()
    receipt = _receipt(runtime)

    with pytest.raises(
        FoundationError,
        match="must not predate a contained receipt",
    ):
        ActionExecutionLedger.create(
            key="premature-execution-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T21:32:59Z"
            ),
            producer_id=runtime.execution_service.actor_id,
            receipts=(
                receipt,
            ),
        )
