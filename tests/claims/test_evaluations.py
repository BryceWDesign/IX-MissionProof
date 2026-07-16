"""Tests for deterministic claim-evidence evaluations."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ix_missionproof.claims import (
    ClaimCatalog,
    ClaimCriticality,
    ClaimEvidenceEvaluation,
    ClaimEvidenceEvaluationStatus,
    ClaimEvidenceEvaluator,
    ClaimEvidenceRequirement,
    ClaimKind,
    ClaimRequirementEvaluationOutcome,
    ClaimRequirementEvaluationReason,
    ClaimReviewLevel,
    ClaimSpecification,
)
from ix_missionproof.evidence import (
    EvidenceAdmissionDecisionLedger,
    EvidenceAdmissionEvaluator,
    EvidenceAdmissionPolicy,
    EvidenceAdmissionResolutionSnapshot,
    EvidenceKind,
    EvidenceLedger,
    EvidenceOrigin,
    EvidenceRecord,
    EvidenceStatus,
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
class _EvaluationRuntime:
    owner: ActorIdentity
    reviewer: ActorIdentity
    sensor: ActorIdentity
    evidence_service: ActorIdentity
    admission_service: ActorIdentity
    resolution_system: ActorIdentity
    claim_service: ActorIdentity
    evaluation_system: ActorIdentity
    registry: ActorRegistry
    claim: ClaimSpecification
    claim_catalog: ClaimCatalog
    evidence_ledger: EvidenceLedger
    resolution_snapshot: EvidenceAdmissionResolutionSnapshot


def _requirement(
    *,
    key: str = "runtime-proof",
    acceptable_kinds: tuple[EvidenceKind, ...] = (
        EvidenceKind.MEASUREMENT,
        EvidenceKind.TEST_RESULT,
    ),
    minimum_records: int = 2,
    require_primary_evidence: bool = True,
    require_subject_match: bool = True,
    require_independent_producers: bool = True,
) -> ClaimEvidenceRequirement:
    return ClaimEvidenceRequirement.create(
        key=key,
        summary=(
            "Provide admitted evidence for the bounded runtime claim."
        ),
        acceptable_kinds=acceptable_kinds,
        minimum_records=minimum_records,
        require_primary_evidence=require_primary_evidence,
        require_subject_match=require_subject_match,
        require_independent_producers=require_independent_producers,
        falsification_conditions=(
            "Any admitted relevant evidence reports failure or blocking.",
            "The required admitted evidence count is not met.",
        ),
    )


def _runtime(
    *,
    include_passing_test: bool = True,
    include_failed_test: bool = False,
    include_asserted_record: bool = False,
    include_invalidated_test: bool = False,
    claim_subject_key: str = "agent-alpha",
    requirement: ClaimEvidenceRequirement | None = None,
) -> _EvaluationRuntime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="evidence-owner",
        display_name="Evidence Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-reviewer",
        display_name="Independent Reviewer",
    )
    sensor = ActorIdentity.create(
        kind=ActorKind.SENSOR,
        key="runtime-sensor",
        display_name="Runtime Sensor",
        accountability_owner_id=owner.actor_id,
    )
    evidence_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="evidence-service",
        display_name="Evidence Service",
        accountability_owner_id=owner.actor_id,
    )
    admission_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="admission-service",
        display_name="Admission Service",
        accountability_owner_id=reviewer.actor_id,
    )
    resolution_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="resolution-system",
        display_name="Resolution System",
        accountability_owner_id=reviewer.actor_id,
    )
    claim_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-service",
        display_name="Claim Service",
        accountability_owner_id=owner.actor_id,
    )
    evaluation_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-evaluation-system",
        display_name="Claim Evaluation System",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-evaluation-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T03:00:00Z"
        ),
        producer_id=reviewer.actor_id,
        actors=(
            owner,
            reviewer,
            sensor,
            evidence_service,
            admission_service,
            resolution_system,
            claim_service,
            evaluation_system,
        ),
    )

    evidence_subject = _identifier(
        "system",
        "agent-alpha",
    )

    records: list[EvidenceRecord] = [
        EvidenceRecord.create(
            key="runtime-measurement",
            created_at=UtcTimestamp.parse(
                "2026-07-16T03:02:00Z"
            ),
            produced_by_id=sensor.actor_id,
            kind=EvidenceKind.MEASUREMENT,
            origin=EvidenceOrigin.MEASURED,
            status=EvidenceStatus.RECORDED,
            subject_ids=(
                evidence_subject,
            ),
            summary="The bounded runtime state was measured.",
            payload={
                "network_enabled": False,
                "sandboxed": True,
            },
            actor_registry=registry,
        )
    ]

    if include_passing_test:
        records.append(
            EvidenceRecord.create(
                key="passing-test-result",
                created_at=UtcTimestamp.parse(
                    "2026-07-16T03:03:00Z"
                ),
                produced_by_id=evidence_service.actor_id,
                kind=EvidenceKind.TEST_RESULT,
                origin=EvidenceOrigin.EXECUTED,
                status=EvidenceStatus.PASSED,
                subject_ids=(
                    evidence_subject,
                ),
                summary="The bounded test target passed.",
                payload={
                    "failed": 0,
                    "passed": 42,
                },
                actor_registry=registry,
            )
        )

    if include_failed_test:
        records.append(
            EvidenceRecord.create(
                key="failed-test-result",
                created_at=UtcTimestamp.parse(
                    "2026-07-16T03:04:00Z"
                ),
                produced_by_id=evidence_service.actor_id,
                kind=EvidenceKind.TEST_RESULT,
                origin=EvidenceOrigin.EXECUTED,
                status=EvidenceStatus.FAILED,
                subject_ids=(
                    evidence_subject,
                ),
                summary="A bounded required test failed.",
                payload={
                    "failed": 1,
                    "passed": 41,
                },
                actor_registry=registry,
            )
        )

    if include_asserted_record:
        records.append(
            EvidenceRecord.create(
                key="asserted-runtime-summary",
                created_at=UtcTimestamp.parse(
                    "2026-07-16T03:05:00Z"
                ),
                produced_by_id=evidence_service.actor_id,
                kind=EvidenceKind.SOURCE_RECORD,
                origin=EvidenceOrigin.ASSERTED,
                status=EvidenceStatus.RECORDED,
                subject_ids=(
                    evidence_subject,
                ),
                summary="An asserted summary of the runtime.",
                payload={
                    "summary": "The runtime remained bounded.",
                },
                actor_registry=registry,
                source_record_ids=(
                    records[0].record_id,
                ),
            )
        )

    if include_invalidated_test:
        records.append(
            EvidenceRecord.create(
                key="invalidated-test-result",
                created_at=UtcTimestamp.parse(
                    "2026-07-16T03:06:00Z"
                ),
                produced_by_id=evidence_service.actor_id,
                kind=EvidenceKind.TEST_RESULT,
                origin=EvidenceOrigin.EXECUTED,
                status=EvidenceStatus.INVALIDATED,
                subject_ids=(
                    evidence_subject,
                ),
                summary="An invalidated test result.",
                payload={
                    "failed": 0,
                    "passed": 42,
                },
                actor_registry=registry,
            )
        )

    evidence_ledger = EvidenceLedger.create(
        key="claim-evaluation-evidence",
        created_at=UtcTimestamp.parse(
            "2026-07-16T03:10:00Z"
        ),
        producer_id=evidence_service.actor_id,
        actor_registry=registry,
        records=tuple(records),
    )
    policy = EvidenceAdmissionPolicy.create(
        key="claim-evaluation-admission-policy",
        created_at=UtcTimestamp.parse(
            "2026-07-16T03:01:00Z"
        ),
        authored_by_id=reviewer.actor_id,
        summary=(
            "Admit intact primary evidence and require review "
            "for asserted evidence."
        ),
        actor_registry=registry,
        allowed_kinds=tuple(EvidenceKind),
        allowed_origins=tuple(EvidenceOrigin),
        allowed_statuses=(
            EvidenceStatus.RECORDED,
            EvidenceStatus.PASSED,
            EvidenceStatus.FAILED,
            EvidenceStatus.BLOCKED,
            EvidenceStatus.INCONCLUSIVE,
        ),
        human_review_origins=(
            EvidenceOrigin.ASSERTED,
        ),
    )
    admission_review = EvidenceAdmissionEvaluator(
        actor_registry=registry,
        evidence_ledger=evidence_ledger,
        policy=policy,
    ).review(
        key="claim-evaluation-admission-review",
        reviewed_at=UtcTimestamp.parse(
            "2026-07-16T03:11:00Z"
        ),
        reviewed_by_id=admission_service.actor_id,
    )
    decision_ledger = EvidenceAdmissionDecisionLedger.create(
        key="claim-evaluation-decisions",
        created_at=UtcTimestamp.parse(
            "2026-07-16T03:12:00Z"
        ),
        producer_id=admission_service.actor_id,
        admission_review=admission_review,
        actor_registry=registry,
        decisions=(),
    )
    resolution_snapshot = EvidenceAdmissionResolutionSnapshot.create(
        key="claim-evaluation-resolution",
        resolved_at=UtcTimestamp.parse(
            "2026-07-16T03:13:00Z"
        ),
        produced_by_id=resolution_system.actor_id,
        admission_review=admission_review,
        decision_ledger=decision_ledger,
        evidence_ledger=evidence_ledger,
        actor_registry=registry,
    )

    selected_requirement = requirement or _requirement()
    claim = ClaimSpecification.create(
        key="bounded-runtime-claim",
        created_at=UtcTimestamp.parse(
            "2026-07-16T03:14:00Z"
        ),
        authored_by_id=claim_service.actor_id,
        kind=ClaimKind.CAPABILITY,
        criticality=ClaimCriticality.MODERATE,
        review_level=ClaimReviewLevel.HUMAN_REVIEW,
        statement=(
            "The bounded runtime can execute the declared "
            "unit-test target."
        ),
        scope={
            "environment": "isolated",
            "target": "tests/unit",
        },
        subject_ids=(
            _identifier(
                "system",
                claim_subject_key,
            ),
        ),
        evidence_requirements=(
            selected_requirement,
        ),
        assumptions=(
            "The evaluated runtime configuration remains unchanged.",
        ),
        limitations=(
            "The claim applies only to the declared test target.",
        ),
        prohibited_interpretations=(
            "Do not interpret this claim as certification.",
            "Do not interpret this claim as execution authority.",
        ),
        actor_registry=registry,
    )
    claim_catalog = ClaimCatalog.create(
        key="claim-evaluation-catalog",
        created_at=UtcTimestamp.parse(
            "2026-07-16T03:15:00Z"
        ),
        producer_id=claim_service.actor_id,
        actor_registry=registry,
        claims=(
            claim,
        ),
    )

    return _EvaluationRuntime(
        owner=owner,
        reviewer=reviewer,
        sensor=sensor,
        evidence_service=evidence_service,
        admission_service=admission_service,
        resolution_system=resolution_system,
        claim_service=claim_service,
        evaluation_system=evaluation_system,
        registry=registry,
        claim=claim,
        claim_catalog=claim_catalog,
        evidence_ledger=evidence_ledger,
        resolution_snapshot=resolution_snapshot,
    )


def _evaluate(
    runtime: _EvaluationRuntime,
) -> ClaimEvidenceEvaluation:
    return ClaimEvidenceEvaluator(
        actor_registry=runtime.registry,
        claim_catalog=runtime.claim_catalog,
        resolution_snapshot=runtime.resolution_snapshot,
        evidence_ledger=runtime.evidence_ledger,
    ).evaluate(
        key="bounded-runtime-evaluation",
        evaluated_at=UtcTimestamp.parse(
            "2026-07-16T03:16:00Z"
        ),
        evaluated_by_id=runtime.evaluation_system.actor_id,
        claim_id=runtime.claim.claim_id,
    )


def test_satisfied_requirements_are_ready_only_for_human_adjudication() -> None:
    runtime = _runtime()
    evaluation = _evaluate(
        runtime
    )
    requirement = runtime.claim.evidence_requirements[0]
    finding = evaluation.require_requirement_evaluation(
        requirement.requirement_id
    )

    assert evaluation.status is (
        ClaimEvidenceEvaluationStatus
        .READY_FOR_HUMAN_ADJUDICATION
    )
    assert evaluation.is_ready_for_human_adjudication is True
    assert evaluation.establishes_truth is False
    assert evaluation.grants_authority is False
    assert evaluation.claims_certification is False

    assert finding.outcome is (
        ClaimRequirementEvaluationOutcome.SATISFIED
    )
    assert set(finding.reasons) == {
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
    }
    assert len(finding.admitted_record_ids) == 2
    assert finding.establishes_claim is False
    assert evaluation.digest().verifies(
        evaluation.canonical_payload()
    ) is True


def test_missing_record_count_and_independence_leave_claim_incomplete() -> None:
    runtime = _runtime(
        include_passing_test=False
    )
    evaluation = _evaluate(
        runtime
    )
    finding = evaluation.require_requirement_evaluation(
        runtime.claim.evidence_requirements[0].requirement_id
    )

    assert evaluation.status is (
        ClaimEvidenceEvaluationStatus.INCOMPLETE
    )
    assert finding.outcome is (
        ClaimRequirementEvaluationOutcome.UNSATISFIED
    )
    assert (
        ClaimRequirementEvaluationReason
        .MINIMUM_RECORDS_NOT_MET
        in finding.reasons
    )
    assert (
        ClaimRequirementEvaluationReason
        .INDEPENDENT_PRODUCERS_MISSING
        in finding.reasons
    )


def test_admitted_adverse_evidence_creates_falsification_signal() -> None:
    runtime = _runtime(
        include_failed_test=True
    )
    evaluation = _evaluate(
        runtime
    )
    finding = evaluation.require_requirement_evaluation(
        runtime.claim.evidence_requirements[0].requirement_id
    )

    assert evaluation.status is (
        ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL
    )
    assert finding.outcome is (
        ClaimRequirementEvaluationOutcome
        .FALSIFICATION_SIGNAL
    )
    assert (
        ClaimRequirementEvaluationReason
        .ADVERSE_EVIDENCE_PRESENT
        in finding.reasons
    )
    assert len(finding.adverse_record_ids) == 1
    assert set(
        finding.adverse_record_ids
    ).issubset(
        finding.admitted_record_ids
    )


def test_unresolved_relevant_evidence_requires_human_review() -> None:
    requirement = _requirement(
        key="asserted-source-requirement",
        acceptable_kinds=(
            EvidenceKind.SOURCE_RECORD,
        ),
        minimum_records=1,
        require_primary_evidence=False,
        require_independent_producers=False,
    )
    runtime = _runtime(
        include_passing_test=False,
        include_asserted_record=True,
        requirement=requirement,
    )
    evaluation = _evaluate(
        runtime
    )
    finding = evaluation.require_requirement_evaluation(
        requirement.requirement_id
    )

    assert evaluation.status is (
        ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED
    )
    assert finding.outcome is (
        ClaimRequirementEvaluationOutcome
        .HUMAN_REVIEW_REQUIRED
    )
    assert finding.unresolved_record_ids == (
        _identifier(
            "record",
            "asserted-runtime-summary",
        ),
    )
    assert (
        ClaimRequirementEvaluationReason
        .UNRESOLVED_RELEVANT_EVIDENCE
        in finding.reasons
    )


def test_excluded_evidence_remains_visible_but_cannot_satisfy_requirement() -> None:
    requirement = _requirement(
        key="test-result-requirement",
        acceptable_kinds=(
            EvidenceKind.TEST_RESULT,
        ),
        minimum_records=1,
        require_primary_evidence=True,
        require_independent_producers=False,
    )
    runtime = _runtime(
        include_passing_test=False,
        include_invalidated_test=True,
        requirement=requirement,
    )
    evaluation = _evaluate(
        runtime
    )
    finding = evaluation.require_requirement_evaluation(
        requirement.requirement_id
    )

    assert evaluation.status is (
        ClaimEvidenceEvaluationStatus.INCOMPLETE
    )
    assert finding.admitted_record_ids == ()
    assert finding.excluded_record_ids == (
        _identifier(
            "record",
            "invalidated-test-result",
        ),
    )
    assert (
        ClaimRequirementEvaluationReason
        .EXCLUDED_RELEVANT_EVIDENCE_PRESENT
        in finding.reasons
    )
    assert (
        ClaimRequirementEvaluationReason
        .NO_ACCEPTABLE_EVIDENCE
        in finding.reasons
    )


def test_subject_mismatch_prevents_evidence_substitution() -> None:
    runtime = _runtime(
        claim_subject_key="agent-beta"
    )
    evaluation = _evaluate(
        runtime
    )
    finding = evaluation.require_requirement_evaluation(
        runtime.claim.evidence_requirements[0].requirement_id
    )

    assert evaluation.status is (
        ClaimEvidenceEvaluationStatus.INCOMPLETE
    )
    assert finding.admitted_record_ids == ()
    assert (
        ClaimRequirementEvaluationReason
        .SUBJECT_MATCH_MISSING
        in finding.reasons
    )


def test_human_actor_cannot_issue_machine_evidence_evaluation() -> None:
    runtime = _runtime()
    evaluator = ClaimEvidenceEvaluator(
        actor_registry=runtime.registry,
        claim_catalog=runtime.claim_catalog,
        resolution_snapshot=runtime.resolution_snapshot,
        evidence_ledger=runtime.evidence_ledger,
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        evaluator.evaluate(
            key="human-issued-evaluation",
            evaluated_at=UtcTimestamp.parse(
                "2026-07-16T03:16:00Z"
            ),
            evaluated_by_id=runtime.reviewer.actor_id,
            claim_id=runtime.claim.claim_id,
        )


def test_evaluator_rejects_unbound_evidence_ledger() -> None:
    runtime = _runtime()
    different_ledger = EvidenceLedger.create(
        key="different-claim-evaluation-evidence",
        created_at=runtime.evidence_ledger.created_at,
        producer_id=runtime.evidence_service.actor_id,
        actor_registry=runtime.registry,
        records=(),
    )

    with pytest.raises(
        FoundationError,
        match="resolution snapshot is not bound",
    ):
        ClaimEvidenceEvaluator(
            actor_registry=runtime.registry,
            claim_catalog=runtime.claim_catalog,
            resolution_snapshot=runtime.resolution_snapshot,
            evidence_ledger=different_ledger,
        )


def test_evaluation_must_follow_claim_catalog_and_resolution() -> None:
    runtime = _runtime()
    evaluator = ClaimEvidenceEvaluator(
        actor_registry=runtime.registry,
        claim_catalog=runtime.claim_catalog,
        resolution_snapshot=runtime.resolution_snapshot,
        evidence_ledger=runtime.evidence_ledger,
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the claim catalog",
    ):
        evaluator.evaluate(
            key="premature-claim-evaluation",
            evaluated_at=UtcTimestamp.parse(
                "2026-07-16T03:14:59Z"
            ),
            evaluated_by_id=runtime.evaluation_system.actor_id,
            claim_id=runtime.claim.claim_id,
        )


def test_claim_evaluation_is_deterministic() -> None:
    first_runtime = _runtime()
    second_runtime = _runtime()

    first = _evaluate(
        first_runtime
    )
    second = _evaluate(
        second_runtime
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
