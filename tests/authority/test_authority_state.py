"""Tests for revocation-aware authority-state resolution."""

import pytest

from ix_missionproof.authority import (
    AuthorityGrant,
    AuthorityGrantLedger,
    AuthorityGrantStatus,
    AuthorityRevocation,
    AuthorityRevocationLedger,
    AuthorityRevocationReason,
    AuthorityStateSnapshot,
    CapabilityCatalog,
    CapabilityDefinition,
    CapabilityOperation,
    CapabilityRiskTier,
    resolve_authority_states,
)
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    FoundationError,
    ScopedIdentifier,
    UtcTimestamp,
)


def _identifier(namespace: str, key: str) -> ScopedIdentifier:
    return ScopedIdentifier.create(namespace=namespace, key=key)


def _fixture() -> tuple[
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
    )
    agent = ActorIdentity.create(
        kind=ActorKind.AGENT,
        key="bounded-agent",
        display_name="Bounded Agent",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key="state-actors",
        created_at=UtcTimestamp.parse("2026-07-15T17:00:00Z"),
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
        key="state-capabilities",
        created_at=UtcTimestamp.parse("2026-07-15T17:00:00Z"),
        producer_id=human.actor_id,
        capabilities=(capability,),
    )
    return human, agent, registry, capability, catalog


def _issue_grant(
    *,
    key: str,
    valid_from: str,
    expires_at: str,
) -> tuple[AuthorityGrant, ActorRegistry]:
    human, agent, registry, capability, catalog = _fixture()
    grant = AuthorityGrant.issue(
        key=key,
        grantee_id=agent.actor_id,
        capability_id=capability.capability_id,
        granted_by_id=human.actor_id,
        issued_at=UtcTimestamp.parse("2026-07-15T17:05:00Z"),
        valid_from=UtcTimestamp.parse(valid_from),
        expires_at=UtcTimestamp.parse(expires_at),
        actor_registry=registry,
        capability_catalog=catalog,
        target_ids=(
            _identifier("bounded-tool", key),
        ),
        supporting_record_ids=(
            _identifier("record", f"{key}-evidence"),
        ),
    )
    return grant, registry


def _grant_ledger() -> tuple[
    AuthorityGrantLedger,
    ActorRegistry,
    AuthorityGrant,
    AuthorityGrant,
    AuthorityGrant,
]:
    pending, registry = _issue_grant(
        key="pending-tool",
        valid_from="2026-07-15T18:00:00Z",
        expires_at="2026-07-15T19:00:00Z",
    )
    active, _ = _issue_grant(
        key="active-tool",
        valid_from="2026-07-15T17:10:00Z",
        expires_at="2026-07-15T19:00:00Z",
    )
    expired, _ = _issue_grant(
        key="expired-tool",
        valid_from="2026-07-15T17:10:00Z",
        expires_at="2026-07-15T17:20:00Z",
    )
    ledger = AuthorityGrantLedger.create(
        key="state-grants",
        created_at=UtcTimestamp.parse("2026-07-15T17:06:00Z"),
        producer_id=active.granted_by_id,
        grants=(pending, active, expired),
    )
    return ledger, registry, pending, active, expired


def test_state_snapshot_resolves_pending_active_expired_and_revoked() -> None:
    grant_ledger, registry, pending, active, expired = (
        _grant_ledger()
    )
    revocation = AuthorityRevocation.revoke(
        key="active-tool-revocation",
        grant_id=active.grant_id,
        revoked_by_id=active.granted_by_id,
        revoked_at=UtcTimestamp.parse("2026-07-15T17:25:00Z"),
        reason_code=AuthorityRevocationReason.SAFETY_HOLD,
        reason="Execution entered a human-issued safety hold.",
        supporting_record_ids=(
            _identifier("record", "safe-hold-evidence"),
        ),
        grant_ledger=grant_ledger,
        actor_registry=registry,
    )
    revocation_ledger = AuthorityRevocationLedger.create(
        key="state-revocations",
        created_at=UtcTimestamp.parse("2026-07-15T17:25:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocations=(revocation,),
    )

    snapshot = AuthorityStateSnapshot.create(
        key="state-at-1730",
        evaluated_at=UtcTimestamp.parse("2026-07-15T17:30:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
    )

    assert snapshot.require_state(
        pending.grant_id
    ).status is AuthorityGrantStatus.PENDING
    assert snapshot.require_state(
        active.grant_id
    ).status is AuthorityGrantStatus.REVOKED
    assert snapshot.require_state(
        expired.grant_id
    ).status is AuthorityGrantStatus.EXPIRED
    assert snapshot.active_grants_for_actor(
        active.grantee_id,
        grant_ledger=grant_ledger,
    ) == ()


def test_active_grant_survives_empty_revocation_ledger() -> None:
    grant_ledger, _, _, active, _ = _grant_ledger()
    revocation_ledger = AuthorityRevocationLedger.create(
        key="empty-state-revocations",
        created_at=UtcTimestamp.parse("2026-07-15T17:06:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocations=(),
    )
    snapshot = AuthorityStateSnapshot.create(
        key="state-at-1730",
        evaluated_at=UtcTimestamp.parse("2026-07-15T17:30:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
    )

    assert snapshot.require_state(
        active.grant_id
    ).status is AuthorityGrantStatus.ACTIVE
    assert snapshot.require_active_grant(
        active.grant_id,
        grant_ledger=grant_ledger,
    ) == active


def test_revoked_grant_cannot_be_required_as_active() -> None:
    grant_ledger, registry, _, active, _ = _grant_ledger()
    revocation = AuthorityRevocation.revoke(
        key="terminal-revocation",
        grant_id=active.grant_id,
        revoked_by_id=active.granted_by_id,
        revoked_at=UtcTimestamp.parse("2026-07-15T17:25:00Z"),
        reason_code=AuthorityRevocationReason.HUMAN_WITHDRAWAL,
        reason="The human grantor withdrew execution authority.",
        supporting_record_ids=(
            _identifier("record", "withdrawal-evidence"),
        ),
        grant_ledger=grant_ledger,
        actor_registry=registry,
    )
    revocation_ledger = AuthorityRevocationLedger.create(
        key="terminal-revocations",
        created_at=UtcTimestamp.parse("2026-07-15T17:25:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocations=(revocation,),
    )
    snapshot = AuthorityStateSnapshot.create(
        key="state-after-revocation",
        evaluated_at=UtcTimestamp.parse("2026-07-15T17:30:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocation_ledger=revocation_ledger,
    )

    with pytest.raises(
        FoundationError,
        match="is revoked",
    ):
        snapshot.require_active_grant(
            active.grant_id,
            grant_ledger=grant_ledger,
        )


def test_state_snapshot_rejects_unbound_grant_ledger() -> None:
    first_ledger, _, _, active, _ = _grant_ledger()
    second_ledger = AuthorityGrantLedger.create(
        key="different-grants",
        created_at=first_ledger.created_at,
        producer_id=first_ledger.producer_id,
        grants=(active,),
    )
    revocation_ledger = AuthorityRevocationLedger.create(
        key="first-ledger-revocations",
        created_at=first_ledger.created_at,
        producer_id=first_ledger.producer_id,
        grant_ledger=first_ledger,
        revocations=(),
    )

    with pytest.raises(
        FoundationError,
        match="not bound to the supplied grant ledger",
    ):
        AuthorityStateSnapshot.create(
            key="mismatched-state",
            evaluated_at=UtcTimestamp.parse(
                "2026-07-15T17:30:00Z"
            ),
            producer_id=active.granted_by_id,
            grant_ledger=second_ledger,
            revocation_ledger=revocation_ledger,
        )


def test_state_snapshot_rejects_stale_ledger_time_boundary() -> None:
    grant_ledger, _, _, active, _ = _grant_ledger()
    revocation_ledger = AuthorityRevocationLedger.create(
        key="later-revocation-ledger",
        created_at=UtcTimestamp.parse("2026-07-15T17:40:00Z"),
        producer_id=active.granted_by_id,
        grant_ledger=grant_ledger,
        revocations=(),
    )

    with pytest.raises(
        FoundationError,
        match="cannot predate the revocation ledger",
    ):
        AuthorityStateSnapshot.create(
            key="historically-invalid-state",
            evaluated_at=UtcTimestamp.parse(
                "2026-07-15T17:30:00Z"
            ),
            producer_id=active.granted_by_id,
            grant_ledger=grant_ledger,
            revocation_ledger=revocation_ledger,
        )


def test_direct_state_resolution_is_input_order_independent() -> None:
    grant_ledger, registry, pending, active, expired = (
        _grant_ledger()
    )
    revocation = AuthorityRevocation.revoke(
        key="direct-resolution-revocation",
        grant_id=active.grant_id,
        revoked_by_id=active.granted_by_id,
        revoked_at=UtcTimestamp.parse("2026-07-15T17:25:00Z"),
        reason_code=AuthorityRevocationReason.SCOPE_INVALIDATED,
        reason="The bounded execution scope no longer exists.",
        supporting_record_ids=(
            _identifier("record", "scope-invalidation"),
        ),
        grant_ledger=grant_ledger,
        actor_registry=registry,
    )
    evaluated_at = UtcTimestamp.parse("2026-07-15T17:30:00Z")

    first = resolve_authority_states(
        (pending, active, expired),
        evaluated_at=evaluated_at,
        revocations=(revocation,),
    )
    second = resolve_authority_states(
        (expired, pending, active),
        evaluated_at=evaluated_at,
        revocations=(revocation,),
    )

    assert first == second
