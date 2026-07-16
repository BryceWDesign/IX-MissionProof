"""Deterministic claim-evidence evaluations for IX-MissionProof."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.specifications import (
    ClaimCatalog,
    ClaimEvidenceRequirement,
    ClaimSpecification,
)
from ix_missionproof.evidence import (
    EvidenceAdmissionResolutionSnapshot,
    EvidenceLedger,
    EvidenceRecord,
)
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
)


class ClaimRequirementEvaluationOutcome(StrEnum):
    """Possible evidence outcomes for one claim requirement."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    FALSIFICATION_SIGNAL = "falsification-signal"

    @property
    def is_satisfied(self) -> bool:
        """Return whether the evidence obligation is currently satisfied."""

        return self is ClaimRequirementEvaluationOutcome.SATISFIED


class ClaimRequirementEvaluationReason(StrEnum):
    """Stable reasons emitted by claim-requirement evaluation."""

    ACCEPTABLE_EVIDENCE_PRESENT = "acceptable-evidence-present"
    MINIMUM_RECORDS_MET = "minimum-records-met"
    PRIMARY_EVIDENCE_PRESENT = "primary-evidence-present"
    SUBJECT_MATCH_CONFIRMED = "subject-match-confirmed"
    INDEPENDENT_PRODUCERS_PRESENT = "independent-producers-present"
    EXCLUDED_RELEVANT_EVIDENCE_PRESENT = (
        "excluded-relevant-evidence-present"
    )
    NO_ACCEPTABLE_EVIDENCE = "no-acceptable-evidence"
    MINIMUM_RECORDS_NOT_MET = "minimum-records-not-met"
    PRIMARY_EVIDENCE_MISSING = "primary-evidence-missing"
    SUBJECT_MATCH_MISSING = "subject-match-missing"
    INDEPENDENT_PRODUCERS_MISSING = "independent-producers-missing"
    UNRESOLVED_RELEVANT_EVIDENCE = "unresolved-relevant-evidence"
    ADVERSE_EVIDENCE_PRESENT = "adverse-evidence-present"


class ClaimEvidenceEvaluationStatus(StrEnum):
    """Aggregate evidence posture for one bounded claim."""

    READY_FOR_HUMAN_ADJUDICATION = "ready-for-human-adjudication"
    INCOMPLETE = "incomplete"
    HUMAN_REVIEW_REQUIRED = "human-review-required"
    FALSIFICATION_SIGNAL = "falsification-signal"

    @property
    def is_ready_for_human_adjudication(self) -> bool:
        """Return whether every evidence obligation is satisfied."""

        return self is (
            ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION
        )


_EVALUATOR_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)

_UNSATISFIED_REASONS: Final[
    frozenset[ClaimRequirementEvaluationReason]
] = frozenset(
    {
        ClaimRequirementEvaluationReason.NO_ACCEPTABLE_EVIDENCE,
        ClaimRequirementEvaluationReason.MINIMUM_RECORDS_NOT_MET,
        ClaimRequirementEvaluationReason.PRIMARY_EVIDENCE_MISSING,
        ClaimRequirementEvaluationReason.SUBJECT_MATCH_MISSING,
        ClaimRequirementEvaluationReason.INDEPENDENT_PRODUCERS_MISSING,
    }
)


def _require_digest(
    value: ContentDigest,
    *,
    field_name: str,
    domain: str,
) -> None:
    if not isinstance(value, ContentDigest):
        raise FoundationError(
            f"{field_name} must be a ContentDigest"
        )
    if value.domain != CanonicalKey(domain):
        raise FoundationError(
            f"{field_name} domain must be {domain}"
        )


def _normalize_reasons(
    values: tuple[ClaimRequirementEvaluationReason, ...],
) -> tuple[ClaimRequirementEvaluationReason, ...]:
    normalized: set[ClaimRequirementEvaluationReason] = set()

    for index, value in enumerate(values):
        if not isinstance(
            value,
            ClaimRequirementEvaluationReason,
        ):
            raise FoundationError(
                f"reasons[{index}] must be a "
                "ClaimRequirementEvaluationReason"
            )
        normalized.add(value)

    if not normalized:
        raise FoundationError(
            "claim-requirement evaluation reasons must not be empty"
        )

    return tuple(
        sorted(
            normalized,
            key=lambda value: value.value,
        )
    )


def _normalize_record_ids(
    values: tuple[ScopedIdentifier, ...],
    *,
    field_name: str,
) -> tuple[ScopedIdentifier, ...]:
    normalized: set[ScopedIdentifier] = set()

    for index, value in enumerate(values):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(
                f"{field_name}[{index}] must be a ScopedIdentifier"
            )
        if value.namespace != CanonicalKey("record"):
            raise FoundationError(
                f"{field_name}[{index}] namespace must be record"
            )
        normalized.add(value)

    return tuple(
        sorted(
            normalized,
            key=str,
        )
    )


@dataclass(frozen=True, slots=True)
class ClaimRequirementEvaluation:
    """Evidence evaluation for one exact claim requirement."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-requirement-evaluation-v1"
    )

    evaluation_id: ScopedIdentifier
    evaluated_at: UtcTimestamp
    claim_id: ScopedIdentifier
    requirement_id: ScopedIdentifier
    outcome: ClaimRequirementEvaluationOutcome
    reasons: tuple[ClaimRequirementEvaluationReason, ...]
    admitted_record_ids: tuple[ScopedIdentifier, ...]
    adverse_record_ids: tuple[ScopedIdentifier, ...]
    unresolved_record_ids: tuple[ScopedIdentifier, ...]
    excluded_record_ids: tuple[ScopedIdentifier, ...]
    claim_digest: ContentDigest
    requirement_digest: ContentDigest
    resolution_snapshot_digest: ContentDigest
    evidence_ledger_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_identifiers()
        self._validate_types()
        self._validate_digests()

        object.__setattr__(
            self,
            "reasons",
            _normalize_reasons(
                self.reasons
            ),
        )
        object.__setattr__(
            self,
            "admitted_record_ids",
            _normalize_record_ids(
                self.admitted_record_ids,
                field_name="admitted_record_ids",
            ),
        )
        object.__setattr__(
            self,
            "adverse_record_ids",
            _normalize_record_ids(
                self.adverse_record_ids,
                field_name="adverse_record_ids",
            ),
        )
        object.__setattr__(
            self,
            "unresolved_record_ids",
            _normalize_record_ids(
                self.unresolved_record_ids,
                field_name="unresolved_record_ids",
            ),
        )
        object.__setattr__(
            self,
            "excluded_record_ids",
            _normalize_record_ids(
                self.excluded_record_ids,
                field_name="excluded_record_ids",
            ),
        )

        self._validate_record_sets()
        self._validate_outcome()

    def _validate_identifiers(self) -> None:
        expected_identifiers = (
            (
                "evaluation_id",
                self.evaluation_id,
                CanonicalKey("claim-requirement-evaluation"),
            ),
            (
                "claim_id",
                self.claim_id,
                CanonicalKey("claim"),
            ),
            (
                "requirement_id",
                self.requirement_id,
                CanonicalKey("claim-evidence-requirement"),
            ),
        )

        for field_name, identifier, namespace in expected_identifiers:
            if not isinstance(
                identifier,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )
            if identifier.namespace != namespace:
                raise FoundationError(
                    f"{field_name} namespace must be "
                    f"{namespace.value}"
                )

    def _validate_types(self) -> None:
        if not isinstance(
            self.evaluated_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "evaluated_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.outcome,
            ClaimRequirementEvaluationOutcome,
        ):
            raise FoundationError(
                "outcome must be a "
                "ClaimRequirementEvaluationOutcome"
            )

    def _validate_digests(self) -> None:
        expected_digests = (
            (
                "claim_digest",
                self.claim_digest,
                "claim-specification",
            ),
            (
                "requirement_digest",
                self.requirement_digest,
                "claim-evidence-requirement",
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
        )

        for field_name, digest, domain in expected_digests:
            _require_digest(
                digest,
                field_name=field_name,
                domain=domain,
            )

    def _validate_record_sets(self) -> None:
        admitted = set(
            self.admitted_record_ids
        )
        adverse = set(
            self.adverse_record_ids
        )
        unresolved = set(
            self.unresolved_record_ids
        )
        excluded = set(
            self.excluded_record_ids
        )

        if not adverse.issubset(admitted):
            raise FoundationError(
                "adverse_record_ids must be a subset "
                "of admitted_record_ids"
            )
        if admitted.intersection(unresolved):
            raise FoundationError(
                "admitted and unresolved record IDs must be disjoint"
            )
        if admitted.intersection(excluded):
            raise FoundationError(
                "admitted and excluded record IDs must be disjoint"
            )
        if unresolved.intersection(excluded):
            raise FoundationError(
                "unresolved and excluded record IDs must be disjoint"
            )

    def _validate_outcome(self) -> None:
        reasons = set(
            self.reasons
        )
        has_unsatisfied = bool(
            reasons.intersection(
                _UNSATISFIED_REASONS
            )
        )
        has_unresolved = (
            ClaimRequirementEvaluationReason
            .UNRESOLVED_RELEVANT_EVIDENCE
            in reasons
        )
        has_adverse = (
            ClaimRequirementEvaluationReason
            .ADVERSE_EVIDENCE_PRESENT
            in reasons
        )

        if (
            self.outcome
            is ClaimRequirementEvaluationOutcome
            .FALSIFICATION_SIGNAL
        ):
            if not has_adverse or not self.adverse_record_ids:
                raise FoundationError(
                    "falsification-signal outcome requires "
                    "adverse admitted evidence"
                )
            return

        if has_adverse:
            raise FoundationError(
                "non-falsification outcome must not contain "
                "adverse-evidence-present"
            )

        if (
            self.outcome
            is ClaimRequirementEvaluationOutcome
            .HUMAN_REVIEW_REQUIRED
        ):
            if not has_unresolved or not self.unresolved_record_ids:
                raise FoundationError(
                    "human-review-required outcome requires "
                    "unresolved relevant evidence"
                )
            return

        if has_unresolved:
            raise FoundationError(
                "resolved requirement outcome must not retain "
                "unresolved relevant evidence"
            )

        if (
            self.outcome
            is ClaimRequirementEvaluationOutcome.UNSATISFIED
        ):
            if not has_unsatisfied:
                raise FoundationError(
                    "unsatisfied outcome requires at least "
                    "one unmet evidence reason"
                )
            return

        if has_unsatisfied:
            raise FoundationError(
                "satisfied outcome must not contain "
                "unmet evidence reasons"
            )

        required_positive = {
            ClaimRequirementEvaluationReason
            .ACCEPTABLE_EVIDENCE_PRESENT,
            ClaimRequirementEvaluationReason
            .MINIMUM_RECORDS_MET,
        }
        if not required_positive.issubset(reasons):
            raise FoundationError(
                "satisfied outcome requires acceptable evidence "
                "and the minimum record count"
            )

    @property
    def is_satisfied(self) -> bool:
        """Return whether this evidence obligation is satisfied."""

        return self.outcome.is_satisfied

    @property
    def establishes_claim(self) -> bool:
        """Return false because requirement evaluation is not adjudication."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic requirement-evaluation representation."""

        reasons: JsonArray = [
            reason.value
            for reason in self.reasons
        ]
        admitted: JsonArray = [
            str(record_id)
            for record_id in self.admitted_record_ids
        ]
        adverse: JsonArray = [
            str(record_id)
            for record_id in self.adverse_record_ids
        ]
        unresolved: JsonArray = [
            str(record_id)
            for record_id in self.unresolved_record_ids
        ]
        excluded: JsonArray = [
            str(record_id)
            for record_id in self.excluded_record_ids
        ]

        return {
            "admitted_record_ids": admitted,
            "adverse_record_ids": adverse,
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "establishes_claim": self.establishes_claim,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_id": str(self.evaluation_id),
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "excluded_record_ids": excluded,
            "is_satisfied": self.is_satisfied,
            "outcome": self.outcome.value,
            "reasons": reasons,
            "requirement_digest": (
                self.requirement_digest.to_payload()
            ),
            "requirement_id": str(self.requirement_id),
            "resolution_snapshot_digest": (
                self.resolution_snapshot_digest.to_payload()
            ),
            "schema": self.SCHEMA.value,
            "unresolved_record_ids": unresolved,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical evaluation document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete requirement evaluation."""

        return self.to_document().digest(
            domain="claim-requirement-evaluation"
        )


@dataclass(frozen=True, slots=True)
class ClaimEvidenceEvaluation:
    """Aggregate evidence posture for one bounded claim."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-evidence-evaluation-v1"
    )

    evaluation_id: ScopedIdentifier
    evaluated_at: UtcTimestamp
    evaluated_by_id: ScopedIdentifier
    evaluator_kind: ActorKind
    evaluator_accountability_owner_id: ScopedIdentifier
    claim_id: ScopedIdentifier
    claim_catalog_id: ScopedIdentifier
    resolution_snapshot_id: ScopedIdentifier
    evidence_ledger_id: ScopedIdentifier
    status: ClaimEvidenceEvaluationStatus
    requirement_evaluations: tuple[
        ClaimRequirementEvaluation,
        ...,
    ]
    claim_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    resolution_snapshot_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        evaluations = tuple(
            self.requirement_evaluations
        )
        self._validate_requirement_evaluations(
            evaluations
        )

        ordered = tuple(
            sorted(
                evaluations,
                key=lambda evaluation: str(
                    evaluation.requirement_id
                ),
            )
        )
        object.__setattr__(
            self,
            "requirement_evaluations",
            ordered,
        )

        expected_status = self._status_for(
            ordered
        )
        if self.status is not expected_status:
            raise FoundationError(
                "claim evidence status does not match "
                "its requirement evaluations"
            )

    def _validate_metadata(self) -> None:
        expected_identifiers = (
            (
                "evaluation_id",
                self.evaluation_id,
                CanonicalKey("claim-evidence-evaluation"),
            ),
            (
                "claim_id",
                self.claim_id,
                CanonicalKey("claim"),
            ),
            (
                "claim_catalog_id",
                self.claim_catalog_id,
                CanonicalKey("claim-catalog"),
            ),
            (
                "resolution_snapshot_id",
                self.resolution_snapshot_id,
                CanonicalKey(
                    "evidence-admission-resolution-snapshot"
                ),
            ),
            (
                "evidence_ledger_id",
                self.evidence_ledger_id,
                CanonicalKey("evidence-ledger"),
            ),
        )

        for field_name, identifier, namespace in expected_identifiers:
            if not isinstance(
                identifier,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )
            if identifier.namespace != namespace:
                raise FoundationError(
                    f"{field_name} namespace must be "
                    f"{namespace.value}"
                )

        if not isinstance(
            self.evaluated_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "evaluated_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.evaluated_by_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "evaluated_by_id must be a ScopedIdentifier"
            )
        if not isinstance(
            self.evaluator_kind,
            ActorKind,
        ):
            raise FoundationError(
                "evaluator_kind must be an ActorKind"
            )
        if self.evaluator_kind not in _EVALUATOR_KINDS:
            raise FoundationError(
                "claim evidence evaluator must be "
                "a service or system actor"
            )
        if self.evaluated_by_id.namespace != CanonicalKey(
            self.evaluator_kind.value
        ):
            raise FoundationError(
                "evaluated_by_id namespace must match evaluator_kind"
            )
        if not isinstance(
            self.evaluator_accountability_owner_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "evaluator_accountability_owner_id must be "
                "a ScopedIdentifier"
            )
        if (
            self.evaluator_accountability_owner_id.namespace
            != CanonicalKey("human")
        ):
            raise FoundationError(
                "evaluator_accountability_owner_id must identify "
                "a human actor"
            )
        if not isinstance(
            self.status,
            ClaimEvidenceEvaluationStatus,
        ):
            raise FoundationError(
                "status must be a ClaimEvidenceEvaluationStatus"
            )

    def _validate_digests(self) -> None:
        expected_digests = (
            (
                "claim_digest",
                self.claim_digest,
                "claim-specification",
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

    def _validate_requirement_evaluations(
        self,
        evaluations: tuple[
            ClaimRequirementEvaluation,
            ...,
        ],
    ) -> None:
        if not evaluations:
            raise FoundationError(
                "claim evidence evaluation requires "
                "requirement evaluations"
            )

        for index, evaluation in enumerate(
            evaluations
        ):
            if not isinstance(
                evaluation,
                ClaimRequirementEvaluation,
            ):
                raise FoundationError(
                    f"requirement_evaluations[{index}] must be "
                    "a ClaimRequirementEvaluation"
                )
            if evaluation.evaluated_at != self.evaluated_at:
                raise FoundationError(
                    "all requirement evaluations must use "
                    "the aggregate evaluation timestamp"
                )
            if evaluation.claim_id != self.claim_id:
                raise FoundationError(
                    "all requirement evaluations must reference "
                    "the evaluated claim"
                )
            if evaluation.claim_digest != self.claim_digest:
                raise FoundationError(
                    "all requirement evaluations must bind "
                    "the evaluated claim"
                )
            if (
                evaluation.resolution_snapshot_digest
                != self.resolution_snapshot_digest
            ):
                raise FoundationError(
                    "all requirement evaluations must bind "
                    "the resolution snapshot"
                )
            if (
                evaluation.evidence_ledger_digest
                != self.evidence_ledger_digest
            ):
                raise FoundationError(
                    "all requirement evaluations must bind "
                    "the evidence ledger"
                )

        requirement_ids = tuple(
            evaluation.requirement_id
            for evaluation in evaluations
        )
        if len(requirement_ids) != len(
            set(requirement_ids)
        ):
            raise FoundationError(
                "claim evidence evaluation must contain "
                "one evaluation per requirement"
            )

    @staticmethod
    def _status_for(
        evaluations: tuple[
            ClaimRequirementEvaluation,
            ...,
        ],
    ) -> ClaimEvidenceEvaluationStatus:
        outcomes = {
            evaluation.outcome
            for evaluation in evaluations
        }

        if (
            ClaimRequirementEvaluationOutcome
            .FALSIFICATION_SIGNAL
            in outcomes
        ):
            return (
                ClaimEvidenceEvaluationStatus
                .FALSIFICATION_SIGNAL
            )

        if (
            ClaimRequirementEvaluationOutcome
            .HUMAN_REVIEW_REQUIRED
            in outcomes
        ):
            return (
                ClaimEvidenceEvaluationStatus
                .HUMAN_REVIEW_REQUIRED
            )

        if (
            ClaimRequirementEvaluationOutcome.UNSATISFIED
            in outcomes
        ):
            return ClaimEvidenceEvaluationStatus.INCOMPLETE

        return (
            ClaimEvidenceEvaluationStatus
            .READY_FOR_HUMAN_ADJUDICATION
        )

    @property
    def is_ready_for_human_adjudication(self) -> bool:
        """Return whether every evidence requirement is satisfied."""

        return self.status.is_ready_for_human_adjudication

    @property
    def establishes_truth(self) -> bool:
        """Return false because evidence evaluation is not adjudication."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because evidence evaluation grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def requirement_evaluation_for(
        self,
        requirement_id: ScopedIdentifier,
    ) -> ClaimRequirementEvaluation | None:
        """Return an evaluation for one evidence requirement."""

        for evaluation in self.requirement_evaluations:
            if evaluation.requirement_id == requirement_id:
                return evaluation

        return None

    def require_requirement_evaluation(
        self,
        requirement_id: ScopedIdentifier,
    ) -> ClaimRequirementEvaluation:
        """Return a requirement evaluation or fail when absent."""

        evaluation = self.requirement_evaluation_for(
            requirement_id
        )

        if evaluation is None:
            raise FoundationError(
                "claim evidence evaluation does not contain "
                f"requirement: {requirement_id}"
            )

        return evaluation

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic aggregate evaluation representation."""

        requirement_payloads: JsonArray = [
            evaluation.to_payload()
            for evaluation in self.requirement_evaluations
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_catalog_id": str(self.claim_catalog_id),
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "establishes_truth": self.establishes_truth,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluated_by_id": str(self.evaluated_by_id),
            "evaluation_id": str(self.evaluation_id),
            "evaluator_accountability_owner_id": str(
                self.evaluator_accountability_owner_id
            ),
            "evaluator_kind": self.evaluator_kind.value,
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "evidence_ledger_id": str(self.evidence_ledger_id),
            "grants_authority": self.grants_authority,
            "is_ready_for_human_adjudication": (
                self.is_ready_for_human_adjudication
            ),
            "requirement_evaluations": requirement_payloads,
            "resolution_snapshot_digest": (
                self.resolution_snapshot_digest.to_payload()
            ),
            "resolution_snapshot_id": str(
                self.resolution_snapshot_id
            ),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical evaluation document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete claim evaluation."""

        return self.to_document().digest(
            domain="claim-evidence-evaluation"
        )


@dataclass(frozen=True, slots=True)
class ClaimEvidenceEvaluator:
    """Evaluate claim obligations against resolved evidence admission."""

    actor_registry: ActorRegistry
    claim_catalog: ClaimCatalog
    resolution_snapshot: EvidenceAdmissionResolutionSnapshot
    evidence_ledger: EvidenceLedger

    def __post_init__(self) -> None:
        actor_registry_digest = self.actor_registry.digest()
        evidence_ledger_digest = self.evidence_ledger.digest()

        if (
            self.claim_catalog.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "claim catalog is not bound to "
                "the supplied actor registry"
            )
        if (
            self.resolution_snapshot.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "resolution snapshot is not bound to "
                "the supplied actor registry"
            )
        if (
            self.evidence_ledger.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "evidence ledger is not bound to "
                "the supplied actor registry"
            )
        if (
            self.resolution_snapshot.evidence_ledger_digest
            != evidence_ledger_digest
        ):
            raise FoundationError(
                "resolution snapshot is not bound to "
                "the supplied evidence ledger"
            )

    def evaluate(
        self,
        *,
        key: str,
        evaluated_at: UtcTimestamp,
        evaluated_by_id: ScopedIdentifier,
        claim_id: ScopedIdentifier,
    ) -> ClaimEvidenceEvaluation:
        """Evaluate evidence readiness without adjudicating claim truth."""

        evaluator = self.actor_registry.require_actor(
            evaluated_by_id
        )
        evaluator_owner_id = self._validate_evaluator(
            evaluator
        )
        claim = self.claim_catalog.require_claim(
            claim_id
        )

        self._validate_time(
            evaluated_at=evaluated_at,
            claim=claim,
        )

        admitted_records = self.resolution_snapshot.admitted_records(
            evidence_ledger=self.evidence_ledger
        )
        unresolved_records = self.resolution_snapshot.unresolved_records(
            evidence_ledger=self.evidence_ledger
        )
        excluded_records = self.resolution_snapshot.excluded_records(
            evidence_ledger=self.evidence_ledger
        )

        evaluations = tuple(
            self._evaluate_requirement(
                key=(
                    f"{key}-"
                    f"{str(requirement.requirement_id)}"
                ),
                evaluated_at=evaluated_at,
                claim=claim,
                requirement=requirement,
                admitted_records=admitted_records,
                unresolved_records=unresolved_records,
                excluded_records=excluded_records,
            )
            for requirement in claim.evidence_requirements
        )

        status = ClaimEvidenceEvaluation._status_for(
            evaluations
        )

        return ClaimEvidenceEvaluation(
            evaluation_id=ScopedIdentifier.create(
                namespace="claim-evidence-evaluation",
                key=key,
                namespace_field="evaluation namespace",
                key_field="evaluation key",
            ),
            evaluated_at=evaluated_at,
            evaluated_by_id=evaluator.actor_id,
            evaluator_kind=evaluator.kind,
            evaluator_accountability_owner_id=(
                evaluator_owner_id
            ),
            claim_id=claim.claim_id,
            claim_catalog_id=self.claim_catalog.catalog_id,
            resolution_snapshot_id=(
                self.resolution_snapshot.snapshot_id
            ),
            evidence_ledger_id=self.evidence_ledger.ledger_id,
            status=status,
            requirement_evaluations=evaluations,
            claim_digest=claim.digest(),
            claim_catalog_digest=self.claim_catalog.digest(),
            resolution_snapshot_digest=(
                self.resolution_snapshot.digest()
            ),
            evidence_ledger_digest=self.evidence_ledger.digest(),
            actor_registry_digest=self.actor_registry.digest(),
        )

    @staticmethod
    def _validate_evaluator(
        evaluator: ActorIdentity,
    ) -> ScopedIdentifier:
        if not evaluator.is_active:
            raise FoundationError(
                "claim evidence evaluator must be active"
            )
        if evaluator.kind not in _EVALUATOR_KINDS:
            raise FoundationError(
                "claim evidence evaluator must be "
                "a service or system actor"
            )

        owner_id = evaluator.accountability_owner_id

        if owner_id is None:
            raise FoundationError(
                "claim evidence evaluator must identify "
                "an accountable human owner"
            )

        return owner_id

    def _validate_time(
        self,
        *,
        evaluated_at: UtcTimestamp,
        claim: ClaimSpecification,
    ) -> None:
        if evaluated_at.value < claim.created_at.value:
            raise FoundationError(
                "claim evidence evaluation must not predate the claim"
            )
        if (
            evaluated_at.value
            < self.claim_catalog.created_at.value
        ):
            raise FoundationError(
                "claim evidence evaluation must not predate "
                "the claim catalog"
            )
        if (
            evaluated_at.value
            < self.resolution_snapshot.resolved_at.value
        ):
            raise FoundationError(
                "claim evidence evaluation must not predate "
                "the resolution snapshot"
            )
        if (
            evaluated_at.value
            < self.evidence_ledger.created_at.value
        ):
            raise FoundationError(
                "claim evidence evaluation must not predate "
                "the evidence ledger"
            )

    def _evaluate_requirement(
        self,
        *,
        key: str,
        evaluated_at: UtcTimestamp,
        claim: ClaimSpecification,
        requirement: ClaimEvidenceRequirement,
        admitted_records: tuple[EvidenceRecord, ...],
        unresolved_records: tuple[EvidenceRecord, ...],
        excluded_records: tuple[EvidenceRecord, ...],
    ) -> ClaimRequirementEvaluation:
        admitted_kind_records = self._records_with_acceptable_kind(
            records=admitted_records,
            requirement=requirement,
        )
        unresolved_kind_records = self._records_with_acceptable_kind(
            records=unresolved_records,
            requirement=requirement,
        )
        excluded_kind_records = self._records_with_acceptable_kind(
            records=excluded_records,
            requirement=requirement,
        )

        admitted_matches = self._subject_matches(
            records=admitted_kind_records,
            claim=claim,
            requirement=requirement,
        )
        unresolved_matches = self._subject_matches(
            records=unresolved_kind_records,
            claim=claim,
            requirement=requirement,
        )
        excluded_matches = self._subject_matches(
            records=excluded_kind_records,
            claim=claim,
            requirement=requirement,
        )

        adverse_matches = tuple(
            record
            for record in admitted_matches
            if record.status.is_adverse
        )

        reasons = self._collect_reasons(
            claim=claim,
            requirement=requirement,
            admitted_kind_records=admitted_kind_records,
            admitted_matches=admitted_matches,
            unresolved_matches=unresolved_matches,
            excluded_matches=excluded_matches,
            adverse_matches=adverse_matches,
        )
        outcome = self._outcome_for(
            reasons
        )

        return ClaimRequirementEvaluation(
            evaluation_id=ScopedIdentifier.create(
                namespace="claim-requirement-evaluation",
                key=key,
                namespace_field="evaluation namespace",
                key_field="evaluation key",
            ),
            evaluated_at=evaluated_at,
            claim_id=claim.claim_id,
            requirement_id=requirement.requirement_id,
            outcome=outcome,
            reasons=tuple(reasons),
            admitted_record_ids=tuple(
                record.record_id
                for record in admitted_matches
            ),
            adverse_record_ids=tuple(
                record.record_id
                for record in adverse_matches
            ),
            unresolved_record_ids=tuple(
                record.record_id
                for record in unresolved_matches
            ),
            excluded_record_ids=tuple(
                record.record_id
                for record in excluded_matches
            ),
            claim_digest=claim.digest(),
            requirement_digest=requirement.digest(),
            resolution_snapshot_digest=(
                self.resolution_snapshot.digest()
            ),
            evidence_ledger_digest=self.evidence_ledger.digest(),
        )

    @staticmethod
    def _records_with_acceptable_kind(
        *,
        records: tuple[EvidenceRecord, ...],
        requirement: ClaimEvidenceRequirement,
    ) -> tuple[EvidenceRecord, ...]:
        acceptable = set(
            requirement.acceptable_kinds
        )

        return tuple(
            record
            for record in records
            if record.kind in acceptable
        )

    @staticmethod
    def _subject_matches(
        *,
        records: tuple[EvidenceRecord, ...],
        claim: ClaimSpecification,
        requirement: ClaimEvidenceRequirement,
    ) -> tuple[EvidenceRecord, ...]:
        if not requirement.require_subject_match:
            return records

        claim_subjects = set(
            claim.subject_ids
        )

        return tuple(
            record
            for record in records
            if claim_subjects.intersection(
                record.subject_ids
            )
        )

    @staticmethod
    def _collect_reasons(
        *,
        claim: ClaimSpecification,
        requirement: ClaimEvidenceRequirement,
        admitted_kind_records: tuple[EvidenceRecord, ...],
        admitted_matches: tuple[EvidenceRecord, ...],
        unresolved_matches: tuple[EvidenceRecord, ...],
        excluded_matches: tuple[EvidenceRecord, ...],
        adverse_matches: tuple[EvidenceRecord, ...],
    ) -> set[ClaimRequirementEvaluationReason]:
        reasons: set[ClaimRequirementEvaluationReason] = set()

        if admitted_matches:
            reasons.add(
                ClaimRequirementEvaluationReason
                .ACCEPTABLE_EVIDENCE_PRESENT
            )
        else:
            reasons.add(
                ClaimRequirementEvaluationReason
                .NO_ACCEPTABLE_EVIDENCE
            )

        if len(admitted_matches) >= requirement.minimum_records:
            reasons.add(
                ClaimRequirementEvaluationReason
                .MINIMUM_RECORDS_MET
            )
        else:
            reasons.add(
                ClaimRequirementEvaluationReason
                .MINIMUM_RECORDS_NOT_MET
            )

        if requirement.require_primary_evidence:
            if any(
                record.is_primary
                for record in admitted_matches
            ):
                reasons.add(
                    ClaimRequirementEvaluationReason
                    .PRIMARY_EVIDENCE_PRESENT
                )
            else:
                reasons.add(
                    ClaimRequirementEvaluationReason
                    .PRIMARY_EVIDENCE_MISSING
                )

        if requirement.require_subject_match:
            if admitted_matches:
                reasons.add(
                    ClaimRequirementEvaluationReason
                    .SUBJECT_MATCH_CONFIRMED
                )
            elif admitted_kind_records:
                reasons.add(
                    ClaimRequirementEvaluationReason
                    .SUBJECT_MATCH_MISSING
                )

        if requirement.require_independent_producers:
            producers = {
                record.produced_by_id
                for record in admitted_matches
            }
            if len(producers) >= 2:
                reasons.add(
                    ClaimRequirementEvaluationReason
                    .INDEPENDENT_PRODUCERS_PRESENT
                )
            else:
                reasons.add(
                    ClaimRequirementEvaluationReason
                    .INDEPENDENT_PRODUCERS_MISSING
                )

        if unresolved_matches:
            reasons.add(
                ClaimRequirementEvaluationReason
                .UNRESOLVED_RELEVANT_EVIDENCE
            )

        if excluded_matches:
            reasons.add(
                ClaimRequirementEvaluationReason
                .EXCLUDED_RELEVANT_EVIDENCE_PRESENT
            )

        if adverse_matches:
            reasons.add(
                ClaimRequirementEvaluationReason
                .ADVERSE_EVIDENCE_PRESENT
            )

        if (
            requirement.require_subject_match
            and not admitted_kind_records
            and claim.subject_ids
        ):
            return reasons

        return reasons

    @staticmethod
    def _outcome_for(
        reasons: set[ClaimRequirementEvaluationReason],
    ) -> ClaimRequirementEvaluationOutcome:
        if (
            ClaimRequirementEvaluationReason
            .ADVERSE_EVIDENCE_PRESENT
            in reasons
        ):
            return (
                ClaimRequirementEvaluationOutcome
                .FALSIFICATION_SIGNAL
            )

        if (
            ClaimRequirementEvaluationReason
            .UNRESOLVED_RELEVANT_EVIDENCE
            in reasons
        ):
            return (
                ClaimRequirementEvaluationOutcome
                .HUMAN_REVIEW_REQUIRED
            )

        if reasons.intersection(
            _UNSATISFIED_REASONS
        ):
            return ClaimRequirementEvaluationOutcome.UNSATISFIED

        return ClaimRequirementEvaluationOutcome.SATISFIED
