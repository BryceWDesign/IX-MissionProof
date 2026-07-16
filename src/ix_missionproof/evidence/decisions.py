"""Independent human decisions for review-required evidence admission."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.evidence.admissions import (
    EvidenceAdmissionFinding,
    EvidenceAdmissionOutcome,
    EvidenceAdmissionReview,
)
from ix_missionproof.evidence.records import (
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
    require_text,
)

_DECISION_LEDGER_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class EvidenceAdmissionDecisionStatus(StrEnum):
    """Human dispositions for evidence awaiting admission review."""

    ADMIT = "admit"
    EXCLUDE = "exclude"
    DEFER = "defer"

    @property
    def is_terminal(self) -> bool:
        """Return whether this disposition resolves the finding."""

        return self in {
            EvidenceAdmissionDecisionStatus.ADMIT,
            EvidenceAdmissionDecisionStatus.EXCLUDE,
        }

    @property
    def resolved_outcome(self) -> EvidenceAdmissionOutcome:
        """Return the evidence-admission outcome produced by this decision."""

        if self is EvidenceAdmissionDecisionStatus.ADMIT:
            return EvidenceAdmissionOutcome.ADMITTED
        if self is EvidenceAdmissionDecisionStatus.EXCLUDE:
            return EvidenceAdmissionOutcome.EXCLUDED
        return EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW


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


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionDecision:
    """An independent human decision over one review-required finding."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-decision-v1"
    )

    decision_id: ScopedIdentifier
    decided_at: UtcTimestamp
    decided_by_id: ScopedIdentifier
    status: EvidenceAdmissionDecisionStatus
    rationale: str
    review_id: ScopedIdentifier
    finding_id: ScopedIdentifier
    record_id: ScopedIdentifier
    supporting_record_ids: tuple[ScopedIdentifier, ...]
    record_digest: ContentDigest
    finding_digest: ContentDigest
    review_digest: ContentDigest
    policy_digest: ContentDigest
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
        object.__setattr__(
            self,
            "supporting_record_ids",
            _normalize_record_ids(
                self.supporting_record_ids
            ),
        )

        if (
            self.status is EvidenceAdmissionDecisionStatus.ADMIT
            and not self.supporting_record_ids
        ):
            raise FoundationError(
                "admit decisions require at least one supporting record"
            )

    def _validate_identifiers(self) -> None:
        expected_identifiers = (
            (
                "decision_id",
                self.decision_id,
                CanonicalKey("evidence-admission-decision"),
            ),
            (
                "review_id",
                self.review_id,
                CanonicalKey("evidence-admission-review"),
            ),
            (
                "finding_id",
                self.finding_id,
                CanonicalKey("evidence-admission-finding"),
            ),
            (
                "record_id",
                self.record_id,
                CanonicalKey("record"),
            ),
        )

        for field_name, identifier, expected_namespace in expected_identifiers:
            if not isinstance(
                identifier,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )
            if identifier.namespace != expected_namespace:
                raise FoundationError(
                    f"{field_name} namespace must be "
                    f"{expected_namespace.value}"
                )

        if not isinstance(
            self.decided_by_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "decided_by_id must be a ScopedIdentifier"
            )
        if self.decided_by_id.namespace != CanonicalKey(
            "human"
        ):
            raise FoundationError(
                "decided_by_id must identify a human actor"
            )

    def _validate_types(self) -> None:
        if not isinstance(
            self.decided_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "decided_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.status,
            EvidenceAdmissionDecisionStatus,
        ):
            raise FoundationError(
                "status must be an EvidenceAdmissionDecisionStatus"
            )

    def _validate_digests(self) -> None:
        expected_digests = (
            (
                "record_digest",
                self.record_digest,
                "evidence-record",
            ),
            (
                "finding_digest",
                self.finding_digest,
                "evidence-admission-finding",
            ),
            (
                "review_digest",
                self.review_digest,
                "evidence-admission-review",
            ),
            (
                "policy_digest",
                self.policy_digest,
                "evidence-admission-policy",
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
        status: EvidenceAdmissionDecisionStatus,
        rationale: str,
        supporting_record_ids: Iterable[ScopedIdentifier],
        finding: EvidenceAdmissionFinding,
        admission_review: EvidenceAdmissionReview,
        evidence_ledger: EvidenceLedger,
        actor_registry: ActorRegistry,
    ) -> EvidenceAdmissionDecision:
        """Resolve only a finding that automated policy left for human review."""

        record = cls._validate_bindings(
            finding=finding,
            admission_review=admission_review,
            evidence_ledger=evidence_ledger,
            actor_registry=actor_registry,
        )
        reviewer = actor_registry.require_actor(
            decided_by_id
        )

        cls._validate_reviewer(
            reviewer=reviewer,
            record=record,
        )
        cls._validate_decision_time(
            decided_at=decided_at,
            admission_review=admission_review,
        )

        normalized_support = _normalize_record_ids(
            supporting_record_ids
        )
        cls._validate_support(
            status=status,
            target_record=record,
            supporting_record_ids=normalized_support,
            admission_review=admission_review,
            evidence_ledger=evidence_ledger,
        )

        return cls(
            decision_id=ScopedIdentifier.create(
                namespace="evidence-admission-decision",
                key=key,
                namespace_field="decision namespace",
                key_field="decision key",
            ),
            decided_at=decided_at,
            decided_by_id=reviewer.actor_id,
            status=status,
            rationale=rationale,
            review_id=admission_review.review_id,
            finding_id=finding.finding_id,
            record_id=record.record_id,
            supporting_record_ids=normalized_support,
            record_digest=record.digest(),
            finding_digest=finding.digest(),
            review_digest=admission_review.digest(),
            policy_digest=admission_review.policy_digest,
            evidence_ledger_digest=evidence_ledger.digest(),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        finding: EvidenceAdmissionFinding,
        admission_review: EvidenceAdmissionReview,
        evidence_ledger: EvidenceLedger,
        actor_registry: ActorRegistry,
    ) -> EvidenceRecord:
        if (
            finding.outcome
            is not EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
        ):
            raise FoundationError(
                "human evidence decisions may resolve only "
                "requires-human-review findings; automated "
                "admissions and exclusions are not overridable"
            )

        reviewed_finding = admission_review.require_finding(
            finding.record_id
        )

        if reviewed_finding.finding_id != finding.finding_id:
            raise FoundationError(
                "finding does not belong to the supplied admission review"
            )
        if reviewed_finding.digest() != finding.digest():
            raise FoundationError(
                "finding digest does not match the admission review"
            )
        if (
            admission_review.evidence_ledger_digest
            != evidence_ledger.digest()
        ):
            raise FoundationError(
                "admission review is not bound to the supplied "
                "evidence ledger"
            )
        if (
            admission_review.actor_registry_digest
            != actor_registry.digest()
        ):
            raise FoundationError(
                "admission review is not bound to the supplied "
                "actor registry"
            )
        if (
            evidence_ledger.actor_registry_digest
            != actor_registry.digest()
        ):
            raise FoundationError(
                "evidence ledger is not bound to the supplied "
                "actor registry"
            )

        record = evidence_ledger.require_record(
            finding.record_id
        )

        if record.digest() != finding.record_digest:
            raise FoundationError(
                "finding record digest does not match the evidence ledger"
            )

        return record

    @staticmethod
    def _validate_reviewer(
        *,
        reviewer: ActorIdentity,
        record: EvidenceRecord,
    ) -> None:
        if not reviewer.is_eligible_for_human_authority:
            raise FoundationError(
                "evidence-admission decisions require an active human reviewer"
            )

        if reviewer.actor_id == record.produced_by_id:
            raise FoundationError(
                "an evidence producer must not decide admission "
                "of its own record"
            )

        if (
            record.producer_accountability_owner_id is not None
            and reviewer.actor_id
            == record.producer_accountability_owner_id
        ):
            raise FoundationError(
                "a machine producer's accountability owner must not "
                "self-approve that machine's evidence"
            )

    @staticmethod
    def _validate_decision_time(
        *,
        decided_at: UtcTimestamp,
        admission_review: EvidenceAdmissionReview,
    ) -> None:
        if decided_at.value < admission_review.reviewed_at.value:
            raise FoundationError(
                "decided_at must not precede the automated admission review"
            )

    @staticmethod
    def _validate_support(
        *,
        status: EvidenceAdmissionDecisionStatus,
        target_record: EvidenceRecord,
        supporting_record_ids: tuple[ScopedIdentifier, ...],
        admission_review: EvidenceAdmissionReview,
        evidence_ledger: EvidenceLedger,
    ) -> None:
        if (
            status is EvidenceAdmissionDecisionStatus.ADMIT
            and not supporting_record_ids
        ):
            raise FoundationError(
                "admit decisions require at least one supporting record"
            )

        for supporting_id in supporting_record_ids:
            if supporting_id == target_record.record_id:
                raise FoundationError(
                    "an evidence-admission decision must not use "
                    "the target record as its own support"
                )

            supporting_record = evidence_ledger.require_record(
                supporting_id
            )
            supporting_finding = admission_review.require_finding(
                supporting_id
            )

            if (
                status is EvidenceAdmissionDecisionStatus.ADMIT
                and not supporting_finding.is_admitted
            ):
                raise FoundationError(
                    "admit decisions may rely only on evidence "
                    "automatically admitted by the bound review"
                )

            if (
                status is EvidenceAdmissionDecisionStatus.ADMIT
                and not set(
                    supporting_record.subject_ids
                ).intersection(
                    target_record.subject_ids
                )
            ):
                raise FoundationError(
                    "supporting evidence must share at least one "
                    "subject with the target record"
                )

        if status is EvidenceAdmissionDecisionStatus.ADMIT:
            for source_id in target_record.source_record_ids:
                source_finding = admission_review.require_finding(
                    source_id
                )

                if source_finding.is_excluded:
                    raise FoundationError(
                        "human admission must not bypass an excluded source"
                    )
                if source_finding.requires_human_review:
                    raise FoundationError(
                        "human admission must not bypass an unresolved "
                        "source finding"
                    )

    @property
    def resolved_outcome(self) -> EvidenceAdmissionOutcome:
        """Return the admission outcome produced by this human decision."""

        return self.status.resolved_outcome

    @property
    def admits_record(self) -> bool:
        """Return whether the human decision admits the record."""

        return self.status is EvidenceAdmissionDecisionStatus.ADMIT

    @property
    def excludes_record(self) -> bool:
        """Return whether the human decision excludes the record."""

        return self.status is EvidenceAdmissionDecisionStatus.EXCLUDE

    @property
    def defers_record(self) -> bool:
        """Return whether the record remains unresolved."""

        return self.status is EvidenceAdmissionDecisionStatus.DEFER

    @property
    def overrides_automated_exclusion(self) -> bool:
        """Return false because automated exclusions are non-overridable."""

        return False

    @property
    def establishes_claim(self) -> bool:
        """Return false because admission is not proof of a claim."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this decision."""

        supporting_payload: JsonArray = [
            str(record_id)
            for record_id in self.supporting_record_ids
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "admits_record": self.admits_record,
            "decided_at": self.decided_at.isoformat(),
            "decided_by_id": str(self.decided_by_id),
            "decision_id": str(self.decision_id),
            "defers_record": self.defers_record,
            "establishes_claim": self.establishes_claim,
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "excludes_record": self.excludes_record,
            "finding_digest": self.finding_digest.to_payload(),
            "finding_id": str(self.finding_id),
            "overrides_automated_exclusion": (
                self.overrides_automated_exclusion
            ),
            "policy_digest": self.policy_digest.to_payload(),
            "rationale": self.rationale,
            "record_digest": self.record_digest.to_payload(),
            "record_id": str(self.record_id),
            "resolved_outcome": self.resolved_outcome.value,
            "review_digest": self.review_digest.to_payload(),
            "review_id": str(self.review_id),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "supporting_record_ids": supporting_payload,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical decision document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete human decision."""

        return self.to_document().digest(
            domain="evidence-admission-decision"
        )


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionDecisionLedger:
    """Immutable history of human evidence-admission decisions."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-decision-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_accountability_owner_id: ScopedIdentifier
    admission_review_id: ScopedIdentifier
    admission_review_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest
    decisions: tuple[EvidenceAdmissionDecision, ...]

    def __post_init__(self) -> None:
        self._validate_metadata()

        decisions = tuple(self.decisions)
        self._validate_decisions(
            decisions
        )

        ordered = tuple(
            sorted(
                decisions,
                key=lambda decision: (
                    decision.decided_at.value,
                    str(decision.decision_id),
                ),
            )
        )
        self._validate_sequences(
            ordered
        )

        object.__setattr__(
            self,
            "decisions",
            ordered,
        )

    def _validate_metadata(self) -> None:
        expected_identifiers = (
            (
                "ledger_id",
                self.ledger_id,
                CanonicalKey(
                    "evidence-admission-decision-ledger"
                ),
            ),
            (
                "admission_review_id",
                self.admission_review_id,
                CanonicalKey("evidence-admission-review"),
            ),
        )

        for field_name, identifier, expected_namespace in expected_identifiers:
            if not isinstance(
                identifier,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )
            if identifier.namespace != expected_namespace:
                raise FoundationError(
                    f"{field_name} namespace must be "
                    f"{expected_namespace.value}"
                )

        if not isinstance(
            self.created_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )

        for field_name, identifier in (
            ("producer_id", self.producer_id),
            (
                "producer_accountability_owner_id",
                self.producer_accountability_owner_id,
            ),
        ):
            if not isinstance(
                identifier,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )

        if (
            self.producer_accountability_owner_id.namespace
            != CanonicalKey("human")
        ):
            raise FoundationError(
                "producer_accountability_owner_id must identify "
                "a human actor"
            )

        expected_digests = (
            (
                "admission_review_digest",
                self.admission_review_digest,
                "evidence-admission-review",
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

    def _validate_decisions(
        self,
        decisions: tuple[EvidenceAdmissionDecision, ...],
    ) -> None:
        for index, decision in enumerate(decisions):
            if not isinstance(
                decision,
                EvidenceAdmissionDecision,
            ):
                raise FoundationError(
                    f"decisions[{index}] must be an "
                    "EvidenceAdmissionDecision"
                )
            if decision.decided_at.value > self.created_at.value:
                raise FoundationError(
                    "decision ledger must not predate a contained decision"
                )
            if decision.review_id != self.admission_review_id:
                raise FoundationError(
                    "every decision must reference the bound admission review"
                )
            if decision.review_digest != self.admission_review_digest:
                raise FoundationError(
                    "every decision must bind the reviewed admission snapshot"
                )
            if (
                decision.evidence_ledger_digest
                != self.evidence_ledger_digest
            ):
                raise FoundationError(
                    "every decision must bind the same evidence ledger"
                )
            if (
                decision.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every decision must bind the same actor registry"
                )

        decision_ids = tuple(
            decision.decision_id
            for decision in decisions
        )
        if len(decision_ids) != len(set(decision_ids)):
            raise FoundationError(
                "decision ledger must contain unique decision IDs"
            )

    @staticmethod
    def _validate_sequences(
        decisions: tuple[EvidenceAdmissionDecision, ...],
    ) -> None:
        latest_by_finding: dict[
            ScopedIdentifier,
            EvidenceAdmissionDecision,
        ] = {}

        for decision in decisions:
            previous = latest_by_finding.get(
                decision.finding_id
            )

            if previous is not None:
                if (
                    previous.record_id != decision.record_id
                    or previous.record_digest
                    != decision.record_digest
                    or previous.finding_digest
                    != decision.finding_digest
                    or previous.review_digest
                    != decision.review_digest
                ):
                    raise FoundationError(
                        "decision sequence must preserve one bound "
                        "finding, record, and admission review"
                    )
                if previous.decided_at == decision.decided_at:
                    raise FoundationError(
                        "decisions for one finding must use strictly "
                        "increasing decision times"
                    )
                if previous.status.is_terminal:
                    raise FoundationError(
                        "terminal evidence-admission decisions "
                        "must not be replaced"
                    )

            latest_by_finding[
                decision.finding_id
            ] = decision

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        admission_review: EvidenceAdmissionReview,
        actor_registry: ActorRegistry,
        decisions: Iterable[EvidenceAdmissionDecision] = (),
    ) -> EvidenceAdmissionDecisionLedger:
        """Create a ledger bound to one admission review."""

        producer = actor_registry.require_actor(
            producer_id
        )
        producer_owner_id = cls._validate_producer(
            producer
        )

        if (
            admission_review.actor_registry_digest
            != actor_registry.digest()
        ):
            raise FoundationError(
                "admission review is not bound to the supplied "
                "actor registry"
            )
        if created_at.value < admission_review.reviewed_at.value:
            raise FoundationError(
                "decision ledger must not predate the admission review"
            )

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace="evidence-admission-decision-ledger",
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            admission_review_id=admission_review.review_id,
            admission_review_digest=admission_review.digest(),
            evidence_ledger_digest=(
                admission_review.evidence_ledger_digest
            ),
            actor_registry_digest=actor_registry.digest(),
            decisions=tuple(decisions),
        )

    @staticmethod
    def _validate_producer(
        producer: ActorIdentity,
    ) -> ScopedIdentifier:
        if not producer.is_active:
            raise FoundationError(
                "decision-ledger producer must be active"
            )
        if producer.kind not in _DECISION_LEDGER_PRODUCER_KINDS:
            raise FoundationError(
                "decision-ledger producer must be a service "
                "or system actor"
            )

        owner_id = producer.accountability_owner_id

        if owner_id is None:
            raise FoundationError(
                "decision-ledger producer must identify "
                "an accountable human owner"
            )

        return owner_id

    def decisions_for_finding(
        self,
        finding_id: ScopedIdentifier,
    ) -> tuple[EvidenceAdmissionDecision, ...]:
        """Return the ordered decision history for one finding."""

        return tuple(
            decision
            for decision in self.decisions
            if decision.finding_id == finding_id
        )

    def latest_for_finding(
        self,
        finding_id: ScopedIdentifier,
    ) -> EvidenceAdmissionDecision | None:
        """Return the latest human decision for a finding."""

        decisions = self.decisions_for_finding(
            finding_id
        )
        return decisions[-1] if decisions else None

    def resolved_outcome_for(
        self,
        finding: EvidenceAdmissionFinding,
    ) -> EvidenceAdmissionOutcome:
        """Resolve a finding without permitting automated exclusions to change."""

        if finding.outcome is EvidenceAdmissionOutcome.ADMITTED:
            return EvidenceAdmissionOutcome.ADMITTED

        if finding.outcome is EvidenceAdmissionOutcome.EXCLUDED:
            return EvidenceAdmissionOutcome.EXCLUDED

        decision = self.latest_for_finding(
            finding.finding_id
        )

        if decision is None:
            return EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW

        if decision.finding_digest != finding.digest():
            raise FoundationError(
                "latest human decision does not match the supplied finding"
            )

        return decision.resolved_outcome

    def unresolved_findings(
        self,
        *,
        admission_review: EvidenceAdmissionReview,
    ) -> tuple[EvidenceAdmissionFinding, ...]:
        """Return review-required findings without a terminal human decision."""

        self._require_bound_review(
            admission_review
        )

        unresolved: list[EvidenceAdmissionFinding] = []

        for finding in admission_review.human_review_findings():
            decision = self.latest_for_finding(
                finding.finding_id
            )

            if decision is None or not decision.status.is_terminal:
                unresolved.append(
                    finding
                )

        return tuple(
            unresolved
        )

    def admitted_records(
        self,
        *,
        admission_review: EvidenceAdmissionReview,
        evidence_ledger: EvidenceLedger,
    ) -> tuple[EvidenceRecord, ...]:
        """Return automatically and independently human-admitted records."""

        self._require_bound_review(
            admission_review
        )

        if evidence_ledger.digest() != self.evidence_ledger_digest:
            raise FoundationError(
                "decision ledger is not bound to the supplied "
                "evidence ledger"
            )

        admitted: list[EvidenceRecord] = []

        for finding in admission_review.findings:
            if (
                self.resolved_outcome_for(finding)
                is not EvidenceAdmissionOutcome.ADMITTED
            ):
                continue

            record = evidence_ledger.require_record(
                finding.record_id
            )

            if record.digest() != finding.record_digest:
                raise FoundationError(
                    "finding record digest does not match "
                    "the evidence ledger"
                )

            admitted.append(
                record
            )

        return tuple(
            admitted
        )

    def _require_bound_review(
        self,
        admission_review: EvidenceAdmissionReview,
    ) -> None:
        if admission_review.review_id != self.admission_review_id:
            raise FoundationError(
                "decision ledger references a different admission review"
            )
        if admission_review.digest() != self.admission_review_digest:
            raise FoundationError(
                "decision ledger is not bound to the supplied "
                "admission review"
            )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this decision ledger."""

        decision_payloads: JsonArray = [
            decision.to_payload()
            for decision in self.decisions
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "admission_review_digest": (
                self.admission_review_digest.to_payload()
            ),
            "admission_review_id": str(
                self.admission_review_id
            ),
            "created_at": self.created_at.isoformat(),
            "decisions": decision_payloads,
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "ledger_id": str(self.ledger_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical decision-ledger document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete decision ledger."""

        return self.to_document().digest(
            domain="evidence-admission-decision-ledger"
        )
