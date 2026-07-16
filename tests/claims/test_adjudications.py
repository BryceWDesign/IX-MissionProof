"""Tests for independent human claim adjudications."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ix_missionproof.claims import (
    ClaimAdjudicationDecision,
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
    registry: ActorRegistry
    requirement: ClaimEvidenceRequirement
    claim: ClaimSpecification
    catalog: ClaimCatalog
    admitted_record_ids: tuple[ScopedIdentifier, ...]
    adverse_record_id: ScopedIdentifier
    unresolved_record_id: ScopedIdentifier
    excluded_record_id: ScopedIdentifier


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
    registry = ActorRegistry.create(
        key="claim-adjudication-actors",
        created_at=UtcTimestamp.parse("2026-07-16T04:00:00Z"),
        producer_id=reviewer.actor_id,
        actors=(
            owner,
            reviewer,
            author_service,
            evaluator_system,
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
        created_at=UtcTimestamp.parse("2026-07-16T04:05:00Z"),
        authored_by_id=author_service.actor_id,
        kind=ClaimKind.SAFETY,
        criticality=ClaimCriticality.HIGH,
        review_level=(ClaimReviewLevel.INDEPENDENT_HUMAN_REVIEW),
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
        evidence_requirements=(requirement,),
        limitations=("The claim applies only to the evaluated test run.",),
        prohibited_interpretations=(
            "Do not interpret this claim as certification.",
            "Do not interpret this claim as execution authority.",
        ),
        actor_registry=registry,
    )
    catalog = ClaimCatalog.create(
        key="claim-adjudication-catalog",
        created_at=UtcTimestamp.parse("2026-07-16T04:06:00Z"),
        producer_id=author_service.actor_id,
        actor_registry=registry,
        claims=(claim,),
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        author_service=author_service,
        evaluator_system=evaluator_system,
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
) -> ClaimEvidenceEvaluation:
    admitted_record_ids = runtime.admitted_record_ids
    adverse_record_ids: tuple[ScopedIdentifier, ...] = ()
    unresolved_record_ids: tuple[ScopedIdentifier, ...] = ()
    excluded_record_ids: tuple[ScopedIdentifier, ...] = ()

    if status is (ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION):
        outcome = ClaimRequirementEvaluationOutcome.SATISFIED
        reasons = (
            ClaimRequirementEvaluationReason.ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.INDEPENDENT_PRODUCERS_PRESENT,
            ClaimRequirementEvaluationReason.MINIMUM_RECORDS_MET,
            ClaimRequirementEvaluationReason.PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.SUBJECT_MATCH_CONFIRMED,
        )
    elif status is ClaimEvidenceEvaluationStatus.INCOMPLETE:
        outcome = ClaimRequirementEvaluationOutcome.UNSATISFIED
        admitted_record_ids = (runtime.admitted_record_ids[0],)
        reasons = (
            ClaimRequirementEvaluationReason.ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.INDEPENDENT_PRODUCERS_MISSING,
            ClaimRequirementEvaluationReason.MINIMUM_RECORDS_NOT_MET,
            ClaimRequirementEvaluationReason.PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.SUBJECT_MATCH_CONFIRMED,
        )
    elif status is (ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED):
        outcome = ClaimRequirementEvaluationOutcome.HUMAN_REVIEW_REQUIRED
        admitted_record_ids = ()
        unresolved_record_ids = (runtime.unresolved_record_id,)
        reasons = (
            ClaimRequirementEvaluationReason.NO_ACCEPTABLE_EVIDENCE,
            ClaimRequirementEvaluationReason.MINIMUM_RECORDS_NOT_MET,
            ClaimRequirementEvaluationReason.PRIMARY_EVIDENCE_MISSING,
            ClaimRequirementEvaluationReason.UNRESOLVED_RELEVANT_EVIDENCE,
        )
    else:
        outcome = ClaimRequirementEvaluationOutcome.FALSIFICATION_SIGNAL
        admitted_record_ids = (
            *runtime.admitted_record_ids,
            runtime.adverse_record_id,
        )
        adverse_record_ids = (runtime.adverse_record_id,)
        excluded_record_ids = (runtime.excluded_record_id,)
        reasons = (
            ClaimRequirementEvaluationReason.ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.ADVERSE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.EXCLUDED_RELEVANT_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.INDEPENDENT_PRODUCERS_PRESENT,
            ClaimRequirementEvaluationReason.MINIMUM_RECORDS_MET,
            ClaimRequirementEvaluationReason.PRIMARY_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason.SUBJECT_MATCH_CONFIRMED,
        )

    requirement_evaluation = ClaimRequirementEvaluation(
        evaluation_id=_identifier(
            "claim-requirement-evaluation",
            f"requirement-{status.value}",
        ),
        evaluated_at=UtcTimestamp.parse("2026-07-16T04:07:00Z"),
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
            status.value,
        ),
        evidence_ledger_digest=_digest(
            "evidence-ledger",
            status.value,
        ),
    )

    return ClaimEvidenceEvaluation(
        evaluation_id=_identifier(
            "claim-evidence-evaluation",
            status.value,
        ),
        evaluated_at=requirement_evaluation.evaluated_at,
        evaluated_by_id=runtime.evaluator_system.actor_id,
        evaluator_kind=runtime.evaluator_system.kind,
        evaluator_accountability_owner_id=(runtime.reviewer.actor_id),
        claim_id=runtime.claim.claim_id,
        claim_catalog_id=runtime.catalog.catalog_id,
        resolution_snapshot_id=_identifier(
            "evidence-admission-resolution-snapshot",
            status.value,
        ),
        evidence_ledger_id=_identifier(
            "evidence-ledger",
            status.value,
        ),
        status=status,
        requirement_evaluations=(requirement_evaluation,),
        claim_digest=runtime.claim.digest(),
        claim_catalog_digest=runtime.catalog.digest(),
        resolution_snapshot_digest=(requirement_evaluation.resolution_snapshot_digest),
        evidence_ledger_digest=(requirement_evaluation.evidence_ledger_digest),
        actor_registry_digest=runtime.registry.digest(),
    )


def _decision(
    runtime: _Runtime,
    evaluation: ClaimEvidenceEvaluation,
    *,
    status: ClaimAdjudicationDecisionStatus,
    key: str,
    supporting_record_ids: tuple[ScopedIdentifier, ...] | None = None,
    decided_by_id: ScopedIdentifier | None = None,
    decided_at: str = "2026-07-16T04:08:00Z",
) -> ClaimAdjudicationDecision:
    default_support = (
        runtime.admitted_record_ids
        if status is ClaimAdjudicationDecisionStatus.SUPPORTED
        else ()
    )

    return ClaimAdjudicationDecision.decide(
        key=key,
        decided_at=UtcTimestamp.parse(decided_at),
        decided_by_id=(decided_by_id or runtime.reviewer.actor_id),
        status=status,
        rationale=f"Bounded human judgment: {status.value}.",
        supporting_record_ids=(
            supporting_record_ids
            if supporting_record_ids is not None
            else default_support
        ),
        claim=runtime.claim,
        evaluation=evaluation,
        claim_catalog=runtime.catalog,
        actor_registry=runtime.registry,
    )


def test_independent_human_can_support_ready_bounded_claim() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION),
    )
    decision = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.SUPPORTED,
        key="support-bounded-runtime",
    )

    assert decision.supports_claim is True
    assert decision.closes_claim is True
    assert decision.reviewer_independent is True
    assert decision.establishes_absolute_truth is False
    assert decision.grants_authority is False
    assert decision.claims_certification is False
    assert decision.claim_digest == runtime.claim.digest()
    assert decision.evaluation_digest == evaluation.digest()
    assert decision.digest().verifies(decision.to_payload()) is True


def test_falsification_signal_cannot_be_supported() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL,
    )

    rejected = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.NOT_SUPPORTED,
        key="reject-falsified-claim",
        supporting_record_ids=(runtime.adverse_record_id,),
    )
    assert rejected.supports_claim is False

    with pytest.raises(
        FoundationError,
        match="ready for human adjudication",
    ):
        _decision(
            runtime,
            evaluation,
            status=ClaimAdjudicationDecisionStatus.SUPPORTED,
            key="support-falsified-claim",
        )


def test_incomplete_or_unresolved_evidence_cannot_be_upgraded() -> None:
    runtime = _runtime()

    for status in (
        ClaimEvidenceEvaluationStatus.INCOMPLETE,
        ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED,
    ):
        evaluation = _evaluation(
            runtime,
            status=status,
        )

        visible_record_id = (
            runtime.unresolved_record_id
            if status is ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED
            else runtime.admitted_record_ids[0]
        )

        with pytest.raises(
            FoundationError,
            match="ready for human adjudication",
        ):
            _decision(
                runtime,
                evaluation,
                status=ClaimAdjudicationDecisionStatus.SUPPORTED,
                key=f"support-{status.value}",
                supporting_record_ids=(visible_record_id,),
            )


def test_claim_author_owner_cannot_adjudicate_own_machine_claim() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION),
    )

    with pytest.raises(
        FoundationError,
        match="must not adjudicate their own claim",
    ):
        _decision(
            runtime,
            evaluation,
            status=ClaimAdjudicationDecisionStatus.SUPPORTED,
            key="owner-self-adjudication",
            decided_by_id=runtime.owner.actor_id,
        )


def test_machine_actor_cannot_issue_human_adjudication() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION),
    )

    with pytest.raises(
        FoundationError,
        match="active human reviewer",
    ):
        _decision(
            runtime,
            evaluation,
            status=ClaimAdjudicationDecisionStatus.SUPPORTED,
            key="machine-adjudication",
            decided_by_id=runtime.evaluator_system.actor_id,
        )


def test_supported_claim_requires_explicit_admitted_citations() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION),
    )

    with pytest.raises(
        FoundationError,
        match="require at least one supporting evidence record",
    ):
        _decision(
            runtime,
            evaluation,
            status=ClaimAdjudicationDecisionStatus.SUPPORTED,
            key="uncited-support",
            supporting_record_ids=(),
        )

    with pytest.raises(
        FoundationError,
        match="present in the bound claim evidence evaluation",
    ):
        _decision(
            runtime,
            evaluation,
            status=ClaimAdjudicationDecisionStatus.SUPPORTED,
            key="unknown-citation",
            supporting_record_ids=(
                _identifier(
                    "record",
                    "unknown-evidence",
                ),
            ),
        )


def test_non_supporting_decisions_may_cite_visible_adverse_evidence() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL,
    )
    decision = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.NOT_SUPPORTED,
        key="not-supported-with-adverse-evidence",
        supporting_record_ids=(
            runtime.adverse_record_id,
            runtime.excluded_record_id,
        ),
    )

    assert decision.supporting_record_ids == (
        runtime.adverse_record_id,
        runtime.excluded_record_id,
    )
    assert decision.closes_claim is True


def test_deferred_decision_is_nonterminal_and_grants_no_authority() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=ClaimEvidenceEvaluationStatus.INCOMPLETE,
    )
    decision = _decision(
        runtime,
        evaluation,
        status=ClaimAdjudicationDecisionStatus.DEFERRED,
        key="defer-incomplete-claim",
    )

    assert decision.supports_claim is False
    assert decision.closes_claim is False
    assert decision.grants_authority is False


def test_adjudication_must_follow_bound_evidence_evaluation() -> None:
    runtime = _runtime()
    evaluation = _evaluation(
        runtime,
        status=(ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION),
    )

    with pytest.raises(
        FoundationError,
        match="must not precede the claim evidence evaluation",
    ):
        _decision(
            runtime,
            evaluation,
            status=ClaimAdjudicationDecisionStatus.DEFERRED,
            key="premature-adjudication",
            decided_at="2026-07-16T04:06:59Z",
        )
