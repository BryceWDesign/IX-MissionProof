"""Tests for terminal authority revocation records and ledgers."""

from dataclasses import replace

import pytest

from ix_missionproof.authority import (
    AuthorityGrant,
    AuthorityGrantLedger,
    AuthorityRevocation,
    AuthorityRevocationLedger,
    AuthorityRevocationReason,
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


def _authority_fixture() -> tuple[
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
        key="revocation-actors",
        created_at=UtcTimestamp.parse("2026-07-15T16:00:00Z"),
        producer_id=human.actor_id,
        actors=(human, agent),
    )
    capability = CapabilityDefinition.create(
        key="execute-bounded-tool",
        operation=CapabilityOperation.EXECUTE,
        target_type="bounded tool",
        summary="Execute one exact bounded tool.",
        risk_tier=CapabilityRiskTier.HIGH,
        permitted_actor_kinds=(ActorKind.AGENT,),
    )
    catalog = CapabilityCatalog.create(
        key="revocation-capabilities",
        created_at=UtcTimestamp.parse("2026-07-15T16:00:00Z"),
        producer_id=human.actor_id,
        capabilities=(capability,),
    )
    return human, agent, registry, capability, catalog


def _grant(
    *,
    key: str = "runtime-grant",
    issued_at: str = "2026-07-15T16:05:00Z",
    valid_from: str = "2026-07-15T16:10:00Z",
    expires_at: str = "2026-07-15T17:00:00Z",
) -> tuple[
    AuthorityGrant,
    AuthorityGrantLedger,
    ActorRegistry,
]:
    human, agent, registry, capability, catalog = (
        _authority_fixture()
    )
    grant = AuthorityGrant.issue(
        key=key,
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=human.actor_id,
        issued_at=UtcTimestamp.parse(issued_at),
        valid_from=UtcTimestamp.parse(valid_from),
        expires_at=UtcTimestamp.parse(expires_at),
        actor_registry=registry,
        capability_catalog=catalog,
        target_ids=(
            _identifier("bounded-tool", "test-runner"),
        ),
        supporting_record_ids=(
            _identifier("record", "grant-evidence-0001"),
        ),
    )
    ledger = AuthorityGrantLedger.create(
        key=f"{key}-ledger",
        created_at=UtcTimestamp.parse(issued_at),
        producer_id=human.actor_id,
        grants=(grant,),
    )
    return grant, ledger, registry


def _revocation(
    *,
    revoked_at: str = "2026-07-15T16:20:00Z",
) -> tuple[
    AuthorityRevocation,
    AuthorityGrantLedger,
    ActorRegistry,
]:
    grant, ledger, registry = _grant()
    revocation = AuthorityRevocation.revoke(
        key="runtime-grant-revocation",
        grant_id=grant.grant_id,
        revoked_by_id=grant.granted_by_id,
        revoked_at=UtcTimestamp.parse(revoked_at),
        reason_code=AuthorityRevocationReason.EVIDENCE_INVALIDATED,
        reason="The evidence supporting the grant was invalidated.",
        supporting_record_ids=(
            _identifier("record", "invalidated-evidence-0001"),
        ),
        grant_ledger=ledger,
        actor_registry=registry,
    )
    return revocation, ledger, registry


def test_original_active_human_grantor_can_revoke_grant() -> None:
    revocation, ledger, registry = _revocation()
    grant = ledger.require_grant(revocation.grant_id)

    assert str(revocation.revocation_id) == (
        "authority-revocation:runtime-grant-revocation"
    )
    assert revocation.revoked_by_id == grant.granted_by_id
    assert revocation.grant_digest == grant.digest()
    assert revocation.grant_ledger_digest == ledger.digest()
    assert revocation.actor_registry_digest == registry.digest()
    assert revocation.digest().verifies(
        revocation.to_payload()
    ) is True


def test_revocation_may_prevent_grant_before_activation() -> None:
    grant, ledger, registry = _grant()

    revocation = AuthorityRevocation.revoke(
        key="preactivation-revocation",
        grant_id=grant.grant_id,
        revoked_by_id=grant.granted_by_id,
        revoked_at=UtcTimestamp.parse("2026-07-15T16:06:00Z"),
        reason_code=AuthorityRevocationReason.HUMAN_WITHDRAWAL,
        reason="The original grantor withdrew the grant.",
        supporting_record_ids=(
            _identifier("record", "withdrawal-0001"),
        ),
        grant_ledger=ledger,
        actor_registry=registry,
    )

    assert revocation.revoked_at.value < grant.valid_from.value


def test_revocation_requires_original_human_grantor() -> None:
    grant, ledger, registry = _grant()
    other_human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-02",
        display_name="Second Reviewer",
    )
    expanded_registry = ActorRegistry.create(
        key="expanded-revocation-actors",
        created_at=UtcTimestamp.parse("2026-07-15T16:10:00Z"),
        producer_id=other_human.actor_id,
        actors=(*registry.actors, other_human),
    )

    with pytest.raises(
        FoundationError,
        match="must be issued by the original human grantor",
    ):
        AuthorityRevocation.revoke(
            key="unauthorized-revocation",
            grant_id=grant.grant_id,
            revoked_by_id=other_human.actor_id,
            revoked_at=UtcTimestamp.parse(
                "2026-07-15T16:20:00Z"
            ),
            reason_code=AuthorityRevocationReason.POLICY_CHANGED,
            reason="A different reviewer attempted revocation.",
            supporting_record_ids=(
                _identifier("record", "policy-change-0001"),
            ),
            grant_ledger=ledger,
            actor_registry=expanded_registry,
        )


def test_inactive_original_grantor_cannot_revoke() -> None:
    grant, ledger, registry = _grant()
    original = registry.require_actor(grant.granted_by_id)
    suspended = replace(
        original,
        status=ActorStatus.SUSPENDED,
    )
    suspended_registry = ActorRegistry.create(
        key="suspended-revocation-actors",
        created_at=UtcTimestamp.parse("2026-07-15T16:10:00Z"),
        producer_id=original.actor_id,
        actors=(
            suspended,
            registry.require_actor(grant.grantee_id),
        ),
    )

    with pytest.raises(
        FoundationError,
        match="requires an active human actor",
    ):
        AuthorityRevocation.revoke(
            key="inactive-grantor-revocation",
            grant_id=grant.grant_id,
            revoked_by_id=original.actor_id,
            revoked_at=UtcTimestamp.parse(
                "2026-07-15T16:20:00Z"
            ),
            reason_code=AuthorityRevocationReason.SAFETY_HOLD,
            reason="An inactive actor attempted revocation.",
            supporting_record_ids=(
                _identifier("record", "safe-hold-0001"),
            ),
            grant_ledger=ledger,
            actor_registry=suspended_registry,
        )


def test_revocation_requires_supporting_record() -> None:
    grant, ledger, registry = _grant()

    with pytest.raises(
        FoundationError,
        match="requires at least one supporting record",
    ):
        AuthorityRevocation.revoke(
            key="unsupported-revocation",
            grant_id=grant.grant_id,
            revoked_by_id=grant.granted_by_id,
            revoked_at=UtcTimestamp.parse(
                "2026-07-15T16:20:00Z"
            ),
            reason_code=AuthorityRevocationReason.GRANT_ERROR,
            reason="The grant was issued in error.",
            supporting_record_ids=(),
            grant_ledger=ledger,
            actor_registry=registry,
        )


def test_expired_grant_cannot_be_revoked() -> None:
    grant, ledger, registry = _grant()

    with pytest.raises(
        FoundationError,
        match="expired authority grant cannot be revoked",
    ):
        AuthorityRevocation.revoke(
            key="late-revocation",
            grant_id=grant.grant_id,
            revoked_by_id=grant.granted_by_id,
            revoked_at=UtcTimestamp.parse(
                "2026-07-15T17:00:00Z"
            ),
            reason_code=AuthorityRevocationReason.HUMAN_WITHDRAWAL,
            reason="The revocation arrived after expiration.",
            supporting_record_ids=(
                _identifier("record", "late-revocation-0001"),
            ),
            grant_ledger=ledger,
            actor_registry=registry,
        )


def test_revocation_ledger_is_terminal_per_grant() -> None:
    revocation, ledger, _ = _revocation()

    with pytest.raises(
        FoundationError,
        match="terminally revoked only once",
    ):
        AuthorityRevocationLedger.create(
            key="duplicate-revocation-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T16:25:00Z"
            ),
            producer_id=revocation.revoked_by_id,
            grant_ledger=ledger,
            revocations=(revocation, revocation),
        )


def test_revocation_ledger_resolves_effective_revocation() -> None:
    revocation, grant_ledger, _ = _revocation()
    ledger = AuthorityRevocationLedger.create(
        key="runtime-revocations",
        created_at=UtcTimestamp.parse("2026-07-15T16:20:00Z"),
        producer_id=revocation.revoked_by_id,
        grant_ledger=grant_ledger,
        revocations=(revocation,),
    )

    assert ledger.require_revocation(
        revocation.grant_id
    ) == revocation
    assert ledger.is_revoked(
        revocation.grant_id,
        at=UtcTimestamp.parse("2026-07-15T16:19:59Z"),
    ) is False
    assert ledger.is_revoked(
        revocation.grant_id,
        at=UtcTimestamp.parse("2026-07-15T16:20:00Z"),
    ) is True


def test_empty_revocation_ledger_is_valid() -> None:
    grant, grant_ledger, _ = _grant()
    ledger = AuthorityRevocationLedger.create(
        key="no-revocations",
        created_at=UtcTimestamp.parse("2026-07-15T16:05:00Z"),
        producer_id=grant.granted_by_id,
        grant_ledger=grant_ledger,
        revocations=(),
    )

    assert ledger.revocations == ()
    assert ledger.is_revoked(
        grant.grant_id,
        at=UtcTimestamp.parse("2026-07-15T16:30:00Z"),
    ) is False
