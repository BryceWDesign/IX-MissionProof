"""Tests for bounded claim specifications and evidence obligations."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.claims import (
    ClaimCatalog,
    ClaimCriticality,
    ClaimEvidenceRequirement,
    ClaimKind,
    ClaimReviewLevel,
    ClaimSpecification,
)
from ix_missionproof.evidence import EvidenceKind
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    ActorStatus,
    CanonicalJsonDocument,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _id(namespace: str, key: str) -> ScopedIdentifier:
    return ScopedIdentifier.create(namespace=namespace, key=key)


@dataclass(frozen=True, slots=True)
class _Actors:
    owner: ActorIdentity
    reviewer: ActorIdentity
    agent: ActorIdentity
    service: ActorIdentity
    registry: ActorRegistry


def _actors(key: str = "claim-actors") -> _Actors:
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
    agent = ActorIdentity.create(
        kind=ActorKind.AGENT,
        key="claim-agent",
        display_name="Claim Agent",
        accountability_owner_id=owner.actor_id,
    )
    service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="claim-catalog-service",
        display_name="Claim Catalog Service",
        accountability_owner_id=reviewer.actor_id,
    )
    registry = ActorRegistry.create(
        key=key,
        created_at=UtcTimestamp.parse("2026-07-16T02:00:00Z"),
        producer_id=reviewer.actor_id,
        actors=(owner, reviewer, agent, service),
    )
    return _Actors(owner, reviewer, agent, service, registry)


def _requirement(
    key: str = "bounded-execution-evidence",
    *,
    minimum_records: int = 2,
) -> ClaimEvidenceRequirement:
    return ClaimEvidenceRequirement.create(
        key=key,
        summary="Provide direct execution and test evidence for the bounded target.",
        acceptable_kinds=(EvidenceKind.EXECUTION_RECEIPT, EvidenceKind.TEST_RESULT),
        minimum_records=minimum_records,
        require_primary_evidence=True,
        require_subject_match=True,
        require_independent_producers=True,
        falsification_conditions=(
            "Any execution occurs outside the declared target scope.",
            "Any required test reports a failed or blocked outcome.",
        ),
    )


def _claim(
    actors: _Actors,
    *,
    key: str = "bounded-test-execution",
    author: ScopedIdentifier | None = None,
    kind: ClaimKind = ClaimKind.CAPABILITY,
    criticality: ClaimCriticality = ClaimCriticality.MODERATE,
    review_level: ClaimReviewLevel = ClaimReviewLevel.HUMAN_REVIEW,
    requirements: tuple[ClaimEvidenceRequirement, ...] | None = None,
) -> ClaimSpecification:
    return ClaimSpecification.create(
        key=key,
        created_at=UtcTimestamp.parse("2026-07-16T02:05:00Z"),
        authored_by_id=author or actors.agent.actor_id,
        kind=kind,
        criticality=criticality,
        review_level=review_level,
        statement="The bounded service can run the declared unit-test target.",
        scope={
            "environment": "isolated",
            "target": "tests/unit",
            "tool": "test-runner",
        },
        subject_ids=(
            _id("system", "execution-service"),
            _id("bounded-tool", "test-runner"),
        ),
        evidence_requirements=requirements or (_requirement(),),
        assumptions=("The isolated workspace configuration remains unchanged.",),
        limitations=(
            "The claim applies only to the declared unit-test target.",
            "The claim does not establish production readiness.",
        ),
        prohibited_interpretations=(
            "Do not interpret this claim as certification.",
            "Do not interpret this claim as permission to execute.",
        ),
        actor_registry=actors.registry,
        labels=(" Capability ", "bounded", "capability"),
    )


def test_requirement_is_falsifiable_and_cannot_hide_adverse_evidence() -> None:
    requirement = _requirement()

    assert requirement.acceptable_kinds == (
        EvidenceKind.EXECUTION_RECEIPT,
        EvidenceKind.TEST_RESULT,
    )
    assert requirement.minimum_records == 2
    assert requirement.adverse_evidence_must_be_included is True
    assert requirement.establishes_claim is False
    assert requirement.digest().verifies(requirement.to_payload()) is True


def test_requirement_rejects_empty_kinds_counts_and_falsifiers() -> None:
    with pytest.raises(FoundationError, match="acceptable_kinds"):
        ClaimEvidenceRequirement.create(
            key="empty-kinds",
            summary="Invalid requirement.",
            acceptable_kinds=(),
            falsification_conditions=("A failure occurs.",),
        )
    with pytest.raises(FoundationError, match="at least 1"):
        _requirement(minimum_records=0)
    with pytest.raises(FoundationError, match="must be an integer"):
        _requirement(minimum_records=True)
    with pytest.raises(FoundationError, match="falsification_conditions"):
        ClaimEvidenceRequirement.create(
            key="no-falsifiers",
            summary="Invalid requirement.",
            acceptable_kinds=(EvidenceKind.TEST_RESULT,),
            falsification_conditions=(),
        )


def test_machine_authored_claim_preserves_accountability_and_boundaries() -> None:
    actors = _actors()
    claim = _claim(actors)

    assert claim.authored_by_id == actors.agent.actor_id
    assert claim.author_kind is ActorKind.AGENT
    assert claim.author_accountability_owner_id == actors.owner.actor_id
    assert claim.establishes_truth is False
    assert claim.grants_authority is False
    assert claim.claims_certification is False
    assert claim.labels == ("capability", "bounded")
    assert claim.digest().verifies(claim.to_payload()) is True


def test_human_authored_claim_has_no_accountability_owner() -> None:
    actors = _actors()
    claim = _claim(actors, key="human-claim", author=actors.owner.actor_id)

    assert claim.author_kind is ActorKind.HUMAN
    assert claim.author_accountability_owner_id is None


def test_inactive_actor_cannot_author_claim() -> None:
    actors = _actors()
    suspended = replace(actors.agent, status=ActorStatus.SUSPENDED)
    registry = ActorRegistry.create(
        key="suspended-claim-actors",
        created_at=actors.registry.created_at,
        producer_id=actors.reviewer.actor_id,
        actors=(actors.owner, actors.reviewer, suspended, actors.service),
    )

    with pytest.raises(FoundationError, match="claim author must be an active actor"):
        ClaimSpecification.create(
            key="invalid-author",
            created_at=UtcTimestamp.parse("2026-07-16T02:05:00Z"),
            authored_by_id=suspended.actor_id,
            kind=ClaimKind.CAPABILITY,
            criticality=ClaimCriticality.MODERATE,
            review_level=ClaimReviewLevel.HUMAN_REVIEW,
            statement="Invalid claim.",
            scope={"target": "tests/unit"},
            subject_ids=(_id("system", "execution-service"),),
            evidence_requirements=(_requirement(),),
            limitations=("Invalid.",),
            prohibited_interpretations=("Do not use.",),
            actor_registry=registry,
        )


def test_claim_requires_scope_subjects_requirements_limits_and_boundaries() -> None:
    base = _claim(_actors())

    with pytest.raises(FoundationError, match="scope"):
        replace(base, scope=CanonicalJsonDocument.from_value({}))
    with pytest.raises(FoundationError, match="subject_ids"):
        replace(base, subject_ids=())
    with pytest.raises(FoundationError, match="require evidence requirements"):
        replace(base, evidence_requirements=())
    with pytest.raises(FoundationError, match="limitations"):
        replace(base, limitations=())
    with pytest.raises(FoundationError, match="prohibited_interpretations"):
        replace(base, prohibited_interpretations=())


def test_equivalent_requirements_cannot_be_duplicated_under_new_ids() -> None:
    actors = _actors()
    first = _requirement("first-requirement")
    second = _requirement("second-requirement")

    assert first.requirement_id != second.requirement_id
    assert first.semantic_digest() == second.semantic_digest()
    with pytest.raises(FoundationError, match="equivalent evidence requirements"):
        _claim(actors, requirements=(first, second))


def test_high_consequence_and_sensitive_claims_require_independent_review() -> None:
    actors = _actors()

    with pytest.raises(FoundationError, match="independent human review"):
        _claim(actors, criticality=ClaimCriticality.HIGH)

    for kind in (
        ClaimKind.SAFETY,
        ClaimKind.SECURITY,
        ClaimKind.COMPLIANCE,
        ClaimKind.READINESS,
    ):
        with pytest.raises(FoundationError, match="independent human review"):
            _claim(actors, key=f"{kind.value}-claim", kind=kind)

    claim = _claim(
        actors,
        key="critical-safety-claim",
        kind=ClaimKind.SAFETY,
        criticality=ClaimCriticality.CRITICAL,
        review_level=ClaimReviewLevel.INDEPENDENT_HUMAN_REVIEW,
    )
    assert claim.requires_independent_review is True


def test_semantic_digest_ignores_claim_identity_and_author_metadata() -> None:
    actors = _actors()
    machine = _claim(actors, key="machine-claim")
    human = _claim(actors, key="human-claim", author=actors.owner.actor_id)

    assert machine.digest() != human.digest()
    assert machine.semantic_digest() == human.semantic_digest()


def test_catalog_rejects_semantic_duplicates() -> None:
    actors = _actors()
    machine = _claim(actors, key="machine-claim")
    human = _claim(actors, key="human-claim", author=actors.owner.actor_id)

    with pytest.raises(FoundationError, match="semantically duplicate claims"):
        ClaimCatalog.create(
            key="duplicate-catalog",
            created_at=UtcTimestamp.parse("2026-07-16T02:10:00Z"),
            producer_id=actors.service.actor_id,
            actor_registry=actors.registry,
            claims=(machine, human),
        )


def test_catalog_filters_claims_without_establishing_truth_or_authority() -> None:
    actors = _actors()
    capability = _claim(actors, key="capability-claim")
    safety = _claim(
        actors,
        key="safety-claim",
        kind=ClaimKind.SAFETY,
        criticality=ClaimCriticality.CRITICAL,
        review_level=ClaimReviewLevel.INDEPENDENT_HUMAN_REVIEW,
    )
    catalog = ClaimCatalog.create(
        key="bounded-claims",
        created_at=UtcTimestamp.parse("2026-07-16T02:10:00Z"),
        producer_id=actors.service.actor_id,
        actor_registry=actors.registry,
        claims=(safety, capability),
    )

    assert catalog.require_claim(capability.claim_id) == capability
    assert catalog.claims_by_kind(ClaimKind.SAFETY) == (safety,)
    assert catalog.high_consequence_claims() == (safety,)
    assert catalog.independent_review_claims() == (safety,)
    assert catalog.establishes_truth is False
    assert catalog.grants_authority is False
    assert catalog.digest().verifies(catalog.canonical_payload()) is True


def test_catalog_rejects_registry_mismatch_and_agent_producer() -> None:
    actors = _actors()
    different = _actors("different-claim-actors")
    claim = _claim(actors)

    with pytest.raises(FoundationError, match="same actor registry"):
        ClaimCatalog.create(
            key="mismatched-catalog",
            created_at=UtcTimestamp.parse("2026-07-16T02:10:00Z"),
            producer_id=different.service.actor_id,
            actor_registry=different.registry,
            claims=(claim,),
        )
    with pytest.raises(FoundationError, match="must be one of"):
        ClaimCatalog.create(
            key="agent-catalog",
            created_at=UtcTimestamp.parse("2026-07-16T02:10:00Z"),
            producer_id=actors.agent.actor_id,
            actor_registry=actors.registry,
            claims=(claim,),
        )


def test_catalog_is_deterministic_across_input_order() -> None:
    actors = _actors()
    capability = _claim(actors, key="stable-capability")
    provenance = _claim(actors, key="stable-provenance", kind=ClaimKind.PROVENANCE)
    created_at = UtcTimestamp.parse("2026-07-16T02:10:00Z")

    first = ClaimCatalog.create(
        key="stable-catalog",
        created_at=created_at,
        producer_id=actors.service.actor_id,
        actor_registry=actors.registry,
        claims=(capability, provenance),
    )
    second = ClaimCatalog.create(
        key="stable-catalog",
        created_at=created_at,
        producer_id=actors.service.actor_id,
        actor_registry=actors.registry,
        claims=(provenance, capability),
    )

    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()
