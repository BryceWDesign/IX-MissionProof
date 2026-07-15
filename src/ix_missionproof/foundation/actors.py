"""Canonical actor identities and registry snapshots for IX-MissionProof."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.foundation.digests import ContentDigest
from ix_missionproof.foundation.documents import CanonicalJsonDocument
from ix_missionproof.foundation.errors import FoundationError
from ix_missionproof.foundation.identifiers import CanonicalKey, ScopedIdentifier
from ix_missionproof.foundation.serialization import JsonArray, JsonObject
from ix_missionproof.foundation.text import require_optional_text, require_text
from ix_missionproof.foundation.time import UtcTimestamp


class ActorKind(StrEnum):
    """Kinds of accountable actors that may appear in MissionProof records."""

    HUMAN = "human"
    MODEL = "model"
    AGENT = "agent"
    SERVICE = "service"
    SYSTEM = "system"
    POLICY = "policy"
    SENSOR = "sensor"
    ORGANIZATION = "organization"
    BUILD_SYSTEM = "build-system"

    @property
    def is_human(self) -> bool:
        """Return whether this kind represents a human actor."""

        return self is ActorKind.HUMAN

    @property
    def is_machine(self) -> bool:
        """Return whether this kind represents executable machine behavior."""

        return self in {
            ActorKind.MODEL,
            ActorKind.AGENT,
            ActorKind.SERVICE,
            ActorKind.SYSTEM,
            ActorKind.POLICY,
            ActorKind.SENSOR,
            ActorKind.BUILD_SYSTEM,
        }


class ActorStatus(StrEnum):
    """Lifecycle status of an actor identity."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"

    @property
    def may_participate(self) -> bool:
        """Return whether the actor may participate in a new governed run."""

        return self is ActorStatus.ACTIVE


def _normalize_roles(
    values: Iterable[CanonicalKey | str],
) -> tuple[CanonicalKey, ...]:
    roles: list[CanonicalKey] = []
    seen: set[CanonicalKey] = set()

    for index, value in enumerate(values):
        role = (
            value
            if isinstance(value, CanonicalKey)
            else CanonicalKey.from_text(value, field_name=f"roles[{index}]")
        )
        if role in seen:
            continue
        seen.add(role)
        roles.append(role)

    return tuple(roles)


@dataclass(frozen=True, slots=True)
class ActorIdentity:
    """An immutable identity declaration for one accountable actor."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("actor-identity-v1")

    actor_id: ScopedIdentifier
    kind: ActorKind
    display_name: str
    status: ActorStatus = ActorStatus.ACTIVE
    roles: tuple[CanonicalKey, ...] = ()
    organization: str | None = None
    accountability_owner_id: ScopedIdentifier | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, ScopedIdentifier):
            raise FoundationError("actor_id must be a ScopedIdentifier")
        if not isinstance(self.kind, ActorKind):
            raise FoundationError("kind must be an ActorKind")
        if not isinstance(self.status, ActorStatus):
            raise FoundationError("status must be an ActorStatus")

        expected_namespace = CanonicalKey(self.kind.value)
        if self.actor_id.namespace != expected_namespace:
            raise FoundationError(
                "actor_id namespace must match the actor kind: "
                f"expected {expected_namespace.value}"
            )

        object.__setattr__(
            self,
            "display_name",
            require_text(self.display_name, field_name="display_name"),
        )
        object.__setattr__(
            self,
            "organization",
            require_optional_text(self.organization, field_name="organization"),
        )
        object.__setattr__(self, "roles", _normalize_roles(self.roles))

        if self.accountability_owner_id is not None:
            if not isinstance(self.accountability_owner_id, ScopedIdentifier):
                raise FoundationError(
                    "accountability_owner_id must be a ScopedIdentifier or None"
                )
            if self.accountability_owner_id == self.actor_id:
                raise FoundationError("an actor must not be its own accountability owner")
            if self.accountability_owner_id.namespace != CanonicalKey("human"):
                raise FoundationError(
                    "accountability_owner_id must identify a human actor"
                )

        if self.kind is ActorKind.HUMAN and self.accountability_owner_id is not None:
            raise FoundationError(
                "human actors must not delegate their identity accountability "
                "to another actor"
            )

    @classmethod
    def create(
        cls,
        *,
        kind: ActorKind,
        key: str,
        display_name: str,
        status: ActorStatus = ActorStatus.ACTIVE,
        roles: Iterable[CanonicalKey | str] = (),
        organization: str | None = None,
        accountability_owner_id: ScopedIdentifier | None = None,
    ) -> ActorIdentity:
        """Create an actor with an identifier namespace derived from its kind."""

        if not isinstance(kind, ActorKind):
            raise FoundationError("kind must be an ActorKind")

        return cls(
            actor_id=ScopedIdentifier.create(
                namespace=kind.value,
                key=key,
                namespace_field="actor kind",
                key_field="actor key",
            ),
            kind=kind,
            display_name=display_name,
            status=status,
            roles=tuple(roles),
            organization=organization,
            accountability_owner_id=accountability_owner_id,
        )

    @property
    def is_active(self) -> bool:
        """Return whether the identity may participate in a new governed run."""

        return self.status.may_participate

    @property
    def is_human(self) -> bool:
        """Return whether this identity represents a human actor."""

        return self.kind.is_human

    @property
    def is_machine(self) -> bool:
        """Return whether this identity represents executable machine behavior."""

        return self.kind.is_machine

    @property
    def is_eligible_for_human_authority(self) -> bool:
        """Return whether this actor may be considered for human authority.

        Eligibility does not itself grant authority. A later authority record
        must explicitly grant a bounded permission or decision role.
        """

        return self.is_human and self.is_active

    @property
    def has_accountability_owner(self) -> bool:
        """Return whether this actor names an accountable human owner."""

        return self.accountability_owner_id is not None

    def has_role(self, role: CanonicalKey | str) -> bool:
        """Return whether the identity declares a canonical role."""

        canonical_role = (
            role
            if isinstance(role, CanonicalKey)
            else CanonicalKey.from_text(role, field_name="role")
        )
        return canonical_role in self.roles

    def to_payload(self) -> JsonObject:
        """Return the deterministic JSON representation of this identity."""

        role_values: JsonArray = [role.value for role in self.roles]
        return {
            "accountability_owner_id": (
                str(self.accountability_owner_id)
                if self.accountability_owner_id is not None
                else None
            ),
            "actor_id": str(self.actor_id),
            "display_name": self.display_name,
            "kind": self.kind.value,
            "organization": self.organization,
            "roles": role_values,
            "schema": self.SCHEMA.value,
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return an immutable canonical document for this identity."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a domain-separated digest covering the complete identity."""

        return self.to_document().digest(domain="actor-identity")


@dataclass(frozen=True, slots=True)
class ActorRegistry:
    """A deterministic closed snapshot of actors participating in a system."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("actor-registry-v1")

    registry_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    actors: tuple[ActorIdentity, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.registry_id, ScopedIdentifier):
            raise FoundationError("registry_id must be a ScopedIdentifier")
        if self.registry_id.namespace != CanonicalKey("actor-registry"):
            raise FoundationError(
                "registry_id namespace must be actor-registry"
            )
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError("producer_id must be a ScopedIdentifier")

        actors = tuple(self.actors)
        for index, actor in enumerate(actors):
            if not isinstance(actor, ActorIdentity):
                raise FoundationError(
                    f"actors[{index}] must be an ActorIdentity"
                )

        actor_ids = tuple(actor.actor_id for actor in actors)
        if len(actor_ids) != len(set(actor_ids)):
            raise FoundationError("actor registry must contain unique actor IDs")

        ordered_actors = tuple(
            sorted(actors, key=lambda actor: str(actor.actor_id))
        )
        actors_by_id = {
            actor.actor_id: actor
            for actor in ordered_actors
        }

        for actor in ordered_actors:
            owner_id = actor.accountability_owner_id
            if owner_id is None:
                continue

            owner = actors_by_id.get(owner_id)
            if owner is None:
                raise FoundationError(
                    "actor registry contains an unresolved accountability owner: "
                    f"{owner_id}"
                )
            if not owner.is_human:
                raise FoundationError(
                    "accountability owners must resolve to human actors"
                )
            if not owner.is_active:
                raise FoundationError(
                    "accountability owners must be active human actors"
                )

        object.__setattr__(self, "actors", ordered_actors)

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        actors: Iterable[ActorIdentity],
    ) -> ActorRegistry:
        """Create a deterministic actor-registry snapshot."""

        return cls(
            registry_id=ScopedIdentifier.create(
                namespace="actor-registry",
                key=key,
                namespace_field="registry namespace",
                key_field="registry key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            actors=tuple(actors),
        )

    def actor_for(
        self,
        actor_id: ScopedIdentifier,
    ) -> ActorIdentity | None:
        """Return the identified actor when it exists in this snapshot."""

        for actor in self.actors:
            if actor.actor_id == actor_id:
                return actor
        return None

    def require_actor(
        self,
        actor_id: ScopedIdentifier,
    ) -> ActorIdentity:
        """Return an actor or fail when the identity is absent."""

        actor = self.actor_for(actor_id)
        if actor is None:
            raise FoundationError(
                f"actor registry does not contain actor: {actor_id}"
            )
        return actor

    def active_actors(self) -> tuple[ActorIdentity, ...]:
        """Return all active actors in canonical identifier order."""

        return tuple(actor for actor in self.actors if actor.is_active)

    def machine_actors_without_accountability(
        self,
    ) -> tuple[ActorIdentity, ...]:
        """Return active machine actors lacking an accountable human owner."""

        return tuple(
            actor
            for actor in self.actors
            if actor.is_active
            and actor.is_machine
            and not actor.has_accountability_owner
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this registry."""

        actor_payloads: JsonArray = [
            actor.to_payload()
            for actor in self.actors
        ]
        return {
            "actors": actor_payloads,
            "created_at": self.created_at.isoformat(),
            "producer_id": str(self.producer_id),
            "registry_id": str(self.registry_id),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical registry document."""

        return CanonicalJsonDocument.from_value(self.canonical_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete registry snapshot."""

        return self.to_document().digest(domain="actor-registry")
