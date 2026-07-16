"""Tests for bounded human-issued authority grants."""

import pytest

from ix_missionproof.authority import (
    AuthorityGrant,
    AuthorityGrantLedger,
    CapabilityCatalog,
    CapabilityDefinition,
    CapabilityOperation,
    CapabilityRiskTier,
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


def _identifier(namespace: str, key: str) -> ScopedIdentifier:
    return ScopedIdentifier.create(namespace=namespace, key=key)


def _human(
    key: str,
    *,
    status: ActorStatus = ActorStatus.ACTIVE,
) -> ActorIdentity:
    return ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key=key,
        display_name=f"Human {key}",
        status=status,
        roles=("authority grantor",),
    )


def _agent(
    owner_id: ScopedIdentifier,
    *,
    key: str = "bounded-agent",
) -> ActorIdentity:
    return ActorIdentity.create(
        kind=ActorKind.AGENT,
        key=key,
        display_name="Bounded Agent",
        roles=("tool executor",),
        accountability_owner_id=owner_id,
    )


def _actor_registry(
    *,
    grantor: ActorIdentity,
    agent: ActorIdentity,
) -> ActorRegistry:
    return ActorRegistry.create(
        key="authority-test-actors",
        created_at=UtcTimestamp.parse("2026-07-15T14:00:00Z"),
        producer_id=grantor.actor_id,
        actors=(agent, grantor),
    )


def _capability(
    *,
    permitted_actor_kinds: tuple[ActorKind, ...] = (ActorKind.AGENT,),
    requires_evidence: bool = True,
    requires_separate_human_authorization: bool = True,
) -> CapabilityDefinition:
    return CapabilityDefinition.create(
        key="execute-bounded-tool",
        operation=CapabilityOperation.EXECUTE,
        target_type="bounded tool",
        summary="Execute one exact bounded tool.",
        risk_tier=CapabilityRiskTier.CRITICAL,
        permitted_actor_kinds=permitted_actor_kinds,
        requires_evidence=requires_evidence,
        requires_separate_human_authorization=(
            requires_separate_human_authorization
        ),
    )


def _catalog(
    *,
    capability: CapabilityDefinition,
    producer_id: ScopedIdentifier,
) -> CapabilityCatalog:
    return CapabilityCatalog.create(
        key="authority-test-capabilities",
        created_at=UtcTimestamp.parse("2026-07-15T14:00:00Z"),
        producer_id=producer_id,
        capabilities=(capability,),
    )


def _issue_grant(
    *,
    key: str = "agent-test-runner",
    issued_at: str = "2026-07-15T14:05:00Z",
    valid_from: str | None = None,
    expires_at: str | None = "2026-07-15T15:05:00Z",
) -> AuthorityGrant:
    grantor = _human("reviewer-01")
    agent = _agent(grantor.actor_id)
    registry = _actor_registry(grantor=grantor, agent=agent)
    capability = _capability()
    catalog = _catalog(
        capability=capability,
        producer_id=grantor.actor_id,
    )

    return AuthorityGrant.issue(
        key=key,
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=grantor.actor_id,
        issued_at=UtcTimestamp.parse(issued_at),
        valid_from=(
            UtcTimestamp.parse(valid_from)
            if valid_from is not None
            else None
        ),
        expires_at=(
            UtcTimestamp.parse(expires_at)
            if expires_at is not None
            else None
        ),
        actor_registry=registry,
        capability_catalog=catalog,
        target_ids=(
            _identifier("bounded-tool", "test-runner"),
        ),
        supporting_record_ids=(
            _identifier("record", "review-evidence-0001"),
        ),
        constraints={
            "allowed_arguments": ["tests/unit"],
            "requires_separate_human_authorization": True,
        },
    )


def test_authority_grant_binds_actor_capability_scope_and_sources() -> None:
    grant = _issue_grant()

    assert str(grant.grant_id) == (
        "authority-grant:agent-test-runner"
    )
    assert str(grant.grantee_id) == "agent:bounded-agent"
    assert str(grant.granted_by_id) == "human:reviewer-01"
    assert grant.target_ids == (
        _identifier("bounded-tool", "test-runner"),
    )
    assert grant.supporting_record_ids == (
        _identifier("record", "review-evidence-0001"),
    )
    assert grant.requires_runtime_authorization is True
    assert grant.covers_target(
        _identifier("bounded-tool", "test-runner")
    )
    assert not grant.covers_target(
        _identifier("bounded-tool", "deployment-tool")
    )


def test_standing_grant_does_not_erase_runtime_human_boundary() -> None:
    grant = _issue_grant()

    assert grant.capability_requires_separate_authorization is True
    assert grant.requires_runtime_authorization is True


def test_authority_grant_payload_and_digest_are_deterministic() -> None:
    grant = _issue_grant()

    assert grant.to_payload() == {
        "actor_registry_digest": grant.actor_registry_digest.to_payload(),
        "capability_catalog_digest": (
            grant.capability_catalog_digest.to_payload()
        ),
        "capability_digest": grant.capability_digest.to_payload(),
        "capability_id": "capability:execute-bounded-tool",
        "constraints": {
            "allowed_arguments": ["tests/unit"],
            "requires_separate_human_authorization": True,
        },
        "expires_at": "2026-07-15T15:05:00Z",
        "grant_id": "authority-grant:agent-test-runner",
        "granted_by_id": "human:reviewer-01",
        "grantee_id": "agent:bounded-agent",
        "issued_at": "2026-07-15T14:05:00Z",
        "schema": "authority-grant-v1",
        "supporting_record_ids": [
            "record:review-evidence-0001",
        ],
        "target_ids": [
            "bounded-tool:test-runner",
        ],
        "valid_from": "2026-07-15T14:05:00Z",
    }
    assert grant.digest().verifies(grant.to_payload()) is True


def test_authority_grant_enforces_time_window() -> None:
    grant = _issue_grant(
        issued_at="2026-07-15T14:00:00Z",
        valid_from="2026-07-15T14:10:00Z",
        expires_at="2026-07-15T15:00:00Z",
    )

    assert grant.is_time_effective(
        UtcTimestamp.parse("2026-07-15T14:09:59Z")
    ) is False
    assert grant.is_time_effective(
        UtcTimestamp.parse("2026-07-15T14:10:00Z")
    ) is True
    assert grant.is_time_effective(
        UtcTimestamp.parse("2026-07-15T14:59:59Z")
    ) is True
    assert grant.is_time_effective(
        UtcTimestamp.parse("2026-07-15T15:00:00Z")
    ) is False


def test_authority_grant_rejects_self_authorization() -> None:
    grantor = _human("reviewer-01")
    registry = ActorRegistry.create(
        key="human-only-registry",
        created_at=UtcTimestamp.parse("2026-07-15T14:00:00Z"),
        producer_id=grantor.actor_id,
        actors=(grantor,),
    )
    capability = _capability(
        permitted_actor_kinds=(ActorKind.HUMAN,),
    )
    catalog = _catalog(
        capability=capability,
        producer_id=grantor.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="must not grant authority to itself",
    ):
        AuthorityGrant.issue(
            key="self-grant",
            grantee_id=grantor.actor_id,
            capability_id=capability.capability_id,
            granted_by_id=grantor.actor_id,
            issued_at=UtcTimestamp.parse("2026-07-15T14:05:00Z"),
            actor_registry=registry,
            capability_catalog=catalog,
            target_ids=(
                _identifier("bounded-tool", "test-runner"),
            ),
            supporting_record_ids=(
                _identifier("record", "review-evidence-0001"),
            ),
        )


def test_authority_grant_rejects_inactive_human_grantor() -> None:
    grantor = _human(
        "reviewer-01",
        status=ActorStatus.SUSPENDED,
    )
    agent = _agent(grantor.actor_id)

    with pytest.raises(
        FoundationError,
        match="accountability owners must be active",
    ):
        _actor_registry(grantor=grantor, agent=agent)


def test_authority_grant_rejects_disallowed_actor_kind() -> None:
    grantor = _human("reviewer-01")
    agent = _agent(grantor.actor_id)
    registry = _actor_registry(grantor=grantor, agent=agent)
    capability = _capability(
        permitted_actor_kinds=(ActorKind.SERVICE,),
    )
    catalog = _catalog(
        capability=capability,
        producer_id=grantor.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="does not permit actor kind agent",
    ):
        AuthorityGrant.issue(
            key="wrong-actor-kind",
            grantee_id=agent.actor_id,
            capability_id=capability.capability_id,
            granted_by_id=grantor.actor_id,
            issued_at=UtcTimestamp.parse("2026-07-15T14:05:00Z"),
            actor_registry=registry,
            capability_catalog=catalog,
            target_ids=(
                _identifier("bounded-tool", "test-runner"),
            ),
            supporting_record_ids=(
                _identifier("record", "review-evidence-0001"),
            ),
        )


def test_authority_grant_rejects_unbounded_scope() -> None:
    grantor = _human("reviewer-01")
    agent = _agent(grantor.actor_id)
    registry = _actor_registry(grantor=grantor, agent=agent)
    capability = _capability()
    catalog = _catalog(
        capability=capability,
        producer_id=grantor.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="at least one bounded target",
    ):
        AuthorityGrant.issue(
            key="unbounded-grant",
            grantee_id=agent.actor_id,
            capability_id=capability.capability_id,
            granted_by_id=grantor.actor_id,
            issued_at=UtcTimestamp.parse("2026-07-15T14:05:00Z"),
            actor_registry=registry,
            capability_catalog=catalog,
            target_ids=(),
            supporting_record_ids=(
                _identifier("record", "review-evidence-0001"),
            ),
        )


def test_authority_grant_rejects_target_type_mismatch() -> None:
    grantor = _human("reviewer-01")
    agent = _agent(grantor.actor_id)
    registry = _actor_registry(grantor=grantor, agent=agent)
    capability = _capability()
    catalog = _catalog(
        capability=capability,
        producer_id=grantor.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="does not match capability target type bounded-tool",
    ):
        AuthorityGrant.issue(
            key="wrong-target-type",
            grantee_id=agent.actor_id,
            capability_id=capability.capability_id,
            granted_by_id=grantor.actor_id,
            issued_at=UtcTimestamp.parse("2026-07-15T14:05:00Z"),
            actor_registry=registry,
            capability_catalog=catalog,
            target_ids=(
                _identifier("workspace", "repository"),
            ),
            supporting_record_ids=(
                _identifier("record", "review-evidence-0001"),
            ),
        )


def test_authority_grant_requires_support_for_evidence_bound_capability() -> None:
    grantor = _human("reviewer-01")
    agent = _agent(grantor.actor_id)
    registry = _actor_registry(grantor=grantor, agent=agent)
    capability = _capability()
    catalog = _catalog(
        capability=capability,
        producer_id=grantor.actor_id,
    )

    with pytest.raises(
        FoundationError,
        match="requires at least one supporting record",
    ):
        AuthorityGrant.issue(
            key="unsupported-grant",
            grantee_id=agent.actor_id,
            capability_id=capability.capability_id,
            granted_by_id=grantor.actor_id,
            issued_at=UtcTimestamp.parse("2026-07-15T14:05:00Z"),
            actor_registry=registry,
            capability_catalog=catalog,
            target_ids=(
                _identifier("bounded-tool", "test-runner"),
            ),
            supporting_record_ids=(),
        )


def test_authority_grant_rejects_invalid_time_bounds() -> None:
    with pytest.raises(
        FoundationError,
        match="valid_from must not precede issued_at",
    ):
        _issue_grant(
            issued_at="2026-07-15T14:10:00Z",
            valid_from="2026-07-15T14:05:00Z",
        )

    with pytest.raises(
        FoundationError,
        match="expires_at must be later than valid_from",
    ):
        _issue_grant(
            issued_at="2026-07-15T14:00:00Z",
            valid_from="2026-07-15T14:10:00Z",
            expires_at="2026-07-15T14:10:00Z",
        )


def test_authority_grant_ledger_orders_and_filters_grants() -> None:
    first = _issue_grant(
        key="later-grant",
        issued_at="2026-07-15T14:10:00Z",
        expires_at="2026-07-15T15:10:00Z",
    )
    second = _issue_grant(
        key="earlier-grant",
        issued_at="2026-07-15T14:05:00Z",
        expires_at="2026-07-15T14:30:00Z",
    )

    ledger = AuthorityGrantLedger.create(
        key="runtime-grants",
        created_at=UtcTimestamp.parse("2026-07-15T14:15:00Z"),
        producer_id=_identifier("human", "reviewer-01"),
        grants=(first, second),
    )

    assert tuple(str(grant.grant_id) for grant in ledger.grants) == (
        "authority-grant:earlier-grant",
        "authority-grant:later-grant",
    )
    assert ledger.require_grant(first.grant_id) == first
    assert ledger.grants_for_actor(first.grantee_id) == (
        second,
        first,
    )
    assert ledger.effective_grants_for_actor(
        first.grantee_id,
        at=UtcTimestamp.parse("2026-07-15T14:35:00Z"),
    ) == (first,)


def test_authority_grant_ledger_rejects_duplicate_ids() -> None:
    grant = _issue_grant()

    with pytest.raises(
        FoundationError,
        match="unique grant IDs",
    ):
        AuthorityGrantLedger.create(
            key="duplicate-grants",
            created_at=UtcTimestamp.parse("2026-07-15T14:10:00Z"),
            producer_id=_identifier("human", "reviewer-01"),
            grants=(grant, grant),
        )


def test_authority_grant_ledger_rejects_future_grants() -> None:
    grant = _issue_grant(
        issued_at="2026-07-15T14:20:00Z",
        expires_at="2026-07-15T15:20:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="must not predate a contained grant",
    ):
        AuthorityGrantLedger.create(
            key="premature-ledger",
            created_at=UtcTimestamp.parse("2026-07-15T14:19:59Z"),
            producer_id=_identifier("human", "reviewer-01"),
            grants=(grant,),
        )


def test_authority_grant_ledger_digest_is_input_order_independent() -> None:
    first = _issue_grant(
        key="first-grant",
        issued_at="2026-07-15T14:05:00Z",
    )
    second = _issue_grant(
        key="second-grant",
        issued_at="2026-07-15T14:10:00Z",
    )
    created_at = UtcTimestamp.parse("2026-07-15T14:15:00Z")
    producer_id = _identifier("human", "reviewer-01")

    first_ledger = AuthorityGrantLedger.create(
        key="stable-ledger",
        created_at=created_at,
        producer_id=producer_id,
        grants=(first, second),
    )
    second_ledger = AuthorityGrantLedger.create(
        key="stable-ledger",
        created_at=created_at,
        producer_id=producer_id,
        grants=(second, first),
    )

    assert (
        first_ledger.canonical_payload()
        == second_ledger.canonical_payload()
    )
    assert first_ledger.digest() == second_ledger.digest()
