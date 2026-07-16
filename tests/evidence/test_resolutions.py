"""Tests for resolved evidence-admission snapshots."""

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
    EvidenceAdmissionResolutionSnapshot,
    EvidenceAdmissionResolutionSource,
    EvidenceAdmissionResolutionStatus,
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
class _ResolutionRuntime:
    owner: ActorIdentity
    reviewer: ActorIdentity
    sensor: ActorIdentity
    evidence_service: ActorIdentity
    admission_service: ActorIdentity
    resolution_service: ActorIdentity
    registry: ActorRegistry
    primary_record: EvidenceRecord
    asserted_record: EvidenceRecord
    invalidated_record: EvidenceRecord
    evidence_ledger: EvidenceLedger
    admission_review: EvidenceAdmissionReview


def _runtime() -> _ResolutionRuntime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="evidence-owner",
        display_name="Evidence Producer Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-reviewer",
        display_name="Independent Evidence Reviewer",
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
    resolution_service = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="admission-resolution-system",
        display_name="Admission Resolution System",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="resolution-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T01:00:00Z"
        ),
        producer_id=reviewer.actor_id,
        actors=(
            owner,
            reviewer,
            sensor,
            evidence_service,
            admission_service,
            resolution_service,
        ),
    )
    primary_record = EvidenceRecord.create(
        key="runtime-observation",
        created_at=UtcTimestamp.parse(
            "2026-07-16T01:02:00Z"
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
            "2026-07-16T01:03:00Z"
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
    invalidated_record = EvidenceRecord.create(
        key="invalidated-observation",
        created_at=UtcTimestamp.parse(
            "2026-07-16T01:04:00Z"
        ),
        produced_by_id=sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=EvidenceStatus.INVALIDATED,
        subject_ids=primary_record.subject_ids,
        summary="An invalidated runtime observation.",
        payload={
            "mode": "unknown",
        },
        actor_registry=registry,
    )
    evidence_ledger = EvidenceLedger.create(
        key="resolution-evidence",
        created_at=UtcTimestamp.parse(
            "2026-07-16T01:10:00Z"
        ),
        producer_id=evidence_service.actor_id,
        actor_registry=registry,
        records=(
            primary_record,
            asserted_record,
            invalidated_record,
        ),
    )
    policy = EvidenceAdmissionPolicy.create(
        key="resolution-policy",
        created_at=UtcTimestamp.parse(
            "2026-07-16T01:01:00Z"
        ),
        authored_by_id=reviewer.actor_id,
        summary=(
            "Require human review for asserted evidence "
            "and exclude invalidated evidence."
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
        key="resolution-review",
        reviewed_at=UtcTimestamp.parse(
            "2026-07-16T01:11:00Z"
        ),
        reviewed_by_id=admission_service.actor_id,
    )

    return _ResolutionRuntime(
        owner=owner,
        reviewer=reviewer,
        sensor=sensor,
        evidence_service=evidence_service,
        admission_service=admission_service,
        resolution_service=resolution_service,
        registry=registry,
        primary_record=primary_record,
        asserted_record=asserted_record,
        invalidated_record=invalidated_record,
        evidence_ledger=evidence_ledger,
        admission_review=admission_review,
    )


def _decision(
    runtime: _ResolutionRuntime,
    *,
    status: EvidenceAdmissionDecisionStatus,
    key: str,
    decided_at: str = "2026-07-16T01:12:00Z",
) -> EvidenceAdmissionDecision:
    finding = runtime.admission_review.require_finding(
        runtime.asserted_record.record_id
    )

    return EvidenceAdmissionDecision.decide(
        key=key,
        decided_at=UtcTimestamp.parse(
            decided_at
        ),
        decided_by_id=runtime.reviewer.actor_id,
        status=status,
        rationale=f"Human admission decision: {status.value}.",
        supporting_record_ids=(
            (
                runtime.primary_record.record_id,
            )
            if status is EvidenceAdmissionDecisionStatus.ADMIT
            else ()
        ),
        finding=finding,
        admission_review=runtime.admission_review,
        evidence_ledger=runtime.evidence_ledger,
        actor_registry=runtime.registry,
    )


def _decision_ledger(
    runtime: _ResolutionRuntime,
    *decisions: EvidenceAdmissionDecision,
    key: str = "resolution-decisions",
    created_at: str = "2026-07-16T01:13:00Z",
) -> EvidenceAdmissionDecisionLedger:
    return EvidenceAdmissionDecisionLedger.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        producer_id=runtime.admission_service.actor_id,
        admission_review=runtime.admission_review,
        actor_registry=runtime.registry,
        decisions=decisions,
    )


def _snapshot(
    runtime: _ResolutionRuntime,
    decision_ledger: EvidenceAdmissionDecisionLedger,
) -> EvidenceAdmissionResolutionSnapshot:
    return EvidenceAdmissionResolutionSnapshot.create(
        key="resolved-admission",
        resolved_at=UtcTimestamp.parse(
            "2026-07-16T01:14:00Z"
        ),
        produced_by_id=runtime.resolution_service.actor_id,
        admission_review=runtime.admission_review,
        decision_ledger=decision_ledger,
        evidence_ledger=runtime.evidence_ledger,
        actor_registry=runtime.registry,
    )


def test_complete_snapshot_separates_admitted_and_excluded_records() -> None:
    runtime = _runtime()
    admitted_decision = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="admit-asserted-record",
    )
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
            admitted_decision,
        ),
    )

    assert snapshot.status is (
        EvidenceAdmissionResolutionStatus.COMPLETE
    )
    assert snapshot.is_complete is True
    assert snapshot.requires_human_attention is False
    assert snapshot.total_count == 3
    assert snapshot.admitted_count == 2
    assert snapshot.excluded_count == 1
    assert snapshot.unresolved_count == 0
    assert snapshot.has_exclusions is True
    assert snapshot.establishes_claim is False

    assert snapshot.admitted_records(
        evidence_ledger=runtime.evidence_ledger,
    ) == (
        runtime.primary_record,
        runtime.asserted_record,
    )
    assert snapshot.excluded_records(
        evidence_ledger=runtime.evidence_ledger,
    ) == (
        runtime.invalidated_record,
    )
    assert snapshot.unresolved_records(
        evidence_ledger=runtime.evidence_ledger,
    ) == ()


def test_resolution_preserves_automated_and_human_authority_sources() -> None:
    runtime = _runtime()
    admitted_decision = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="human-admission",
    )
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
            admitted_decision,
        ),
    )

    primary = snapshot.require_resolution(
        runtime.primary_record.record_id
    )
    asserted = snapshot.require_resolution(
        runtime.asserted_record.record_id
    )
    invalidated = snapshot.require_resolution(
        runtime.invalidated_record.record_id
    )

    assert primary.source is (
        EvidenceAdmissionResolutionSource.AUTOMATED_POLICY
    )
    assert primary.outcome is EvidenceAdmissionOutcome.ADMITTED
    assert primary.decision_id is None

    assert asserted.source is (
        EvidenceAdmissionResolutionSource.HUMAN_DECISION
    )
    assert asserted.outcome is EvidenceAdmissionOutcome.ADMITTED
    assert asserted.decision_id == admitted_decision.decision_id
    assert asserted.decision_digest == admitted_decision.digest()

    assert invalidated.source is (
        EvidenceAdmissionResolutionSource.AUTOMATED_POLICY
    )
    assert invalidated.outcome is EvidenceAdmissionOutcome.EXCLUDED
    assert invalidated.decision_id is None


def test_missing_human_decision_keeps_review_open() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
        ),
    )
    resolution = snapshot.require_resolution(
        runtime.asserted_record.record_id
    )

    assert snapshot.status is (
        EvidenceAdmissionResolutionStatus.HUMAN_REVIEW_OPEN
    )
    assert snapshot.is_complete is False
    assert snapshot.requires_human_attention is True
    assert snapshot.unresolved_count == 1
    assert resolution.source is (
        EvidenceAdmissionResolutionSource.UNRESOLVED
    )
    assert resolution.outcome is (
        EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
    )
    assert resolution.decision_id is None
    assert snapshot.unresolved_records(
        evidence_ledger=runtime.evidence_ledger,
    ) == (
        runtime.asserted_record,
    )


def test_deferred_human_decision_keeps_review_open() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.DEFER,
        key="defer-asserted-record",
    )
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
            deferred,
        ),
    )
    resolution = snapshot.require_resolution(
        runtime.asserted_record.record_id
    )

    assert snapshot.requires_human_attention is True
    assert resolution.source is (
        EvidenceAdmissionResolutionSource.UNRESOLVED
    )
    assert resolution.decision_id == deferred.decision_id
    assert resolution.decision_status is (
        EvidenceAdmissionDecisionStatus.DEFER
    )
    assert resolution.decision_digest == deferred.digest()


def test_human_exclusion_completes_review_without_hiding_record() -> None:
    runtime = _runtime()
    excluded = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.EXCLUDE,
        key="exclude-asserted-record",
    )
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
            excluded,
        ),
    )
    resolution = snapshot.require_resolution(
        runtime.asserted_record.record_id
    )

    assert snapshot.is_complete is True
    assert snapshot.admitted_count == 1
    assert snapshot.excluded_count == 2
    assert resolution.source is (
        EvidenceAdmissionResolutionSource.HUMAN_DECISION
    )
    assert resolution.outcome is EvidenceAdmissionOutcome.EXCLUDED
    assert snapshot.excluded_records(
        evidence_ledger=runtime.evidence_ledger,
    ) == (
        runtime.asserted_record,
        runtime.invalidated_record,
    )


def test_automated_exclusion_remains_non_overridable() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
        ),
    )
    resolution = snapshot.require_resolution(
        runtime.invalidated_record.record_id
    )

    assert resolution.outcome is EvidenceAdmissionOutcome.EXCLUDED
    assert resolution.source is (
        EvidenceAdmissionResolutionSource.AUTOMATED_POLICY
    )
    assert resolution.decision_id is None


def test_snapshot_rejects_decision_for_unknown_finding() -> None:
    runtime = _runtime()
    admitted = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="valid-admission",
    )
    malformed = replace(
        admitted,
        finding_id=_identifier(
            "evidence-admission-finding",
            "unknown-finding",
        ),
    )
    malformed_ledger = _decision_ledger(
        runtime,
        malformed,
        key="malformed-resolution-decisions",
    )

    with pytest.raises(
        FoundationError,
        match="finding absent from the admission review",
    ):
        _snapshot(
            runtime,
            malformed_ledger,
        )


def test_snapshot_rejects_different_evidence_ledger() -> None:
    runtime = _runtime()
    decision_ledger = _decision_ledger(
        runtime,
    )
    different_ledger = EvidenceLedger.create(
        key="different-resolution-evidence",
        created_at=runtime.evidence_ledger.created_at,
        producer_id=runtime.evidence_service.actor_id,
        actor_registry=runtime.registry,
        records=(
            runtime.primary_record,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="admission review is not bound",
    ):
        EvidenceAdmissionResolutionSnapshot.create(
            key="mismatched-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T01:14:00Z"
            ),
            produced_by_id=runtime.resolution_service.actor_id,
            admission_review=runtime.admission_review,
            decision_ledger=decision_ledger,
            evidence_ledger=different_ledger,
            actor_registry=runtime.registry,
        )


def test_snapshot_rejects_unaccountable_or_human_producer() -> None:
    runtime = _runtime()
    decision_ledger = _decision_ledger(
        runtime,
    )
    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-resolution-service",
        display_name="Unowned Resolution Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-resolution-actors",
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
        EvidenceAdmissionResolutionSnapshot.create(
            key="unowned-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T01:14:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            admission_review=runtime.admission_review,
            decision_ledger=decision_ledger,
            evidence_ledger=runtime.evidence_ledger,
            actor_registry=expanded_registry,
        )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        EvidenceAdmissionResolutionSnapshot.create(
            key="human-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T01:14:00Z"
            ),
            produced_by_id=runtime.reviewer.actor_id,
            admission_review=runtime.admission_review,
            decision_ledger=decision_ledger,
            evidence_ledger=runtime.evidence_ledger,
            actor_registry=runtime.registry,
        )


def test_snapshot_must_not_predate_decision_ledger() -> None:
    runtime = _runtime()
    decision_ledger = _decision_ledger(
        runtime,
        created_at="2026-07-16T01:15:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the decision ledger",
    ):
        EvidenceAdmissionResolutionSnapshot.create(
            key="premature-resolution",
            resolved_at=UtcTimestamp.parse(
                "2026-07-16T01:14:00Z"
            ),
            produced_by_id=runtime.resolution_service.actor_id,
            admission_review=runtime.admission_review,
            decision_ledger=decision_ledger,
            evidence_ledger=runtime.evidence_ledger,
            actor_registry=runtime.registry,
        )


def test_record_queries_reject_unbound_evidence_ledger() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _decision_ledger(
            runtime,
        ),
    )
    different_ledger = EvidenceLedger.create(
        key="query-mismatch-evidence",
        created_at=runtime.evidence_ledger.created_at,
        producer_id=runtime.evidence_service.actor_id,
        actor_registry=runtime.registry,
        records=(),
    )

    with pytest.raises(
        FoundationError,
        match="not bound to the supplied evidence ledger",
    ):
        snapshot.admitted_records(
            evidence_ledger=different_ledger,
        )


def test_resolution_snapshot_is_deterministic() -> None:
    runtime = _runtime()
    deferred = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.DEFER,
        key="stable-deferral",
        decided_at="2026-07-16T01:12:00Z",
    )
    admitted = _decision(
        runtime,
        status=EvidenceAdmissionDecisionStatus.ADMIT,
        key="stable-admission",
        decided_at="2026-07-16T01:13:00Z",
    )
    first_ledger = _decision_ledger(
        runtime,
        deferred,
        admitted,
        key="stable-resolution-decisions",
        created_at="2026-07-16T01:13:00Z",
    )
    second_ledger = _decision_ledger(
        runtime,
        admitted,
        deferred,
        key="stable-resolution-decisions",
        created_at="2026-07-16T01:13:00Z",
    )

    first = _snapshot(
        runtime,
        first_ledger,
    )
    second = _snapshot(
        runtime,
        second_ledger,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
    assert first.digest().verifies(
        first.canonical_payload()
    ) is True
