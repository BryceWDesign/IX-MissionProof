"""Revocation-aware authority-state resolution for IX-MissionProof."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.authority.grants import (
    AuthorityGrant,
    AuthorityGrantLedger,
)
from ix_missionproof.authority.revocations import (
    AuthorityRevocation,
    AuthorityRevocationLedger,
)
from ix_missionproof.foundation import (
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonArray,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
)


class AuthorityGrantStatus(StrEnum):
    """Resolved lifecycle state for an authority grant."""

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

    @property
    def permits_use(self) -> bool:
        """Return whether this status permits consideration for use."""

        return self is AuthorityGrantStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class AuthorityGrantState:
    """Resolved status of one grant at one exact evaluation time."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "authority-grant-state-v1"
    )

    grant_id: ScopedIdentifier
    grantee_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    evaluated_at: UtcTimestamp
    status: AuthorityGrantStatus
    grant_digest: ContentDigest
    revocation_id: ScopedIdentifier | None = None
    revocation_digest: ContentDigest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.grant_id, ScopedIdentifier):
            raise FoundationError(
                "grant_id must be a ScopedIdentifier"
            )
        if self.grant_id.namespace != CanonicalKey("authority-grant"):
            raise FoundationError(
                "grant_id namespace must be authority-grant"
            )
        if not isinstance(self.grantee_id, ScopedIdentifier):
            raise FoundationError(
                "grantee_id must be a ScopedIdentifier"
            )
        if not isinstance(self.capability_id, ScopedIdentifier):
            raise FoundationError(
                "capability_id must be a ScopedIdentifier"
            )
        if self.capability_id.namespace != CanonicalKey("capability"):
            raise FoundationError(
                "capability_id namespace must be capability"
            )
        if not isinstance(self.evaluated_at, UtcTimestamp):
            raise FoundationError(
                "evaluated_at must be a UtcTimestamp"
            )
        if not isinstance(self.status, AuthorityGrantStatus):
            raise FoundationError(
                "status must be an AuthorityGrantStatus"
            )
        if not isinstance(self.grant_digest, ContentDigest):
            raise FoundationError(
                "grant_digest must be a ContentDigest"
            )
        if self.grant_digest.domain != CanonicalKey(
            "authority-grant"
        ):
            raise FoundationError(
                "grant_digest domain must be authority-grant"
            )

        if self.status is AuthorityGrantStatus.REVOKED:
            if self.revocation_id is None:
                raise FoundationError(
                    "revoked grant state requires a revocation_id"
                )
            if self.revocation_digest is None:
                raise FoundationError(
                    "revoked grant state requires a revocation_digest"
                )
        elif (
            self.revocation_id is not None
            or self.revocation_digest is not None
        ):
            raise FoundationError(
                "non-revoked grant state must not carry revocation data"
            )

        if self.revocation_id is not None:
            if not isinstance(self.revocation_id, ScopedIdentifier):
                raise FoundationError(
                    "revocation_id must be a ScopedIdentifier or None"
                )
            if self.revocation_id.namespace != CanonicalKey(
                "authority-revocation"
            ):
                raise FoundationError(
                    "revocation_id namespace must be "
                    "authority-revocation"
                )

        if self.revocation_digest is not None:
            if not isinstance(self.revocation_digest, ContentDigest):
                raise FoundationError(
                    "revocation_digest must be a ContentDigest or None"
                )
            if self.revocation_digest.domain != CanonicalKey(
                "authority-revocation"
            ):
                raise FoundationError(
                    "revocation_digest domain must be "
                    "authority-revocation"
                )

    @classmethod
    def resolve(
        cls,
        *,
        grant: AuthorityGrant,
        evaluated_at: UtcTimestamp,
        revocation: AuthorityRevocation | None,
    ) -> AuthorityGrantState:
        """Resolve a grant using time bounds and terminal revocation."""

        if (
            revocation is not None
            and revocation.grant_id != grant.grant_id
        ):
            raise FoundationError(
                "revocation does not reference the supplied grant"
            )
        if (
            revocation is not None
            and revocation.grant_digest != grant.digest()
        ):
            raise FoundationError(
                "revocation digest binding does not match the grant"
            )

        if (
            revocation is not None
            and revocation.revoked_at.value <= evaluated_at.value
        ):
            status = AuthorityGrantStatus.REVOKED
        elif evaluated_at.value < grant.valid_from.value:
            status = AuthorityGrantStatus.PENDING
        elif (
            grant.expires_at is not None
            and evaluated_at.value >= grant.expires_at.value
        ):
            status = AuthorityGrantStatus.EXPIRED
        else:
            status = AuthorityGrantStatus.ACTIVE

        return cls(
            grant_id=grant.grant_id,
            grantee_id=grant.grantee_id,
            capability_id=grant.capability_id,
            evaluated_at=evaluated_at,
            status=status,
            grant_digest=grant.digest(),
            revocation_id=(
                revocation.revocation_id
                if status is AuthorityGrantStatus.REVOKED
                and revocation is not None
                else None
            ),
            revocation_digest=(
                revocation.digest()
                if status is AuthorityGrantStatus.REVOKED
                and revocation is not None
                else None
            ),
        )

    @property
    def permits_use(self) -> bool:
        """Return whether this resolved state permits grant use."""

        return self.status.permits_use

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this grant state."""

        return {
            "capability_id": str(self.capability_id),
            "evaluated_at": self.evaluated_at.isoformat(),
            "grant_digest": self.grant_digest.to_payload(),
            "grant_id": str(self.grant_id),
            "grantee_id": str(self.grantee_id),
            "permits_use": self.permits_use,
            "revocation_digest": (
                self.revocation_digest.to_payload()
                if self.revocation_digest is not None
                else None
            ),
            "revocation_id": (
                str(self.revocation_id)
                if self.revocation_id is not None
                else None
            ),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class AuthorityStateSnapshot:
    """A deterministic revocation-aware snapshot of all authority grants."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "authority-state-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    evaluated_at: UtcTimestamp
    producer_id: ScopedIdentifier
    grant_ledger_digest: ContentDigest
    revocation_ledger_digest: ContentDigest
    states: tuple[AuthorityGrantState, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_id, ScopedIdentifier):
            raise FoundationError(
                "snapshot_id must be a ScopedIdentifier"
            )
        if self.snapshot_id.namespace != CanonicalKey(
            "authority-state"
        ):
            raise FoundationError(
                "snapshot_id namespace must be authority-state"
            )
        if not isinstance(self.evaluated_at, UtcTimestamp):
            raise FoundationError(
                "evaluated_at must be a UtcTimestamp"
            )
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )

        expected_domains = (
            (
                "grant_ledger_digest",
                self.grant_ledger_digest,
                CanonicalKey("authority-grant-ledger"),
            ),
            (
                "revocation_ledger_digest",
                self.revocation_ledger_digest,
                CanonicalKey("authority-revocation-ledger"),
            ),
        )
        for field_name, digest, expected_domain in expected_domains:
            if not isinstance(digest, ContentDigest):
                raise FoundationError(
                    f"{field_name} must be a ContentDigest"
                )
            if digest.domain != expected_domain:
                raise FoundationError(
                    f"{field_name} domain must be "
                    f"{expected_domain.value}"
                )

        states = tuple(self.states)
        for index, state in enumerate(states):
            if not isinstance(state, AuthorityGrantState):
                raise FoundationError(
                    f"states[{index}] must be an AuthorityGrantState"
                )
            if state.evaluated_at != self.evaluated_at:
                raise FoundationError(
                    "all grant states must use the snapshot "
                    "evaluation time"
                )

        grant_ids = tuple(state.grant_id for state in states)
        if len(grant_ids) != len(set(grant_ids)):
            raise FoundationError(
                "authority-state snapshot must contain unique grant IDs"
            )

        object.__setattr__(
            self,
            "states",
            tuple(
                sorted(
                    states,
                    key=lambda state: str(state.grant_id),
                )
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        evaluated_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        grant_ledger: AuthorityGrantLedger,
        revocation_ledger: AuthorityRevocationLedger,
    ) -> AuthorityStateSnapshot:
        """Resolve every grant against the bound revocation ledger."""

        grant_ledger_digest = grant_ledger.digest()
        if revocation_ledger.grant_ledger_digest != grant_ledger_digest:
            raise FoundationError(
                "revocation ledger is not bound to the supplied "
                "grant ledger"
            )
        if grant_ledger.created_at.value > evaluated_at.value:
            raise FoundationError(
                "authority state cannot predate the grant ledger"
            )
        if revocation_ledger.created_at.value > evaluated_at.value:
            raise FoundationError(
                "authority state cannot predate the revocation ledger"
            )

        states = tuple(
            AuthorityGrantState.resolve(
                grant=grant,
                evaluated_at=evaluated_at,
                revocation=revocation_ledger.revocation_for(
                    grant.grant_id
                ),
            )
            for grant in grant_ledger.grants
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace="authority-state",
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            evaluated_at=evaluated_at,
            producer_id=producer_id,
            grant_ledger_digest=grant_ledger_digest,
            revocation_ledger_digest=revocation_ledger.digest(),
            states=states,
        )

    def state_for(
        self,
        grant_id: ScopedIdentifier,
    ) -> AuthorityGrantState | None:
        """Return the resolved state of a grant, when present."""

        for state in self.states:
            if state.grant_id == grant_id:
                return state
        return None

    def require_state(
        self,
        grant_id: ScopedIdentifier,
    ) -> AuthorityGrantState:
        """Return a grant state or fail when it is absent."""

        state = self.state_for(grant_id)
        if state is None:
            raise FoundationError(
                "authority-state snapshot does not contain grant: "
                f"{grant_id}"
            )
        return state

    def active_states_for_actor(
        self,
        actor_id: ScopedIdentifier,
    ) -> tuple[AuthorityGrantState, ...]:
        """Return all active grant states for one actor."""

        return tuple(
            state
            for state in self.states
            if state.grantee_id == actor_id
            and state.permits_use
        )

    def active_grants_for_actor(
        self,
        actor_id: ScopedIdentifier,
        *,
        grant_ledger: AuthorityGrantLedger,
    ) -> tuple[AuthorityGrant, ...]:
        """Return active grants after verifying the bound grant ledger."""

        self._require_bound_grant_ledger(grant_ledger)
        active_ids = {
            state.grant_id
            for state in self.active_states_for_actor(actor_id)
        }
        return tuple(
            grant
            for grant in grant_ledger.grants
            if grant.grant_id in active_ids
        )

    def require_active_grant(
        self,
        grant_id: ScopedIdentifier,
        *,
        grant_ledger: AuthorityGrantLedger,
    ) -> AuthorityGrant:
        """Return a grant only when its resolved state is active."""

        self._require_bound_grant_ledger(grant_ledger)
        state = self.require_state(grant_id)
        if not state.permits_use:
            raise FoundationError(
                f"authority grant {grant_id} is {state.status.value}"
            )
        grant = grant_ledger.require_grant(grant_id)
        if grant.digest() != state.grant_digest:
            raise FoundationError(
                "authority-state grant digest does not match the ledger"
            )
        return grant

    def _require_bound_grant_ledger(
        self,
        grant_ledger: AuthorityGrantLedger,
    ) -> None:
        if grant_ledger.digest() != self.grant_ledger_digest:
            raise FoundationError(
                "authority-state snapshot is not bound to the supplied "
                "grant ledger"
            )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this snapshot."""

        state_payloads: JsonArray = [
            state.to_payload()
            for state in self.states
        ]
        return {
            "evaluated_at": self.evaluated_at.isoformat(),
            "grant_ledger_digest": self.grant_ledger_digest.to_payload(),
            "producer_id": str(self.producer_id),
            "revocation_ledger_digest": (
                self.revocation_ledger_digest.to_payload()
            ),
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "states": state_payloads,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical authority-state document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete authority state."""

        return self.to_document().digest(
            domain="authority-state-snapshot"
        )


def resolve_authority_states(
    grants: Iterable[AuthorityGrant],
    *,
    evaluated_at: UtcTimestamp,
    revocations: Iterable[AuthorityRevocation],
) -> tuple[AuthorityGrantState, ...]:
    """Resolve grants directly for deterministic unit-level composition."""

    revocations_by_grant: dict[
        ScopedIdentifier,
        AuthorityRevocation,
    ] = {}

    for revocation in revocations:
        if revocation.grant_id in revocations_by_grant:
            raise FoundationError(
                "multiple terminal revocations reference the same grant"
            )
        revocations_by_grant[revocation.grant_id] = revocation

    states = (
        AuthorityGrantState.resolve(
            grant=grant,
            evaluated_at=evaluated_at,
            revocation=revocations_by_grant.get(grant.grant_id),
        )
        for grant in grants
    )
    return tuple(
        sorted(
            states,
            key=lambda state: str(state.grant_id),
        )
    )
