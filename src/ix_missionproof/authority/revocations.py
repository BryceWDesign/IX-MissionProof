"""Terminal human-issued revocation records for IX-MissionProof."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.authority.grants import AuthorityGrant, AuthorityGrantLedger
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorRegistry,
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonArray,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
    require_text,
)


class AuthorityRevocationReason(StrEnum):
    """Controlled reasons for permanently withdrawing an authority grant."""

    HUMAN_WITHDRAWAL = "human-withdrawal"
    EVIDENCE_INVALIDATED = "evidence-invalidated"
    ACTOR_SUSPENDED = "actor-suspended"
    POLICY_CHANGED = "policy-changed"
    SCOPE_INVALIDATED = "scope-invalidated"
    SECURITY_INCIDENT = "security-incident"
    SAFETY_HOLD = "safety-hold"
    GRANT_ERROR = "grant-error"


def _normalize_record_ids(
    values: Iterable[ScopedIdentifier],
) -> tuple[ScopedIdentifier, ...]:
    normalized: set[ScopedIdentifier] = set()

    for index, value in enumerate(values):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(
                f"supporting_record_ids[{index}] must be a ScopedIdentifier"
            )
        if value.namespace != CanonicalKey("record"):
            raise FoundationError(
                "supporting_record_ids must identify record values"
            )
        normalized.add(value)

    return tuple(sorted(normalized, key=str))


@dataclass(frozen=True, slots=True)
class AuthorityRevocation:
    """An immutable terminal withdrawal of one exact authority grant."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "authority-revocation-v1"
    )

    revocation_id: ScopedIdentifier
    grant_id: ScopedIdentifier
    revoked_by_id: ScopedIdentifier
    revoked_at: UtcTimestamp
    reason_code: AuthorityRevocationReason
    reason: str
    supporting_record_ids: tuple[ScopedIdentifier, ...]
    grant_digest: ContentDigest
    grant_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        if not isinstance(self.revocation_id, ScopedIdentifier):
            raise FoundationError(
                "revocation_id must be a ScopedIdentifier"
            )
        if self.revocation_id.namespace != CanonicalKey(
            "authority-revocation"
        ):
            raise FoundationError(
                "revocation_id namespace must be authority-revocation"
            )
        if not isinstance(self.grant_id, ScopedIdentifier):
            raise FoundationError(
                "grant_id must be a ScopedIdentifier"
            )
        if self.grant_id.namespace != CanonicalKey("authority-grant"):
            raise FoundationError(
                "grant_id namespace must be authority-grant"
            )
        if not isinstance(self.revoked_by_id, ScopedIdentifier):
            raise FoundationError(
                "revoked_by_id must be a ScopedIdentifier"
            )
        if self.revoked_by_id.namespace != CanonicalKey("human"):
            raise FoundationError(
                "revoked_by_id must identify a human actor"
            )
        if not isinstance(self.revoked_at, UtcTimestamp):
            raise FoundationError(
                "revoked_at must be a UtcTimestamp"
            )
        if not isinstance(self.reason_code, AuthorityRevocationReason):
            raise FoundationError(
                "reason_code must be an AuthorityRevocationReason"
            )

        object.__setattr__(
            self,
            "reason",
            require_text(self.reason, field_name="reason"),
        )

        supporting_record_ids = _normalize_record_ids(
            self.supporting_record_ids
        )
        if not supporting_record_ids:
            raise FoundationError(
                "authority revocation requires at least one supporting record"
            )
        object.__setattr__(
            self,
            "supporting_record_ids",
            supporting_record_ids,
        )

        expected_domains = (
            (
                "grant_digest",
                self.grant_digest,
                CanonicalKey("authority-grant"),
            ),
            (
                "grant_ledger_digest",
                self.grant_ledger_digest,
                CanonicalKey("authority-grant-ledger"),
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                CanonicalKey("actor-registry"),
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

    @classmethod
    def revoke(
        cls,
        *,
        key: str,
        grant_id: ScopedIdentifier,
        revoked_by_id: ScopedIdentifier,
        revoked_at: UtcTimestamp,
        reason_code: AuthorityRevocationReason,
        reason: str,
        supporting_record_ids: Iterable[ScopedIdentifier],
        grant_ledger: AuthorityGrantLedger,
        actor_registry: ActorRegistry,
    ) -> AuthorityRevocation:
        """Permanently revoke one grant through its original human grantor."""

        grant = grant_ledger.require_grant(grant_id)
        revoker = actor_registry.require_actor(revoked_by_id)

        cls._validate_revoker(
            revoker=revoker,
            grant=grant,
        )
        cls._validate_revocation_time(
            grant=grant,
            revoked_at=revoked_at,
        )

        return cls(
            revocation_id=ScopedIdentifier.create(
                namespace="authority-revocation",
                key=key,
                namespace_field="revocation namespace",
                key_field="revocation key",
            ),
            grant_id=grant.grant_id,
            revoked_by_id=revoker.actor_id,
            revoked_at=revoked_at,
            reason_code=reason_code,
            reason=reason,
            supporting_record_ids=tuple(supporting_record_ids),
            grant_digest=grant.digest(),
            grant_ledger_digest=grant_ledger.digest(),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_revoker(
        *,
        revoker: ActorIdentity,
        grant: AuthorityGrant,
    ) -> None:
        if not revoker.is_eligible_for_human_authority:
            raise FoundationError(
                "authority revocation requires an active human actor"
            )
        if revoker.actor_id != grant.granted_by_id:
            raise FoundationError(
                "authority revocation must be issued by the original "
                "human grantor"
            )

    @staticmethod
    def _validate_revocation_time(
        *,
        grant: AuthorityGrant,
        revoked_at: UtcTimestamp,
    ) -> None:
        if revoked_at.value < grant.issued_at.value:
            raise FoundationError(
                "revoked_at must not precede grant issuance"
            )
        if (
            grant.expires_at is not None
            and revoked_at.value >= grant.expires_at.value
        ):
            raise FoundationError(
                "an expired authority grant cannot be revoked"
            )

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this revocation."""

        supporting_payload: JsonArray = [
            str(record_id)
            for record_id in self.supporting_record_ids
        ]
        return {
            "actor_registry_digest": self.actor_registry_digest.to_payload(),
            "grant_digest": self.grant_digest.to_payload(),
            "grant_id": str(self.grant_id),
            "grant_ledger_digest": self.grant_ledger_digest.to_payload(),
            "reason": self.reason,
            "reason_code": self.reason_code.value,
            "revocation_id": str(self.revocation_id),
            "revoked_at": self.revoked_at.isoformat(),
            "revoked_by_id": str(self.revoked_by_id),
            "schema": self.SCHEMA.value,
            "supporting_record_ids": supporting_payload,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical revocation document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete revocation."""

        return self.to_document().digest(domain="authority-revocation")


@dataclass(frozen=True, slots=True)
class AuthorityRevocationLedger:
    """An immutable terminal-revocation snapshot for one grant ledger."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "authority-revocation-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    grant_ledger_digest: ContentDigest
    revocations: tuple[AuthorityRevocation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ledger_id, ScopedIdentifier):
            raise FoundationError(
                "ledger_id must be a ScopedIdentifier"
            )
        if self.ledger_id.namespace != CanonicalKey(
            "authority-revocation-ledger"
        ):
            raise FoundationError(
                "ledger_id namespace must be authority-revocation-ledger"
            )
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )
        if not isinstance(self.grant_ledger_digest, ContentDigest):
            raise FoundationError(
                "grant_ledger_digest must be a ContentDigest"
            )
        if self.grant_ledger_digest.domain != CanonicalKey(
            "authority-grant-ledger"
        ):
            raise FoundationError(
                "grant_ledger_digest domain must be "
                "authority-grant-ledger"
            )

        revocations = tuple(self.revocations)
        for index, revocation in enumerate(revocations):
            if not isinstance(revocation, AuthorityRevocation):
                raise FoundationError(
                    f"revocations[{index}] must be an "
                    "AuthorityRevocation"
                )
            if revocation.revoked_at.value > self.created_at.value:
                raise FoundationError(
                    "revocation ledger must not predate a contained "
                    "revocation"
                )
            if (
                revocation.grant_ledger_digest
                != self.grant_ledger_digest
            ):
                raise FoundationError(
                    "every revocation must bind the same grant ledger"
                )

        revocation_ids = tuple(
            revocation.revocation_id
            for revocation in revocations
        )
        if len(revocation_ids) != len(set(revocation_ids)):
            raise FoundationError(
                "revocation ledger must contain unique revocation IDs"
            )

        revoked_grant_ids = tuple(
            revocation.grant_id
            for revocation in revocations
        )
        if len(revoked_grant_ids) != len(set(revoked_grant_ids)):
            raise FoundationError(
                "an authority grant may be terminally revoked only once"
            )

        object.__setattr__(
            self,
            "revocations",
            tuple(
                sorted(
                    revocations,
                    key=lambda revocation: (
                        revocation.revoked_at.value,
                        str(revocation.revocation_id),
                    ),
                )
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        grant_ledger: AuthorityGrantLedger,
        revocations: Iterable[AuthorityRevocation],
    ) -> AuthorityRevocationLedger:
        """Create and validate a revocation-ledger snapshot."""

        normalized = tuple(revocations)
        grant_ledger_digest = grant_ledger.digest()

        for revocation in normalized:
            grant = grant_ledger.require_grant(
                revocation.grant_id
            )
            if revocation.grant_digest != grant.digest():
                raise FoundationError(
                    "revocation grant digest does not match the "
                    "referenced authority grant"
                )
            if revocation.grant_ledger_digest != grant_ledger_digest:
                raise FoundationError(
                    "revocation references a different grant ledger"
                )

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace="authority-revocation-ledger",
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            grant_ledger_digest=grant_ledger_digest,
            revocations=normalized,
        )

    def revocation_for(
        self,
        grant_id: ScopedIdentifier,
    ) -> AuthorityRevocation | None:
        """Return the terminal revocation for a grant, when present."""

        for revocation in self.revocations:
            if revocation.grant_id == grant_id:
                return revocation
        return None

    def require_revocation(
        self,
        grant_id: ScopedIdentifier,
    ) -> AuthorityRevocation:
        """Return a grant revocation or fail when none exists."""

        revocation = self.revocation_for(grant_id)
        if revocation is None:
            raise FoundationError(
                "revocation ledger does not contain a revocation for "
                f"grant: {grant_id}"
            )
        return revocation

    def is_revoked(
        self,
        grant_id: ScopedIdentifier,
        *,
        at: UtcTimestamp,
    ) -> bool:
        """Return whether a terminal revocation is effective at a time."""

        if not isinstance(at, UtcTimestamp):
            raise FoundationError(
                "at must be a UtcTimestamp"
            )

        revocation = self.revocation_for(grant_id)
        return (
            revocation is not None
            and revocation.revoked_at.value <= at.value
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this ledger."""

        revocation_payloads: JsonArray = [
            revocation.to_payload()
            for revocation in self.revocations
        ]
        return {
            "created_at": self.created_at.isoformat(),
            "grant_ledger_digest": self.grant_ledger_digest.to_payload(),
            "ledger_id": str(self.ledger_id),
            "producer_id": str(self.producer_id),
            "revocations": revocation_payloads,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical revocation-ledger document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete revocation ledger."""

        return self.to_document().digest(
            domain="authority-revocation-ledger"
        )
