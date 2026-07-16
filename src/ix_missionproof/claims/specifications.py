"""Bounded claim specifications and falsifiable evidence obligations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.evidence import EvidenceKind
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonArray,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
    normalize_labels,
    require_text,
)


class ClaimKind(StrEnum):
    """Kinds of bounded assertions represented by MissionProof."""

    CAPABILITY = "capability"
    PERFORMANCE = "performance"
    SAFETY = "safety"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    READINESS = "readiness"
    PROCESS = "process"
    PROVENANCE = "provenance"
    LIMITATION = "limitation"


class ClaimCriticality(StrEnum):
    """Consequence tier assigned before evidence review."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def is_high_consequence(self) -> bool:
        """Return whether independent human review is mandatory."""

        return self in {ClaimCriticality.HIGH, ClaimCriticality.CRITICAL}


class ClaimReviewLevel(StrEnum):
    """Minimum human-review independence required for a claim."""

    HUMAN_REVIEW = "human-review"
    INDEPENDENT_HUMAN_REVIEW = "independent-human-review"

    @property
    def is_independent(self) -> bool:
        """Return whether the reviewer must be independent of the author."""

        return self is ClaimReviewLevel.INDEPENDENT_HUMAN_REVIEW


_INDEPENDENT_KINDS: Final[frozenset[ClaimKind]] = frozenset(
    {ClaimKind.SAFETY, ClaimKind.SECURITY, ClaimKind.COMPLIANCE, ClaimKind.READINESS}
)
_CATALOG_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {ActorKind.HUMAN, ActorKind.SERVICE, ActorKind.SYSTEM}
)


def _texts(
    values: Iterable[str],
    *,
    field_name: str,
    required: bool,
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        text = require_text(value, field_name=f"{field_name}[{index}]")
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            result.append(text)
    if required and not result:
        raise FoundationError(f"{field_name} must contain at least one value")
    return tuple(result)


def _identifiers(
    values: Iterable[ScopedIdentifier],
    *,
    field_name: str,
    required: bool,
) -> tuple[ScopedIdentifier, ...]:
    result: set[ScopedIdentifier] = set()
    for index, value in enumerate(values):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(f"{field_name}[{index}] must be a ScopedIdentifier")
        result.add(value)
    if required and not result:
        raise FoundationError(f"{field_name} must contain at least one identifier")
    return tuple(sorted(result, key=str))


def _kinds(values: Iterable[EvidenceKind]) -> tuple[EvidenceKind, ...]:
    result: set[EvidenceKind] = set()
    for index, value in enumerate(values):
        if not isinstance(value, EvidenceKind):
            raise FoundationError(f"acceptable_kinds[{index}] must be an EvidenceKind")
        result.add(value)
    if not result:
        raise FoundationError(
            "acceptable_kinds must contain at least one evidence kind"
        )
    return tuple(sorted(result, key=lambda value: value.value))


def _actor_snapshot(
    actor: ActorIdentity,
    *,
    role: str,
    allowed_kinds: frozenset[ActorKind] | None = None,
) -> tuple[ActorKind, ScopedIdentifier | None]:
    if not actor.is_active:
        raise FoundationError(f"{role} must be an active actor")
    if allowed_kinds is not None and actor.kind not in allowed_kinds:
        allowed = ", ".join(sorted(kind.value for kind in allowed_kinds))
        raise FoundationError(f"{role} must be one of: {allowed}")
    if actor.kind is ActorKind.ORGANIZATION:
        raise FoundationError(f"organization must not directly act as {role}")
    if actor.kind.is_machine and actor.accountability_owner_id is None:
        raise FoundationError(
            f"machine {role} must identify an accountable human owner"
        )
    return actor.kind, actor.accountability_owner_id


def _validate_actor_binding(
    *,
    actor_id: ScopedIdentifier,
    actor_kind: ActorKind,
    owner_id: ScopedIdentifier | None,
    role: str,
) -> None:
    if actor_id.namespace != CanonicalKey(actor_kind.value):
        raise FoundationError(f"{role}_id namespace must match {role}_kind")
    if actor_kind.is_machine:
        if owner_id is None or owner_id.namespace != CanonicalKey("human"):
            raise FoundationError(
                f"machine {role} must identify an accountable human owner"
            )
    elif owner_id is not None:
        raise FoundationError(
            f"non-machine {role} must not declare an accountability owner"
        )


@dataclass(frozen=True, slots=True)
class ClaimEvidenceRequirement:
    """One evidence obligation and its explicit falsification conditions."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("claim-evidence-requirement-v1")

    requirement_id: ScopedIdentifier
    summary: str
    acceptable_kinds: tuple[EvidenceKind, ...]
    minimum_records: int
    require_primary_evidence: bool
    require_subject_match: bool
    require_independent_producers: bool
    falsification_conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.requirement_id.namespace != CanonicalKey("claim-evidence-requirement"):
            raise FoundationError(
                "requirement_id namespace must be claim-evidence-requirement"
            )
        object.__setattr__(
            self, "summary", require_text(self.summary, field_name="summary")
        )
        object.__setattr__(self, "acceptable_kinds", _kinds(self.acceptable_kinds))
        if isinstance(self.minimum_records, bool) or not isinstance(
            self.minimum_records, int
        ):
            raise FoundationError("minimum_records must be an integer")
        if self.minimum_records < 1:
            raise FoundationError("minimum_records must be at least 1")
        for field_name, value in (
            ("require_primary_evidence", self.require_primary_evidence),
            ("require_subject_match", self.require_subject_match),
            ("require_independent_producers", self.require_independent_producers),
        ):
            if not isinstance(value, bool):
                raise FoundationError(f"{field_name} must be a boolean")
        object.__setattr__(
            self,
            "falsification_conditions",
            _texts(
                self.falsification_conditions,
                field_name="falsification_conditions",
                required=True,
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        summary: str,
        acceptable_kinds: Iterable[EvidenceKind],
        falsification_conditions: Iterable[str],
        minimum_records: int = 1,
        require_primary_evidence: bool = True,
        require_subject_match: bool = True,
        require_independent_producers: bool = False,
    ) -> ClaimEvidenceRequirement:
        """Create an immutable evidence obligation."""

        return cls(
            requirement_id=ScopedIdentifier.create(
                namespace="claim-evidence-requirement",
                key=key,
                namespace_field="requirement namespace",
                key_field="requirement key",
            ),
            summary=summary,
            acceptable_kinds=tuple(acceptable_kinds),
            minimum_records=minimum_records,
            require_primary_evidence=require_primary_evidence,
            require_subject_match=require_subject_match,
            require_independent_producers=require_independent_producers,
            falsification_conditions=tuple(falsification_conditions),
        )

    @property
    def adverse_evidence_must_be_included(self) -> bool:
        """Return the fixed rule that adverse evidence cannot be hidden."""

        return True

    @property
    def establishes_claim(self) -> bool:
        """Return false because an obligation is not proof."""

        return False

    def semantic_payload(self) -> JsonObject:
        """Return the requirement's meaning without its identifier."""

        acceptable: JsonArray = [kind.value for kind in self.acceptable_kinds]
        falsifiers: JsonArray = list(self.falsification_conditions)
        return {
            "acceptable_kinds": acceptable,
            "adverse_evidence_must_be_included": self.adverse_evidence_must_be_included,
            "falsification_conditions": falsifiers,
            "minimum_records": self.minimum_records,
            "require_independent_producers": self.require_independent_producers,
            "require_primary_evidence": self.require_primary_evidence,
            "require_subject_match": self.require_subject_match,
            "summary": self.summary,
        }

    def semantic_digest(self) -> ContentDigest:
        """Return a digest of the obligation's substantive meaning."""

        return ContentDigest.from_payload(
            self.semantic_payload(), domain="claim-evidence-requirement-semantics"
        )

    def to_payload(self) -> JsonObject:
        """Return the deterministic requirement representation."""

        payload = self.semantic_payload()
        payload.update(
            {
                "establishes_claim": self.establishes_claim,
                "requirement_id": str(self.requirement_id),
                "schema": self.SCHEMA.value,
                "semantic_digest": self.semantic_digest().to_payload(),
            }
        )
        return payload

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete requirement."""

        return CanonicalJsonDocument.from_value(self.to_payload()).digest(
            domain="claim-evidence-requirement"
        )


@dataclass(frozen=True, slots=True)
class ClaimSpecification:
    """A bounded assertion with scope, limits, evidence duties, and falsifiers."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("claim-specification-v1")

    claim_id: ScopedIdentifier
    created_at: UtcTimestamp
    authored_by_id: ScopedIdentifier
    author_kind: ActorKind
    author_accountability_owner_id: ScopedIdentifier | None
    kind: ClaimKind
    criticality: ClaimCriticality
    review_level: ClaimReviewLevel
    statement: str
    scope: CanonicalJsonDocument
    subject_ids: tuple[ScopedIdentifier, ...]
    evidence_requirements: tuple[ClaimEvidenceRequirement, ...]
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    prohibited_interpretations: tuple[str, ...]
    actor_registry_digest: ContentDigest
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.claim_id.namespace != CanonicalKey("claim"):
            raise FoundationError("claim_id namespace must be claim")
        _validate_actor_binding(
            actor_id=self.authored_by_id,
            actor_kind=self.author_kind,
            owner_id=self.author_accountability_owner_id,
            role="author",
        )
        if self.author_kind is ActorKind.ORGANIZATION:
            raise FoundationError("organization must not directly author a claim")
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        if not isinstance(self.kind, ClaimKind):
            raise FoundationError("kind must be a ClaimKind")
        if not isinstance(self.criticality, ClaimCriticality):
            raise FoundationError("criticality must be a ClaimCriticality")
        if not isinstance(self.review_level, ClaimReviewLevel):
            raise FoundationError("review_level must be a ClaimReviewLevel")
        if self.actor_registry_digest.domain != CanonicalKey("actor-registry"):
            raise FoundationError("actor_registry_digest domain must be actor-registry")
        if (
            not isinstance(self.scope, CanonicalJsonDocument)
            or not self.scope.require_object()
        ):
            raise FoundationError("claim scope must be a non-empty canonical object")

        requirements = tuple(self.evidence_requirements)
        if not requirements:
            raise FoundationError("claim specifications require evidence requirements")
        if any(not isinstance(item, ClaimEvidenceRequirement) for item in requirements):
            raise FoundationError(
                "evidence_requirements must contain requirement objects"
            )
        ids = tuple(item.requirement_id for item in requirements)
        semantics = tuple(item.semantic_digest() for item in requirements)
        if len(ids) != len(set(ids)):
            raise FoundationError("evidence requirement IDs must be unique")
        if len(semantics) != len(set(semantics)):
            raise FoundationError(
                "equivalent evidence requirements must not be duplicated"
            )

        object.__setattr__(
            self, "statement", require_text(self.statement, field_name="statement")
        )
        object.__setattr__(
            self,
            "subject_ids",
            _identifiers(self.subject_ids, field_name="subject_ids", required=True),
        )
        object.__setattr__(
            self,
            "evidence_requirements",
            tuple(sorted(requirements, key=lambda item: str(item.requirement_id))),
        )
        object.__setattr__(
            self,
            "assumptions",
            _texts(self.assumptions, field_name="assumptions", required=False),
        )
        object.__setattr__(
            self,
            "limitations",
            _texts(self.limitations, field_name="limitations", required=True),
        )
        object.__setattr__(
            self,
            "prohibited_interpretations",
            _texts(
                self.prohibited_interpretations,
                field_name="prohibited_interpretations",
                required=True,
            ),
        )
        object.__setattr__(
            self, "labels", normalize_labels(self.labels, field_name="labels")
        )

        independent_required = (
            self.criticality.is_high_consequence or self.kind in _INDEPENDENT_KINDS
        )
        if independent_required and not self.review_level.is_independent:
            raise FoundationError(
                "high-consequence, safety, security, compliance, and readiness claims "
                "require independent human review"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        authored_by_id: ScopedIdentifier,
        kind: ClaimKind,
        criticality: ClaimCriticality,
        review_level: ClaimReviewLevel,
        statement: str,
        scope: JsonObject,
        subject_ids: Iterable[ScopedIdentifier],
        evidence_requirements: Iterable[ClaimEvidenceRequirement],
        limitations: Iterable[str],
        prohibited_interpretations: Iterable[str],
        actor_registry: ActorRegistry,
        assumptions: Iterable[str] = (),
        labels: Iterable[str] = (),
    ) -> ClaimSpecification:
        """Create a bounded claim from a registered accountable author."""

        author = actor_registry.require_actor(authored_by_id)
        author_kind, owner_id = _actor_snapshot(author, role="claim author")
        return cls(
            claim_id=ScopedIdentifier.create(
                namespace="claim",
                key=key,
                namespace_field="claim namespace",
                key_field="claim key",
            ),
            created_at=created_at,
            authored_by_id=author.actor_id,
            author_kind=author_kind,
            author_accountability_owner_id=owner_id,
            kind=kind,
            criticality=criticality,
            review_level=review_level,
            statement=statement,
            scope=CanonicalJsonDocument.from_value(scope),
            subject_ids=tuple(subject_ids),
            evidence_requirements=tuple(evidence_requirements),
            assumptions=tuple(assumptions),
            limitations=tuple(limitations),
            prohibited_interpretations=tuple(prohibited_interpretations),
            actor_registry_digest=actor_registry.digest(),
            labels=tuple(labels),
        )

    @property
    def requires_independent_review(self) -> bool:
        """Return whether an independent human reviewer is required."""

        return self.review_level.is_independent

    @property
    def establishes_truth(self) -> bool:
        """Return false because a claim specification is only an assertion."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claims never grant execution authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def semantic_payload(self) -> JsonObject:
        """Return claim meaning without identity, author, or creation metadata."""

        requirements: JsonArray = [
            requirement.semantic_payload() for requirement in self.evidence_requirements
        ]
        subjects: JsonArray = [str(subject_id) for subject_id in self.subject_ids]
        return {
            "assumptions": list(self.assumptions),
            "criticality": self.criticality.value,
            "evidence_requirements": requirements,
            "kind": self.kind.value,
            "limitations": list(self.limitations),
            "prohibited_interpretations": list(self.prohibited_interpretations),
            "review_level": self.review_level.value,
            "scope": self.scope.to_value(),
            "statement": self.statement,
            "subject_ids": subjects,
        }

    def semantic_digest(self) -> ContentDigest:
        """Return a digest of the claim's substantive meaning."""

        return ContentDigest.from_payload(
            self.semantic_payload(), domain="claim-semantics"
        )

    def to_payload(self) -> JsonObject:
        """Return the deterministic claim representation."""

        payload = self.semantic_payload()
        payload["evidence_requirements"] = [
            requirement.to_payload() for requirement in self.evidence_requirements
        ]
        payload.update(
            {
                "actor_registry_digest": self.actor_registry_digest.to_payload(),
                "author_accountability_owner_id": (
                    str(self.author_accountability_owner_id)
                    if self.author_accountability_owner_id is not None
                    else None
                ),
                "author_kind": self.author_kind.value,
                "authored_by_id": str(self.authored_by_id),
                "claim_id": str(self.claim_id),
                "claims_certification": self.claims_certification,
                "created_at": self.created_at.isoformat(),
                "establishes_truth": self.establishes_truth,
                "grants_authority": self.grants_authority,
                "labels": list(self.labels),
                "requires_independent_review": self.requires_independent_review,
                "schema": self.SCHEMA.value,
                "semantic_digest": self.semantic_digest().to_payload(),
            }
        )
        return payload

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete claim specification."""

        return CanonicalJsonDocument.from_value(self.to_payload()).digest(
            domain="claim-specification"
        )


@dataclass(frozen=True, slots=True)
class ClaimCatalog:
    """Deterministic catalog of bounded, semantically unique claims."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("claim-catalog-v1")

    catalog_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier | None
    actor_registry_digest: ContentDigest
    claims: tuple[ClaimSpecification, ...]

    def __post_init__(self) -> None:
        if self.catalog_id.namespace != CanonicalKey("claim-catalog"):
            raise FoundationError("catalog_id namespace must be claim-catalog")
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        _validate_actor_binding(
            actor_id=self.producer_id,
            actor_kind=self.producer_kind,
            owner_id=self.producer_accountability_owner_id,
            role="producer",
        )
        if self.producer_kind not in _CATALOG_PRODUCER_KINDS:
            raise FoundationError(
                "claim-catalog producer must be human, service, or system"
            )
        if self.actor_registry_digest.domain != CanonicalKey("actor-registry"):
            raise FoundationError("actor_registry_digest domain must be actor-registry")

        claims = tuple(self.claims)
        if any(not isinstance(claim, ClaimSpecification) for claim in claims):
            raise FoundationError("claims must contain ClaimSpecification values")
        if any(claim.created_at.value > self.created_at.value for claim in claims):
            raise FoundationError("claim catalog must not predate a contained claim")
        if any(
            claim.actor_registry_digest != self.actor_registry_digest
            for claim in claims
        ):
            raise FoundationError("every claim must bind the same actor registry")
        ids = tuple(claim.claim_id for claim in claims)
        semantics = tuple(claim.semantic_digest() for claim in claims)
        if len(ids) != len(set(ids)):
            raise FoundationError("claim catalog must contain unique claim IDs")
        if len(semantics) != len(set(semantics)):
            raise FoundationError(
                "claim catalog must not contain semantically duplicate claims"
            )
        object.__setattr__(
            self, "claims", tuple(sorted(claims, key=lambda claim: str(claim.claim_id)))
        )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        actor_registry: ActorRegistry,
        claims: Iterable[ClaimSpecification] = (),
    ) -> ClaimCatalog:
        """Create a claim catalog from a registered accountable producer."""

        producer = actor_registry.require_actor(producer_id)
        producer_kind, owner_id = _actor_snapshot(
            producer,
            role="claim-catalog producer",
            allowed_kinds=_CATALOG_PRODUCER_KINDS,
        )
        return cls(
            catalog_id=ScopedIdentifier.create(
                namespace="claim-catalog",
                key=key,
                namespace_field="catalog namespace",
                key_field="catalog key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_kind=producer_kind,
            producer_accountability_owner_id=owner_id,
            actor_registry_digest=actor_registry.digest(),
            claims=tuple(claims),
        )

    def claim_for(self, claim_id: ScopedIdentifier) -> ClaimSpecification | None:
        """Return a claim by identifier, when present."""

        return next(
            (claim for claim in self.claims if claim.claim_id == claim_id), None
        )

    def require_claim(self, claim_id: ScopedIdentifier) -> ClaimSpecification:
        """Return a claim or fail when it is absent."""

        claim = self.claim_for(claim_id)
        if claim is None:
            raise FoundationError(f"claim catalog does not contain claim: {claim_id}")
        return claim

    def claims_by_kind(self, kind: ClaimKind) -> tuple[ClaimSpecification, ...]:
        """Return claims of one kind."""

        if not isinstance(kind, ClaimKind):
            raise FoundationError("kind must be a ClaimKind")
        return tuple(claim for claim in self.claims if claim.kind is kind)

    def high_consequence_claims(self) -> tuple[ClaimSpecification, ...]:
        """Return high and critical consequence claims."""

        return tuple(
            claim for claim in self.claims if claim.criticality.is_high_consequence
        )

    def independent_review_claims(self) -> tuple[ClaimSpecification, ...]:
        """Return claims requiring independent human review."""

        return tuple(
            claim for claim in self.claims if claim.requires_independent_review
        )

    @property
    def establishes_truth(self) -> bool:
        """Return false because a catalog is not an adjudication result."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim catalogs do not grant authority."""

        return False

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic claim-catalog representation."""

        claims: JsonArray = [claim.to_payload() for claim in self.claims]
        return {
            "actor_registry_digest": self.actor_registry_digest.to_payload(),
            "catalog_id": str(self.catalog_id),
            "claims": claims,
            "created_at": self.created_at.isoformat(),
            "establishes_truth": self.establishes_truth,
            "grants_authority": self.grants_authority,
            "producer_accountability_owner_id": (
                str(self.producer_accountability_owner_id)
                if self.producer_accountability_owner_id is not None
                else None
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "schema": self.SCHEMA.value,
        }

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete claim catalog."""

        return CanonicalJsonDocument.from_value(self.canonical_payload()).digest(
            domain="claim-catalog"
        )
