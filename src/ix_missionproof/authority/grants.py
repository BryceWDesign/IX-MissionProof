"""Bounded human-issued authority grants for IX-MissionProof."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from ix_missionproof.authority.capabilities import (
    CapabilityCatalog,
    CapabilityDefinition,
)
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
)

_SEPARATE_AUTHORIZATION_CONSTRAINT = "requires_separate_human_authorization"


def _normalize_identifiers(
    values: Iterable[ScopedIdentifier],
    *,
    field_name: str,
) -> tuple[ScopedIdentifier, ...]:
    normalized: set[ScopedIdentifier] = set()

    for index, value in enumerate(values):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(
                f"{field_name}[{index}] must be a ScopedIdentifier"
            )
        normalized.add(value)

    return tuple(sorted(normalized, key=str))


def _bind_capability_constraints(
    constraints: JsonObject | None,
    *,
    capability: CapabilityDefinition,
) -> CanonicalJsonDocument:
    """Bind capability-controlled terms into the immutable grant constraints."""

    payload: JsonObject = dict(constraints) if constraints is not None else {}
    required = capability.requires_separate_human_authorization

    if _SEPARATE_AUTHORIZATION_CONSTRAINT in payload:
        declared = payload[_SEPARATE_AUTHORIZATION_CONSTRAINT]
        if not isinstance(declared, bool):
            raise FoundationError(
                "requires_separate_human_authorization constraint "
                "must be a boolean"
            )
        if declared is not required:
            raise FoundationError(
                "grant constraints must not override the capability's "
                "separate human-authorization requirement"
            )

    payload[_SEPARATE_AUTHORIZATION_CONSTRAINT] = required
    return CanonicalJsonDocument.from_value(payload)


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    """An immutable human-issued grant over one capability and bounded targets."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("authority-grant-v1")

    grant_id: ScopedIdentifier
    grantee_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    granted_by_id: ScopedIdentifier
    issued_at: UtcTimestamp
    valid_from: UtcTimestamp
    expires_at: UtcTimestamp | None
    target_ids: tuple[ScopedIdentifier, ...]
    supporting_record_ids: tuple[ScopedIdentifier, ...]
    constraints: CanonicalJsonDocument
    capability_digest: ContentDigest
    actor_registry_digest: ContentDigest
    capability_catalog_digest: ContentDigest

    def __post_init__(self) -> None:
        if not isinstance(self.grant_id, ScopedIdentifier):
            raise FoundationError("grant_id must be a ScopedIdentifier")
        if self.grant_id.namespace != CanonicalKey("authority-grant"):
            raise FoundationError(
                "grant_id namespace must be authority-grant"
            )
        if not isinstance(self.grantee_id, ScopedIdentifier):
            raise FoundationError("grantee_id must be a ScopedIdentifier")
        if not isinstance(self.capability_id, ScopedIdentifier):
            raise FoundationError(
                "capability_id must be a ScopedIdentifier"
            )
        if self.capability_id.namespace != CanonicalKey("capability"):
            raise FoundationError(
                "capability_id namespace must be capability"
            )
        if not isinstance(self.granted_by_id, ScopedIdentifier):
            raise FoundationError(
                "granted_by_id must be a ScopedIdentifier"
            )
        if self.granted_by_id.namespace != CanonicalKey("human"):
            raise FoundationError(
                "granted_by_id must identify a human actor"
            )
        if self.granted_by_id == self.grantee_id:
            raise FoundationError(
                "an actor must not grant authority to itself"
            )
        if not isinstance(self.issued_at, UtcTimestamp):
            raise FoundationError("issued_at must be a UtcTimestamp")
        if not isinstance(self.valid_from, UtcTimestamp):
            raise FoundationError("valid_from must be a UtcTimestamp")
        if self.expires_at is not None and not isinstance(
            self.expires_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "expires_at must be a UtcTimestamp or None"
            )
        if self.valid_from.value < self.issued_at.value:
            raise FoundationError(
                "valid_from must not precede issued_at"
            )
        if (
            self.expires_at is not None
            and self.expires_at.value <= self.valid_from.value
        ):
            raise FoundationError(
                "expires_at must be later than valid_from"
            )
        if not isinstance(self.constraints, CanonicalJsonDocument):
            raise FoundationError(
                "constraints must be a CanonicalJsonDocument"
            )

        constraint_payload = self.constraints.require_object()
        authorization_requirement = constraint_payload.get(
            _SEPARATE_AUTHORIZATION_CONSTRAINT
        )
        if not isinstance(authorization_requirement, bool):
            raise FoundationError(
                "constraints must contain a boolean "
                "requires_separate_human_authorization value"
            )

        for field_name, digest in (
            ("capability_digest", self.capability_digest),
            ("actor_registry_digest", self.actor_registry_digest),
            ("capability_catalog_digest", self.capability_catalog_digest),
        ):
            if not isinstance(digest, ContentDigest):
                raise FoundationError(
                    f"{field_name} must be a ContentDigest"
                )

        if self.capability_digest.domain != CanonicalKey(
            "capability-definition"
        ):
            raise FoundationError(
                "capability_digest domain must be capability-definition"
            )
        if self.actor_registry_digest.domain != CanonicalKey(
            "actor-registry"
        ):
            raise FoundationError(
                "actor_registry_digest domain must be actor-registry"
            )
        if self.capability_catalog_digest.domain != CanonicalKey(
            "capability-catalog"
        ):
            raise FoundationError(
                "capability_catalog_digest domain must be capability-catalog"
            )

        normalized_targets = _normalize_identifiers(
            self.target_ids,
            field_name="target_ids",
        )
        if not normalized_targets:
            raise FoundationError(
                "authority grants must identify at least one bounded target"
            )

        object.__setattr__(self, "target_ids", normalized_targets)
        object.__setattr__(
            self,
            "supporting_record_ids",
            _normalize_identifiers(
                self.supporting_record_ids,
                field_name="supporting_record_ids",
            ),
        )

    @classmethod
    def issue(
        cls,
        *,
        key: str,
        grantee_id: ScopedIdentifier,
        capability_id: ScopedIdentifier,
        granted_by_id: ScopedIdentifier,
        issued_at: UtcTimestamp,
        actor_registry: ActorRegistry,
        capability_catalog: CapabilityCatalog,
        target_ids: Iterable[ScopedIdentifier],
        supporting_record_ids: Iterable[ScopedIdentifier],
        constraints: JsonObject | None = None,
        valid_from: UtcTimestamp | None = None,
        expires_at: UtcTimestamp | None = None,
    ) -> AuthorityGrant:
        """Issue a grant after validating actors, capability, scope, and evidence."""

        grantor = actor_registry.require_actor(granted_by_id)
        grantee = actor_registry.require_actor(grantee_id)
        capability = capability_catalog.require_capability(capability_id)

        cls._validate_grantor(grantor)
        cls._validate_grantee(grantee, capability)

        normalized_targets = _normalize_identifiers(
            target_ids,
            field_name="target_ids",
        )
        cls._validate_targets(
            target_ids=normalized_targets,
            capability=capability,
        )

        normalized_supporting_records = _normalize_identifiers(
            supporting_record_ids,
            field_name="supporting_record_ids",
        )
        if (
            capability.requires_evidence
            and not normalized_supporting_records
        ):
            raise FoundationError(
                "capability requires at least one supporting record"
            )

        effective_from = valid_from or issued_at

        return cls(
            grant_id=ScopedIdentifier.create(
                namespace="authority-grant",
                key=key,
                namespace_field="grant namespace",
                key_field="grant key",
            ),
            grantee_id=grantee_id,
            capability_id=capability_id,
            granted_by_id=granted_by_id,
            issued_at=issued_at,
            valid_from=effective_from,
            expires_at=expires_at,
            target_ids=normalized_targets,
            supporting_record_ids=normalized_supporting_records,
            constraints=_bind_capability_constraints(
                constraints,
                capability=capability,
            ),
            capability_digest=capability.digest(),
            actor_registry_digest=actor_registry.digest(),
            capability_catalog_digest=capability_catalog.digest(),
        )

    @staticmethod
    def _validate_grantor(grantor: ActorIdentity) -> None:
        if not grantor.is_eligible_for_human_authority:
            raise FoundationError(
                "authority grants must be issued by an active human actor"
            )

    @staticmethod
    def _validate_grantee(
        grantee: ActorIdentity,
        capability: CapabilityDefinition,
    ) -> None:
        if not grantee.is_active:
            raise FoundationError(
                "authority grants require an active grantee"
            )
        if not capability.enabled:
            raise FoundationError(
                "disabled capabilities must not be granted"
            )
        if not capability.allows_actor_kind(grantee.kind):
            raise FoundationError(
                f"capability {capability.capability_id} does not permit "
                f"actor kind {grantee.kind.value}"
            )

    @staticmethod
    def _validate_targets(
        *,
        target_ids: tuple[ScopedIdentifier, ...],
        capability: CapabilityDefinition,
    ) -> None:
        if not target_ids:
            raise FoundationError(
                "authority grants must identify at least one bounded target"
            )

        for target_id in target_ids:
            if target_id.namespace != capability.target_type:
                raise FoundationError(
                    f"target {target_id} does not match capability target "
                    f"type {capability.target_type.value}"
                )

    @property
    def requires_runtime_authorization(self) -> bool:
        """Return whether each action still requires separate human approval.

        A standing grant never satisfies a capability's explicit requirement
        for separate runtime authorization.
        """

        return self.capability_requires_separate_authorization

    @property
    def capability_requires_separate_authorization(self) -> bool:
        """Return the capability-controlled authorization requirement."""

        payload = self.constraints.require_object()
        value = payload.get(_SEPARATE_AUTHORIZATION_CONSTRAINT)
        if not isinstance(value, bool):
            raise FoundationError(
                "grant constraints lost the bound authorization requirement"
            )
        return value

    def is_time_effective(self, at: UtcTimestamp) -> bool:
        """Return whether this grant is inside its declared time window."""

        if not isinstance(at, UtcTimestamp):
            raise FoundationError("at must be a UtcTimestamp")
        if at.value < self.valid_from.value:
            return False
        if self.expires_at is not None and at.value >= self.expires_at.value:
            return False
        return True

    def covers_target(self, target_id: ScopedIdentifier) -> bool:
        """Return whether this grant explicitly covers an exact target."""

        if not isinstance(target_id, ScopedIdentifier):
            raise FoundationError(
                "target_id must be a ScopedIdentifier"
            )
        return target_id in self.target_ids

    def to_payload(self) -> JsonObject:
        """Return the deterministic JSON representation of this grant."""

        target_payload: JsonArray = [
            str(target_id)
            for target_id in self.target_ids
        ]
        supporting_payload: JsonArray = [
            str(record_id)
            for record_id in self.supporting_record_ids
        ]

        return {
            "actor_registry_digest": self.actor_registry_digest.to_payload(),
            "capability_catalog_digest": (
                self.capability_catalog_digest.to_payload()
            ),
            "capability_digest": self.capability_digest.to_payload(),
            "capability_id": str(self.capability_id),
            "constraints": self.constraints.to_value(),
            "expires_at": (
                self.expires_at.isoformat()
                if self.expires_at is not None
                else None
            ),
            "grant_id": str(self.grant_id),
            "granted_by_id": str(self.granted_by_id),
            "grantee_id": str(self.grantee_id),
            "issued_at": self.issued_at.isoformat(),
            "schema": self.SCHEMA.value,
            "supporting_record_ids": supporting_payload,
            "target_ids": target_payload,
            "valid_from": self.valid_from.isoformat(),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical grant document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete authority grant."""

        return self.to_document().digest(domain="authority-grant")


@dataclass(frozen=True, slots=True)
class AuthorityGrantLedger:
    """A deterministic immutable snapshot of issued authority grants."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "authority-grant-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    grants: tuple[AuthorityGrant, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ledger_id, ScopedIdentifier):
            raise FoundationError(
                "ledger_id must be a ScopedIdentifier"
            )
        if self.ledger_id.namespace != CanonicalKey(
            "authority-grant-ledger"
        ):
            raise FoundationError(
                "ledger_id namespace must be authority-grant-ledger"
            )
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )

        grants = tuple(self.grants)
        for index, grant in enumerate(grants):
            if not isinstance(grant, AuthorityGrant):
                raise FoundationError(
                    f"grants[{index}] must be an AuthorityGrant"
                )
            if grant.issued_at.value > self.created_at.value:
                raise FoundationError(
                    "authority-grant ledger must not predate a contained grant"
                )

        grant_ids = tuple(grant.grant_id for grant in grants)
        if len(grant_ids) != len(set(grant_ids)):
            raise FoundationError(
                "authority-grant ledger must contain unique grant IDs"
            )

        object.__setattr__(
            self,
            "grants",
            tuple(
                sorted(
                    grants,
                    key=lambda grant: (
                        grant.issued_at.value,
                        str(grant.grant_id),
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
        grants: Iterable[AuthorityGrant],
    ) -> AuthorityGrantLedger:
        """Create a deterministic authority-grant ledger snapshot."""

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace="authority-grant-ledger",
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            grants=tuple(grants),
        )

    def grant_for(
        self,
        grant_id: ScopedIdentifier,
    ) -> AuthorityGrant | None:
        """Return a grant when it exists in this ledger."""

        for grant in self.grants:
            if grant.grant_id == grant_id:
                return grant
        return None

    def require_grant(
        self,
        grant_id: ScopedIdentifier,
    ) -> AuthorityGrant:
        """Return a grant or fail when its identifier is absent."""

        grant = self.grant_for(grant_id)
        if grant is None:
            raise FoundationError(
                f"authority-grant ledger does not contain grant: {grant_id}"
            )
        return grant

    def grants_for_actor(
        self,
        actor_id: ScopedIdentifier,
    ) -> tuple[AuthorityGrant, ...]:
        """Return all grants issued to an actor."""

        return tuple(
            grant
            for grant in self.grants
            if grant.grantee_id == actor_id
        )

    def effective_grants_for_actor(
        self,
        actor_id: ScopedIdentifier,
        *,
        at: UtcTimestamp,
    ) -> tuple[AuthorityGrant, ...]:
        """Return time-effective grants issued to an actor.

        Revocation is intentionally not evaluated here. A revocation-aware
        authority-state snapshot must be used before execution.
        """

        return tuple(
            grant
            for grant in self.grants_for_actor(actor_id)
            if grant.is_time_effective(at)
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this ledger."""

        grant_payloads: JsonArray = [
            grant.to_payload()
            for grant in self.grants
        ]
        return {
            "created_at": self.created_at.isoformat(),
            "grants": grant_payloads,
            "ledger_id": str(self.ledger_id),
            "producer_id": str(self.producer_id),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical grant-ledger document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete grant ledger."""

        return self.to_document().digest(domain="authority-grant-ledger")
