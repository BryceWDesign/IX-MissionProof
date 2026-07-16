"""Claim adjudication ledgers and resolved claim states."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.adjudications import (
    ClaimAdjudicationDecision,
    ClaimAdjudicationDecisionStatus,
)
from ix_missionproof.claims.evaluations import (
    ClaimEvidenceEvaluation,
    ClaimEvidenceEvaluationStatus,
)
from ix_missionproof.claims.specifications import ClaimCatalog, ClaimSpecification
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

_LEDGER_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)

_RESOLUTION_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimResolutionSource(StrEnum):
    """Authority source responsible for a resolved claim state."""

    EVIDENCE_EVALUATION = "evidence-evaluation"
    HUMAN_ADJUDICATION = "human-adjudication"


class ClaimResolutionStatus(StrEnum):
    """Resolved state of one exact claim evidence evaluation."""

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not-supported"
    DEFERRED = "deferred"
    AWAITING_ADJUDICATION = "awaiting-adjudication"
    INCOMPLETE_EVIDENCE = "incomplete-evidence"
    EVIDENCE_REVIEW_OPEN = "evidence-review-open"
    FALSIFICATION_SIGNAL = "falsification-signal"

    @property
    def is_terminal_for_evaluation(self) -> bool:
        """Return whether a human terminal judgment closed the evaluation."""

        return self in {
            ClaimResolutionStatus.SUPPORTED,
            ClaimResolutionStatus.NOT_SUPPORTED,
        }

    @property
    def supports_claim(self) -> bool:
        """Return whether the bounded claim was human-adjudicated as supported."""

        return self is ClaimResolutionStatus.SUPPORTED

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the resolved state still requires human attention."""

        return not self.is_terminal_for_evaluation


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


def _require_optional_digest(
    value: ContentDigest | None,
    *,
    field_name: str,
    domain: str,
) -> None:
    if value is None:
        return
    _require_digest(
        value,
        field_name=field_name,
        domain=domain,
    )


def _validate_machine_producer(
    producer: ActorIdentity,
    *,
    role: str,
    allowed_kinds: frozenset[ActorKind],
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(f"{role} must be active")
    if producer.kind not in allowed_kinds:
        raise FoundationError(f"{role} must be a service or system actor")

    owner_id = producer.accountability_owner_id
    if owner_id is None:
        raise FoundationError(f"{role} must identify an accountable human owner")
    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimAdjudicationDecisionLedger:
    """Immutable history of exact claim-evaluation adjudications."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-adjudication-decision-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    claim_catalog_id: ScopedIdentifier
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest
    decisions: tuple[ClaimAdjudicationDecision, ...]

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        decisions = tuple(self.decisions)
        self._validate_decisions(decisions)

        ordered = tuple(
            sorted(
                decisions,
                key=lambda decision: (
                    decision.decided_at.value,
                    str(decision.decision_id),
                ),
            )
        )
        self._validate_sequences(ordered)
        object.__setattr__(self, "decisions", ordered)

    def _validate_metadata(self) -> None:
        expected_identifiers = (
            (
                "ledger_id",
                self.ledger_id,
                CanonicalKey("claim-adjudication-decision-ledger"),
            ),
            (
                "claim_catalog_id",
                self.claim_catalog_id,
                CanonicalKey("claim-catalog"),
            ),
        )

        for field_name, identifier, namespace in expected_identifiers:
            if not isinstance(identifier, ScopedIdentifier):
                raise FoundationError(f"{field_name} must be a ScopedIdentifier")
            if identifier.namespace != namespace:
                raise FoundationError(
                    f"{field_name} namespace must be {namespace.value}"
                )

        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError("created_at must be a UtcTimestamp")
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError("producer_id must be a ScopedIdentifier")
        if not isinstance(self.producer_kind, ActorKind):
            raise FoundationError("producer_kind must be an ActorKind")
        if self.producer_kind not in _LEDGER_PRODUCER_KINDS:
            raise FoundationError(
                "decision-ledger producer must be a service or system actor"
            )
        if self.producer_id.namespace != CanonicalKey(self.producer_kind.value):
            raise FoundationError("producer_id namespace must match producer_kind")
        if not isinstance(
            self.producer_accountability_owner_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "producer_accountability_owner_id must be a ScopedIdentifier"
            )
        if self.producer_accountability_owner_id.namespace != CanonicalKey("human"):
            raise FoundationError(
                "producer_accountability_owner_id must identify a human actor"
            )

    def _validate_digests(self) -> None:
        _require_digest(
            self.claim_catalog_digest,
            field_name="claim_catalog_digest",
            domain="claim-catalog",
        )
        _require_digest(
            self.actor_registry_digest,
            field_name="actor_registry_digest",
            domain="actor-registry",
        )

    def _validate_decisions(
        self,
        decisions: tuple[ClaimAdjudicationDecision, ...],
    ) -> None:
        for index, decision in enumerate(decisions):
            if not isinstance(decision, ClaimAdjudicationDecision):
                raise FoundationError(
                    f"decisions[{index}] must be a ClaimAdjudicationDecision"
                )
            if decision.decided_at.value > self.created_at.value:
                raise FoundationError(
                    "decision ledger must not predate a contained decision"
                )
            if decision.claim_catalog_digest != self.claim_catalog_digest:
                raise FoundationError(
                    "every adjudication must bind the same claim catalog"
                )
            if decision.actor_registry_digest != self.actor_registry_digest:
                raise FoundationError(
                    "every adjudication must bind the same actor registry"
                )

        decision_ids = tuple(decision.decision_id for decision in decisions)
        if len(decision_ids) != len(set(decision_ids)):
            raise FoundationError("decision ledger must contain unique decision IDs")

    @staticmethod
    def _validate_sequences(
        decisions: tuple[ClaimAdjudicationDecision, ...],
    ) -> None:
        latest_by_evaluation: dict[
            ScopedIdentifier,
            ClaimAdjudicationDecision,
        ] = {}

        for decision in decisions:
            previous = latest_by_evaluation.get(decision.evaluation_id)
            if previous is not None:
                if (
                    previous.claim_id != decision.claim_id
                    or previous.claim_digest != decision.claim_digest
                    or previous.evaluation_digest != decision.evaluation_digest
                ):
                    raise FoundationError(
                        "adjudication sequence must preserve one bound "
                        "claim and evidence evaluation"
                    )
                if previous.decided_at == decision.decided_at:
                    raise FoundationError(
                        "adjudications for one evaluation must use "
                        "strictly increasing decision times"
                    )
                if previous.status.is_terminal:
                    raise FoundationError(
                        "terminal claim adjudications must not be replaced"
                    )

            latest_by_evaluation[decision.evaluation_id] = decision

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
        decisions: Iterable[ClaimAdjudicationDecision] = (),
    ) -> ClaimAdjudicationDecisionLedger:
        """Create a decision ledger bound to one claim catalog."""

        producer = actor_registry.require_actor(producer_id)
        owner_id = _validate_machine_producer(
            producer,
            role="decision-ledger producer",
            allowed_kinds=_LEDGER_PRODUCER_KINDS,
        )

        if claim_catalog.actor_registry_digest != actor_registry.digest():
            raise FoundationError(
                "claim catalog is not bound to the supplied actor registry"
            )
        if created_at.value < claim_catalog.created_at.value:
            raise FoundationError("decision ledger must not predate the claim catalog")

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace="claim-adjudication-decision-ledger",
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=owner_id,
            claim_catalog_id=claim_catalog.catalog_id,
            claim_catalog_digest=claim_catalog.digest(),
            actor_registry_digest=actor_registry.digest(),
            decisions=tuple(decisions),
        )

    def decisions_for_evaluation(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> tuple[ClaimAdjudicationDecision, ...]:
        """Return ordered adjudication history for one evaluation."""

        return tuple(
            decision
            for decision in self.decisions
            if decision.evaluation_id == evaluation_id
        )

    def latest_for_evaluation(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> ClaimAdjudicationDecision | None:
        """Return the latest adjudication for one evaluation."""

        decisions = self.decisions_for_evaluation(evaluation_id)
        return decisions[-1] if decisions else None

    def require_terminal_decision(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> ClaimAdjudicationDecision:
        """Return a terminal adjudication or fail when still unresolved."""

        decision = self.latest_for_evaluation(evaluation_id)
        if decision is None:
            raise FoundationError(
                "decision ledger does not contain an adjudication for "
                f"evaluation: {evaluation_id}"
            )
        if not decision.status.is_terminal:
            raise FoundationError(f"claim adjudication is {decision.status.value}")
        return decision

    def append(
        self,
        decision: ClaimAdjudicationDecision,
        *,
        created_at: UtcTimestamp,
    ) -> ClaimAdjudicationDecisionLedger:
        """Return the next immutable ledger snapshot."""

        if created_at.value < self.created_at.value:
            raise FoundationError(
                "next decision-ledger snapshot must not predate the current snapshot"
            )

        return ClaimAdjudicationDecisionLedger(
            ledger_id=self.ledger_id,
            created_at=created_at,
            producer_id=self.producer_id,
            producer_kind=self.producer_kind,
            producer_accountability_owner_id=(
                self.producer_accountability_owner_id
            ),
            claim_catalog_id=self.claim_catalog_id,
            claim_catalog_digest=self.claim_catalog_digest,
            actor_registry_digest=self.actor_registry_digest,
            decisions=(*self.decisions, decision),
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic decision-ledger representation."""

        decision_payloads: JsonArray = [
            decision.to_payload() for decision in self.decisions
        ]
        return {
            "actor_registry_digest": self.actor_registry_digest.to_payload(),
            "claim_catalog_digest": self.claim_catalog_digest.to_payload(),
            "claim_catalog_id": str(self.claim_catalog_id),
            "created_at": self.created_at.isoformat(),
            "decisions": decision_payloads,
            "ledger_id": str(self.ledger_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical decision-ledger document."""

        return CanonicalJsonDocument.from_value(self.canonical_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete adjudication ledger."""

        return self.to_document().digest(
            domain="claim-adjudication-decision-ledger"
        )


@dataclass(frozen=True, slots=True)
class ClaimResolution:
    """Resolved state of one exact claim evidence evaluation."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey("claim-resolution-v1")

    resolution_id: ScopedIdentifier
    resolved_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    claim_id: ScopedIdentifier
    evaluation_id: ScopedIdentifier
    status: ClaimResolutionStatus
    source: ClaimResolutionSource
    decision_id: ScopedIdentifier | None
    decision_status: ClaimAdjudicationDecisionStatus | None
    claim_digest: ContentDigest
    evaluation_digest: ContentDigest
    decision_digest: ContentDigest | None
    decision_ledger_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    resolution_snapshot_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_source_semantics()

    def _validate_metadata(self) -> None:
        expected_identifiers = (
            (
                "resolution_id",
                self.resolution_id,
                CanonicalKey("claim-resolution"),
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

        if not isinstance(self.resolved_at, UtcTimestamp):
            raise FoundationError("resolved_at must be a UtcTimestamp")
        if not isinstance(self.produced_by_id, ScopedIdentifier):
            raise FoundationError("produced_by_id must be a ScopedIdentifier")
        if not isinstance(self.producer_kind, ActorKind):
            raise FoundationError("producer_kind must be an ActorKind")
        if self.producer_kind not in _RESOLUTION_PRODUCER_KINDS:
            raise FoundationError(
                "claim-resolution producer must be a service or system actor"
            )
        if self.produced_by_id.namespace != CanonicalKey(self.producer_kind.value):
            raise FoundationError("produced_by_id namespace must match producer_kind")
        if not isinstance(
            self.producer_accountability_owner_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "producer_accountability_owner_id must be a ScopedIdentifier"
            )
        if self.producer_accountability_owner_id.namespace != CanonicalKey("human"):
            raise FoundationError(
                "producer_accountability_owner_id must identify a human actor"
            )
        if not isinstance(self.status, ClaimResolutionStatus):
            raise FoundationError("status must be a ClaimResolutionStatus")
        if not isinstance(self.source, ClaimResolutionSource):
            raise FoundationError("source must be a ClaimResolutionSource")

        if self.decision_id is not None:
            if not isinstance(self.decision_id, ScopedIdentifier):
                raise FoundationError("decision_id must be a ScopedIdentifier or None")
            if self.decision_id.namespace != CanonicalKey(
                "claim-adjudication-decision"
            ):
                raise FoundationError(
                    "decision_id namespace must be claim-adjudication-decision"
                )

        if self.decision_status is not None and not isinstance(
            self.decision_status,
            ClaimAdjudicationDecisionStatus,
        ):
            raise FoundationError(
                "decision_status must be a ClaimAdjudicationDecisionStatus or None"
            )

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
                "decision_ledger_digest",
                self.decision_ledger_digest,
                "claim-adjudication-decision-ledger",
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

        _require_optional_digest(
            self.decision_digest,
            field_name="decision_digest",
            domain="claim-adjudication-decision",
        )

    def _validate_source_semantics(self) -> None:
        decision_fields_present = (
            self.decision_id is not None,
            self.decision_status is not None,
            self.decision_digest is not None,
        )
        if len(set(decision_fields_present)) != 1:
            raise FoundationError(
                "decision_id, decision_status, and decision_digest "
                "must be present or absent together"
            )

        if self.source is ClaimResolutionSource.HUMAN_ADJUDICATION:
            if not all(decision_fields_present):
                raise FoundationError(
                    "human-adjudication resolution requires decision data"
                )
            expected_status = self._status_for_decision(self.decision_status)
            if self.status is not expected_status:
                raise FoundationError(
                    "claim resolution status does not match the human adjudication"
                )
            return

        if any(decision_fields_present):
            raise FoundationError(
                "evidence-evaluation resolution must not contain human decision data"
            )
        if self.status in {
            ClaimResolutionStatus.SUPPORTED,
            ClaimResolutionStatus.NOT_SUPPORTED,
            ClaimResolutionStatus.DEFERRED,
        }:
            raise FoundationError(
                "evidence evaluation must not produce a human adjudication status"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        resolved_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
        decision_ledger: ClaimAdjudicationDecisionLedger,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
    ) -> ClaimResolution:
        """Resolve one claim evaluation without self-certification."""

        producer = actor_registry.require_actor(produced_by_id)
        owner_id = _validate_machine_producer(
            producer,
            role="claim-resolution producer",
            allowed_kinds=_RESOLUTION_PRODUCER_KINDS,
        )
        cls._validate_bindings(
            resolved_at=resolved_at,
            claim=claim,
            evaluation=evaluation,
            decision_ledger=decision_ledger,
            claim_catalog=claim_catalog,
            actor_registry=actor_registry,
        )

        decision = decision_ledger.latest_for_evaluation(evaluation.evaluation_id)
        if decision is None:
            source = ClaimResolutionSource.EVIDENCE_EVALUATION
            status = cls._status_for_evaluation(evaluation.status)
        else:
            cls._validate_decision(
                decision=decision,
                claim=claim,
                evaluation=evaluation,
            )
            source = ClaimResolutionSource.HUMAN_ADJUDICATION
            status = cls._status_for_decision(decision.status)

        return cls(
            resolution_id=ScopedIdentifier.create(
                namespace="claim-resolution",
                key=key,
                namespace_field="resolution namespace",
                key_field="resolution key",
            ),
            resolved_at=resolved_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=owner_id,
            claim_id=claim.claim_id,
            evaluation_id=evaluation.evaluation_id,
            status=status,
            source=source,
            decision_id=(
                decision.decision_id
                if decision is not None
                else None
            ),
            decision_status=(
                decision.status
                if decision is not None
                else None
            ),
            claim_digest=claim.digest(),
            evaluation_digest=evaluation.digest(),
            decision_digest=(
                decision.digest()
                if decision is not None
                else None
            ),
            decision_ledger_digest=decision_ledger.digest(),
            claim_catalog_digest=claim_catalog.digest(),
            resolution_snapshot_digest=(
                evaluation.resolution_snapshot_digest
            ),
            evidence_ledger_digest=evaluation.evidence_ledger_digest,
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        resolved_at: UtcTimestamp,
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
        decision_ledger: ClaimAdjudicationDecisionLedger,
        claim_catalog: ClaimCatalog,
        actor_registry: ActorRegistry,
    ) -> None:
        catalog_claim = claim_catalog.require_claim(claim.claim_id)
        if catalog_claim.digest() != claim.digest():
            raise FoundationError(
                "claim does not match the supplied claim catalog"
            )
        if evaluation.claim_id != claim.claim_id:
            raise FoundationError(
                "evaluation references a different claim"
            )
        if evaluation.claim_digest != claim.digest():
            raise FoundationError(
                "evaluation claim digest does not match the claim"
            )
        if evaluation.claim_catalog_id != claim_catalog.catalog_id:
            raise FoundationError(
                "evaluation references a different claim catalog"
            )
        if evaluation.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError(
                "evaluation claim-catalog digest does not match"
            )
        if decision_ledger.claim_catalog_id != claim_catalog.catalog_id:
            raise FoundationError(
                "decision ledger references a different claim catalog"
            )
        if decision_ledger.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError(
                "decision ledger is not bound to the supplied claim catalog"
            )

        actor_registry_digest = actor_registry.digest()
        if claim.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "claim is not bound to the supplied actor registry"
            )
        if claim_catalog.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "claim catalog is not bound to the supplied actor registry"
            )
        if evaluation.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "evaluation is not bound to the supplied actor registry"
            )
        if decision_ledger.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "decision ledger is not bound to the supplied actor registry"
            )

        if resolved_at.value < evaluation.evaluated_at.value:
            raise FoundationError(
                "claim resolution must not predate the evidence evaluation"
            )
        if resolved_at.value < decision_ledger.created_at.value:
            raise FoundationError(
                "claim resolution must not predate the decision ledger"
            )

    @staticmethod
    def _validate_decision(
        *,
        decision: ClaimAdjudicationDecision,
        claim: ClaimSpecification,
        evaluation: ClaimEvidenceEvaluation,
    ) -> None:
        if decision.claim_id != claim.claim_id:
            raise FoundationError(
                "human adjudication references a different claim"
            )
        if decision.claim_digest != claim.digest():
            raise FoundationError(
                "human adjudication claim digest does not match"
            )
        if decision.evaluation_id != evaluation.evaluation_id:
            raise FoundationError(
                "human adjudication references a different evaluation"
            )
        if decision.evaluation_digest != evaluation.digest():
            raise FoundationError(
                "human adjudication evaluation digest does not match"
            )

    @staticmethod
    def _status_for_evaluation(
        status: ClaimEvidenceEvaluationStatus,
    ) -> ClaimResolutionStatus:
        mapping = {
            ClaimEvidenceEvaluationStatus.READY_FOR_HUMAN_ADJUDICATION: (
                ClaimResolutionStatus.AWAITING_ADJUDICATION
            ),
            ClaimEvidenceEvaluationStatus.INCOMPLETE: (
                ClaimResolutionStatus.INCOMPLETE_EVIDENCE
            ),
            ClaimEvidenceEvaluationStatus.HUMAN_REVIEW_REQUIRED: (
                ClaimResolutionStatus.EVIDENCE_REVIEW_OPEN
            ),
            ClaimEvidenceEvaluationStatus.FALSIFICATION_SIGNAL: (
                ClaimResolutionStatus.FALSIFICATION_SIGNAL
            ),
        }
        return mapping[status]

    @staticmethod
    def _status_for_decision(
        status: ClaimAdjudicationDecisionStatus | None,
    ) -> ClaimResolutionStatus:
        if status is None:
            raise FoundationError(
                "human-adjudication resolution requires a decision status"
            )
        mapping = {
            ClaimAdjudicationDecisionStatus.SUPPORTED: (
                ClaimResolutionStatus.SUPPORTED
            ),
            ClaimAdjudicationDecisionStatus.NOT_SUPPORTED: (
                ClaimResolutionStatus.NOT_SUPPORTED
            ),
            ClaimAdjudicationDecisionStatus.DEFERRED: (
                ClaimResolutionStatus.DEFERRED
            ),
        }
        return mapping[status]

    @property
    def supports_claim(self) -> bool:
        """Return whether this exact claim evaluation was supported."""

        return self.status.supports_claim

    @property
    def is_terminal_for_evaluation(self) -> bool:
        """Return whether a terminal human judgment closed the evaluation."""

        return self.status.is_terminal_for_evaluation

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the state still requires human attention."""

        return self.status.requires_human_attention

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because claim resolution remains bounded and revisable."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim resolution never grants action authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic resolved-claim representation."""

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "decision_digest": (
                self.decision_digest.to_payload()
                if self.decision_digest is not None
                else None
            ),
            "decision_id": (
                str(self.decision_id)
                if self.decision_id is not None
                else None
            ),
            "decision_ledger_digest": (
                self.decision_ledger_digest.to_payload()
            ),
            "decision_status": (
                self.decision_status.value
                if self.decision_status is not None
                else None
            ),
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "evaluation_digest": self.evaluation_digest.to_payload(),
            "evaluation_id": str(self.evaluation_id),
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "grants_authority": self.grants_authority,
            "is_terminal_for_evaluation": (
                self.is_terminal_for_evaluation
            ),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "requires_human_attention": (
                self.requires_human_attention
            ),
            "resolution_id": str(self.resolution_id),
            "resolution_snapshot_digest": (
                self.resolution_snapshot_digest.to_payload()
            ),
            "resolved_at": self.resolved_at.isoformat(),
            "schema": self.SCHEMA.value,
            "source": self.source.value,
            "status": self.status.value,
            "supports_claim": self.supports_claim,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical claim-resolution document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete resolved claim state."""

        return self.to_document().digest(
            domain="claim-resolution"
        )
