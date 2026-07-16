"""Tests for catalog-wide current claim posture snapshots."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimCatalog,
    ClaimCriticality,
    ClaimEvidenceRequirement,
    ClaimKind,
    ClaimPostureSnapshot,
    ClaimPostureSource,
    ClaimPostureStatus,
    ClaimResolutionHistory,
    ClaimResolutionHistoryEntry,
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
        {
            "key": key,
        },
        domain=domain,
    )


@dataclass(frozen=True, slots=True)
class _Runtime:
    owner: ActorIdentity
    reviewer: ActorIdentity
    claim_service: ActorIdentity
    history_service: ActorIdentity
    posture_system: ActorIdentity
    registry: ActorRegistry
    supported_claim: ClaimSpecification
    adverse_claim: ClaimSpecification
    incomplete_claim: ClaimSpecification
    unevaluated_claim: ClaimSpecification
    catalog: ClaimCatalog


def _requirement(
    key: str,
) -> ClaimEvidenceRequirement:
    return ClaimEvidenceRequirement.create(
        key=key,
        summary=(
            "Provide direct admitted evidence for "
            "the bounded claim."
        ),
        acceptable_kinds=(
            EvidenceKind.MEASUREMENT,
            EvidenceKind.TEST_RESULT,
        ),
        minimum_records=1,
        require_primary_evidence=True,
        require_subject_match=True,
        require_independent_producers=False,
        falsification_conditions=(
            "Any relevant admitted test reports failure.",
        ),
    )


def _claim(
    *,
    key: str,
    statement: str,
    subject_key: str,
    authored_by_id: ScopedIdentifier,
    actor_registry: ActorRegistry,
) -> ClaimSpecification:
    return ClaimSpecification.create(
        key=key,
        created_at=UtcTimestamp.parse(
            "2026-07-16T07:05:00Z"
        ),
        authored_by_id=authored_by_id,
        kind=ClaimKind.CAPABILITY,
        criticality=ClaimCriticality.MODERATE,
        review_level=ClaimReviewLevel.HUMAN_REVIEW,
        statement=statement,
        scope={
            "environment": "isolated",
            "subject": subject_key,
        },
        subject_ids=(
            _identifier(
                "system",
                subject_key,
            ),
        ),
        evidence_requirements=(
            _requirement(
                f"{key}-requirement"
            ),
        ),
        limitations=(
            "The claim applies only to the evaluated scope.",
        ),
        prohibited_interpretations=(
            "Do not interpret this claim as certification.",
            "Do not interpret this claim as execution authority.",
        ),
        actor_registry=actor_registry,
    )


def _runtime(
    *,
    catalog_key: str = "claim-posture-catalog",
) -> _Runtime:
    owner = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="claim-owner",
        display_name="Claim Owner",
    )
    reviewer = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="independent-reviewer",
        display_name="Independent Reviewer",
    )
    claim_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-service",
        display_name="Claim Service",
        accountability_owner_id=owner.actor_id,
    )
    history_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-history-service",
        display_name="Claim History Service",
        accountability_owner_id=reviewer.actor_id,
    )
    posture_system = ActorIdentity.create(
        kind=ActorKind.SYSTEM,
        key="claim-posture-system",
        display_name="Claim Posture System",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key="claim-posture-actors",
        created_at=UtcTimestamp.parse(
            "2026-07-16T07:00:00Z"
        ),
        producer_id=reviewer.actor_id,
        actors=(
            owner,
            reviewer,
            claim_service,
            history_service,
            posture_system,
        ),
    )

    supported_claim = _claim(
        key="supported-runtime",
        statement=(
            "The supported runtime completed "
            "the declared bounded operation."
        ),
        subject_key="supported-runtime",
        authored_by_id=claim_service.actor_id,
        actor_registry=registry,
    )
    adverse_claim = _claim(
        key="adverse-runtime",
        statement=(
            "The adverse runtime maintained "
            "the declared operational boundary."
        ),
        subject_key="adverse-runtime",
        authored_by_id=claim_service.actor_id,
        actor_registry=registry,
    )
    incomplete_claim = _claim(
        key="incomplete-runtime",
        statement=(
            "The incomplete runtime satisfies "
            "the declared evidence obligation."
        ),
        subject_key="incomplete-runtime",
        authored_by_id=claim_service.actor_id,
        actor_registry=registry,
    )
    unevaluated_claim = _claim(
        key="unevaluated-runtime",
        statement=(
            "The unevaluated runtime can perform "
            "the declared bounded operation."
        ),
        subject_key="unevaluated-runtime",
        authored_by_id=claim_service.actor_id,
        actor_registry=registry,
    )
    catalog = ClaimCatalog.create(
        key=catalog_key,
        created_at=UtcTimestamp.parse(
            "2026-07-16T07:06:00Z"
        ),
        producer_id=claim_service.actor_id,
        actor_registry=registry,
        claims=(
            supported_claim,
            adverse_claim,
            incomplete_claim,
            unevaluated_claim,
        ),
    )

    return _Runtime(
        owner=owner,
        reviewer=reviewer,
        claim_service=claim_service,
        history_service=history_service,
        posture_system=posture_system,
        registry=registry,
        supported_claim=supported_claim,
        adverse_claim=adverse_claim,
        incomplete_claim=incomplete_claim,
        unevaluated_claim=unevaluated_claim,
        catalog=catalog,
    )


def _entry(
    runtime: _Runtime,
    claim: ClaimSpecification,
    *,
    key: str,
    evaluated_at: str,
    resolved_at: str,
    recorded_at: str,
    status: ClaimResolutionStatus,
) -> ClaimResolutionHistoryEntry:
    source = (
        ClaimResolutionSource.HUMAN_ADJUDICATION
        if status in {
            ClaimResolutionStatus.SUPPORTED,
            ClaimResolutionStatus.NOT_SUPPORTED,
            ClaimResolutionStatus.DEFERRED,
        }
        else ClaimResolutionSource.EVIDENCE_EVALUATION
    )

    return ClaimResolutionHistoryEntry(
        entry_id=_identifier(
            "claim-resolution-history-entry",
            key,
        ),
        recorded_at=UtcTimestamp.parse(
            recorded_at
        ),
        claim_id=claim.claim_id,
        evaluation_id=_identifier(
            "claim-evidence-evaluation",
            f"{key}-evaluation",
        ),
        evaluation_evaluated_at=UtcTimestamp.parse(
            evaluated_at
        ),
        resolution_id=_identifier(
            "claim-resolution",
            f"{key}-resolution",
        ),
        resolution_resolved_at=UtcTimestamp.parse(
            resolved_at
        ),
        status=status,
        source=source,
        claim_digest=claim.digest(),
        evaluation_digest=_digest(
            "claim-evidence-evaluation",
            key,
        ),
        resolution_digest=_digest(
            "claim-resolution",
            key,
        ),
        claim_catalog_digest=runtime.catalog.digest(),
        decision_ledger_digest=_digest(
            "claim-adjudication-decision-ledger",
            key,
        ),
        resolution_snapshot_digest=_digest(
            "evidence-admission-resolution-snapshot",
            key,
        ),
        evidence_ledger_digest=_digest(
            "evidence-ledger",
            key,
        ),
        actor_registry_digest=runtime.registry.digest(),
    )


def _history(
    runtime: _Runtime,
    *entries: ClaimResolutionHistoryEntry,
    key: str = "claim-posture-history",
    created_at: str = "2026-07-16T07:20:00Z",
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


def _standard_history(
    runtime: _Runtime,
) -> ClaimResolutionHistory:
    supported = _entry(
        runtime,
        runtime.supported_claim,
        key="current-supported",
        evaluated_at="2026-07-16T07:08:00Z",
        resolved_at="2026-07-16T07:09:00Z",
        recorded_at="2026-07-16T07:10:00Z",
        status=ClaimResolutionStatus.SUPPORTED,
    )
    old_adverse_support = _entry(
        runtime,
        runtime.adverse_claim,
        key="old-adverse-support",
        evaluated_at="2026-07-16T07:08:30Z",
        resolved_at="2026-07-16T07:09:30Z",
        recorded_at="2026-07-16T07:10:30Z",
        status=ClaimResolutionStatus.SUPPORTED,
    )
    current_adverse = _entry(
        runtime,
        runtime.adverse_claim,
        key="current-adverse-falsification",
        evaluated_at="2026-07-16T07:12:00Z",
        resolved_at="2026-07-16T07:13:00Z",
        recorded_at="2026-07-16T07:14:00Z",
        status=ClaimResolutionStatus.FALSIFICATION_SIGNAL,
    )
    incomplete = _entry(
        runtime,
        runtime.incomplete_claim,
        key="current-incomplete",
        evaluated_at="2026-07-16T07:11:00Z",
        resolved_at="2026-07-16T07:12:00Z",
        recorded_at="2026-07-16T07:13:00Z",
        status=ClaimResolutionStatus.INCOMPLETE_EVIDENCE,
    )

    return _history(
        runtime,
        current_adverse,
        supported,
        incomplete,
        old_adverse_support,
    )


def _snapshot(
    runtime: _Runtime,
    history: ClaimResolutionHistory,
    *,
    captured_at: str = "2026-07-16T07:21:00Z",
) -> ClaimPostureSnapshot:
    return ClaimPostureSnapshot.create(
        key="current-claim-postures",
        captured_at=UtcTimestamp.parse(
            captured_at
        ),
        produced_by_id=runtime.posture_system.actor_id,
        claim_catalog=runtime.catalog,
        history=history,
        actor_registry=runtime.registry,
    )


def test_snapshot_includes_supported_adverse_incomplete_and_unevaluated_claims() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _standard_history(runtime),
    )

    supported = snapshot.require_posture(
        runtime.supported_claim.claim_id
    )
    adverse = snapshot.require_posture(
        runtime.adverse_claim.claim_id
    )
    incomplete = snapshot.require_posture(
        runtime.incomplete_claim.claim_id
    )
    unevaluated = snapshot.require_posture(
        runtime.unevaluated_claim.claim_id
    )

    assert supported.status is ClaimPostureStatus.SUPPORTED
    assert supported.source is (
        ClaimPostureSource.RESOLUTION_HISTORY
    )
    assert supported.is_supported is True
    assert supported.requires_human_attention is False

    assert adverse.status is (
        ClaimPostureStatus.FALSIFICATION_SIGNAL
    )
    assert adverse.is_supported is False
    assert adverse.has_adverse_signal is True
    assert adverse.requires_human_attention is True

    assert incomplete.status is (
        ClaimPostureStatus.INCOMPLETE_EVIDENCE
    )
    assert incomplete.requires_human_attention is True

    assert unevaluated.status is (
        ClaimPostureStatus.UNEVALUATED
    )
    assert unevaluated.source is (
        ClaimPostureSource.NO_RESOLUTION
    )
    assert unevaluated.current_evaluation_id is None
    assert unevaluated.current_resolution_id is None


def test_newer_falsification_supersedes_older_support() -> None:
    runtime = _runtime()
    history = _standard_history(
        runtime
    )
    snapshot = _snapshot(
        runtime,
        history,
    )
    posture = snapshot.require_posture(
        runtime.adverse_claim.claim_id
    )
    current = history.require_current_for_claim(
        runtime.adverse_claim.claim_id
    )

    assert current.status is (
        ClaimResolutionStatus.FALSIFICATION_SIGNAL
    )
    assert posture.current_history_entry_id == current.entry_id
    assert posture.current_history_entry_digest == current.digest()
    assert posture.status is (
        ClaimPostureStatus.FALSIFICATION_SIGNAL
    )
    assert posture.is_supported is False


def test_snapshot_counts_and_filters_current_postures() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _standard_history(runtime),
    )

    assert snapshot.total_count == 4
    assert snapshot.supported_count == 1
    assert snapshot.adverse_count == 1
    assert snapshot.attention_count == 3
    assert snapshot.unevaluated_count == 1
    assert snapshot.all_claims_currently_supported is False

    assert snapshot.supported_postures() == (
        snapshot.require_posture(
            runtime.supported_claim.claim_id
        ),
    )
    assert snapshot.adverse_postures() == (
        snapshot.require_posture(
            runtime.adverse_claim.claim_id
        ),
    )
    assert set(
        posture.claim_id
        for posture in snapshot.attention_postures()
    ) == {
        runtime.adverse_claim.claim_id,
        runtime.incomplete_claim.claim_id,
        runtime.unevaluated_claim.claim_id,
    }
    assert snapshot.unevaluated_postures() == (
        snapshot.require_posture(
            runtime.unevaluated_claim.claim_id
        ),
    )


def test_snapshot_is_non_certifying_and_non_authorizing() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _standard_history(runtime),
    )

    assert snapshot.establishes_absolute_truth is False
    assert snapshot.grants_authority is False
    assert snapshot.claims_certification is False
    assert snapshot.digest().verifies(
        snapshot.canonical_payload()
    ) is True

    for posture in snapshot.postures:
        assert posture.establishes_absolute_truth is False
        assert posture.grants_authority is False
        assert posture.claims_certification is False


def test_empty_history_marks_every_catalog_claim_unevaluated() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _history(runtime),
    )

    assert snapshot.total_count == 4
    assert snapshot.supported_count == 0
    assert snapshot.adverse_count == 0
    assert snapshot.attention_count == 4
    assert snapshot.unevaluated_count == 4
    assert snapshot.all_claims_currently_supported is False
    assert all(
        posture.status is ClaimPostureStatus.UNEVALUATED
        for posture in snapshot.postures
    )


def test_snapshot_rejects_different_claim_catalog_binding() -> None:
    runtime = _runtime()
    history = _standard_history(
        runtime
    )
    different_catalog = ClaimCatalog.create(
        key="different-claim-posture-catalog",
        created_at=runtime.catalog.created_at,
        producer_id=runtime.claim_service.actor_id,
        actor_registry=runtime.registry,
        claims=runtime.catalog.claims,
    )

    with pytest.raises(
        FoundationError,
        match="references a different claim catalog",
    ):
        ClaimPostureSnapshot.create(
            key="mismatched-posture-snapshot",
            captured_at=UtcTimestamp.parse(
                "2026-07-16T07:21:00Z"
            ),
            produced_by_id=runtime.posture_system.actor_id,
            claim_catalog=different_catalog,
            history=history,
            actor_registry=runtime.registry,
        )


def test_snapshot_rejects_history_claim_absent_from_catalog() -> None:
    runtime = _runtime()
    foreign_claim_id = _identifier(
        "claim",
        "foreign-claim",
    )
    malformed_entry = replace(
        _entry(
            runtime,
            runtime.supported_claim,
            key="foreign-history-entry",
            evaluated_at="2026-07-16T07:08:00Z",
            resolved_at="2026-07-16T07:09:00Z",
            recorded_at="2026-07-16T07:10:00Z",
            status=ClaimResolutionStatus.SUPPORTED,
        ),
        claim_id=foreign_claim_id,
    )
    history = _history(
        runtime,
        malformed_entry,
    )

    with pytest.raises(
        FoundationError,
        match="claim absent from the supplied claim catalog",
    ):
        _snapshot(
            runtime,
            history,
        )


def test_snapshot_rejects_human_or_unaccountable_producer() -> None:
    runtime = _runtime()
    history = _standard_history(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="service or system actor",
    ):
        ClaimPostureSnapshot.create(
            key="human-produced-posture",
            captured_at=UtcTimestamp.parse(
                "2026-07-16T07:21:00Z"
            ),
            produced_by_id=runtime.reviewer.actor_id,
            claim_catalog=runtime.catalog,
            history=history,
            actor_registry=runtime.registry,
        )

    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-posture-service",
        display_name="Unowned Posture Service",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-claim-posture-actors",
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
        ClaimPostureSnapshot.create(
            key="unowned-produced-posture",
            captured_at=UtcTimestamp.parse(
                "2026-07-16T07:21:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            claim_catalog=runtime.catalog,
            history=history,
            actor_registry=expanded_registry,
        )


def test_snapshot_must_not_predate_claim_history() -> None:
    runtime = _runtime()
    history = _standard_history(
        runtime
    )

    with pytest.raises(
        FoundationError,
        match="must not predate the claim history",
    ):
        _snapshot(
            runtime,
            history,
            captured_at="2026-07-16T07:19:59Z",
        )


def test_snapshot_rejects_duplicate_claim_posture() -> None:
    runtime = _runtime()
    snapshot = _snapshot(
        runtime,
        _standard_history(runtime),
    )
    duplicate = replace(
        snapshot.postures[0],
        posture_id=_identifier(
            "claim-posture",
            "duplicate-posture",
        ),
    )

    with pytest.raises(
        FoundationError,
        match="one posture per claim",
    ):
        replace(
            snapshot,
            postures=(
                *snapshot.postures,
                duplicate,
            ),
        )


def test_snapshot_is_deterministic_across_history_input_order() -> None:
    runtime = _runtime()
    first_history = _standard_history(
        runtime
    )
    second_history = _history(
        runtime,
        *reversed(first_history.entries),
    )

    first = _snapshot(
        runtime,
        first_history,
    )
    second = _snapshot(
        runtime,
        second_history,
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
