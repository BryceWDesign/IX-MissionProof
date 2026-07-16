"""Independent human adjudications for bounded MissionProof claims."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.claims.evaluations import (
    ClaimEvidenceEvaluation,
    ClaimEvidenceEvaluationStatus,
)
from ix_missionproof.claims.specifications import (
    ClaimCatalog,
    ClaimReviewLevel,
    ClaimSpecification,
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
    require_text,
)


class ClaimAdjudicationDecisionStatus(StrEnum):
    """Human dispositions for one bounded claim evidence evaluation."""

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not-supported"
    DEFERRED = "deferred"

    @property
    def is_terminal(self) -> bool:
        """Return whether this disposition closes the evaluated claim."""

        return self in {
            ClaimAdjudicationDecisionStatus.SUPPORTED,
            ClaimAdjudicationDecisionStatus.NOT_SUPPORTED,
        }

    @property
    def supports_claim(self) -> bool:
        """Return whether this disposition supports the bounded claim."""

        return self is ClaimAdjudicationDecisionStatus.SUPPORTED


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
            raise FoundationError("supporting_record_ids must identify record values")
        normalized.add(value)

    return tuple(sorted(normalized, key=str))


def _require_digest(
    value: ContentDigest,
    *,
    field_name: str,
    domain: str,
) -> None:
    if not isinstance(value, ContentDigest):
        raise FoundationError(f"{field_name} must be a ContentDigest")
    if value.domain != CanonicalKey(domain):
        raise FoundationError(f"{field_name} domain must be {domain}")


@dataclass(frozen=True, slots=True)
class ClaimAdjudicationDecision:
    """An independent human judgment over one exact claim evaluation."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("claim-adjudication-decision-v1")

    decision_id: ScopedIdentifier
    decided_at: UtcTimestamp
    decided_by_id: ScopedIdentifier
    status: ClaimAdjudicationDecisionStatus
    rationale: str
    claim_id: ScopedIdentifier
    evaluation_id: ScopedIdentifier
    review_level: ClaimReviewLevel
    reviewer_independent: bool
    supporting_record_ids: tuple[ScopedIdentifier, ...]
    claim_digest: ContentDigest
    evaluation_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    resolution_snapshot_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_identifiers()
        self._validate_types()
        self._validate_digests()

        object.__setattr__(
            self,
            "rationale",
            require_text(
                self.rationale,
                field_name="rationale",
            ),
        )
        supporting_record_ids = _normalize_record_ids(self.supporting_record_ids)
        object.__setattr__(
            self,
            "supporting_record_ids",
            supporting_record_ids,
        )

        if self.status.supports_claim and not supporting_record_ids:
            raise FoundationError(
                "supported claim decisions require at least one "
                "supporting evidence record"
            )
        if self.review_level.is_independent and not self.reviewer_independent:
            raise FoundationError(
                "independent-review claims require an independent reviewer"
            )

    def _validate_identifiers(self) -> None:
        expected_identifiers = (
            (
                "decision_id",
                self.decision_id,
                CanonicalKey("claim-adjudication-decision"),
            ),
            (
                "claim_id",
                self.claim_id,
                CanonicalKey("claim"),
            ),
            (
                "evaluation_id",
                self.evaluation_id,
                CanonicalKey("claim-evidence-evaluation"),
            ),
        )

        for field_name, identifier, namespace in expected_identifiers:
            if not isinstance(identifier, ScopedIdentifier):
                raise FoundationError(f"{field_name} must be a ScopedIdentifier")
            if identifier.namespace != namespace:
                raise FoundationError(
                    f"{field_name} namespace must be {namespace.value}"
                )

        if not isinstance(self.decided_by_id, ScopedIdentifier):
            raise FoundationError("decided_by_id must be a ScopedIdentifier")
        if self.decided_by_id.namespace != CanonicalKey("human"):
            raise FoundationError("decided_by_id must identify a human actor")

    def _validate_types(self) -> None:
        if not isinstance(self.decided_at, UtcTimestamp):
            raise FoundationError("decided_at must be a UtcTimestamp")
        if not isinstance(
            self.status,
            ClaimAdjudicationDecisionStatus,
        ):
            raise FoundationError("status must be a ClaimAdjudicationDecisionStatus")
        if not isinstance(self.review_level, ClaimReviewLevel):
            raise FoundationError("review_level must be a ClaimReviewLevel")
        if not isinstance(self.reviewer_independent, bool):
            raise FoundationError("reviewer_independent must be a boolean")

    def _validate_digests(self) -> None:
        expected_digests = (
            (
                "claim_digest",
                self.claim_digest,
                "claim-specification",
            ),
            (
                "evaluation_digest",
                self.evaluation_digest,
                "claim-evidence-evaluation",
            ),
            (
                "claim_catalog_digest",
                self.claim_catalog_digest,
                "claim-catalog",
            ),
            (
                "resolution_snapshot_digest",
                self.resolution_snapshot_digest,
                "evidence-admission-resolution-snapshot",
            ),
            (
                "evidence_ledger_digest",
                self.evidence_ledger_digest,
                "evidence-ledger",
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                "actor-registry",
            ),
        )

        for field_name, digest, domain in expected_digests:
            _require_digest(
                digest,
                field_name=field_name,
                domain=domain,
            )

    @classmethod
    def decide(
        cls,
        *,
        key: str,
        decided_at: UtcTimestamp,
        decided_by_id: ScopedIdentifier,
        status: ClaimAdjudicationDecisionStatus,
        rationale: str,
        supporting_record_ids: Iterable[ScopedIdentifier],
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
    ) -> ClaimAdjudicationDecision:
        """Issue a bounded human judgment without granting authority."""

        cls._validate_bindings(
            claim=claim,
            evaluation=evaluation,
            claim_catalog=claim_catalog,
            actor_registry=actor_registry,
        )
        reviewer = actor_registry.require_actor(decided_by_id)
        cls._validate_reviewer(
            reviewer=reviewer,
            claim=claim,
        )
        cls._validate_time(
            decided_at=decided_at,
            evaluation=evaluation,
        )

        supporting_records = _normalize_record_ids(supporting_record_ids)
        cls._validate_decision(
            status=status,
            supporting_record_ids=supporting_records,
            evaluation=evaluation,
        )

        return cls(
            decision_id=ScopedIdentifier.create(
                namespace="claim-adjudication-decision",
                key=key,
                namespace_field="decision namespace",
                key_field="decision key",
            ),
            decided_at=decided_at,
            decided_by_id=reviewer.actor_id,
            status=status,
            rationale=rationale,
            claim_id=claim.claim_id,
            evaluation_id=evaluation.evaluation_id,
            review_level=claim.review_level,
            reviewer_independent=True,
            supporting_record_ids=supporting_records,
            claim_digest=claim.digest(),
            evaluation_digest=evaluation.digest(),
            claim_catalog_digest=claim_catalog.digest(),
            resolution_snapshot_digest=(evaluation.resolution_snapshot_digest),
            evidence_ledger_digest=evaluation.evidence_ledger_digest,
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
    ) -> None:
        catalog_claim = claim_catalog.require_claim(claim.claim_id)
        if catalog_claim.digest() != claim.digest():
            raise FoundationError("claim does not match the supplied claim catalog")
        if evaluation.claim_id != claim.claim_id:
            raise FoundationError("evaluation references a different claim")
        if evaluation.claim_digest != claim.digest():
            raise FoundationError("evaluation claim digest does not match the claim")
        if evaluation.claim_catalog_id != claim_catalog.catalog_id:
            raise FoundationError("evaluation references a different claim catalog")
        if evaluation.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError("evaluation claim-catalog digest does not match")

        actor_registry_digest = actor_registry.digest()
        if claim.actor_registry_digest != actor_registry_digest:
            raise FoundationError("claim is not bound to the supplied actor registry")
        if claim_catalog.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "claim catalog is not bound to the supplied actor registry"
            )
        if evaluation.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "evaluation is not bound to the supplied actor registry"
            )

    @staticmethod
    def _validate_reviewer(
        *,
        reviewer: ActorIdentity,
        claim: ClaimSpecification,
    ) -> None:
        if not reviewer.is_eligible_for_human_authority:
            raise FoundationError(
                "claim adjudication requires an active human reviewer"
            )
        if reviewer.actor_id in {
            claim.authored_by_id,
            claim.author_accountability_owner_id,
        }:
            raise FoundationError(
                "claim author and author accountability owner must not "
                "adjudicate their own claim"
            )

    @staticmethod
    def _validate_time(
        *,
        decided_at: UtcTimestamp,
        evaluation: ClaimEvidenceEvaluation,
    ) -> None:
        if decided_at.value < evaluation.evaluated_at.value:
            raise FoundationError(
                "decided_at must not precede the claim evidence evaluation"
            )

    @staticmethod
    def _validate_decision(
        *,
        status: ClaimAdjudicationDecisionStatus,
        supporting_record_ids: tuple[ScopedIdentifier, ...],
        evaluation: ClaimEvidenceEvaluation,
    ) -> None:
        if not isinstance(status, ClaimAdjudicationDecisionStatus):
            raise FoundationError("status must be a ClaimAdjudicationDecisionStatus")

        admitted_record_ids: set[ScopedIdentifier] = set()
        available_record_ids: set[ScopedIdentifier] = set()

        for requirement in evaluation.requirement_evaluations:
            admitted_record_ids.update(requirement.admitted_record_ids)
            available_record_ids.update(requirement.admitted_record_ids)
            available_record_ids.update(requirement.adverse_record_ids)
            available_record_ids.update(requirement.unresolved_record_ids)
            available_record_ids.update(requirement.excluded_record_ids)

        if not set(supporting_record_ids).issubset(available_record_ids):
            raise FoundationError(
                "supporting records must be present in the bound "
                "claim evidence evaluation"
            )

        if not status.supports_claim:
            return

        if evaluation.status is not (
            ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION
        ):
            raise FoundationError(
                "a claim may be supported only when its evidence "
                "evaluation is ready for human adjudication"
            )
        if not supporting_record_ids:
            raise FoundationError(
                "supported claim decisions require at least one "
                "supporting evidence record"
            )
        if not set(supporting_record_ids).issubset(admitted_record_ids):
            raise FoundationError(
                "supported claims may cite only admitted evidence records"
            )

    @property
    def supports_claim(self) -> bool:
        """Return whether this decision supports the bounded claim."""

        return self.status.supports_claim

    @property
    def closes_claim(self) -> bool:
        """Return whether the decision is terminal for this evaluation."""

        return self.status.is_terminal

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because adjudication remains bounded and revisable."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim judgment never grants action authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic adjudication representation."""

        supporting_records: JsonArray = [
            str(record_id) for record_id in self.supporting_record_ids
        ]

        return {
            "actor_registry_digest": (self.actor_registry_digest.to_payload()),
            "claim_catalog_digest": (self.claim_catalog_digest.to_payload()),
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "closes_claim": self.closes_claim,
            "decided_at": self.decided_at.isoformat(),
            "decided_by_id": str(self.decided_by_id),
            "decision_id": str(self.decision_id),
            "establishes_absolute_truth": (self.establishes_absolute_truth),
            "evaluation_digest": self.evaluation_digest.to_payload(),
            "evaluation_id": str(self.evaluation_id),
            "evidence_ledger_digest": (self.evidence_ledger_digest.to_payload()),
            "grants_authority": self.grants_authority,
            "rationale": self.rationale,
            "resolution_snapshot_digest": (
                self.resolution_snapshot_digest.to_payload()
            ),
            "review_level": self.review_level.value,
            "reviewer_independent": self.reviewer_independent,
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "supporting_record_ids": supporting_records,
            "supports_claim": self.supports_claim,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical adjudication document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete adjudication."""

        return self.to_document().digest(domain="claim-adjudication-decision")
