"""Tests for temporal claim-resolution history and current posture."""

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
    ClaimResolutionHistory,
    ClaimResolutionHistoryEntry,
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
    history_service: ActorIdentity
    registry: ActorRegistry
    requirement: ClaimEvidenceRequirement
    claim: ClaimSpecification
    catalog: ClaimCatalog
    admitted_record_ids: tuple[ScopedIdentifier, ...]
    adverse_record_id: ScopedIdentifier


def _runtime() -> _Runtime:
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
    history_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-history-service",
        display_name="Claim History Service",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-history-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T06:00:00Z"
        ),
        producer_id=reviewer.actor_id,
        actors=(
            owner,
            reviewer,
            author_service,
            evaluator_system,
            ledger_service,
            resolution_system,
            history_service,
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
            "2026-07-16T06:05:00Z"
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
        key="claim-history-catalog",
        created_at=UtcTimestamp.parse(
            "2026-07-16T06:06:00Z"
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
        history_service=history_service,
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
    )


def _evaluation(
    runtime: _Runtime,
    *,
    key: str,
    evaluated_at: str,
    status: ClaimEvidenceEvaluationStatus,
) -> ClaimEvidenceEvaluation:
    evaluated = UtcTimestamp.parse(
        evaluated_at
    )
    admitted_record_ids = runtime.admitted_record_ids
    adverse_record_ids: tuple[ScopedIdentifier, ...] = ()

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
        reasons = (
            ClaimRequirementEvaluationReason
            .ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .ADVERSE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .INDEPENDENT_PRODUCERS_PRESENT,
            ClaimRequirementEvaluationReason
            .MINIMUM_RECORDS_MET,
            ClaimRequirementEvaluationReason
            .PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .SUBJECT_MATCH_CONFIRMED,
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
        unresolved_record_ids=(),
        excluded_record_ids=(),
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
            requirement_evaluation.resolution_snapshot_digest
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
    key: str,
    decided_at: str,
    status: ClaimAdjudicationDecisionStatus,
) -> ClaimAdjudicationDecision:
    supporting_record_ids = (
        runtime.admitted_record_ids
        if status is ClaimAdjudicationDecisionStatus.SUPPORTED
        else ()
    )

    return ClaimAdjudicationDecision.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=runtime.reviewer.actor_id,
        status=status,
        rationale=f"Bounded human judgment: {status.value}.",
        supporting_record_ids=supporting_record_ids,
        claim=runtime.claim,
        evaluation=evaluation,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
    )


def _decision_ledger(
    runtime: _Runtime,
    *decisions: ClaimAdjudicationDecision,
    key: str,
    created_at: str,
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
    key: str,
    resolved_at: str,
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


def _entry(
    runtime: _Runtime,
    evaluation: ClaimEvidenceEvaluation,
    resolution: ClaimResolution,
    *,
    key: str,
    recorded_at: str,
) -> ClaimResolutionHistoryEntry:
    return ClaimResolutionHistoryEntry.capture(
        key=key,
        recorded_at=UtcTimestamp.parse(
            recorded_at
        ),
        claim=runtime.claim,
        evaluation=evaluation,
        resolution=resolution,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
    )


def _history(
    runtime: _Runtime,
    *entries: ClaimResolutionHistoryEntry,
    key: str = "claim-resolution-history",
    created_at: str = "2026-07-16T06:20:00Z",
) -> ClaimResolutionHistory:
    return ClaimResolutionHistory.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.history_service.actor_id,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
        entries=entries,
    )


def test_history_entry_binds_exact_claim_evaluation_and_resolution() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        key="ready-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
    )
    decision = _decision(
        runtime,
        evaluation,
        key="support-ready-evaluation",
        decided_at="2026-07-16T06:08:00Z",
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
    )
    ledger = _decision_ledger(
        runtime,
        decision,
        key="ready-decision-ledger",
        created_at="2026-07-16T06:09:00Z",
    )
    resolution = _resolution(
        runtime,
        evaluation,
        ledger,
        key="ready-resolution",
        resolved_at="2026-07-16T06:10:00Z",
    )
    entry = _entry(
        runtime,
        evaluation,
        resolution,
        key="ready-history-entry",
        recorded_at="2026-07-16T06:11:00Z",
    )

    assert entry.status is ClaimResolutionStatus.SUPPORTED
    assert entry.supports_claim is True
    assert entry.is_terminal_for_evaluation is True
    assert entry.requires_human_attention is False
    assert entry.claim_digest == runtime.claim.digest()
    assert entry.evaluation_digest == evaluation.digest()
    assert entry.resolution_digest == resolution.digest()
    assert entry.establishes_absolute_truth is False
    assert entry.grants_authority is False
    assert entry.digest().verifies(
        entry.to_payload()
    ) is True


def test_current_posture_uses_newest_evaluation_not_latest_recording() -> None:
    runtime = _runtime()
    older_evaluation = _evaluation(
        runtime,
        key="older-ready-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
    )
    older_decision = _decision(
        runtime,
        older_evaluation,
        key="older-support",
        decided_at="2026-07-16T06:08:00Z",
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
    )
    older_resolution = _resolution(
        runtime,
        older_evaluation,
        _decision_ledger(
            runtime,
            older_decision,
            key="older-decision-ledger",
            created_at="2026-07-16T06:11:00Z",
        ),
        key="older-supported-resolution",
        resolved_at="2026-07-16T06:12:00Z",
    )
    older_entry = _entry(
        runtime,
        older_evaluation,
        older_resolution,
        key="older-supported-entry",
        recorded_at="2026-07-16T06:14:00Z",
    )

    newer_evaluation = _evaluation(
        runtime,
        key="newer-falsifying-evaluation",
        evaluated_at="2026-07-16T06:09:00Z",
        status=(
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
        ),
    )
    newer_resolution = _resolution(
        runtime,
        newer_evaluation,
        _decision_ledger(
            runtime,
            key="newer-empty-ledger",
            created_at="2026-07-16T06:09:30Z",
        ),
        key="newer-falsifying-resolution",
        resolved_at="2026-07-16T06:10:00Z",
    )
    newer_entry = _entry(
        runtime,
        newer_evaluation,
        newer_resolution,
        key="newer-falsifying-entry",
        recorded_at="2026-07-16T06:11:00Z",
    )
    history = _history(
        runtime,
        older_entry,
        newer_entry,
    )

    current = history.require_current_for_claim(
        runtime.claim.claim_id
    )

    assert current == newer_entry
    assert current.status is (
        ClaimResolutionStatus.FALSIFICATION_SIGNAL
    )
    assert history.is_currently_supported(
        runtime.claim.claim_id
    ) is False
    assert history.superseded_supported_entries(
        runtime.claim.claim_id
    ) == (
        older_entry,
    )
    assert history.claims_requiring_attention() == (
        runtime.claim.claim_id,
    )


def test_deferral_then_terminal_resolution_for_same_evaluation_is_allowed() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        key="deferred-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
    )
    deferred = _decision(
        runtime,
        evaluation,
        key="defer-evaluation",
        decided_at="2026-07-16T06:08:00Z",
        status=ClaimAdjudicationDecisionStatus.DEFERRED,
    )
    first_resolution = _resolution(
        runtime,
        evaluation,
        _decision_ledger(
            runtime,
            deferred,
            key="deferred-ledger",
            created_at="2026-07-16T06:09:00Z",
        ),
        key="deferred-resolution",
        resolved_at="2026-07-16T06:10:00Z",
    )
    first_entry = _entry(
        runtime,
        evaluation,
        first_resolution,
        key="deferred-entry",
        recorded_at="2026-07-16T06:10:30Z",
    )

    supported = _decision(
        runtime,
        evaluation,
        key="support-after-deferral",
        decided_at="2026-07-16T06:11:00Z",
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
    )
    second_resolution = _resolution(
        runtime,
        evaluation,
        _decision_ledger(
            runtime,
            deferred,
            supported,
            key="terminal-ledger",
            created_at="2026-07-16T06:12:00Z",
        ),
        key="supported-resolution",
        resolved_at="2026-07-16T06:13:00Z",
    )
    second_entry = _entry(
        runtime,
        evaluation,
        second_resolution,
        key="supported-entry",
        recorded_at="2026-07-16T06:14:00Z",
    )
    history = _history(
        runtime,
        second_entry,
        first_entry,
    )

    assert history.entries_for_evaluation(
        evaluation.evaluation_id
    ) == (
        first_entry,
        second_entry,
    )
    assert history.latest_for_evaluation(
        evaluation.evaluation_id
    ) == second_entry
    assert history.is_currently_supported(
        runtime.claim.claim_id
    ) is True
    assert history.claims_requiring_attention() == ()


def test_terminal_resolution_cannot_be_replaced_for_same_evaluation() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        key="terminal-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=(
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        ),
    )
    supported = _decision(
        runtime,
        evaluation,
        key="terminal-support",
        decided_at="2026-07-16T06:08:00Z",
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
    )
    supported_resolution = _resolution(
        runtime,
        evaluation,
        _decision_ledger(
            runtime,
            supported,
            key="supported-only-ledger",
            created_at="2026-07-16T06:09:00Z",
        ),
        key="terminal-supported-resolution",
        resolved_at="2026-07-16T06:10:00Z",
    )
    supported_entry = _entry(
        runtime,
        evaluation,
        supported_resolution,
        key="terminal-supported-entry",
        recorded_at="2026-07-16T06:10:30Z",
    )

    not_supported = _decision(
        runtime,
        evaluation,
        key="replacement-not-supported",
        decided_at="2026-07-16T06:11:00Z",
        status=(
            ClaimAdjudicationDecisionStatus.NOT_SUPPORTED
        ),
    )
    replacement_resolution = _resolution(
        runtime,
        evaluation,
        _decision_ledger(
            runtime,
            not_supported,
            key="not-supported-only-ledger",
            created_at="2026-07-16T06:12:00Z",
        ),
        key="replacement-resolution",
        resolved_at="2026-07-16T06:13:00Z",
    )
    replacement_entry = _entry(
        runtime,
        evaluation,
        replacement_resolution,
        key="replacement-entry",
        recorded_at="2026-07-16T06:14:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="terminal claim resolutions must not be replaced",
    ):
        _history(
            runtime,
            supported_entry,
            replacement_entry,
        )


def test_distinct_evaluations_cannot_share_one_claim_evaluation_time() -> None:
    runtime = _runtime()
    first_evaluation = _evaluation(
        runtime,
        key="same-time-first",
        evaluated_at="2026-07-16T06:07:00Z",
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
    )
    second_evaluation = _evaluation(
        runtime,
        key="same-time-second",
        evaluated_at="2026-07-16T06:07:00Z",
        status=(
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
        ),
    )
    first_resolution = _resolution(
        runtime,
        first_evaluation,
        _decision_ledger(
            runtime,
            key="same-time-first-ledger",
            created_at="2026-07-16T06:08:00Z",
        ),
        key="same-time-first-resolution",
        resolved_at="2026-07-16T06:09:00Z",
    )
    second_resolution = _resolution(
        runtime,
        second_evaluation,
        _decision_ledger(
            runtime,
            key="same-time-second-ledger",
            created_at="2026-07-16T06:08:30Z",
        ),
        key="same-time-second-resolution",
        resolved_at="2026-07-16T06:09:30Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not share the same evaluation time",
    ):
        _history(
            runtime,
            _entry(
                runtime,
                first_evaluation,
                first_resolution,
                key="same-time-first-entry",
                recorded_at="2026-07-16T06:10:00Z",
            ),
            _entry(
                runtime,
                second_evaluation,
                second_resolution,
                key="same-time-second-entry",
                recorded_at="2026-07-16T06:10:30Z",
            ),
        )


def test_capture_rejects_different_claim_catalog() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        key="catalog-bound-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
    )
    resolution = _resolution(
        runtime,
        evaluation,
        _decision_ledger(
            runtime,
            key="catalog-bound-ledger",
            created_at="2026-07-16T06:08:00Z",
        ),
        key="catalog-bound-resolution",
        resolved_at="2026-07-16T06:09:00Z",
    )
    different_catalog = ClaimCatalog.create(
        key="different-claim-history-catalog",
        created_at=runtime.catalog.created_at,
        producer_id=runtime.author_service.actor_id,
        actor_registry=runtime.registry,
        claims=(
            runtime.claim,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="evaluation references a different claim catalog",
    ):
        ClaimResolutionHistoryEntry.capture(
            key="mismatched-catalog-entry",
            recorded_at=UtcTimestamp.parse(
                "2026-07-16T06:10:00Z"
            ),
            claim=runtime.claim,
            evaluation=evaluation,
            resolution=resolution,
            claim_catalog=different_catalog,
            actor_registry=runtime.registry,
        )


def test_history_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimResolutionHistory.create(
            key="human-produced-history",
            created_at=UtcTimestamp.parse(
                "2026-07-16T06:20:00Z"
            ),
            producer_id=runtime.reviewer.actor_id,
            claim_catalog=runtime.catalog,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-history-service",
        display_name="Unowned History Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-claim-history-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.reviewer.actor_id,
        actors=(
            *runtime.registry.actors,
            unowned_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="must identify an accountable human owner",
    ):
        ClaimResolutionHistory.create(
            key="unowned-produced-history",
            created_at=UtcTimestamp.parse(
                "2026-07-16T06:20:00Z"
            ),
            producer_id=unowned_service.actor_id,
            claim_catalog=runtime.catalog,
            actor_registry=expanded_registry,
        )


def test_history_is_deterministic_across_input_order() -> None:
    runtime = _runtime()
    first_evaluation = _evaluation(
        runtime,
        key="stable-first-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
    )
    second_evaluation = _evaluation(
        runtime,
        key="stable-second-evaluation",
        evaluated_at="2026-07-16T06:09:00Z",
        status=(
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
        ),
    )
    first_entry = _entry(
        runtime,
        first_evaluation,
        _resolution(
            runtime,
            first_evaluation,
            _decision_ledger(
                runtime,
                key="stable-first-ledger",
                created_at="2026-07-16T06:08:00Z",
            ),
            key="stable-first-resolution",
            resolved_at="2026-07-16T06:08:30Z",
        ),
        key="stable-first-entry",
        recorded_at="2026-07-16T06:09:00Z",
    )
    second_entry = _entry(
        runtime,
        second_evaluation,
        _resolution(
            runtime,
            second_evaluation,
            _decision_ledger(
                runtime,
                key="stable-second-ledger",
                created_at="2026-07-16T06:10:00Z",
            ),
            key="stable-second-resolution",
            resolved_at="2026-07-16T06:10:30Z",
        ),
        key="stable-second-entry",
        recorded_at="2026-07-16T06:11:00Z",
    )

    first = _history(
        runtime,
        first_entry,
        second_entry,
        key="stable-history",
    )
    second = _history(
        runtime,
        second_entry,
        first_entry,
        key="stable-history",
    )

    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()
    assert first.establishes_absolute_truth is False
    assert first.grants_authority is False


def test_history_rejects_duplicate_resolution_identity() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        key="duplicate-resolution-evaluation",
        evaluated_at="2026-07-16T06:07:00Z",
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
    )
    resolution = _resolution(
        runtime,
        evaluation,
        _decision_ledger(
            runtime,
            key="duplicate-resolution-ledger",
            created_at="2026-07-16T06:08:00Z",
        ),
        key="duplicate-resolution",
        resolved_at="2026-07-16T06:09:00Z",
    )
    first = _entry(
        runtime,
        evaluation,
        resolution,
        key="duplicate-resolution-first",
        recorded_at="2026-07-16T06:10:00Z",
    )
    second = replace(
        first,
        entry_id=_identifier(
            "claim-resolution-history-entry",
            "duplicate-resolution-second",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="unique resolution IDs",
    ):
        _history(
            runtime,
            first,
            second,
        )
