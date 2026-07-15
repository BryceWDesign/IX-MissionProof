"""Canonical capability definitions for bounded MissionProof authority."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.foundation import (
    ActorKind,
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


class CapabilityOperation(StrEnum):
    """Operations that a governed actor may request permission to perform."""

    OBSERVE = "observe"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    ACCESS_SECRET = "access-secret"
    UPDATE_MEMORY = "update-memory"
    ISSUE_EVIDENCE = "issue-evidence"
    REVIEW_EVIDENCE = "review-evidence"
    AUTHORIZE_ACTION = "authorize-action"
    OVERRIDE_CONTROL = "override-control"
    REVOKE_AUTHORITY = "revoke-authority"

    @property
    def is_human_only(self) -> bool:
        """Return whether the operation must remain exclusively human-held."""

        return self in _HUMAN_ONLY_OPERATIONS


class CapabilityRiskTier(StrEnum):
    """Risk classification attached to a capability definition."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return the deterministic ordering rank for this risk tier."""

        return {
            CapabilityRiskTier.LOW: 0,
            CapabilityRiskTier.MODERATE: 1,
            CapabilityRiskTier.HIGH: 2,
            CapabilityRiskTier.CRITICAL: 3,
        }[self]

    def meets_or_exceeds(self, other: CapabilityRiskTier) -> bool:
        """Return whether this tier is at least as severe as another tier."""

        if not isinstance(other, CapabilityRiskTier):
            raise FoundationError("other must be a CapabilityRiskTier")
        return self.rank >= other.rank


_HUMAN_ONLY_OPERATIONS: Final[frozenset[CapabilityOperation]] = frozenset(
    {
        CapabilityOperation.AUTHORIZE_ACTION,
        CapabilityOperation.OVERRIDE_CONTROL,
        CapabilityOperation.REVOKE_AUTHORITY,
    }
)

_NON_EXECUTING_ACTOR_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.ORGANIZATION,
    }
)


def _normalize_actor_kinds(
    values: Iterable[ActorKind],
) -> tuple[ActorKind, ...]:
    normalized: set[ActorKind] = set()

    for index, value in enumerate(values):
        if not isinstance(value, ActorKind):
            raise FoundationError(
                f"permitted_actor_kinds[{index}] must be an ActorKind"
            )
        if value in _NON_EXECUTING_ACTOR_KINDS:
            raise FoundationError(
                f"actor kind {value.value} cannot directly exercise capabilities"
            )
        normalized.add(value)

    if not normalized:
        raise FoundationError("permitted_actor_kinds must not be empty")

    return tuple(sorted(normalized, key=lambda actor_kind: actor_kind.value))


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    """An immutable description of one bounded operation over a target type."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("capability-definition-v1")

    capability_id: ScopedIdentifier
    operation: CapabilityOperation
    target_type: CanonicalKey
    summary: str
    risk_tier: CapabilityRiskTier
    permitted_actor_kinds: tuple[ActorKind, ...]
    requires_evidence: bool = True
    requires_separate_human_authorization: bool = False
    reversible: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, ScopedIdentifier):
            raise FoundationError("capability_id must be a ScopedIdentifier")
        if self.capability_id.namespace != CanonicalKey("capability"):
            raise FoundationError("capability_id namespace must be capability")
        if not isinstance(self.operation, CapabilityOperation):
            raise FoundationError("operation must be a CapabilityOperation")
        if not isinstance(self.target_type, CanonicalKey):
            raise FoundationError("target_type must be a CanonicalKey")
        if not isinstance(self.risk_tier, CapabilityRiskTier):
            raise FoundationError("risk_tier must be a CapabilityRiskTier")
        if not isinstance(self.requires_evidence, bool):
            raise FoundationError("requires_evidence must be a boolean")
        if not isinstance(self.requires_separate_human_authorization, bool):
            raise FoundationError(
                "requires_separate_human_authorization must be a boolean"
            )
        if not isinstance(self.reversible, bool):
            raise FoundationError("reversible must be a boolean")
        if not isinstance(self.enabled, bool):
            raise FoundationError("enabled must be a boolean")

        object.__setattr__(
            self,
            "summary",
            require_text(self.summary, field_name="summary"),
        )
        object.__setattr__(
            self,
            "permitted_actor_kinds",
            _normalize_actor_kinds(self.permitted_actor_kinds),
        )

        if self.operation.is_human_only and self.permitted_actor_kinds != (
            ActorKind.HUMAN,
        ):
            raise FoundationError(
                f"operation {self.operation.value} must be restricted to human actors"
            )

        if (
            self.risk_tier.meets_or_exceeds(CapabilityRiskTier.HIGH)
            and not self.requires_evidence
        ):
            raise FoundationError(
                "high-risk and critical capabilities must require evidence"
            )

        if not self.reversible:
            if not self.requires_evidence:
                raise FoundationError(
                    "irreversible capabilities must require evidence"
                )
            if not self.requires_separate_human_authorization:
                raise FoundationError(
                    "irreversible capabilities must require separate human authorization"
                )

        if (
            self.risk_tier is CapabilityRiskTier.CRITICAL
            and self.is_machine_exercisable
            and not self.requires_separate_human_authorization
        ):
            raise FoundationError(
                "machine-exercisable critical capabilities must require "
                "separate human authorization"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        operation: CapabilityOperation,
        target_type: str,
        summary: str,
        risk_tier: CapabilityRiskTier,
        permitted_actor_kinds: Iterable[ActorKind],
        requires_evidence: bool = True,
        requires_separate_human_authorization: bool = False,
        reversible: bool = True,
        enabled: bool = True,
    ) -> CapabilityDefinition:
        """Create a normalized capability definition."""

        return cls(
            capability_id=ScopedIdentifier.create(
                namespace="capability",
                key=key,
                namespace_field="capability namespace",
                key_field="capability key",
            ),
            operation=operation,
            target_type=CanonicalKey.from_text(
                target_type,
                field_name="target_type",
            ),
            summary=summary,
            risk_tier=risk_tier,
            permitted_actor_kinds=tuple(permitted_actor_kinds),
            requires_evidence=requires_evidence,
            requires_separate_human_authorization=(
                requires_separate_human_authorization
            ),
            reversible=reversible,
            enabled=enabled,
        )

    @property
    def human_only(self) -> bool:
        """Return whether only human actors may exercise this capability."""

        return self.permitted_actor_kinds == (ActorKind.HUMAN,)

    @property
    def is_machine_exercisable(self) -> bool:
        """Return whether at least one executable machine actor kind is permitted."""

        return any(
            actor_kind.is_machine
            for actor_kind in self.permitted_actor_kinds
        )

    @property
    def requires_human_boundary(self) -> bool:
        """Return whether a human boundary is intrinsic to this capability."""

        return (
            self.human_only
            or self.requires_separate_human_authorization
        )

    def allows_actor_kind(self, actor_kind: ActorKind) -> bool:
        """Return whether an actor kind is eligible to request this capability."""

        if not isinstance(actor_kind, ActorKind):
            raise FoundationError("actor_kind must be an ActorKind")
        return self.enabled and actor_kind in self.permitted_actor_kinds

    def to_payload(self) -> JsonObject:
        """Return the deterministic JSON representation of this capability."""

        actor_kinds: JsonArray = [
            actor_kind.value
            for actor_kind in self.permitted_actor_kinds
        ]
        return {
            "capability_id": str(self.capability_id),
            "enabled": self.enabled,
            "human_only": self.human_only,
            "operation": self.operation.value,
            "permitted_actor_kinds": actor_kinds,
            "requires_evidence": self.requires_evidence,
            "requires_human_boundary": self.requires_human_boundary,
            "requires_separate_human_authorization": (
                self.requires_separate_human_authorization
            ),
            "reversible": self.reversible,
            "risk_tier": self.risk_tier.value,
            "schema": self.SCHEMA.value,
            "summary": self.summary,
            "target_type": self.target_type.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical capability document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete capability definition."""

        return self.to_document().digest(domain="capability-definition")


@dataclass(frozen=True, slots=True)
class CapabilityCatalog:
    """A deterministic closed snapshot of supported capabilities."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("capability-catalog-v1")

    catalog_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    capabilities: tuple[CapabilityDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.catalog_id, ScopedIdentifier):
            raise FoundationError("catalog_id must be a ScopedIdentifier")
        if self.catalog_id.namespace != CanonicalKey("capability-catalog"):
            raise FoundationError(
                "catalog_id namespace must be capability-catalog"
            )
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError("producer_id must be a ScopedIdentifier")

        capabilities = tuple(self.capabilities)
        for index, capability in enumerate(capabilities):
            if not isinstance(capability, CapabilityDefinition):
                raise FoundationError(
                    f"capabilities[{index}] must be a CapabilityDefinition"
                )

        capability_ids = tuple(
            capability.capability_id
            for capability in capabilities
        )
        if len(capability_ids) != len(set(capability_ids)):
            raise FoundationError(
                "capability catalog must contain unique capability IDs"
            )

        semantic_keys = tuple(
            (capability.operation, capability.target_type)
            for capability in capabilities
        )
        if len(semantic_keys) != len(set(semantic_keys)):
            raise FoundationError(
                "capability catalog must not contain duplicate "
                "operation and target combinations"
            )

        object.__setattr__(
            self,
            "capabilities",
            tuple(
                sorted(
                    capabilities,
                    key=lambda capability: str(capability.capability_id),
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
        capabilities: Iterable[CapabilityDefinition],
    ) -> CapabilityCatalog:
        """Create a deterministic capability-catalog snapshot."""

        return cls(
            catalog_id=ScopedIdentifier.create(
                namespace="capability-catalog",
                key=key,
                namespace_field="catalog namespace",
                key_field="catalog key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            capabilities=tuple(capabilities),
        )

    def capability_for(
        self,
        capability_id: ScopedIdentifier,
    ) -> CapabilityDefinition | None:
        """Return a capability definition when it exists in this snapshot."""

        for capability in self.capabilities:
            if capability.capability_id == capability_id:
                return capability
        return None

    def require_capability(
        self,
        capability_id: ScopedIdentifier,
    ) -> CapabilityDefinition:
        """Return a capability or fail when the definition is absent."""

        capability = self.capability_for(capability_id)
        if capability is None:
            raise FoundationError(
                f"capability catalog does not contain capability: {capability_id}"
            )
        return capability

    def enabled_capabilities(self) -> tuple[CapabilityDefinition, ...]:
        """Return all enabled capabilities in canonical identifier order."""

        return tuple(
            capability
            for capability in self.capabilities
            if capability.enabled
        )

    def capabilities_for_kind(
        self,
        actor_kind: ActorKind,
    ) -> tuple[CapabilityDefinition, ...]:
        """Return enabled capabilities available to an actor kind."""

        if not isinstance(actor_kind, ActorKind):
            raise FoundationError("actor_kind must be an ActorKind")
        return tuple(
            capability
            for capability in self.capabilities
            if capability.allows_actor_kind(actor_kind)
        )

    def critical_machine_capabilities(
        self,
    ) -> tuple[CapabilityDefinition, ...]:
        """Return enabled critical capabilities exercisable by machines."""

        return tuple(
            capability
            for capability in self.capabilities
            if capability.enabled
            and capability.risk_tier is CapabilityRiskTier.CRITICAL
            and capability.is_machine_exercisable
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this catalog."""

        capability_payloads: JsonArray = [
            capability.to_payload()
            for capability in self.capabilities
        ]
        return {
            "capabilities": capability_payloads,
            "catalog_id": str(self.catalog_id),
            "created_at": self.created_at.isoformat(),
            "producer_id": str(self.producer_id),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical catalog document."""

        return CanonicalJsonDocument.from_value(self.canonical_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete catalog snapshot."""

        return self.to_document().digest(domain="capability-catalog")
