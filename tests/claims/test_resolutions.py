"""Tests for claim adjudication ledgers and resolved claim states."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimAdjudicationDecision,
    ClaimAdjudicationDecisionLedger,
    ClaimAdjudicationDecisionStatus,
    ClaimCatalog,
    ClaimCriticality,
    ClaimEvidenceEvaluation,
    ClaimEvidenceEvaluationStatus,
    ClaimEvidenceRequirement,
    ClaimKind,
    ClaimRequirementEvaluation,
    ClaimRequirementEvaluationOutcome,
    ClaimRequirementEvaluationReason,
    ClaimResolution,
    ClaimResolutionSource,
    ClaimResolutionStatus,
    ClaimReviewLevel,
    ClaimSpecification,
)
from ix_missionproof.evidence import EvidenceKind
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    ContentDigest,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _identifier(namespace: str, key: str) -> ScopedIdentifier:
    return ScopedIdentifier.create(
        namespace=namespace,
        key=key,
    )


def _digest(domain: str, key: str) -> ContentDigest:
    return ContentDigest.from_payload(
        {"key": key},
        domain=domain,
    )


@dataclass(frozen=True, slots=True)
class _Runtime:
    owner: ActorIdentity
    reviewer: ActorIdentity
    author_service: ActorIdentity
    evaluator_system: ActorIdentity
    ledger_service: ActorIdentity
    resolution_system: ActorIdentity
    registry: ActorRegistry
    requirement: ClaimEvidenceRequirement
    claim: ClaimSpecification
    catalog: ClaimCatalog
    admitted_record_ids: tuple[ScopedIdentifier, ...]
    adverse_record_id: ScopedIdentifier
    unresolved_record_id: ScopedIdentifier
    excluded_record_id: ScopedIdentifier


def _runtime(
    *,
    catalog_key: str = "claim-resolution-catalog",
) -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="claim-owner",
        display_name="Claim Author Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-reviewer",
        display_name="Independent Claim Reviewer",
    )
    author_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-service",
        display_name="Claim Service",
        accountability_owner_id=owner.actor_id,
    )
    evaluator_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-evaluation-system",
        display_name="Claim Evaluation System",
        accountability_owner_id=reviewer.actor_id,
    )
    ledger_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-decision-ledger-service",
        display_name="Claim Decision Ledger Service",
        accountability_owner_id=reviewer.actor_id,
    )
    resolution_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-resolution-system",
        display_name="Claim Resolution System",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-resolution-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T05:00:00Z"
        ),
        producer_id=reviewer.actor_id,
        actors=(
            owner,
            reviewer,
            author_service,
            evaluator_system,
            ledger_service,
            resolution_system,
        ),
    )
    requirement = ClaimEvidenceRequirement.create(
        key="bounded-runtime-proof",
        summary="Provide measured and executed evidence.",
        acceptable_kinds=(
            EvidenceKind.MEASUREMENT,
            EvidenceKind.TEST_RESULT,
        ),
        minimum_records=2,
        require_primary_evidence=True,
        require_subject_match=True,
        require_independent_producers=True,
        falsification_conditions=(
            "Any admitted relevant test reports failure.",
            "The required evidence count is not met.",
        ),
    )
    claim = ClaimSpecification.create(
        key="bounded-runtime-safety",
        created_at=UtcTimestamp.parse(
            "2026-07-16T05:05:00Z"
        ),
        authored_by_id=author_service.actor_id,
        kind=ClaimKind.SAFETY,
        criticality=ClaimCriticality.HIGH,
        review_level=(
            ClaimReviewLevel.INDEPENDENT_HUMAN_REVIEW
        ),
        statement=(
            "The bounded runtime maintained the declared "
            "safety boundary during the evaluated test."
        ),
        scope={
            "environment": "isolated",
            "target": "tests/unit",
        },
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
        ),
        evidence_requirements=(
            requirement,
        ),
        limitations=(
            "The claim applies only to the evaluated test run.",
        ),
        prohibited_interpretations=(
            "Do not interpret this claim as certification.",
            "Do not interpret this claim as execution authority.",
        ),
        actor_registry=registry,
    )
    catalog = ClaimCatalog.create(
        key=catalog_key,
        created_at=UtcTimestamp.parse(
            "2026-07-16T05:06:00Z"
        ),
        producer_id=author_service.actor_id,
        actor_registry=registry,
        claims=(
            claim,
        ),
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        author_service=author_service,
        evaluator_system=evaluator_system,
        ledger_service=ledger_service,
        resolution_system=resolution_system,
        registry=registry,
        requirement=requirement,
        claim=claim,
        catalog=catalog,
        admitted_record_ids=(
            _identifier(
                "record",
                "runtime-measurement",
            ),
            _identifier(
                "record",
                "bounded-test-result",
            ),
        ),
        adverse_record_id=_identifier(
            "record",
            "failed-test-result",
        ),
        unresolved_record_id=_identifier(
            "record",
            "asserted-runtime-summary",
        ),
        excluded_record_id=_identifier(
            "record",
            "invalidated-test-result",
        ),
    )


def _evaluation(
    runtime: _Runtime,
    *,
    status: ClaimEvidenceEvaluationStatus,
    key: str,
    evaluated_at: str,
) -> ClaimEvidenceEvaluation:
    admitted_record_ids = runtime.admitted_record_ids
    adverse_record_ids: tuple[ScopedIdentifier, ...] = ()
    unresolved_record_ids: tuple[ScopedIdentifier, ...] = ()
    excluded_record_ids: tuple[ScopedIdentifier, ...] = ()
    reasons: tuple[
        ClaimRequirementEvaluationReason,
        ...,
    ]

    if status is (
        ClaimEvidenceEvaluationStatus
        .READY_FOR_HUMAN_ADJUDICATION
    ):
        outcome = ClaimRequirementEvaluationOutcome.SATISFIED
        reasons = (
            ClaimRequirementEvaluationReason
            .ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .INDEPENDENT_PRODUCERS_PRESENT,
            ClaimRequirementEvaluationReason
            .MINIMUM_RECORDS_MET,
            ClaimRequirementEvaluationReason
            .PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .SUBJECT_MATCH_CONFIRMED,
        )
    elif status is ClaimEvidenceEvaluationStatus.INCOMPLETE:
        outcome = ClaimRequirementEvaluationOutcome.UNSATISFIED
        admitted_record_ids = (
            runtime.admitted_record_ids[0],
        )
        reasons = (
            ClaimRequirementEvaluationReason
            .ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .INDEPENDENT_PRODUCERS_MISSING,
            ClaimRequirementEvaluationReason
            .MINIMUM_RECORDS_NOT_MET,
            ClaimRequirementEvaluationReason
            .PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .SUBJECT_MATCH_CONFIRMED,
        )
    elif status is (
        ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED
    ):
        outcome = (
            ClaimRequirementEvaluationOutcome
            .HUMAN_REVIEW_REQUIRED
        )
        admitted_record_ids = ()
        unresolved_record_ids = (
            runtime.unresolved_record_id,
        )
        reasons = (
            ClaimRequirementEvaluationReason
            .NO_ACCEPTABLE_EVIDENCE,
            ClaimRequirementEvaluationReason
            .MINIMUM_RECORDS_NOT_MET,
            ClaimRequirementEvaluationReason
            .PRIMARY_EVIDENCE_MISSING,
            ClaimRequirementEvaluationReason
            .UNRESOLVED_RELEVANT_EVIDENCE,
        )
    else:
        outcome = (
            ClaimRequirementEvaluationOutcome
            .FALSIFICATION_SIGNAL
        )
        admitted_record_ids = (
            *runtime.admitted_record_ids,
            runtime.adverse_record_id,
        )
        adverse_record_ids = (
            runtime.adverse_record_id,
        )
        excluded_record_ids = (
            runtime.excluded_record_id,
        )
        reasons = (
            ClaimRequirementEvaluationReason
            .ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .ADVERSE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .EXCLUDED_RELEVANT_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .INDEPENDENT_PRODUCERS_PRESENT,
            ClaimRequirementEvaluationReason
            .MINIMUM_RECORDS_MET,
            ClaimRequirementEvaluationReason
            .PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .SUBJECT_MATCH_CONFIRMED,
        )

    evaluated = UtcTimestamp.parse(
        evaluated_at
    )
    requirement_evaluation = ClaimRequirementEvaluation(
        evaluation_id=_identifier(
            "claim-requirement-evaluation",
            f"{key}-requirement",
        ),
        evaluated_at=evaluated,
        claim_id=runtime.claim.claim_id,
        requirement_id=runtime.requirement.requirement_id,
        outcome=outcome,
        reasons=reasons,
        admitted_record_ids=admitted_record_ids,
        adverse_record_ids=adverse_record_ids,
        unresolved_record_ids=unresolved_record_ids,
        excluded_record_ids=excluded_record_ids,
        claim_digest=runtime.claim.digest(),
        requirement_digest=runtime.requirement.digest(),
        resolution_snapshot_digest=_digest(
            "evidence-admission-resolution-snapshot",
            key,
        ),
        evidence_ledger_digest=_digest(
            "evidence-ledger",
            key,
        ),
    )

    return ClaimEvidenceEvaluation(
        evaluation_id=_identifier(
            "claim-evidence-evaluation",
            key,
        ),
        evaluated_at=evaluated,
        evaluated_by_id=runtime.evaluator_system.actor_id,
        evaluator_kind=runtime.evaluator_system.kind,
        evaluator_accountability_owner_id=(
            runtime.reviewer.actor_id
        ),
        claim_id=runtime.claim.claim_id,
        claim_catalog_id=runtime.catalog.catalog_id,
        resolution_snapshot_id=_identifier(
            "evidence-admission-resolution-snapshot",
            key,
        ),
        evidence_ledger_id=_identifier(
            "evidence-ledger",
            key,
        ),
        status=status,
        requirement_evaluations=(
            requirement_evaluation,
        ),
        claim_digest=runtime.claim.digest(),
        claim_catalog_digest=runtime.catalog.digest(),
        resolution_snapshot_digest=(
            requirement_evaluation
            .resolution_snapshot_digest
        ),
        evidence_ledger_digest=(
            requirement_evaluation.evidence_ledger_digest
        ),
        actor_registry_digest=runtime.registry.digest(),
    )


def _decision(
    runtime: _Runtime,
    evaluation: ClaimEvidenceEvaluation,
    *,
    status: ClaimAdjudicationDecisionStatus,
    key: str,
    decided_at: str,
) -> ClaimAdjudicationDecision:
    support: tuple[ScopedIdentifier, ...]

    if status is ClaimAdjudicationDecisionStatus.SUPPORTED:
        support = runtime.admitted_record_ids
    elif evaluation.status is (
        ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
    ):
        support = (
            runtime.adverse_record_id,
        )
    else:
        support = ()

    return ClaimAdjudicationDecision.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=runtime.reviewer.actor_id,
        status=status,
        rationale=f"Bounded human judgment: {status.value}.",
        supporting_record_ids=support,
        claim=runtime.claim,
        evaluation=evaluation,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
    )


def _ledger(
    runtime: _Runtime,
    *decisions: ClaimAdjudicationDecision,
    key: str = "claim-adjudication-ledger",
    created_at: str = "2026-07-16T05:10:00Z",
) -> ClaimAdjudicationDecisionLedger:
    return ClaimAdjudicationDecisionLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.ledger_service.actor_id,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
        decisions=decisions,
    )


def _resolution(
    runtime: _Runtime,
    evaluation: ClaimEvidenceEvaluation,
    ledger: ClaimAdjudicationDecisionLedger,
    *,
    key: str = "claim-resolution",
    resolved_at: str = "2026-07-16T05:11:00Z",
) -> ClaimResolution:
    return ClaimResolution.create(
        key=key,
        resolved_at=UtcTimestamp.parse(
            resolved_at
        ),
        produced_by_id=runtime.resolution_system.actor_id,
        claim=runtime.claim,
        evaluation=evaluation,
        decision_ledger=ledger,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
    )


def test_ledger_preserves_deferral_then_terminal_adjudication() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="ready-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    deferred = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.DEFERRED,
        key="defer-ready-claim",
        decided_at="2026-07-16T05:08:00Z",
    )
    supported = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="support-ready-claim",
        decided_at="2026-07-16T05:09:00Z",
    )
    ledger = _ledger(
        runtime,
        supported,
        deferred,
    )

    assert ledger.decisions_for_evaluation(
        evaluation.evaluation_id
    ) == (
        deferred,
        supported,
    )
    assert ledger.latest_for_evaluation(
        evaluation.evaluation_id
    ) == supported
    assert ledger.require_terminal_decision(
        evaluation.evaluation_id
    ) == supported
    assert ledger.digest().verifies(
        ledger.canonical_payload()
    ) is True


def test_terminal_adjudication_cannot_be_replaced() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="terminal-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    supported = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="terminal-support",
        decided_at="2026-07-16T05:08:00Z",
    )
    rejected = _decision(
        runtime,
        evaluation,
        status=(
            ClaimAdjudicationDecisionStatus.NOT_SUPPORTED
        ),
        key="replacement-rejection",
        decided_at="2026-07-16T05:09:00Z",
    )

    with pytest.raises(
        FoundationError,
        match=(
            "terminal claim adjudications "
            "must not be replaced"
        ),
    ):
        _ledger(
            runtime,
            supported,
            rejected,
        )


def test_distinct_evaluations_keep_distinct_terminal_history() -> None:
    runtime = _runtime()
    ready = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="original-ready",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    falsifying = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
        ),
        key="later-falsification",
        evaluated_at="2026-07-16T05:09:00Z",
    )
    supported = _decision(
        runtime,
        ready,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="support-original-evaluation",
        decided_at="2026-07-16T05:08:00Z",
    )
    not_supported = _decision(
        runtime,
        falsifying,
        status=(
            ClaimAdjudicationDecisionStatus.NOT_SUPPORTED
        ),
        key="reject-later-evaluation",
        decided_at="2026-07-16T05:10:00Z",
    )
    ledger = _ledger(
        runtime,
        supported,
        not_supported,
        created_at="2026-07-16T05:10:00Z",
    )

    assert ledger.require_terminal_decision(
        ready.evaluation_id
    ) == supported
    assert ledger.require_terminal_decision(
        falsifying.evaluation_id
    ) == not_supported


def test_ledger_append_preserves_identity_and_rejects_replacement() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="append-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    deferred = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.DEFERRED,
        key="append-deferral",
        decided_at="2026-07-16T05:08:00Z",
    )
    supported = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="append-support",
        decided_at="2026-07-16T05:09:00Z",
    )
    ledger = _ledger(
        runtime,
        deferred,
        created_at="2026-07-16T05:08:00Z",
    )
    next_ledger = ledger.append(
        supported,
        created_at=UtcTimestamp.parse(
            "2026-07-16T05:09:00Z"
        ),
    )

    assert next_ledger.ledger_id == ledger.ledger_id
    assert next_ledger.producer_id == ledger.producer_id
    assert next_ledger.require_terminal_decision(
        evaluation.evaluation_id
    ) == supported


def test_ready_evaluation_without_decision_awaits_adjudication() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="awaiting-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    resolution = _resolution(
        runtime,
        evaluation,
        _ledger(runtime),
    )

    assert resolution.status is (
        ClaimResolutionStatus.AWAITING_ADJUDICATION
    )
    assert resolution.source is (
        ClaimResolutionSource.EVIDENCE_EVALUATION
    )
    assert resolution.decision_id is None
    assert resolution.supports_claim is False
    assert resolution.is_terminal_for_evaluation is False
    assert resolution.requires_human_attention is True


def test_supported_resolution_remains_bounded_and_non_authorizing() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="supported-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    decision = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="supported-decision",
        decided_at="2026-07-16T05:08:00Z",
    )
    resolution = _resolution(
        runtime,
        evaluation,
        _ledger(
            runtime,
            decision,
        ),
    )

    assert resolution.status is ClaimResolutionStatus.SUPPORTED
    assert resolution.source is (
        ClaimResolutionSource.HUMAN_ADJUDICATION
    )
    assert resolution.decision_id == decision.decision_id
    assert resolution.decision_digest == decision.digest()
    assert resolution.supports_claim is True
    assert resolution.is_terminal_for_evaluation is True
    assert resolution.requires_human_attention is False
    assert resolution.establishes_absolute_truth is False
    assert resolution.grants_authority is False
    assert resolution.claims_certification is False
    assert resolution.digest().verifies(
        resolution.to_payload()
    ) is True


def test_machine_evaluation_states_remain_nonterminal() -> None:
    cases = (
        (
            ClaimEvidenceEvaluationStatus.INCOMPLETE,
            ClaimResolutionStatus.INCOMPLETE_EVIDENCE,
        ),
        (
            ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED,
            ClaimResolutionStatus.EVIDENCE_REVIEW_OPEN,
        ),
        (
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL,
            ClaimResolutionStatus.FALSIFICATION_SIGNAL,
        ),
    )

    for evaluation_status, resolution_status in cases:
        runtime = _runtime()
        evaluation = _evaluation(
            runtime,
            status=evaluation_status,
            key=f"{evaluation_status.value}-evaluation",
            evaluated_at="2026-07-16T05:07:00Z",
        )
        resolution = _resolution(
            runtime,
            evaluation,
            _ledger(runtime),
        )

        assert resolution.status is resolution_status
        assert resolution.source is (
            ClaimResolutionSource.EVIDENCE_EVALUATION
        )
        assert resolution.supports_claim is False
        assert resolution.requires_human_attention is True


def test_human_not_supported_decision_closes_falsifying_evaluation() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
        ),
        key="falsifying-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    decision = _decision(
        runtime,
        evaluation,
        status=(
            ClaimAdjudicationDecisionStatus.NOT_SUPPORTED
        ),
        key="not-supported-decision",
        decided_at="2026-07-16T05:08:00Z",
    )
    resolution = _resolution(
        runtime,
        evaluation,
        _ledger(
            runtime,
            decision,
        ),
    )

    assert resolution.status is (
        ClaimResolutionStatus.NOT_SUPPORTED
    )
    assert resolution.source is (
        ClaimResolutionSource.HUMAN_ADJUDICATION
    )
    assert resolution.is_terminal_for_evaluation is True
    assert resolution.supports_claim is False


def test_deferred_adjudication_remains_open() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
        key="deferred-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    decision = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.DEFERRED,
        key="deferred-decision",
        decided_at="2026-07-16T05:08:00Z",
    )
    resolution = _resolution(
        runtime,
        evaluation,
        _ledger(
            runtime,
            decision,
        ),
    )

    assert resolution.status is ClaimResolutionStatus.DEFERRED
    assert resolution.source is (
        ClaimResolutionSource.HUMAN_ADJUDICATION
    )
    assert resolution.requires_human_attention is True
    assert resolution.is_terminal_for_evaluation is False


def test_old_supported_decision_does_not_apply_to_new_falsifying_evaluation() -> None:
    runtime = _runtime()
    old_evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="old-ready-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    new_evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
        ),
        key="new-falsifying-evaluation",
        evaluated_at="2026-07-16T05:09:00Z",
    )
    old_decision = _decision(
        runtime,
        old_evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="old-supported-decision",
        decided_at="2026-07-16T05:08:00Z",
    )
    ledger = _ledger(
        runtime,
        old_decision,
        created_at="2026-07-16T05:10:00Z",
    )
    resolution = _resolution(
        runtime,
        new_evaluation,
        ledger,
        resolved_at="2026-07-16T05:11:00Z",
    )

    assert resolution.status is (
        ClaimResolutionStatus.FALSIFICATION_SIGNAL
    )
    assert resolution.source is (
        ClaimResolutionSource.EVIDENCE_EVALUATION
    )
    assert resolution.decision_id is None
    assert resolution.supports_claim is False


def test_resolution_rejects_different_claim_catalog_binding() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="catalog-binding-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    ledger = _ledger(runtime)
    different_catalog = ClaimCatalog.create(
        key="different-claim-resolution-catalog",
        created_at=runtime.catalog.created_at,
        producer_id=runtime.author_service.actor_id,
        actor_registry=runtime.registry,
        claims=(
            runtime.claim,
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "evaluation references a different claim catalog"
        ),
    ):
        ClaimResolution.create(
            key="mismatched-catalog-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T05:11:00Z"
            ),
            produced_by_id=runtime.resolution_system.actor_id,
            claim=runtime.claim,
            evaluation=evaluation,
            decision_ledger=ledger,
            claim_catalog=different_catalog,
            actor_registry=runtime.registry,
        )


def test_resolution_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
        key="producer-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    ledger = _ledger(runtime)

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimResolution.create(
            key="human-produced-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T05:11:00Z"
            ),
            produced_by_id=runtime.reviewer.actor_id,
            claim=runtime.claim,
            evaluation=evaluation,
            decision_ledger=ledger,
            claim_catalog=runtime.catalog,
            actor_registry=runtime.registry,
        )

    unowned_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="unowned-resolution-system",
        display_name="Unowned Resolution System",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-claim-resolution-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.reviewer.actor_id,
        actors=(
            *runtime.registry.actors,
            unowned_system,
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "must identify an accountable human owner"
        ),
    ):
        ClaimResolution.create(
            key="unowned-produced-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T05:11:00Z"
            ),
            produced_by_id=unowned_system.actor_id,
            claim=runtime.claim,
            evaluation=evaluation,
            decision_ledger=ledger,
            claim_catalog=runtime.catalog,
            actor_registry=expanded_registry,
        )


def test_ledger_and_resolution_are_deterministic() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="stable-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    deferred = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.DEFERRED,
        key="stable-deferral",
        decided_at="2026-07-16T05:08:00Z",
    )
    supported = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="stable-support",
        decided_at="2026-07-16T05:09:00Z",
    )
    first_ledger = _ledger(
        runtime,
        deferred,
        supported,
    )
    second_ledger = _ledger(
        runtime,
        supported,
        deferred,
    )

    first = _resolution(
        runtime,
        evaluation,
        first_ledger,
    )
    second = _resolution(
        runtime,
        evaluation,
        second_ledger,
    )

    assert (
        first_ledger.canonical_payload()
        == second_ledger.canonical_payload()
    )
    assert first_ledger.digest() == second_ledger.digest()
    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()


def test_resolution_rejects_tampered_latest_decision_binding() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
        key="tampered-evaluation",
        evaluated_at="2026-07-16T05:07:00Z",
    )
    decision = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="tampered-decision",
        decided_at="2026-07-16T05:08:00Z",
    )
    tampered = replace(
        decision,
        evaluation_digest=_digest(
            "claim-evidence-evaluation",
            "different-evaluation",
        ),
    )
    ledger = _ledger(
        runtime,
        tampered,
    )

    with pytest.raises(
        FoundationError,
        match="evaluation digest does not match",
    ):
        _resolution(
            runtime,
            evaluation,
            ledger,
        )
