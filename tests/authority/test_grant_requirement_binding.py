"""Tests for capability-controlled authority-grant requirements."""

from dataclasses import replace

import pytest

from ix_missionproof.authority import (
    AuthorityGrant,
    CapabilityCatalog,
    CapabilityDefinition,
    CapabilityOperation,
    CapabilityRiskTier,
)
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    CanonicalJsonDocument,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _identifier(namespace: str, key: str) -> ScopedIdentifier:
    return ScopedIdentifier.create(namespace=namespace, key=key)


def _grant_inputs(
    *,
    requires_separate_human_authorization: bool,
) -> tuple[
    ActorIdentity,
    ActorIdentity,
    ActorRegistry,
    CapabilityDefinition,
    CapabilityCatalog,
]:
    human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-01",
        display_name="Mission Reviewer",
        roles=("authority grantor",),
    )
    agent = ActorIdentity.create(
        kind=ActorKind.AGENT,
        key="bounded-agent",
        display_name="Bounded Agent",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key="grant-binding-actors",
        created_at=UtcTimestamp.parse("2026-07-15T15:00:00Z"),
        producer_id=human.actor_id,
        actors=(human, agent),
    )
    capability = CapabilityDefinition.create(
        key="execute-bounded-tool",
        operation=CapabilityOperation.EXECUTE,
        target_type="bounded tool",
        summary="Execute one exact bounded tool.",
        risk_tier=(
            CapabilityRiskTier.CRITICAL
            if requires_separate_human_authorization
            else CapabilityRiskTier.HIGH
        ),
        permitted_actor_kinds=(ActorKind.AGENT,),
        requires_separate_human_authorization=(
            requires_separate_human_authorization
        ),
    )
    catalog = CapabilityCatalog.create(
        key="grant-binding-capabilities",
        created_at=UtcTimestamp.parse("2026-07-15T15:00:00Z"),
        producer_id=human.actor_id,
        capabilities=(capability,),
    )
    return human, agent, registry, capability, catalog


def _issue(
    *,
    requires_separate_human_authorization: bool,
    constraints: dict[str, object] | None,
) -> AuthorityGrant:
    human, agent, registry, capability, catalog = _grant_inputs(
        requires_separate_human_authorization=(
            requires_separate_human_authorization
        )
    )

    return AuthorityGrant.issue(
        key="bound-requirement",
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=human.actor_id,
        issued_at=UtcTimestamp.parse("2026-07-15T15:05:00Z"),
        actor_registry=registry,
        capability_catalog=catalog,
        target_ids=(
            _identifier("bounded-tool", "test-runner"),
        ),
        supporting_record_ids=(
            _identifier("record", "review-evidence-0001"),
        ),
        constraints=constraints,
    )


def test_issue_inserts_capability_requirement_when_caller_omits_it() -> None:
    grant = _issue(
        requires_separate_human_authorization=True,
        constraints={"allowed_arguments": ["tests/unit"]},
    )

    assert grant.constraints.require_object() == {
        "allowed_arguments": ["tests/unit"],
        "requires_separate_human_authorization": True,
    }
    assert grant.capability_requires_separate_authorization is True
    assert grant.requires_runtime_authorization is True


def test_issue_records_false_requirement_when_capability_does_not_require_it() -> None:
    grant = _issue(
        requires_separate_human_authorization=False,
        constraints=None,
    )

    assert grant.constraints.require_object() == {
        "requires_separate_human_authorization": False,
    }
    assert grant.capability_requires_separate_authorization is False
    assert grant.requires_runtime_authorization is False


def test_caller_cannot_remove_required_separate_authorization() -> None:
    with pytest.raises(
        FoundationError,
        match="must not override the capability's separate human-authorization",
    ):
        _issue(
            requires_separate_human_authorization=True,
            constraints={
                "requires_separate_human_authorization": False,
            },
        )


def test_caller_cannot_invent_separate_authorization_requirement() -> None:
    with pytest.raises(
        FoundationError,
        match="must not override the capability's separate human-authorization",
    ):
        _issue(
            requires_separate_human_authorization=False,
            constraints={
                "requires_separate_human_authorization": True,
            },
        )


def test_authorization_requirement_must_be_boolean() -> None:
    with pytest.raises(
        FoundationError,
        match="constraint must be a boolean",
    ):
        _issue(
            requires_separate_human_authorization=True,
            constraints={
                "requires_separate_human_authorization": "yes",
            },
        )


def test_direct_grant_construction_cannot_drop_bound_requirement() -> None:
    grant = _issue(
        requires_separate_human_authorization=True,
        constraints=None,
    )

    with pytest.raises(
        FoundationError,
        match="constraints must contain a boolean",
    ):
        replace(
            grant,
            constraints=CanonicalJsonDocument.from_value({}),
        )
