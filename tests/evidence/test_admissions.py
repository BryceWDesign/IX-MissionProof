"""Tests for deterministic evidence-admission review."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.evidence import (
    EvidenceAdmissionEvaluator,
    EvidenceAdmissionOutcome,
    EvidenceAdmissionPolicy,
    EvidenceAdmissionReason,
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
class _AdmissionActors:
    human: ActorIdentity
    sensor: ActorIdentity
    evidence_service: ActorIdentity
    admission_service: ActorIdentity
    registry: ActorRegistry


def _actors(
    *,
    key: str = "admission-actors",
) -> _AdmissionActors:
    human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-01",
        display_name="Mission Reviewer",
        roles=(
            "evidence policy author",
        ),
    )
    sensor = ActorIdentity.create(
        kind=ActorKind.SENSOR,
        key="runtime-sensor",
        display_name="Runtime Sensor",
        accountability_owner_id=human.actor_id,
    )
    evidence_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="evidence-service",
        display_name="Evidence Service",
        accountability_owner_id=human.actor_id,
    )
    admission_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="admission-service",
        display_name="Evidence Admission Service",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key=key,
        created_at=UtcTimestamp.parse(
            "2026-07-15T23:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            sensor,
            evidence_service,
            admission_service,
        ),
    )

    return _AdmissionActors(
        human=human,
        sensor=sensor,
        evidence_service=evidence_service,
        admission_service=admission_service,
        registry=registry,
    )


def _policy(
    actors: _AdmissionActors,
    *,
    key: str = "default-admission-policy",
    allowed_kinds: tuple[EvidenceKind, ...] | None = None,
    allowed_statuses: tuple[EvidenceStatus, ...] | None = None,
    human_review_origins: tuple[EvidenceOrigin, ...] = (
        EvidenceOrigin.ASSERTED,
        EvidenceOrigin.IMPORTED,
        EvidenceOrigin.SIMULATED,
    ),
) -> EvidenceAdmissionPolicy:
    return EvidenceAdmissionPolicy.create(
        key=key,
        created_at=UtcTimestamp.parse(
            "2026-07-15T23:01:00Z"
        ),
        authored_by_id=actors.human.actor_id,
        summary=(
            "Admit intact evidence while preserving "
            "corroboration and human-review boundaries."
        ),
        actor_registry=actors.registry,
        allowed_kinds=(
            allowed_kinds
            if allowed_kinds is not None
            else tuple(EvidenceKind)
        ),
        allowed_origins=tuple(EvidenceOrigin),
        allowed_statuses=(
            allowed_statuses
            if allowed_statuses is not None
            else (
                EvidenceStatus.RECORDED,
                EvidenceStatus.PASSED,
                EvidenceStatus.FAILED,
                EvidenceStatus.BLOCKED,
                EvidenceStatus.INCONCLUSIVE,
            )
        ),
        human_review_origins=human_review_origins,
        require_primary_ancestry=True,
    )


def _observation(
    actors: _AdmissionActors,
    *,
    key: str = "runtime-observation",
    created_at: str = "2026-07-15T23:02:00Z",
    status: EvidenceStatus = EvidenceStatus.RECORDED,
) -> EvidenceRecord:
    return EvidenceRecord.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        produced_by_id=actors.sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=status,
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
        ),
        summary=(
            "The bounded runtime state was observed."
        ),
        payload={
            "mode": "bounded",
            "network_enabled": False,
        },
        actor_registry=actors.registry,
    )


def _test_result(
    actors: _AdmissionActors,
    *,
    key: str = "test-result",
    status: EvidenceStatus = EvidenceStatus.PASSED,
    created_at: str = "2026-07-15T23:03:00Z",
) -> EvidenceRecord:
    return EvidenceRecord.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        produced_by_id=actors.evidence_service.actor_id,
        kind=EvidenceKind.TEST_RESULT,
        origin=EvidenceOrigin.EXECUTED,
        status=status,
        subject_ids=(
            _identifier(
                "run",
                "unit-tests-0001",
            ),
        ),
        summary=(
            "The bounded unit-test target completed."
        ),
        payload={
            "failed": (
                0
                if status is EvidenceStatus.PASSED
                else 1
            ),
            "passed": 42,
        },
        actor_registry=actors.registry,
    )


def _derived(
    actors: _AdmissionActors,
    source: EvidenceRecord,
    *,
    key: str = "derived-summary",
    origin: EvidenceOrigin = EvidenceOrigin.DERIVED,
    created_at: str = "2026-07-15T23:04:00Z",
) -> EvidenceRecord:
    return EvidenceRecord.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        produced_by_id=actors.evidence_service.actor_id,
        kind=EvidenceKind.SOURCE_RECORD,
        origin=origin,
        status=EvidenceStatus.RECORDED,
        subject_ids=source.subject_ids,
        summary=(
            "A source-bound summary of the runtime evidence."
        ),
        payload={
            "summary": "The runtime remained bounded.",
        },
        actor_registry=actors.registry,
        source_record_ids=(
            source.record_id,
        ),
    )


def _ledger(
    actors: _AdmissionActors,
    *records: EvidenceRecord,
    key: str = "admission-evidence",
) -> EvidenceLedger:
    return EvidenceLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            "2026-07-15T23:10:00Z"
        ),
        producer_id=actors.evidence_service.actor_id,
        actor_registry=actors.registry,
        records=records,
    )


def _review(
    actors: _AdmissionActors,
    ledger: EvidenceLedger,
    policy: EvidenceAdmissionPolicy,
) -> EvidenceAdmissionReview:
    return EvidenceAdmissionEvaluator(
        actor_registry=actors.registry,
        evidence_ledger=ledger,
        policy=policy,
    ).review(
        key="admission-review",
        reviewed_at=UtcTimestamp.parse(
            "2026-07-15T23:11:00Z"
        ),
        reviewed_by_id=actors.admission_service.actor_id,
    )


def test_policy_is_human_authored_and_deterministic() -> None:
    actors = _actors()
    policy = _policy(
        actors
    )

    assert str(policy.policy_id) == (
        "evidence-admission-policy:default-admission-policy"
    )
    assert policy.authored_by_id == actors.human.actor_id
    assert policy.actor_registry_digest == actors.registry.digest()
    assert policy.requires_human_review(
        EvidenceOrigin.ASSERTED
    ) is True
    assert policy.requires_human_review(
        EvidenceOrigin.DERIVED
    ) is False
    assert policy.digest().verifies(
        policy.to_payload()
    ) is True


def test_policy_rejects_inactive_or_machine_author() -> None:
    actors = _actors()
    suspended_human = replace(
        actors.human,
        status=ActorStatus.SUSPENDED,
    )
    suspended_registry = ActorRegistry.create(
        key="suspended-policy-actors",
        created_at=actors.registry.created_at,
        producer_id=actors.human.actor_id,
        actors=(
            suspended_human,
            actors.sensor,
            actors.evidence_service,
            actors.admission_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="requires an active human author",
    ):
        EvidenceAdmissionPolicy.create(
            key="suspended-author-policy",
            created_at=UtcTimestamp.parse(
                "2026-07-15T23:01:00Z"
            ),
            authored_by_id=suspended_human.actor_id,
            summary="Invalid policy author.",
            actor_registry=suspended_registry,
            allowed_kinds=tuple(EvidenceKind),
            allowed_origins=tuple(EvidenceOrigin),
            allowed_statuses=(
                EvidenceStatus.RECORDED,
            ),
        )

    with pytest.raises(
        FoundationError,
        match="requires an active human author",
    ):
        EvidenceAdmissionPolicy.create(
            key="machine-author-policy",
            created_at=UtcTimestamp.parse(
                "2026-07-15T23:01:00Z"
            ),
            authored_by_id=actors.evidence_service.actor_id,
            summary="Invalid machine-authored policy.",
            actor_registry=actors.registry,
            allowed_kinds=tuple(EvidenceKind),
            allowed_origins=tuple(EvidenceOrigin),
            allowed_statuses=(
                EvidenceStatus.RECORDED,
            ),
        )


def test_policy_can_never_allow_invalidated_status() -> None:
    actors = _actors()

    with pytest.raises(
        FoundationError,
        match="must never be an allowed status",
    ):
        EvidenceAdmissionPolicy.create(
            key="invalidated-policy",
            created_at=UtcTimestamp.parse(
                "2026-07-15T23:01:00Z"
            ),
            authored_by_id=actors.human.actor_id,
            summary="Invalid policy.",
            actor_registry=actors.registry,
            allowed_kinds=tuple(EvidenceKind),
            allowed_origins=tuple(EvidenceOrigin),
            allowed_statuses=(
                EvidenceStatus.RECORDED,
                EvidenceStatus.INVALIDATED,
            ),
        )


def test_primary_observation_is_admitted_but_proves_no_claim() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    ledger = _ledger(
        actors,
        observation,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )
    finding = review.require_finding(
        observation.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.ADMITTED
    )
    assert finding.reasons == (
        EvidenceAdmissionReason.ADMITTED_BY_POLICY,
    )
    assert review.admitted_records(
        evidence_ledger=ledger
    ) == (
        observation,
    )
    assert review.establishes_claim is False
    assert review.digest().verifies(
        review.canonical_payload()
    ) is True


def test_derived_record_requires_admitted_primary_ancestry() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    derived = _derived(
        actors,
        observation,
    )
    ledger = _ledger(
        actors,
        derived,
        observation,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )
    finding = review.require_finding(
        derived.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.ADMITTED
    )
    assert set(finding.reasons) == {
        EvidenceAdmissionReason.ADMITTED_BY_POLICY,
        EvidenceAdmissionReason
        .CORROBORATED_BY_ADMITTED_SOURCE,
    }


def test_asserted_record_requires_separate_human_review() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    asserted = _derived(
        actors,
        observation,
        key="asserted-summary",
        origin=EvidenceOrigin.ASSERTED,
    )
    ledger = _ledger(
        actors,
        observation,
        asserted,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )
    finding = review.require_finding(
        asserted.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
    )
    assert finding.reasons == (
        EvidenceAdmissionReason
        .ORIGIN_REQUIRES_HUMAN_REVIEW,
    )
    assert review.human_review_findings() == (
        finding,
    )
    assert asserted not in review.admitted_records(
        evidence_ledger=ledger
    )


def test_human_review_requirement_propagates_to_dependent_record() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    asserted = _derived(
        actors,
        observation,
        key="asserted-source",
        origin=EvidenceOrigin.ASSERTED,
        created_at="2026-07-15T23:04:00Z",
    )
    dependent = _derived(
        actors,
        asserted,
        key="dependent-summary",
        origin=EvidenceOrigin.DERIVED,
        created_at="2026-07-15T23:05:00Z",
    )
    ledger = _ledger(
        actors,
        observation,
        asserted,
        dependent,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )
    finding = review.require_finding(
        dependent.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
    )
    assert finding.reasons == (
        EvidenceAdmissionReason
        .SOURCE_REQUIRES_HUMAN_REVIEW,
    )


def test_invalidated_source_excludes_dependent_evidence() -> None:
    actors = _actors()
    invalidated = _observation(
        actors,
        key="invalidated-observation",
        status=EvidenceStatus.INVALIDATED,
    )
    derived = _derived(
        actors,
        invalidated,
        key="invalidated-derived-summary",
    )
    ledger = _ledger(
        actors,
        invalidated,
        derived,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )

    source_finding = review.require_finding(
        invalidated.record_id
    )
    derived_finding = review.require_finding(
        derived.record_id
    )

    assert source_finding.outcome is (
        EvidenceAdmissionOutcome.EXCLUDED
    )
    assert set(source_finding.reasons) == {
        EvidenceAdmissionReason.RECORD_INVALIDATED,
        EvidenceAdmissionReason.STATUS_NOT_ALLOWED,
    }
    assert derived_finding.outcome is (
        EvidenceAdmissionOutcome.EXCLUDED
    )
    assert set(derived_finding.reasons) == {
        EvidenceAdmissionReason.SOURCE_EXCLUDED,
        EvidenceAdmissionReason
        .USABLE_PRIMARY_ANCESTRY_MISSING,
    }


def test_policy_excludes_disallowed_kind() -> None:
    actors = _actors()
    test_result = _test_result(
        actors
    )
    ledger = _ledger(
        actors,
        test_result,
    )
    policy = _policy(
        actors,
        allowed_kinds=(
            EvidenceKind.OBSERVATION,
        ),
    )
    review = _review(
        actors,
        ledger,
        policy,
    )
    finding = review.require_finding(
        test_result.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.EXCLUDED
    )
    assert finding.reasons == (
        EvidenceAdmissionReason.KIND_NOT_ALLOWED,
    )


def test_adverse_evidence_remains_admissible_when_policy_allows_it() -> None:
    actors = _actors()
    failed_test = _test_result(
        actors,
        key="failed-test-result",
        status=EvidenceStatus.FAILED,
    )
    ledger = _ledger(
        actors,
        failed_test,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )

    finding = review.require_finding(
        failed_test.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.ADMITTED
    )
    assert failed_test.status.is_adverse is True
    assert review.admitted_records(
        evidence_ledger=ledger
    ) == (
        failed_test,
    )


def test_policy_may_exclude_failed_status_without_hiding_record() -> None:
    actors = _actors()
    failed_test = _test_result(
        actors,
        key="excluded-failed-test",
        status=EvidenceStatus.FAILED,
    )
    ledger = _ledger(
        actors,
        failed_test,
    )
    policy = _policy(
        actors,
        allowed_statuses=(
            EvidenceStatus.RECORDED,
            EvidenceStatus.PASSED,
            EvidenceStatus.BLOCKED,
            EvidenceStatus.INCONCLUSIVE,
        ),
    )
    review = _review(
        actors,
        ledger,
        policy,
    )
    finding = review.require_finding(
        failed_test.record_id
    )

    assert finding.outcome is (
        EvidenceAdmissionOutcome.EXCLUDED
    )
    assert finding.reasons == (
        EvidenceAdmissionReason.STATUS_NOT_ALLOWED,
    )
    assert ledger.require_record(
        failed_test.record_id
    ) == failed_test


def test_admission_reviewer_requires_accountable_service_or_system() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    ledger = _ledger(
        actors,
        observation,
    )
    evaluator = EvidenceAdmissionEvaluator(
        actor_registry=actors.registry,
        evidence_ledger=ledger,
        policy=_policy(actors),
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        evaluator.review(
            key="human-reviewer-attempt",
            reviewed_at=UtcTimestamp.parse(
                "2026-07-15T23:11:00Z"
            ),
            reviewed_by_id=actors.human.actor_id,
        )


def test_admission_review_rejects_registry_mismatch() -> None:
    actors = _actors()
    different_actors = _actors(
        key="different-admission-actors"
    )
    observation = _observation(
        actors
    )
    ledger = _ledger(
        actors,
        observation,
    )

    with pytest.raises(
        FoundationError,
        match="evidence ledger is not bound",
    ):
        EvidenceAdmissionEvaluator(
            actor_registry=different_actors.registry,
            evidence_ledger=ledger,
            policy=_policy(
                different_actors
            ),
        )


def test_admitted_records_reject_different_ledger() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    ledger = _ledger(
        actors,
        observation,
    )
    review = _review(
        actors,
        ledger,
        _policy(actors),
    )
    different_ledger = EvidenceLedger.create(
        key="different-admission-evidence",
        created_at=ledger.created_at,
        producer_id=actors.evidence_service.actor_id,
        actor_registry=actors.registry,
        records=(),
    )

    with pytest.raises(
        FoundationError,
        match="not bound to the supplied evidence ledger",
    ):
        review.admitted_records(
            evidence_ledger=different_ledger
        )


def test_review_findings_are_deterministic_across_input_order() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    test_result = _test_result(
        actors
    )
    first_ledger = _ledger(
        actors,
        observation,
        test_result,
        key="stable-admission-evidence",
    )
    second_ledger = _ledger(
        actors,
        test_result,
        observation,
        key="stable-admission-evidence",
    )
    policy = _policy(
        actors
    )

    first = _review(
        actors,
        first_ledger,
        policy,
    )
    second = _review(
        actors,
        second_ledger,
        policy,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
