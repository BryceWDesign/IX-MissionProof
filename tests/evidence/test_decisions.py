"""Tests for independent human evidence-admission decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.evidence import (
    EvidenceAdmissionDecision,
    EvidenceAdmissionDecisionLedger,
    EvidenceAdmissionDecisionStatus,
    EvidenceAdmissionEvaluator,
    EvidenceAdmissionOutcome,
    EvidenceAdmissionPolicy,
    EvidenceAdmissionReview,
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
    ActorStatus,
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
class _DecisionRuntime:
    owner: ActorIdentity
    independent_reviewer: ActorIdentity
    sensor: ActorIdentity
    evidence_service: ActorIdentity
    admission_service: ActorIdentity
    registry: ActorRegistry
    primary_record: EvidenceRecord
    asserted_record: EvidenceRecord
    excluded_record: EvidenceRecord
    ledger: EvidenceLedger
    review: EvidenceAdmissionReview


def _runtime() -> _DecisionRuntime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="evidence-owner",
        display_name="Evidence Producer Owner",
        roles=("evidence accountability owner",),
    )
    independent_reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-reviewer",
        display_name="Independent Evidence Reviewer",
        roles=("evidence admission reviewer",),
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
        accountability_owner_id=independent_reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="evidence-decision-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:00:00Z"
        ),
        producer_id=independent_reviewer.actor_id,
        actors=(
            owner,
            independent_reviewer,
            sensor,
            evidence_service,
            admission_service,
        ),
    )
    primary_record = EvidenceRecord.create(
        key="runtime-observation",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:02:00Z"
        ),
        produced_by_id=sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=EvidenceStatus.RECORDED,
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
        ),
        summary="The bounded runtime was observed.",
        payload={
            "mode": "bounded",
            "network_enabled": False,
        },
        actor_registry=registry,
    )
    asserted_record = EvidenceRecord.create(
        key="asserted-runtime-summary",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:03:00Z"
        ),
        produced_by_id=evidence_service.actor_id,
        kind=EvidenceKind.SOURCE_RECORD,
        origin=EvidenceOrigin.ASSERTED,
        status=EvidenceStatus.RECORDED,
        subject_ids=primary_record.subject_ids,
        summary="An asserted summary of the runtime evidence.",
        payload={
            "summary": "The runtime remained bounded.",
        },
        actor_registry=registry,
        source_record_ids=(
            primary_record.record_id,
        ),
    )
    excluded_record = EvidenceRecord.create(
        key="invalidated-observation",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:04:00Z"
        ),
        produced_by_id=sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=EvidenceStatus.INVALIDATED,
        subject_ids=primary_record.subject_ids,
        summary="An invalidated observation.",
        payload={
            "mode": "unknown",
        },
        actor_registry=registry,
    )
    ledger = EvidenceLedger.create(
        key="evidence-decision-ledger",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:10:00Z"
        ),
        producer_id=evidence_service.actor_id,
        actor_registry=registry,
        records=(
            primary_record,
            asserted_record,
            excluded_record,
        ),
    )
    policy = EvidenceAdmissionPolicy.create(
        key="evidence-decision-policy",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:01:00Z"
        ),
        authored_by_id=independent_reviewer.actor_id,
        summary=(
            "Require human review for asserted evidence "
            "while excluding invalidated evidence."
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
    review = EvidenceAdmissionEvaluator(
        actor_registry=registry,
        evidence_ledger=ledger,
        policy=policy,
    ).review(
        key="evidence-decision-review",
        reviewed_at=UtcTimestamp.parse(
            "2026-07-16T00:11:00Z"
        ),
        reviewed_by_id=admission_service.actor_id,
    )

    return _DecisionRuntime(
        owner=owner,
        independent_reviewer=independent_reviewer,
        sensor=sensor,
        evidence_service=evidence_service,
        admission_service=admission_service,
        registry=registry,
        primary_record=primary_record,
        asserted_record=asserted_record,
        excluded_record=excluded_record,
        ledger=ledger,
        review=review,
    )


def _decision(
    runtime: _DecisionRuntime,
    *,
    status: EvidenceAdmissionDecisionStatus,
    key: str,
    decided_at: str = "2026-07-16T00:12:00Z",
    decided_by_id: ScopedIdentifier | None = None,
    supporting_record_ids: tuple[ScopedIdentifier, ...] | None = None,
) -> EvidenceAdmissionDecision:
    finding = runtime.review.require_finding(
        runtime.asserted_record.record_id
    )

    return EvidenceAdmissionDecision.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=(
            decided_by_id
            or runtime.independent_reviewer.actor_id
        ),
        status=status,
        rationale=f"Human decision: {status.value}.",
        supporting_record_ids=(
            supporting_record_ids
            if supporting_record_ids is not None
            else (
                runtime.primary_record.record_id,
            )
        ),
        finding=finding,
        admission_review=runtime.review,
        evidence_ledger=runtime.ledger,
        actor_registry=runtime.registry,
    )


def test_independent_human_can_admit_review_required_record() -> None:
    runtime = _runtime()
    decision = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="admit-asserted-summary",
    )

    assert decision.admits_record is True
    assert decision.excludes_record is False
    assert decision.defers_record is False
    assert decision.resolved_outcome is (
        EvidenceAdmissionOutcome.ADMITTED
    )
    assert decision.overrides_automated_exclusion is False
    assert decision.establishes_claim is False
    assert decision.record_digest == runtime.asserted_record.digest()
    assert decision.review_digest == runtime.review.digest()
    assert decision.digest().verifies(
        decision.to_payload()
    ) is True


def test_human_can_exclude_or_defer_review_required_record() -> None:
    runtime = _runtime()
    excluded = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.EXCLUDE,
        key="exclude-asserted-summary",
    )
    deferred = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.DEFER,
        key="defer-asserted-summary",
        supporting_record_ids=(),
    )

    assert excluded.excludes_record is True
    assert excluded.resolved_outcome is (
        EvidenceAdmissionOutcome.EXCLUDED
    )
    assert deferred.defers_record is True
    assert deferred.resolved_outcome is (
        EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
    )


def test_automated_exclusion_cannot_be_human_overridden() -> None:
    runtime = _runtime()
    finding = runtime.review.require_finding(
        runtime.excluded_record.record_id
    )

    assert finding.outcome is EvidenceAdmissionOutcome.EXCLUDED

    with pytest.raises(
        FoundationError,
        match="automated admissions and exclusions are not overridable",
    ):
        EvidenceAdmissionDecision.decide(
            key="override-invalidated-evidence",
            decided_at=UtcTimestamp.parse(
                "2026-07-16T00:12:00Z"
            ),
            decided_by_id=runtime.independent_reviewer.actor_id,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            rationale="Attempted override.",
            supporting_record_ids=(
                runtime.primary_record.record_id,
            ),
            finding=finding,
            admission_review=runtime.review,
            evidence_ledger=runtime.ledger,
            actor_registry=runtime.registry,
        )


def test_automatic_admission_does_not_accept_unnecessary_decision() -> None:
    runtime = _runtime()
    finding = runtime.review.require_finding(
        runtime.primary_record.record_id
    )

    assert finding.outcome is EvidenceAdmissionOutcome.ADMITTED

    with pytest.raises(
        FoundationError,
        match="automated admissions and exclusions are not overridable",
    ):
        EvidenceAdmissionDecision.decide(
            key="unnecessary-admission-decision",
            decided_at=UtcTimestamp.parse(
                "2026-07-16T00:12:00Z"
            ),
            decided_by_id=runtime.independent_reviewer.actor_id,
            status=EvidenceAdmissionDecisionStatus.EXCLUDE,
            rationale="Attempted replacement of automatic admission.",
            supporting_record_ids=(),
            finding=finding,
            admission_review=runtime.review,
            evidence_ledger=runtime.ledger,
            actor_registry=runtime.registry,
        )


def test_machine_owner_cannot_self_approve_machine_evidence() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="accountability owner must not self-approve",
    ):
        _decision(
            runtime,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            key="owner-self-approval",
            decided_by_id=runtime.owner.actor_id,
        )


def test_machine_or_inactive_human_cannot_decide_admission() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="active human reviewer",
    ):
        _decision(
            runtime,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            key="machine-reviewer",
            decided_by_id=runtime.admission_service.actor_id,
        )

    suspended = replace(
        runtime.independent_reviewer,
        status=ActorStatus.SUSPENDED,
    )
    suspended_registry = ActorRegistry.create(
        key="suspended-evidence-decision-actors",
        created_at=runtime.registry.created_at,
        producer_id=runtime.owner.actor_id,
        actors=(
            runtime.owner,
            suspended,
            runtime.sensor,
            runtime.evidence_service,
            runtime.admission_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="active human reviewer",
    ):
        EvidenceAdmissionDecision.decide(
            key="suspended-reviewer",
            decided_at=UtcTimestamp.parse(
                "2026-07-16T00:12:00Z"
            ),
            decided_by_id=suspended.actor_id,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            rationale="Suspended reviewer attempted admission.",
            supporting_record_ids=(
                runtime.primary_record.record_id,
            ),
            finding=runtime.review.require_finding(
                runtime.asserted_record.record_id
            ),
            admission_review=runtime.review,
            evidence_ledger=runtime.ledger,
            actor_registry=suspended_registry,
        )


def test_admit_decision_requires_admitted_support() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="require at least one supporting record",
    ):
        _decision(
            runtime,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            key="unsupported-admission",
            supporting_record_ids=(),
        )

    with pytest.raises(
        FoundationError,
        match="automatically admitted",
    ):
        _decision(
            runtime,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            key="invalidated-support",
            supporting_record_ids=(
                runtime.excluded_record.record_id,
            ),
        )


def test_supporting_record_must_share_subject_with_target() -> None:
    runtime = _runtime()
    unrelated = EvidenceRecord.create(
        key="unrelated-observation",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:05:00Z"
        ),
        produced_by_id=runtime.sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=EvidenceStatus.RECORDED,
        subject_ids=(
            _identifier(
                "system",
                "unrelated-system",
            ),
        ),
        summary="An unrelated observation.",
        payload={
            "state": "unrelated",
        },
        actor_registry=runtime.registry,
    )
    expanded_ledger = EvidenceLedger.create(
        key="expanded-evidence-decision-ledger",
        created_at=runtime.ledger.created_at,
        producer_id=runtime.evidence_service.actor_id,
        actor_registry=runtime.registry,
        records=(
            *runtime.ledger.records,
            unrelated,
        ),
    )
    policy = EvidenceAdmissionPolicy.create(
        key="expanded-evidence-decision-policy",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:01:00Z"
        ),
        authored_by_id=runtime.independent_reviewer.actor_id,
        summary="Expanded admission policy.",
        actor_registry=runtime.registry,
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
    expanded_review = EvidenceAdmissionEvaluator(
        actor_registry=runtime.registry,
        evidence_ledger=expanded_ledger,
        policy=policy,
    ).review(
        key="expanded-evidence-decision-review",
        reviewed_at=runtime.review.reviewed_at,
        reviewed_by_id=runtime.admission_service.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="share at least one subject",
    ):
        EvidenceAdmissionDecision.decide(
            key="unrelated-support",
            decided_at=UtcTimestamp.parse(
                "2026-07-16T00:12:00Z"
            ),
            decided_by_id=runtime.independent_reviewer.actor_id,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            rationale="Attempted admission using unrelated evidence.",
            supporting_record_ids=(
                unrelated.record_id,
            ),
            finding=expanded_review.require_finding(
                runtime.asserted_record.record_id
            ),
            admission_review=expanded_review,
            evidence_ledger=expanded_ledger,
            actor_registry=runtime.registry,
        )


def test_decision_must_follow_automated_review() -> None:
    runtime = _runtime()

    with pytest.raises(
        FoundationError,
        match="must not precede the automated admission review",
    ):
        _decision(
            runtime,
            status=EvidenceAdmissionDecisionStatus.ADMIT,
            key="premature-admission",
            decided_at="2026-07-16T00:10:59Z",
        )


def test_ledger_allows_deferral_then_terminal_decision() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.DEFER,
        key="defer-for-more-evidence",
        decided_at="2026-07-16T00:12:00Z",
        supporting_record_ids=(),
    )
    admitted = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="admit-after-review",
        decided_at="2026-07-16T00:13:00Z",
    )
    ledger = EvidenceAdmissionDecisionLedger.create(
        key="human-admission-decisions",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:14:00Z"
        ),
        producer_id=runtime.admission_service.actor_id,
        admission_review=runtime.review,
        actor_registry=runtime.registry,
        decisions=(
            admitted,
            deferred,
        ),
    )
    finding = runtime.review.require_finding(
        runtime.asserted_record.record_id
    )

    assert ledger.decisions_for_finding(
        finding.finding_id
    ) == (
        deferred,
        admitted,
    )
    assert ledger.latest_for_finding(
        finding.finding_id
    ) == admitted
    assert ledger.resolved_outcome_for(
        finding
    ) is EvidenceAdmissionOutcome.ADMITTED
    assert ledger.unresolved_findings(
        admission_review=runtime.review
    ) == ()


def test_ledger_rejects_replacement_after_terminal_decision() -> None:
    runtime = _runtime()
    admitted = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="terminal-admission",
        decided_at="2026-07-16T00:12:00Z",
    )
    excluded = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.EXCLUDE,
        key="replacement-exclusion",
        decided_at="2026-07-16T00:13:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="terminal evidence-admission decisions must not be replaced",
    ):
        EvidenceAdmissionDecisionLedger.create(
            key="invalid-terminal-sequence",
            created_at=UtcTimestamp.parse(
                "2026-07-16T00:14:00Z"
            ),
            producer_id=runtime.admission_service.actor_id,
            admission_review=runtime.review,
            actor_registry=runtime.registry,
            decisions=(
                admitted,
                excluded,
            ),
        )


def test_ledger_combines_automatic_and_human_admissions() -> None:
    runtime = _runtime()
    admitted = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="human-admission",
    )
    ledger = EvidenceAdmissionDecisionLedger.create(
        key="resolved-admission-decisions",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:13:00Z"
        ),
        producer_id=runtime.admission_service.actor_id,
        admission_review=runtime.review,
        actor_registry=runtime.registry,
        decisions=(
            admitted,
        ),
    )

    assert ledger.admitted_records(
        admission_review=runtime.review,
        evidence_ledger=runtime.ledger,
    ) == (
        runtime.asserted_record,
        runtime.primary_record,
    )


def test_deferred_finding_remains_unresolved() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.DEFER,
        key="unresolved-deferral",
        supporting_record_ids=(),
    )
    ledger = EvidenceAdmissionDecisionLedger.create(
        key="deferred-admission-decisions",
        created_at=UtcTimestamp.parse(
            "2026-07-16T00:13:00Z"
        ),
        producer_id=runtime.admission_service.actor_id,
        admission_review=runtime.review,
        actor_registry=runtime.registry,
        decisions=(
            deferred,
        ),
    )

    assert ledger.unresolved_findings(
        admission_review=runtime.review
    ) == (
        runtime.review.require_finding(
            runtime.asserted_record.record_id
        ),
    )


def test_decision_ledger_digest_is_input_order_independent() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.DEFER,
        key="stable-deferral",
        decided_at="2026-07-16T00:12:00Z",
        supporting_record_ids=(),
    )
    admitted = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="stable-admission",
        decided_at="2026-07-16T00:13:00Z",
    )
    created_at = UtcTimestamp.parse(
        "2026-07-16T00:14:00Z"
    )

    first = EvidenceAdmissionDecisionLedger.create(
        key="stable-decision-ledger",
        created_at=created_at,
        producer_id=runtime.admission_service.actor_id,
        admission_review=runtime.review,
        actor_registry=runtime.registry,
        decisions=(
            deferred,
            admitted,
        ),
    )
    second = EvidenceAdmissionDecisionLedger.create(
        key="stable-decision-ledger",
        created_at=created_at,
        producer_id=runtime.admission_service.actor_id,
        admission_review=runtime.review,
        actor_registry=runtime.registry,
        decisions=(
            admitted,
            deferred,
        ),
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
