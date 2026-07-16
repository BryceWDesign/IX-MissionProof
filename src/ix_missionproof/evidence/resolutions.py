"""Resolved evidence-admission snapshots for IX-MissionProof."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.evidence.admissions import (
    EvidenceAdmissionFinding,
    EvidenceAdmissionOutcome,
    EvidenceAdmissionReview,
)
from ix_missionproof.evidence.decisions import (
    EvidenceAdmissionDecision,
    EvidenceAdmissionDecisionLedger,
    EvidenceAdmissionDecisionStatus,
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
)

_RESOLUTION_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class EvidenceAdmissionResolutionSource(StrEnum):
    """Authority source responsible for a resolved admission outcome."""

    AUTOMATED_POLICY = "automated-policy"
    HUMAN_DECISION = "human-decision"
    UNRESOLVED = "unresolved"


class EvidenceAdmissionResolutionStatus(StrEnum):
    """Aggregate state of an evidence-admission resolution snapshot."""

    COMPLETE = "complete"
    HUMAN_REVIEW_OPEN = "human-review-open"

    @property
    def is_complete(self) -> bool:
        """Return whether no admission findings remain unresolved."""

        return self is EvidenceAdmissionResolutionStatus.COMPLETE


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


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionResolution:
    """Resolved state of one automated evidence-admission finding."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-resolution-v1"
    )

    resolution_id: ScopedIdentifier
    resolved_at: UtcTimestamp
    record_id: ScopedIdentifier
    finding_id: ScopedIdentifier
    outcome: EvidenceAdmissionOutcome
    source: EvidenceAdmissionResolutionSource
    decision_id: ScopedIdentifier | None
    decision_status: EvidenceAdmissionDecisionStatus | None
    record_digest: ContentDigest
    finding_digest: ContentDigest
    review_digest: ContentDigest
    decision_digest: ContentDigest | None
    decision_ledger_digest: ContentDigest
    evidence_ledger_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_identifiers()
        self._validate_types()
        self._validate_digests()
        self._validate_source_semantics()

    def _validate_identifiers(self) -> None:
        expected_identifiers = (
            (
                "resolution_id",
                self.resolution_id,
                CanonicalKey("evidence-admission-resolution"),
            ),
            (
                "record_id",
                self.record_id,
                CanonicalKey("record"),
            ),
            (
                "finding_id",
                self.finding_id,
                CanonicalKey("evidence-admission-finding"),
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

        if self.decision_id is not None:
            if not isinstance(
                self.decision_id,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    "decision_id must be a ScopedIdentifier or None"
                )
            if self.decision_id.namespace != CanonicalKey(
                "evidence-admission-decision"
            ):
                raise FoundationError(
                    "decision_id namespace must be "
                    "evidence-admission-decision"
                )

    def _validate_types(self) -> None:
        if not isinstance(
            self.resolved_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "resolved_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.outcome,
            EvidenceAdmissionOutcome,
        ):
            raise FoundationError(
                "outcome must be an EvidenceAdmissionOutcome"
            )
        if not isinstance(
            self.source,
            EvidenceAdmissionResolutionSource,
        ):
            raise FoundationError(
                "source must be an EvidenceAdmissionResolutionSource"
            )
        if (
            self.decision_status is not None
            and not isinstance(
                self.decision_status,
                EvidenceAdmissionDecisionStatus,
            )
        ):
            raise FoundationError(
                "decision_status must be an "
                "EvidenceAdmissionDecisionStatus or None"
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
                "decision_ledger_digest",
                self.decision_ledger_digest,
                "evidence-admission-decision-ledger",
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

        _require_optional_digest(
            self.decision_digest,
            field_name="decision_digest",
            domain="evidence-admission-decision",
        )

    def _validate_source_semantics(self) -> None:
        has_decision_id = self.decision_id is not None
        has_decision_digest = self.decision_digest is not None
        has_decision_status = self.decision_status is not None

        if not (
            has_decision_id
            == has_decision_digest
            == has_decision_status
        ):
            raise FoundationError(
                "decision_id, decision_digest, and decision_status "
                "must be present or absent together"
            )

        if (
            self.source
            is EvidenceAdmissionResolutionSource.AUTOMATED_POLICY
        ):
            if self.outcome not in {
                EvidenceAdmissionOutcome.ADMITTED,
                EvidenceAdmissionOutcome.EXCLUDED,
            }:
                raise FoundationError(
                    "automated-policy resolution must be admitted "
                    "or excluded"
                )
            if has_decision_id:
                raise FoundationError(
                    "automated-policy resolution must not contain "
                    "human decision data"
                )
            return

        if (
            self.source
            is EvidenceAdmissionResolutionSource.HUMAN_DECISION
        ):
            if not has_decision_id:
                raise FoundationError(
                    "human-decision resolution requires decision data"
                )
            if self.decision_status not in {
                EvidenceAdmissionDecisionStatus.ADMIT,
                EvidenceAdmissionDecisionStatus.EXCLUDE,
            }:
                raise FoundationError(
                    "human-decision resolution requires a terminal "
                    "admit or exclude decision"
                )
            if self.outcome is not self.decision_status.resolved_outcome:
                raise FoundationError(
                    "human decision status does not match "
                    "the resolved outcome"
                )
            return

        if (
            self.outcome
            is not EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
        ):
            raise FoundationError(
                "unresolved resolution must retain "
                "requires-human-review outcome"
            )

        if (
            self.decision_status is not None
            and self.decision_status
            is not EvidenceAdmissionDecisionStatus.DEFER
        ):
            raise FoundationError(
                "unresolved resolution may contain only "
                "a deferred human decision"
            )

    @classmethod
    def resolve(
        cls,
        *,
        key: str,
        resolved_at: UtcTimestamp,
        finding: EvidenceAdmissionFinding,
        admission_review: EvidenceAdmissionReview,
        decision: EvidenceAdmissionDecision | None,
        decision_ledger: EvidenceAdmissionDecisionLedger,
        evidence_ledger: EvidenceLedger,
    ) -> EvidenceAdmissionResolution:
        """Resolve one finding without allowing automated outcomes to change."""

        record = cls._validate_bindings(
            finding=finding,
            admission_review=admission_review,
            decision=decision,
            decision_ledger=decision_ledger,
            evidence_ledger=evidence_ledger,
        )

        if finding.outcome in {
            EvidenceAdmissionOutcome.ADMITTED,
            EvidenceAdmissionOutcome.EXCLUDED,
        }:
            if decision is not None:
                raise FoundationError(
                    "automated admission outcomes must not contain "
                    "human decisions"
                )

            outcome = finding.outcome
            source = EvidenceAdmissionResolutionSource.AUTOMATED_POLICY
        elif decision is None:
            outcome = EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
            source = EvidenceAdmissionResolutionSource.UNRESOLVED
        elif decision.status is EvidenceAdmissionDecisionStatus.DEFER:
            outcome = EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
            source = EvidenceAdmissionResolutionSource.UNRESOLVED
        else:
            outcome = decision.resolved_outcome
            source = EvidenceAdmissionResolutionSource.HUMAN_DECISION

        return cls(
            resolution_id=ScopedIdentifier.create(
                namespace="evidence-admission-resolution",
                key=key,
                namespace_field="resolution namespace",
                key_field="resolution key",
            ),
            resolved_at=resolved_at,
            record_id=record.record_id,
            finding_id=finding.finding_id,
            outcome=outcome,
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
            record_digest=record.digest(),
            finding_digest=finding.digest(),
            review_digest=admission_review.digest(),
            decision_digest=(
                decision.digest()
                if decision is not None
                else None
            ),
            decision_ledger_digest=decision_ledger.digest(),
            evidence_ledger_digest=evidence_ledger.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        finding: EvidenceAdmissionFinding,
        admission_review: EvidenceAdmissionReview,
        decision: EvidenceAdmissionDecision | None,
        decision_ledger: EvidenceAdmissionDecisionLedger,
        evidence_ledger: EvidenceLedger,
    ) -> EvidenceRecord:
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
            decision_ledger.admission_review_id
            != admission_review.review_id
        ):
            raise FoundationError(
                "decision ledger references a different admission review"
            )
        if (
            decision_ledger.admission_review_digest
            != admission_review.digest()
        ):
            raise FoundationError(
                "decision ledger is not bound to the supplied "
                "admission review"
            )
        if (
            decision_ledger.evidence_ledger_digest
            != evidence_ledger.digest()
        ):
            raise FoundationError(
                "decision ledger is not bound to the supplied "
                "evidence ledger"
            )

        record = evidence_ledger.require_record(
            finding.record_id
        )

        if record.digest() != finding.record_digest:
            raise FoundationError(
                "finding record digest does not match "
                "the evidence ledger"
            )

        if decision is not None:
            EvidenceAdmissionResolution._validate_decision(
                decision=decision,
                finding=finding,
                admission_review=admission_review,
                decision_ledger=decision_ledger,
                record=record,
            )

        return record

    @staticmethod
    def _validate_decision(
        *,
        decision: EvidenceAdmissionDecision,
        finding: EvidenceAdmissionFinding,
        admission_review: EvidenceAdmissionReview,
        decision_ledger: EvidenceAdmissionDecisionLedger,
        record: EvidenceRecord,
    ) -> None:
        latest = decision_ledger.latest_for_finding(
            finding.finding_id
        )

        if latest is None:
            raise FoundationError(
                "supplied human decision is absent from "
                "the decision ledger"
            )
        if latest.decision_id != decision.decision_id:
            raise FoundationError(
                "supplied human decision is not the latest "
                "decision for the finding"
            )
        if latest.digest() != decision.digest():
            raise FoundationError(
                "human decision digest does not match "
                "the decision ledger"
            )
        if decision.finding_id != finding.finding_id:
            raise FoundationError(
                "human decision references a different finding"
            )
        if decision.finding_digest != finding.digest():
            raise FoundationError(
                "human decision finding digest does not match "
                "the admission finding"
            )
        if decision.record_id != record.record_id:
            raise FoundationError(
                "human decision references a different record"
            )
        if decision.record_digest != record.digest():
            raise FoundationError(
                "human decision record digest does not match "
                "the evidence record"
            )
        if decision.review_id != admission_review.review_id:
            raise FoundationError(
                "human decision references a different admission review"
            )
        if decision.review_digest != admission_review.digest():
            raise FoundationError(
                "human decision review digest does not match "
                "the admission review"
            )

    @property
    def is_admitted(self) -> bool:
        """Return whether the record is resolved as admitted."""

        return self.outcome is EvidenceAdmissionOutcome.ADMITTED

    @property
    def is_excluded(self) -> bool:
        """Return whether the record is resolved as excluded."""

        return self.outcome is EvidenceAdmissionOutcome.EXCLUDED

    @property
    def requires_human_review(self) -> bool:
        """Return whether the record remains unresolved."""

        return (
            self.outcome
            is EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
        )

    @property
    def establishes_claim(self) -> bool:
        """Return false because admission resolution is not claim proof."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this resolution."""

        return {
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
            "establishes_claim": self.establishes_claim,
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "finding_digest": self.finding_digest.to_payload(),
            "finding_id": str(self.finding_id),
            "is_admitted": self.is_admitted,
            "is_excluded": self.is_excluded,
            "outcome": self.outcome.value,
            "record_digest": self.record_digest.to_payload(),
            "record_id": str(self.record_id),
            "requires_human_review": (
                self.requires_human_review
            ),
            "resolution_id": str(self.resolution_id),
            "resolved_at": self.resolved_at.isoformat(),
            "review_digest": self.review_digest.to_payload(),
            "schema": self.SCHEMA.value,
            "source": self.source.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical resolution document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete resolution."""

        return self.to_document().digest(
            domain="evidence-admission-resolution"
        )


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionResolutionSnapshot:
    """Complete resolved view of one evidence-admission review."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-resolution-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    resolved_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    status: EvidenceAdmissionResolutionStatus
    admission_review_id: ScopedIdentifier
    decision_ledger_id: ScopedIdentifier
    evidence_ledger_id: ScopedIdentifier
    resolutions: tuple[EvidenceAdmissionResolution, ...]
    admission_review_digest: ContentDigest
    decision_ledger_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        resolutions = tuple(
            self.resolutions
        )
        self._validate_resolutions(
            resolutions
        )

        ordered = tuple(
            sorted(
                resolutions,
                key=lambda resolution: str(
                    resolution.record_id
                ),
            )
        )
        object.__setattr__(
            self,
            "resolutions",
            ordered,
        )

        expected_status = (
            EvidenceAdmissionResolutionStatus.HUMAN_REVIEW_OPEN
            if any(
                resolution.requires_human_review
                for resolution in ordered
            )
            else EvidenceAdmissionResolutionStatus.COMPLETE
        )

        if self.status is not expected_status:
            raise FoundationError(
                "resolution snapshot status does not match "
                "its unresolved evidence count"
            )

    def _validate_metadata(self) -> None:
        expected_identifiers = (
            (
                "snapshot_id",
                self.snapshot_id,
                CanonicalKey(
                    "evidence-admission-resolution-snapshot"
                ),
            ),
            (
                "admission_review_id",
                self.admission_review_id,
                CanonicalKey("evidence-admission-review"),
            ),
            (
                "decision_ledger_id",
                self.decision_ledger_id,
                CanonicalKey(
                    "evidence-admission-decision-ledger"
                ),
            ),
            (
                "evidence_ledger_id",
                self.evidence_ledger_id,
                CanonicalKey("evidence-ledger"),
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
            self.resolved_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "resolved_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.produced_by_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "produced_by_id must be a ScopedIdentifier"
            )
        if not isinstance(
            self.producer_kind,
            ActorKind,
        ):
            raise FoundationError(
                "producer_kind must be an ActorKind"
            )
        if self.producer_kind not in _RESOLUTION_PRODUCER_KINDS:
            raise FoundationError(
                "resolution producer must be a service "
                "or system actor"
            )
        if self.produced_by_id.namespace != CanonicalKey(
            self.producer_kind.value
        ):
            raise FoundationError(
                "produced_by_id namespace must match producer_kind"
            )
        if not isinstance(
            self.producer_accountability_owner_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "producer_accountability_owner_id must be "
                "a ScopedIdentifier"
            )
        if (
            self.producer_accountability_owner_id.namespace
            != CanonicalKey("human")
        ):
            raise FoundationError(
                "producer_accountability_owner_id must identify "
                "a human actor"
            )
        if not isinstance(
            self.status,
            EvidenceAdmissionResolutionStatus,
        ):
            raise FoundationError(
                "status must be an "
                "EvidenceAdmissionResolutionStatus"
            )

    def _validate_digests(self) -> None:
        expected_digests = (
            (
                "admission_review_digest",
                self.admission_review_digest,
                "evidence-admission-review",
            ),
            (
                "decision_ledger_digest",
                self.decision_ledger_digest,
                "evidence-admission-decision-ledger",
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

    def _validate_resolutions(
        self,
        resolutions: tuple[
            EvidenceAdmissionResolution,
            ...,
        ],
    ) -> None:
        for index, resolution in enumerate(
            resolutions
        ):
            if not isinstance(
                resolution,
                EvidenceAdmissionResolution,
            ):
                raise FoundationError(
                    f"resolutions[{index}] must be an "
                    "EvidenceAdmissionResolution"
                )
            if resolution.resolved_at != self.resolved_at:
                raise FoundationError(
                    "every resolution must use the snapshot "
                    "resolution time"
                )
            if (
                resolution.review_digest
                != self.admission_review_digest
            ):
                raise FoundationError(
                    "every resolution must bind "
                    "the admission review"
                )
            if (
                resolution.decision_ledger_digest
                != self.decision_ledger_digest
            ):
                raise FoundationError(
                    "every resolution must bind "
                    "the decision ledger"
                )
            if (
                resolution.evidence_ledger_digest
                != self.evidence_ledger_digest
            ):
                raise FoundationError(
                    "every resolution must bind "
                    "the evidence ledger"
                )

        record_ids = tuple(
            resolution.record_id
            for resolution in resolutions
        )
        if len(record_ids) != len(set(record_ids)):
            raise FoundationError(
                "resolution snapshot must contain one "
                "resolution per record"
            )

        finding_ids = tuple(
            resolution.finding_id
            for resolution in resolutions
        )
        if len(finding_ids) != len(set(finding_ids)):
            raise FoundationError(
                "resolution snapshot must contain one "
                "resolution per finding"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        resolved_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        admission_review: EvidenceAdmissionReview,
        decision_ledger: EvidenceAdmissionDecisionLedger,
        evidence_ledger: EvidenceLedger,
        actor_registry: ActorRegistry,
    ) -> EvidenceAdmissionResolutionSnapshot:
        """Create one immutable resolved admission snapshot."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = cls._validate_producer(
            producer
        )

        cls._validate_bindings(
            resolved_at=resolved_at,
            admission_review=admission_review,
            decision_ledger=decision_ledger,
            evidence_ledger=evidence_ledger,
            actor_registry=actor_registry,
        )
        cls._validate_decision_membership(
            admission_review=admission_review,
            decision_ledger=decision_ledger,
        )

        resolutions = tuple(
            EvidenceAdmissionResolution.resolve(
                key=(
                    f"{key}-"
                    f"{str(finding.record_id)}"
                ),
                resolved_at=resolved_at,
                finding=finding,
                admission_review=admission_review,
                decision=decision_ledger.latest_for_finding(
                    finding.finding_id
                ),
                decision_ledger=decision_ledger,
                evidence_ledger=evidence_ledger,
            )
            for finding in admission_review.findings
        )

        status = (
            EvidenceAdmissionResolutionStatus.HUMAN_REVIEW_OPEN
            if any(
                resolution.requires_human_review
                for resolution in resolutions
            )
            else EvidenceAdmissionResolutionStatus.COMPLETE
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace=(
                    "evidence-admission-resolution-snapshot"
                ),
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            resolved_at=resolved_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            status=status,
            admission_review_id=admission_review.review_id,
            decision_ledger_id=decision_ledger.ledger_id,
            evidence_ledger_id=evidence_ledger.ledger_id,
            resolutions=resolutions,
            admission_review_digest=admission_review.digest(),
            decision_ledger_digest=decision_ledger.digest(),
            evidence_ledger_digest=evidence_ledger.digest(),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_producer(
        producer: ActorIdentity,
    ) -> ScopedIdentifier:
        if not producer.is_active:
            raise FoundationError(
                "resolution producer must be active"
            )
        if producer.kind not in _RESOLUTION_PRODUCER_KINDS:
            raise FoundationError(
                "resolution producer must be a service "
                "or system actor"
            )

        owner_id = producer.accountability_owner_id

        if owner_id is None:
            raise FoundationError(
                "resolution producer must identify "
                "an accountable human owner"
            )

        return owner_id

    @staticmethod
    def _validate_bindings(
        *,
        resolved_at: UtcTimestamp,
        admission_review: EvidenceAdmissionReview,
        decision_ledger: EvidenceAdmissionDecisionLedger,
        evidence_ledger: EvidenceLedger,
        actor_registry: ActorRegistry,
    ) -> None:
        evidence_ledger_digest = evidence_ledger.digest()
        actor_registry_digest = actor_registry.digest()

        if (
            admission_review.evidence_ledger_digest
            != evidence_ledger_digest
        ):
            raise FoundationError(
                "admission review is not bound to "
                "the supplied evidence ledger"
            )
        if (
            admission_review.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "admission review is not bound to "
                "the supplied actor registry"
            )
        if (
            decision_ledger.admission_review_id
            != admission_review.review_id
        ):
            raise FoundationError(
                "decision ledger references a different "
                "admission review"
            )
        if (
            decision_ledger.admission_review_digest
            != admission_review.digest()
        ):
            raise FoundationError(
                "decision ledger is not bound to "
                "the supplied admission review"
            )
        if (
            decision_ledger.evidence_ledger_digest
            != evidence_ledger_digest
        ):
            raise FoundationError(
                "decision ledger is not bound to "
                "the supplied evidence ledger"
            )
        if (
            decision_ledger.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "decision ledger is not bound to "
                "the supplied actor registry"
            )

        if resolved_at.value < admission_review.reviewed_at.value:
            raise FoundationError(
                "resolution snapshot must not predate "
                "the admission review"
            )
        if resolved_at.value < decision_ledger.created_at.value:
            raise FoundationError(
                "resolution snapshot must not predate "
                "the decision ledger"
            )
        if resolved_at.value < evidence_ledger.created_at.value:
            raise FoundationError(
                "resolution snapshot must not predate "
                "the evidence ledger"
            )

    @staticmethod
    def _validate_decision_membership(
        *,
        admission_review: EvidenceAdmissionReview,
        decision_ledger: EvidenceAdmissionDecisionLedger,
    ) -> None:
        findings_by_id = {
            finding.finding_id: finding
            for finding in admission_review.findings
        }

        for decision in decision_ledger.decisions:
            finding = findings_by_id.get(
                decision.finding_id
            )

            if finding is None:
                raise FoundationError(
                    "decision ledger contains a decision "
                    "for a finding absent from the admission review"
                )
            if decision.finding_digest != finding.digest():
                raise FoundationError(
                    "decision finding digest does not match "
                    "the admission review"
                )
            if decision.record_id != finding.record_id:
                raise FoundationError(
                    "decision record does not match "
                    "the admission finding"
                )
            if decision.record_digest != finding.record_digest:
                raise FoundationError(
                    "decision record digest does not match "
                    "the admission finding"
                )

    @property
    def is_complete(self) -> bool:
        """Return whether all review-required evidence was resolved."""

        return self.status.is_complete

    @property
    def requires_human_attention(self) -> bool:
        """Return whether unresolved evidence remains open."""

        return not self.is_complete

    @property
    def establishes_claim(self) -> bool:
        """Return false because resolved admission is not claim proof."""

        return False

    @property
    def admitted_count(self) -> int:
        """Return the number of admitted evidence records."""

        return sum(
            resolution.is_admitted
            for resolution in self.resolutions
        )

    @property
    def excluded_count(self) -> int:
        """Return the number of excluded evidence records."""

        return sum(
            resolution.is_excluded
            for resolution in self.resolutions
        )

    @property
    def unresolved_count(self) -> int:
        """Return the number of evidence records awaiting human review."""

        return sum(
            resolution.requires_human_review
            for resolution in self.resolutions
        )

    @property
    def total_count(self) -> int:
        """Return the total number of resolved admission entries."""

        return len(
            self.resolutions
        )

    @property
    def has_exclusions(self) -> bool:
        """Return whether the snapshot preserves excluded evidence."""

        return self.excluded_count > 0

    def resolution_for(
        self,
        record_id: ScopedIdentifier,
    ) -> EvidenceAdmissionResolution | None:
        """Return the resolution for an evidence record."""

        for resolution in self.resolutions:
            if resolution.record_id == record_id:
                return resolution

        return None

    def require_resolution(
        self,
        record_id: ScopedIdentifier,
    ) -> EvidenceAdmissionResolution:
        """Return a resolution or fail when it is absent."""

        resolution = self.resolution_for(
            record_id
        )

        if resolution is None:
            raise FoundationError(
                "resolution snapshot does not contain "
                f"record: {record_id}"
            )

        return resolution

    def admitted_records(
        self,
        *,
        evidence_ledger: EvidenceLedger,
    ) -> tuple[EvidenceRecord, ...]:
        """Return admitted evidence after verifying ledger binding."""

        return self._records_with_outcome(
            outcome=EvidenceAdmissionOutcome.ADMITTED,
            evidence_ledger=evidence_ledger,
        )

    def excluded_records(
        self,
        *,
        evidence_ledger: EvidenceLedger,
    ) -> tuple[EvidenceRecord, ...]:
        """Return excluded evidence without deleting or hiding it."""

        return self._records_with_outcome(
            outcome=EvidenceAdmissionOutcome.EXCLUDED,
            evidence_ledger=evidence_ledger,
        )

    def unresolved_records(
        self,
        *,
        evidence_ledger: EvidenceLedger,
    ) -> tuple[EvidenceRecord, ...]:
        """Return evidence that still requires human admission review."""

        return self._records_with_outcome(
            outcome=(
                EvidenceAdmissionOutcome
                .REQUIRES_HUMAN_REVIEW
            ),
            evidence_ledger=evidence_ledger,
        )

    def _records_with_outcome(
        self,
        *,
        outcome: EvidenceAdmissionOutcome,
        evidence_ledger: EvidenceLedger,
    ) -> tuple[EvidenceRecord, ...]:
        if evidence_ledger.digest() != self.evidence_ledger_digest:
            raise FoundationError(
                "resolution snapshot is not bound to "
                "the supplied evidence ledger"
            )

        matching_ids: set[ScopedIdentifier] = set()

        for resolution in self.resolutions:
            if resolution.outcome is not outcome:
                continue

            record = evidence_ledger.require_record(
                resolution.record_id
            )

            if record.digest() != resolution.record_digest:
                raise FoundationError(
                    "resolution record digest does not match "
                    "the evidence ledger"
                )

            matching_ids.add(
                record.record_id
            )

        return tuple(
            record
            for record in evidence_ledger.records
            if record.record_id in matching_ids
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this snapshot."""

        resolution_payloads: JsonArray = [
            resolution.to_payload()
            for resolution in self.resolutions
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
            "admitted_count": self.admitted_count,
            "decision_ledger_digest": (
                self.decision_ledger_digest.to_payload()
            ),
            "decision_ledger_id": str(
                self.decision_ledger_id
            ),
            "establishes_claim": self.establishes_claim,
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "evidence_ledger_id": str(
                self.evidence_ledger_id
            ),
            "excluded_count": self.excluded_count,
            "has_exclusions": self.has_exclusions,
            "is_complete": self.is_complete,
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "requires_human_attention": (
                self.requires_human_attention
            ),
            "resolutions": resolution_payloads,
            "resolved_at": self.resolved_at.isoformat(),
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "status": self.status.value,
            "total_count": self.total_count,
            "unresolved_count": self.unresolved_count,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical snapshot document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete resolution snapshot."""

        return self.to_document().digest(
            domain="evidence-admission-resolution-snapshot"
        )
