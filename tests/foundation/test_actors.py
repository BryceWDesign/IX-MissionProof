"""Tests for canonical actor identities and registry snapshots."""

import pytest

from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    ActorStatus,
    CanonicalKey,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _human(
    key: str = "reviewer-01",
    *,
    status: ActorStatus = ActorStatus.ACTIVE,
) -> ActorIdentity:
    return ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key=key,
        display_name="Mission Reviewer",
        status=status,
        roles=("human reviewer", "governance authority"),
        organization="IX Research",
    )


def _model(
    owner_id: ScopedIdentifier | None,
    *,
    key: str = "planner-01",
) -> ActorIdentity:
    return ActorIdentity.create(
        kind=ActorKind.MODEL,
        key=key,
        display_name="Planning Model",
        roles=("proposal author", "plan generator", "proposal author"),
        accountability_owner_id=owner_id,
    )


def test_actor_identity_derives_namespace_from_kind() -> None:
    actor = _model(_human().actor_id)

    assert str(actor.actor_id) == "model:planner-01"
    assert actor.kind is ActorKind.MODEL
    assert actor.is_machine is True
    assert actor.is_human is False
    assert actor.is_eligible_for_human_authority is False
    assert actor.has_accountability_owner is True
    assert actor.roles == (
        CanonicalKey("proposal-author"),
        CanonicalKey("plan-generator"),
    )


def test_human_identity_is_only_eligible_not_automatically_authorized() -> None:
    human = _human()

    assert human.is_human is True
    assert human.is_machine is False
    assert human.is_eligible_for_human_authority is True
    assert human.has_role("human reviewer") is True


def test_suspended_human_is_not_eligible_for_human_authority() -> None:
    human = _human(status=ActorStatus.SUSPENDED)

    assert human.is_active is False
    assert human.is_eligible_for_human_authority is False


def test_actor_identity_normalizes_display_and_organization_text() -> None:
    actor = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="evidence-service",
        display_name="  Evidence   Service ",
        organization="  IX   Research ",
    )

    assert actor.display_name == "Evidence Service"
    assert actor.organization == "IX Research"


def test_actor_identity_rejects_namespace_kind_mismatch() -> None:
    with pytest.raises(
        FoundationError,
        match="actor_id namespace must match the actor kind",
    ):
        ActorIdentity(
            actor_id=ScopedIdentifier.create(
                namespace="system",
                key="planner-01",
            ),
            kind=ActorKind.MODEL,
            display_name="Planning Model",
        )


def test_actor_identity_rejects_nonhuman_accountability_owner() -> None:
    with pytest.raises(
        FoundationError,
        match="must identify a human actor",
    ):
        ActorIdentity.create(
            kind=ActorKind.AGENT,
            key="agent-01",
            display_name="Governed Agent",
            accountability_owner_id=ScopedIdentifier.create(
                namespace="organization",
                key="ix-research",
            ),
        )


def test_human_identity_rejects_delegated_identity_accountability() -> None:
    with pytest.raises(
        FoundationError,
        match="human actors must not delegate",
    ):
        ActorIdentity.create(
            kind=ActorKind.HUMAN,
            key="reviewer-02",
            display_name="Second Reviewer",
            accountability_owner_id=_human().actor_id,
        )


def test_actor_identity_payload_and_digest_are_deterministic() -> None:
    owner = _human()
    actor = _model(owner.actor_id)

    assert actor.to_payload() == {
        "accountability_owner_id": "human:reviewer-01",
        "actor_id": "model:planner-01",
        "display_name": "Planning Model",
        "kind": "model",
        "organization": None,
        "roles": [
            "proposal-author",
            "plan-generator",
        ],
        "schema": "actor-identity-v1",
        "status": "active",
    }
    assert actor.digest().verifies(actor.to_payload()) is True


def test_actor_registry_orders_and_resolves_actors() -> None:
    human = _human()
    model = _model(human.actor_id)
    policy = ActorIdentity.create(
        kind=ActorKind.POLICY,
        key="mission-policy",
        display_name="Mission Policy",
        accountability_owner_id=human.actor_id,
    )

    registry = ActorRegistry.create(
        key="initial-runtime",
        created_at=UtcTimestamp.parse("2026-07-15T12:00:00Z"),
        producer_id=ScopedIdentifier.create(
            namespace="build-system",
            key="missionproof-ci",
        ),
        actors=(policy, model, human),
    )

    assert tuple(str(actor.actor_id) for actor in registry.actors) == (
        "human:reviewer-01",
        "model:planner-01",
        "policy:mission-policy",
    )
    assert registry.actor_for(model.actor_id) == model
    assert registry.require_actor(human.actor_id) == human
    assert registry.machine_actors_without_accountability() == ()


def test_actor_registry_rejects_duplicate_actor_ids() -> None:
    human = _human()

    with pytest.raises(
        FoundationError,
        match="unique actor IDs",
    ):
        ActorRegistry.create(
            key="duplicate-registry",
            created_at=UtcTimestamp.parse("2026-07-15T12:05:00Z"),
            producer_id=human.actor_id,
            actors=(human, human),
        )


def test_actor_registry_rejects_unresolved_accountability_owner() -> None:
    external_human_id = ScopedIdentifier.create(
        namespace="human",
        key="missing-reviewer",
    )
    model = _model(external_human_id)

    with pytest.raises(
        FoundationError,
        match="unresolved accountability owner",
    ):
        ActorRegistry.create(
            key="unresolved-owner",
            created_at=UtcTimestamp.parse("2026-07-15T12:10:00Z"),
            producer_id=model.actor_id,
            actors=(model,),
        )


def test_actor_registry_rejects_inactive_accountability_owner() -> None:
    suspended_human = _human(status=ActorStatus.SUSPENDED)
    model = _model(suspended_human.actor_id)

    with pytest.raises(
        FoundationError,
        match="accountability owners must be active",
    ):
        ActorRegistry.create(
            key="inactive-owner",
            created_at=UtcTimestamp.parse("2026-07-15T12:15:00Z"),
            producer_id=model.actor_id,
            actors=(suspended_human, model),
        )


def test_actor_registry_reports_unassigned_machine_actors() -> None:
    human = _human()
    unassigned_model = _model(None)
    assigned_agent = ActorIdentity.create(
        kind=ActorKind.AGENT,
        key="review-agent",
        display_name="Review Agent",
        accountability_owner_id=human.actor_id,
    )
    organization = ActorIdentity.create(
        kind=ActorKind.ORGANIZATION,
        key="ix-research",
        display_name="IX Research",
    )

    registry = ActorRegistry.create(
        key="accountability-check",
        created_at=UtcTimestamp.parse("2026-07-15T12:20:00Z"),
        producer_id=human.actor_id,
        actors=(organization, assigned_agent, unassigned_model, human),
    )

    assert registry.machine_actors_without_accountability() == (
        unassigned_model,
    )


def test_actor_registry_digest_is_independent_of_input_order() -> None:
    human = _human()
    model = _model(human.actor_id)

    first = ActorRegistry.create(
        key="stable-registry",
        created_at=UtcTimestamp.parse("2026-07-15T12:25:00Z"),
        producer_id=human.actor_id,
        actors=(human, model),
    )
    second = ActorRegistry.create(
        key="stable-registry",
        created_at=UtcTimestamp.parse("2026-07-15T12:25:00Z"),
        producer_id=human.actor_id,
        actors=(model, human),
    )

    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()


def test_actor_registry_require_actor_fails_for_unknown_identity() -> None:
    registry = ActorRegistry.create(
        key="empty-registry",
        created_at=UtcTimestamp.parse("2026-07-15T12:30:00Z"),
        producer_id=ScopedIdentifier.create(
            namespace="build-system",
            key="missionproof-ci",
        ),
        actors=(),
    )

    with pytest.raises(
        FoundationError,
        match="does not contain actor",
    ):
        registry.require_actor(
            ScopedIdentifier.create(
                namespace="model",
                key="unknown-model",
            )
        )
