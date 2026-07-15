"""Tests for canonical capability definitions and catalog snapshots."""

import pytest

from ix_missionproof.authority import (
    CapabilityCatalog,
    CapabilityDefinition,
    CapabilityOperation,
    CapabilityRiskTier,
)
from ix_missionproof.foundation import (
    ActorKind,
    CanonicalKey,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _producer_id() -> ScopedIdentifier:
    return ScopedIdentifier.create(
        namespace="build-system",
        key="missionproof-ci",
    )


def _observe_capability() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        key="observe-runtime-state",
        operation=CapabilityOperation.OBSERVE,
        target_type="runtime state",
        summary="Observe a bounded runtime-state snapshot.",
        risk_tier=CapabilityRiskTier.LOW,
        permitted_actor_kinds=(
            ActorKind.HUMAN,
            ActorKind.AGENT,
            ActorKind.SERVICE,
        ),
    )


def _execute_capability() -> CapabilityDefinition:
    return CapabilityDefinition.create(
        key="execute-bounded-tool",
        operation=CapabilityOperation.EXECUTE,
        target_type="bounded tool",
        summary="Execute one allowlisted tool under recorded authority.",
        risk_tier=CapabilityRiskTier.CRITICAL,
        permitted_actor_kinds=(
            ActorKind.AGENT,
            ActorKind.SERVICE,
        ),
        requires_separate_human_authorization=True,
    )


def test_capability_definition_normalizes_identity_and_actor_kinds() -> None:
    capability = CapabilityDefinition.create(
        key="  Read Evidence Bundle ",
        operation=CapabilityOperation.READ,
        target_type=" Evidence Bundle ",
        summary="  Read an existing   evidence bundle. ",
        risk_tier=CapabilityRiskTier.LOW,
        permitted_actor_kinds=(
            ActorKind.SERVICE,
            ActorKind.HUMAN,
            ActorKind.SERVICE,
        ),
    )

    assert str(capability.capability_id) == "capability:read-evidence-bundle"
    assert capability.target_type == CanonicalKey("evidence-bundle")
    assert capability.summary == "Read an existing evidence bundle."
    assert capability.permitted_actor_kinds == (
        ActorKind.HUMAN,
        ActorKind.SERVICE,
    )
    assert capability.human_only is False
    assert capability.is_machine_exercisable is True


def test_human_authority_operations_are_human_only() -> None:
    capability = CapabilityDefinition.create(
        key="authorize-consequential-action",
        operation=CapabilityOperation.AUTHORIZE_ACTION,
        target_type="consequential action",
        summary="Authorize one exact consequential action.",
        risk_tier=CapabilityRiskTier.CRITICAL,
        permitted_actor_kinds=(ActorKind.HUMAN,),
    )

    assert capability.human_only is True
    assert capability.is_machine_exercisable is False
    assert capability.requires_human_boundary is True
    assert capability.allows_actor_kind(ActorKind.HUMAN) is True
    assert capability.allows_actor_kind(ActorKind.AGENT) is False


def test_human_only_operation_rejects_machine_actor_kind() -> None:
    with pytest.raises(
        FoundationError,
        match="must be restricted to human actors",
    ):
        CapabilityDefinition.create(
            key="machine-authorization",
            operation=CapabilityOperation.AUTHORIZE_ACTION,
            target_type="consequential action",
            summary="Invalid machine authorization capability.",
            risk_tier=CapabilityRiskTier.CRITICAL,
            permitted_actor_kinds=(
                ActorKind.HUMAN,
                ActorKind.AGENT,
            ),
            requires_separate_human_authorization=True,
        )


def test_organization_cannot_directly_exercise_capability() -> None:
    with pytest.raises(
        FoundationError,
        match="organization cannot directly exercise capabilities",
    ):
        CapabilityDefinition.create(
            key="organization-observation",
            operation=CapabilityOperation.OBSERVE,
            target_type="runtime state",
            summary="Invalid organization-held capability.",
            risk_tier=CapabilityRiskTier.LOW,
            permitted_actor_kinds=(ActorKind.ORGANIZATION,),
        )


def test_high_risk_capability_requires_evidence() -> None:
    with pytest.raises(
        FoundationError,
        match="must require evidence",
    ):
        CapabilityDefinition.create(
            key="unrecorded-secret-access",
            operation=CapabilityOperation.ACCESS_SECRET,
            target_type="secret",
            summary="Access a secret without evidence.",
            risk_tier=CapabilityRiskTier.HIGH,
            permitted_actor_kinds=(ActorKind.SERVICE,),
            requires_evidence=False,
        )


def test_irreversible_capability_requires_human_authorization() -> None:
    with pytest.raises(
        FoundationError,
        match="must require separate human authorization",
    ):
        CapabilityDefinition.create(
            key="irreversible-write",
            operation=CapabilityOperation.WRITE,
            target_type="external system",
            summary="Perform an irreversible external write.",
            risk_tier=CapabilityRiskTier.HIGH,
            permitted_actor_kinds=(ActorKind.AGENT,),
            reversible=False,
        )


def test_machine_exercisable_critical_capability_requires_human_authorization() -> None:
    with pytest.raises(
        FoundationError,
        match="machine-exercisable critical capabilities",
    ):
        CapabilityDefinition.create(
            key="unreviewed-critical-execution",
            operation=CapabilityOperation.EXECUTE,
            target_type="critical tool",
            summary="Execute a critical tool without a human boundary.",
            risk_tier=CapabilityRiskTier.CRITICAL,
            permitted_actor_kinds=(ActorKind.AGENT,),
        )


def test_disabled_capability_allows_no_actor_kind() -> None:
    capability = CapabilityDefinition.create(
        key="retired-network-access",
        operation=CapabilityOperation.NETWORK,
        target_type="external endpoint",
        summary="A disabled network capability.",
        risk_tier=CapabilityRiskTier.HIGH,
        permitted_actor_kinds=(ActorKind.SERVICE,),
        enabled=False,
    )

    assert capability.allows_actor_kind(ActorKind.SERVICE) is False


def test_capability_payload_and_digest_are_deterministic() -> None:
    capability = _execute_capability()

    assert capability.to_payload() == {
        "capability_id": "capability:execute-bounded-tool",
        "enabled": True,
        "human_only": False,
        "operation": "execute",
        "permitted_actor_kinds": [
            "agent",
            "service",
        ],
        "requires_evidence": True,
        "requires_human_boundary": True,
        "requires_separate_human_authorization": True,
        "reversible": True,
        "risk_tier": "critical",
        "schema": "capability-definition-v1",
        "summary": "Execute one allowlisted tool under recorded authority.",
        "target_type": "bounded-tool",
    }
    assert capability.digest().verifies(capability.to_payload()) is True


def test_capability_catalog_orders_and_resolves_capabilities() -> None:
    observe = _observe_capability()
    execute = _execute_capability()

    catalog = CapabilityCatalog.create(
        key="initial-runtime",
        created_at=UtcTimestamp.parse("2026-07-15T13:00:00Z"),
        producer_id=_producer_id(),
        capabilities=(observe, execute),
    )

    assert tuple(
        str(capability.capability_id)
        for capability in catalog.capabilities
    ) == (
        "capability:execute-bounded-tool",
        "capability:observe-runtime-state",
    )
    assert catalog.require_capability(execute.capability_id) == execute
    assert catalog.capability_for(observe.capability_id) == observe
    assert catalog.capabilities_for_kind(ActorKind.AGENT) == (
        execute,
        observe,
    )
    assert catalog.critical_machine_capabilities() == (execute,)


def test_capability_catalog_rejects_duplicate_capability_ids() -> None:
    capability = _observe_capability()

    with pytest.raises(
        FoundationError,
        match="unique capability IDs",
    ):
        CapabilityCatalog.create(
            key="duplicate-identifiers",
            created_at=UtcTimestamp.parse("2026-07-15T13:05:00Z"),
            producer_id=_producer_id(),
            capabilities=(capability, capability),
        )


def test_capability_catalog_rejects_duplicate_operation_target_pairs() -> None:
    first = _observe_capability()
    second = CapabilityDefinition.create(
        key="second-runtime-observer",
        operation=CapabilityOperation.OBSERVE,
        target_type="runtime state",
        summary="Duplicate semantic capability.",
        risk_tier=CapabilityRiskTier.MODERATE,
        permitted_actor_kinds=(ActorKind.HUMAN,),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate operation and target combinations",
    ):
        CapabilityCatalog.create(
            key="duplicate-semantics",
            created_at=UtcTimestamp.parse("2026-07-15T13:10:00Z"),
            producer_id=_producer_id(),
            capabilities=(first, second),
        )


def test_capability_catalog_digest_is_independent_of_input_order() -> None:
    observe = _observe_capability()
    execute = _execute_capability()

    first = CapabilityCatalog.create(
        key="stable-catalog",
        created_at=UtcTimestamp.parse("2026-07-15T13:15:00Z"),
        producer_id=_producer_id(),
        capabilities=(observe, execute),
    )
    second = CapabilityCatalog.create(
        key="stable-catalog",
        created_at=UtcTimestamp.parse("2026-07-15T13:15:00Z"),
        producer_id=_producer_id(),
        capabilities=(execute, observe),
    )

    assert first.canonical_payload() == second.canonical_payload()
    assert first.digest() == second.digest()


def test_capability_catalog_require_capability_rejects_unknown_id() -> None:
    catalog = CapabilityCatalog.create(
        key="empty-catalog",
        created_at=UtcTimestamp.parse("2026-07-15T13:20:00Z"),
        producer_id=_producer_id(),
        capabilities=(),
    )

    with pytest.raises(
        FoundationError,
        match="does not contain capability",
    ):
        catalog.require_capability(
            ScopedIdentifier.create(
                namespace="capability",
                key="unknown-capability",
            )
        )
