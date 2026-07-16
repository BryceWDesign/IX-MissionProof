"""Deterministic evidence-admission policies and review findings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.evidence.records import (
    EvidenceKind,
    EvidenceLedger,
    EvidenceOrigin,
    EvidenceRecord,
    EvidenceStatus,
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


class EvidenceAdmissionOutcome(StrEnum):
    """Possible deterministic dispositions of one evidence record."""

    ADMITTED = "admitted"
    REQUIRES_HUMAN_REVIEW = "requires-human-review"
    EXCLUDED = "excluded"

    @property
    def is_admitted(self) -> bool:
        """Return whether the record passed automated admission."""

        return self is EvidenceAdmissionOutcome.ADMITTED


class EvidenceAdmissionReason(StrEnum):
    """Stable reasons emitted by evidence-admission review."""

    ADMITTED_BY_POLICY = "admitted-by-policy"
    CORROBORATED_BY_ADMITTED_SOURCE = (
        "corroborated-by-admitted-source"
    )
    ORIGIN_REQUIRES_HUMAN_REVIEW = (
        "origin-requires-human-review"
    )
    SOURCE_REQUIRES_HUMAN_REVIEW = (
        "source-requires-human-review"
    )
    KIND_NOT_ALLOWED = "kind-not-allowed"
    ORIGIN_NOT_ALLOWED = "origin-not-allowed"
    STATUS_NOT_ALLOWED = "status-not-allowed"
    RECORD_INVALIDATED = "record-invalidated"
    PAYLOAD_DIGEST_MISMATCH = "payload-digest-mismatch"
    ACTOR_REGISTRY_BINDING_MISMATCH = (
        "actor-registry-binding-mismatch"
    )
    CORROBORATION_MISSING = "corroboration-missing"
    SOURCE_EXCLUDED = "source-excluded"
    USABLE_PRIMARY_ANCESTRY_MISSING = (
        "usable-primary-ancestry-missing"
    )


_EXCLUSION_REASONS: Final[frozenset[EvidenceAdmissionReason]] = frozenset(
    {
        EvidenceAdmissionReason.KIND_NOT_ALLOWED,
        EvidenceAdmissionReason.ORIGIN_NOT_ALLOWED,
        EvidenceAdmissionReason.STATUS_NOT_ALLOWED,
        EvidenceAdmissionReason.RECORD_INVALIDATED,
        EvidenceAdmissionReason.PAYLOAD_DIGEST_MISMATCH,
        EvidenceAdmissionReason.ACTOR_REGISTRY_BINDING_MISMATCH,
        EvidenceAdmissionReason.CORROBORATION_MISSING,
        EvidenceAdmissionReason.SOURCE_EXCLUDED,
        EvidenceAdmissionReason.USABLE_PRIMARY_ANCESTRY_MISSING,
    }
)

_HUMAN_REVIEW_REASONS: Final[
    frozenset[EvidenceAdmissionReason]
] = frozenset(
    {
        EvidenceAdmissionReason.ORIGIN_REQUIRES_HUMAN_REVIEW,
        EvidenceAdmissionReason.SOURCE_REQUIRES_HUMAN_REVIEW,
    }
)

_ADMISSION_REVIEWER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


def _normalize_kinds(
    values: tuple[EvidenceKind, ...],
) -> tuple[EvidenceKind, ...]:
    normalized: set[EvidenceKind] = set()

    for index, value in enumerate(values):
        if not isinstance(value, EvidenceKind):
            raise FoundationError(
                f"allowed_kinds[{index}] must be an EvidenceKind"
            )
        normalized.add(value)

    if not normalized:
        raise FoundationError(
            "allowed_kinds must not be empty"
        )

    return tuple(
        sorted(
            normalized,
            key=lambda value: value.value,
        )
    )


def _normalize_origins(
    values: tuple[EvidenceOrigin, ...],
    *,
    field_name: str,
    allow_empty: bool,
) -> tuple[EvidenceOrigin, ...]:
    normalized: set[EvidenceOrigin] = set()

    for index, value in enumerate(values):
        if not isinstance(value, EvidenceOrigin):
            raise FoundationError(
                f"{field_name}[{index}] must be an EvidenceOrigin"
            )
        normalized.add(value)

    if not allow_empty and not normalized:
        raise FoundationError(
            f"{field_name} must not be empty"
        )

    return tuple(
        sorted(
            normalized,
            key=lambda value: value.value,
        )
    )


def _normalize_statuses(
    values: tuple[EvidenceStatus, ...],
) -> tuple[EvidenceStatus, ...]:
    normalized: set[EvidenceStatus] = set()

    for index, value in enumerate(values):
        if not isinstance(value, EvidenceStatus):
            raise FoundationError(
                f"allowed_statuses[{index}] must be an EvidenceStatus"
            )
        normalized.add(value)

    if not normalized:
        raise FoundationError(
            "allowed_statuses must not be empty"
        )

    if EvidenceStatus.INVALIDATED in normalized:
        raise FoundationError(
            "invalidated evidence must never be an allowed status"
        )

    return tuple(
        sorted(
            normalized,
            key=lambda value: value.value,
        )
    )


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionPolicy:
    """A human-authored policy for automated evidence admission review."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-policy-v1"
    )

    policy_id: ScopedIdentifier
    created_at: UtcTimestamp
    authored_by_id: ScopedIdentifier
    summary: str
    allowed_kinds: tuple[EvidenceKind, ...]
    allowed_origins: tuple[EvidenceOrigin, ...]
    allowed_statuses: tuple[EvidenceStatus, ...]
    human_review_origins: tuple[EvidenceOrigin, ...]
    require_primary_ancestry: bool
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        if not isinstance(
            self.policy_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "policy_id must be a ScopedIdentifier"
            )
        if self.policy_id.namespace != CanonicalKey(
            "evidence-admission-policy"
        ):
            raise FoundationError(
                "policy_id namespace must be "
                "evidence-admission-policy"
            )
        if not isinstance(
            self.created_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.authored_by_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "authored_by_id must be a ScopedIdentifier"
            )
        if self.authored_by_id.namespace != CanonicalKey(
            "human"
        ):
            raise FoundationError(
                "authored_by_id must identify a human actor"
            )
        if not isinstance(
            self.require_primary_ancestry,
            bool,
        ):
            raise FoundationError(
                "require_primary_ancestry must be a boolean"
            )
        if not isinstance(
            self.actor_registry_digest,
            ContentDigest,
        ):
            raise FoundationError(
                "actor_registry_digest must be a ContentDigest"
            )
        if self.actor_registry_digest.domain != CanonicalKey(
            "actor-registry"
        ):
            raise FoundationError(
                "actor_registry_digest domain must be actor-registry"
            )

        object.__setattr__(
            self,
            "summary",
            require_text(
                self.summary,
                field_name="summary",
            ),
        )
        object.__setattr__(
            self,
            "allowed_kinds",
            _normalize_kinds(
                self.allowed_kinds
            ),
        )
        object.__setattr__(
            self,
            "allowed_origins",
            _normalize_origins(
                self.allowed_origins,
                field_name="allowed_origins",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "allowed_statuses",
            _normalize_statuses(
                self.allowed_statuses
            ),
        )
        object.__setattr__(
            self,
            "human_review_origins",
            _normalize_origins(
                self.human_review_origins,
                field_name="human_review_origins",
                allow_empty=True,
            ),
        )

        if not set(
            self.human_review_origins
        ).issubset(
            self.allowed_origins
        ):
            raise FoundationError(
                "human_review_origins must be a subset "
                "of allowed_origins"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        authored_by_id: ScopedIdentifier,
        summary: str,
        actor_registry: ActorRegistry,
        allowed_kinds: tuple[EvidenceKind, ...],
        allowed_origins: tuple[EvidenceOrigin, ...],
        allowed_statuses: tuple[EvidenceStatus, ...],
        human_review_origins: tuple[EvidenceOrigin, ...] = (),
        require_primary_ancestry: bool = True,
    ) -> EvidenceAdmissionPolicy:
        """Create a policy after validating its human author."""

        author = actor_registry.require_actor(
            authored_by_id
        )

        if not author.is_eligible_for_human_authority:
            raise FoundationError(
                "evidence-admission policy requires "
                "an active human author"
            )

        return cls(
            policy_id=ScopedIdentifier.create(
                namespace="evidence-admission-policy",
                key=key,
                namespace_field="policy namespace",
                key_field="policy key",
            ),
            created_at=created_at,
            authored_by_id=authored_by_id,
            summary=summary,
            allowed_kinds=allowed_kinds,
            allowed_origins=allowed_origins,
            allowed_statuses=allowed_statuses,
            human_review_origins=human_review_origins,
            require_primary_ancestry=require_primary_ancestry,
            actor_registry_digest=actor_registry.digest(),
        )

    def allows_kind(
        self,
        kind: EvidenceKind,
    ) -> bool:
        """Return whether an evidence kind is permitted."""

        if not isinstance(
            kind,
            EvidenceKind,
        ):
            raise FoundationError(
                "kind must be an EvidenceKind"
            )

        return kind in self.allowed_kinds

    def allows_origin(
        self,
        origin: EvidenceOrigin,
    ) -> bool:
        """Return whether an evidence origin is permitted."""

        if not isinstance(
            origin,
            EvidenceOrigin,
        ):
            raise FoundationError(
                "origin must be an EvidenceOrigin"
            )

        return origin in self.allowed_origins

    def allows_status(
        self,
        status: EvidenceStatus,
    ) -> bool:
        """Return whether an evidence status is permitted."""

        if not isinstance(
            status,
            EvidenceStatus,
        ):
            raise FoundationError(
                "status must be an EvidenceStatus"
            )

        return status in self.allowed_statuses

    def requires_human_review(
        self,
        origin: EvidenceOrigin,
    ) -> bool:
        """Return whether an origin requires a separate human review."""

        if not isinstance(
            origin,
            EvidenceOrigin,
        ):
            raise FoundationError(
                "origin must be an EvidenceOrigin"
            )

        return origin in self.human_review_origins

    def to_payload(self) -> JsonObject:
        """Return the deterministic policy representation."""

        allowed_kind_payload: JsonArray = [
            kind.value
            for kind in self.allowed_kinds
        ]
        allowed_origin_payload: JsonArray = [
            origin.value
            for origin in self.allowed_origins
        ]
        allowed_status_payload: JsonArray = [
            status.value
            for status in self.allowed_statuses
        ]
        review_origin_payload: JsonArray = [
            origin.value
            for origin in self.human_review_origins
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "allowed_kinds": allowed_kind_payload,
            "allowed_origins": allowed_origin_payload,
            "allowed_statuses": allowed_status_payload,
            "authored_by_id": str(self.authored_by_id),
            "created_at": self.created_at.isoformat(),
            "human_review_origins": review_origin_payload,
            "policy_id": str(self.policy_id),
            "require_primary_ancestry": (
                self.require_primary_ancestry
            ),
            "schema": self.SCHEMA.value,
            "summary": self.summary,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical policy document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete admission policy."""

        return self.to_document().digest(
            domain="evidence-admission-policy"
        )


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionFinding:
    """One deterministic admission finding over an evidence record."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-finding-v1"
    )

    finding_id: ScopedIdentifier
    reviewed_at: UtcTimestamp
    record_id: ScopedIdentifier
    outcome: EvidenceAdmissionOutcome
    reasons: tuple[EvidenceAdmissionReason, ...]
    source_record_ids: tuple[ScopedIdentifier, ...]
    record_digest: ContentDigest
    policy_digest: ContentDigest
    evidence_ledger_digest: ContentDigest

    def __post_init__(self) -> None:
        expected_identifiers = (
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
            self.reviewed_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "reviewed_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.outcome,
            EvidenceAdmissionOutcome,
        ):
            raise FoundationError(
                "outcome must be an EvidenceAdmissionOutcome"
            )

        normalized_reasons: set[EvidenceAdmissionReason] = set()

        for index, reason in enumerate(self.reasons):
            if not isinstance(
                reason,
                EvidenceAdmissionReason,
            ):
                raise FoundationError(
                    f"reasons[{index}] must be "
                    "an EvidenceAdmissionReason"
                )
            normalized_reasons.add(reason)

        if not normalized_reasons:
            raise FoundationError(
                "admission finding reasons must not be empty"
            )

        object.__setattr__(
            self,
            "reasons",
            tuple(
                sorted(
                    normalized_reasons,
                    key=lambda reason: reason.value,
                )
            ),
        )

        normalized_sources: set[ScopedIdentifier] = set()

        for index, source_id in enumerate(
            self.source_record_ids
        ):
            if not isinstance(
                source_id,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"source_record_ids[{index}] must be "
                    "a ScopedIdentifier"
                )
            if source_id.namespace != CanonicalKey(
                "record"
            ):
                raise FoundationError(
                    "source_record_ids must identify record values"
                )
            normalized_sources.add(source_id)

        object.__setattr__(
            self,
            "source_record_ids",
            tuple(
                sorted(
                    normalized_sources,
                    key=str,
                )
            ),
        )

        expected_digests = (
            (
                "record_digest",
                self.record_digest,
                CanonicalKey("evidence-record"),
            ),
            (
                "policy_digest",
                self.policy_digest,
                CanonicalKey("evidence-admission-policy"),
            ),
            (
                "evidence_ledger_digest",
                self.evidence_ledger_digest,
                CanonicalKey("evidence-ledger"),
            ),
        )

        for field_name, digest, expected_domain in expected_digests:
            if not isinstance(
                digest,
                ContentDigest,
            ):
                raise FoundationError(
                    f"{field_name} must be a ContentDigest"
                )
            if digest.domain != expected_domain:
                raise FoundationError(
                    f"{field_name} domain must be "
                    f"{expected_domain.value}"
                )

        self._validate_outcome_reasons()

    def _validate_outcome_reasons(self) -> None:
        reason_set = set(self.reasons)
        exclusion_reasons = reason_set.intersection(
            _EXCLUSION_REASONS
        )
        review_reasons = reason_set.intersection(
            _HUMAN_REVIEW_REASONS
        )

        if self.outcome is EvidenceAdmissionOutcome.EXCLUDED:
            if not exclusion_reasons:
                raise FoundationError(
                    "excluded evidence requires at least one "
                    "exclusion reason"
                )
            if EvidenceAdmissionReason.ADMITTED_BY_POLICY in reason_set:
                raise FoundationError(
                    "excluded evidence must not be marked admitted"
                )
            return

        if exclusion_reasons:
            raise FoundationError(
                "non-excluded evidence must not contain "
                "exclusion reasons"
            )

        if (
            self.outcome
            is EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
        ):
            if not review_reasons:
                raise FoundationError(
                    "human-review outcome requires at least "
                    "one human-review reason"
                )
            if EvidenceAdmissionReason.ADMITTED_BY_POLICY in reason_set:
                raise FoundationError(
                    "human-review evidence must not be marked admitted"
                )
            return

        if review_reasons:
            raise FoundationError(
                "admitted evidence must not retain "
                "human-review reasons"
            )
        if reason_set != {
            EvidenceAdmissionReason.ADMITTED_BY_POLICY
        } and EvidenceAdmissionReason.ADMITTED_BY_POLICY not in reason_set:
            raise FoundationError(
                "admitted evidence requires the admitted-by-policy reason"
            )

    @property
    def is_admitted(self) -> bool:
        """Return whether the record passed automated admission."""

        return self.outcome.is_admitted

    @property
    def requires_human_review(self) -> bool:
        """Return whether admission remains human-dependent."""

        return (
            self.outcome
            is EvidenceAdmissionOutcome.REQUIRES_HUMAN_REVIEW
        )

    @property
    def is_excluded(self) -> bool:
        """Return whether the record was excluded."""

        return self.outcome is EvidenceAdmissionOutcome.EXCLUDED

    def to_payload(self) -> JsonObject:
        """Return the deterministic admission-finding representation."""

        reason_payload: JsonArray = [
            reason.value
            for reason in self.reasons
        ]
        source_payload: JsonArray = [
            str(record_id)
            for record_id in self.source_record_ids
        ]

        return {
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "finding_id": str(self.finding_id),
            "is_admitted": self.is_admitted,
            "is_excluded": self.is_excluded,
            "outcome": self.outcome.value,
            "policy_digest": self.policy_digest.to_payload(),
            "reasons": reason_payload,
            "record_digest": self.record_digest.to_payload(),
            "record_id": str(self.record_id),
            "requires_human_review": (
                self.requires_human_review
            ),
            "reviewed_at": self.reviewed_at.isoformat(),
            "schema": self.SCHEMA.value,
            "source_record_ids": source_payload,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical finding document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete admission finding."""

        return self.to_document().digest(
            domain="evidence-admission-finding"
        )


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionReview:
    """A deterministic review over every record in a closed ledger."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "evidence-admission-review-v1"
    )

    review_id: ScopedIdentifier
    reviewed_at: UtcTimestamp
    reviewed_by_id: ScopedIdentifier
    reviewer_kind: ActorKind
    reviewer_accountability_owner_id: ScopedIdentifier
    policy_id: ScopedIdentifier
    evidence_ledger_id: ScopedIdentifier
    findings: tuple[EvidenceAdmissionFinding, ...]
    policy_digest: ContentDigest
    evidence_ledger_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_identifiers()
        self._validate_reviewer()
        self._validate_digests()

        findings = tuple(self.findings)

        for index, finding in enumerate(findings):
            if not isinstance(
                finding,
                EvidenceAdmissionFinding,
            ):
                raise FoundationError(
                    f"findings[{index}] must be an "
                    "EvidenceAdmissionFinding"
                )
            if finding.reviewed_at != self.reviewed_at:
                raise FoundationError(
                    "all admission findings must use "
                    "the review timestamp"
                )
            if finding.policy_digest != self.policy_digest:
                raise FoundationError(
                    "all admission findings must bind "
                    "the reviewed policy"
                )
            if (
                finding.evidence_ledger_digest
                != self.evidence_ledger_digest
            ):
                raise FoundationError(
                    "all admission findings must bind "
                    "the reviewed evidence ledger"
                )

        record_ids = tuple(
            finding.record_id
            for finding in findings
        )
        if len(record_ids) != len(set(record_ids)):
            raise FoundationError(
                "admission review must contain one finding "
                "per record"
            )

        object.__setattr__(
            self,
            "findings",
            tuple(
                sorted(
                    findings,
                    key=lambda finding: str(
                        finding.record_id
                    ),
                )
            ),
        )

    def _validate_identifiers(self) -> None:
        expected_identifiers = (
            (
                "review_id",
                self.review_id,
                CanonicalKey("evidence-admission-review"),
            ),
            (
                "policy_id",
                self.policy_id,
                CanonicalKey("evidence-admission-policy"),
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

        for field_name, identifier in (
            ("reviewed_by_id", self.reviewed_by_id),
            (
                "reviewer_accountability_owner_id",
                self.reviewer_accountability_owner_id,
            ),
        ):
            if not isinstance(
                identifier,
                ScopedIdentifier,
            ):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )

        if not isinstance(
            self.reviewed_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "reviewed_at must be a UtcTimestamp"
            )

    def _validate_reviewer(self) -> None:
        if not isinstance(
            self.reviewer_kind,
            ActorKind,
        ):
            raise FoundationError(
                "reviewer_kind must be an ActorKind"
            )
        if self.reviewer_kind not in _ADMISSION_REVIEWER_KINDS:
            raise FoundationError(
                "admission reviewer must be a service "
                "or system actor"
            )
        if self.reviewed_by_id.namespace != CanonicalKey(
            self.reviewer_kind.value
        ):
            raise FoundationError(
                "reviewed_by_id namespace must match reviewer_kind"
            )
        if (
            self.reviewer_accountability_owner_id.namespace
            != CanonicalKey("human")
        ):
            raise FoundationError(
                "reviewer_accountability_owner_id must "
                "identify a human actor"
            )

    def _validate_digests(self) -> None:
        expected_digests = (
            (
                "policy_digest",
                self.policy_digest,
                CanonicalKey("evidence-admission-policy"),
            ),
            (
                "evidence_ledger_digest",
                self.evidence_ledger_digest,
                CanonicalKey("evidence-ledger"),
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                CanonicalKey("actor-registry"),
            ),
        )

        for field_name, digest, expected_domain in expected_digests:
            if not isinstance(
                digest,
                ContentDigest,
            ):
                raise FoundationError(
                    f"{field_name} must be a ContentDigest"
                )
            if digest.domain != expected_domain:
                raise FoundationError(
                    f"{field_name} domain must be "
                    f"{expected_domain.value}"
                )

    @property
    def establishes_claim(self) -> bool:
        """Return false: admission does not independently prove a claim."""

        return False

    def finding_for(
        self,
        record_id: ScopedIdentifier,
    ) -> EvidenceAdmissionFinding | None:
        """Return the admission finding for a record, when present."""

        for finding in self.findings:
            if finding.record_id == record_id:
                return finding

        return None

    def require_finding(
        self,
        record_id: ScopedIdentifier,
    ) -> EvidenceAdmissionFinding:
        """Return an admission finding or fail when it is absent."""

        finding = self.finding_for(
            record_id
        )

        if finding is None:
            raise FoundationError(
                "admission review does not contain a finding "
                f"for record: {record_id}"
            )

        return finding

    def admitted_findings(
        self,
    ) -> tuple[EvidenceAdmissionFinding, ...]:
        """Return all automatically admitted findings."""

        return tuple(
            finding
            for finding in self.findings
            if finding.is_admitted
        )

    def human_review_findings(
        self,
    ) -> tuple[EvidenceAdmissionFinding, ...]:
        """Return findings awaiting separate human review."""

        return tuple(
            finding
            for finding in self.findings
            if finding.requires_human_review
        )

    def excluded_findings(
        self,
    ) -> tuple[EvidenceAdmissionFinding, ...]:
        """Return all excluded findings."""

        return tuple(
            finding
            for finding in self.findings
            if finding.is_excluded
        )

    def admitted_records(
        self,
        *,
        evidence_ledger: EvidenceLedger,
    ) -> tuple[EvidenceRecord, ...]:
        """Return admitted records after verifying ledger binding."""

        if (
            evidence_ledger.digest()
            != self.evidence_ledger_digest
        ):
            raise FoundationError(
                "admission review is not bound to "
                "the supplied evidence ledger"
            )

        admitted_ids = {
            finding.record_id
            for finding in self.admitted_findings()
        }

        for finding in self.admitted_findings():
            record = evidence_ledger.require_record(
                finding.record_id
            )
            if record.digest() != finding.record_digest:
                raise FoundationError(
                    "admission finding record digest does not "
                    "match the evidence ledger"
                )

        return tuple(
            record
            for record in evidence_ledger.records
            if record.record_id in admitted_ids
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic admission-review representation."""

        finding_payloads: JsonArray = [
            finding.to_payload()
            for finding in self.findings
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "establishes_claim": self.establishes_claim,
            "evidence_ledger_digest": (
                self.evidence_ledger_digest.to_payload()
            ),
            "evidence_ledger_id": str(
                self.evidence_ledger_id
            ),
            "findings": finding_payloads,
            "policy_digest": self.policy_digest.to_payload(),
            "policy_id": str(self.policy_id),
            "review_id": str(self.review_id),
            "reviewed_at": self.reviewed_at.isoformat(),
            "reviewed_by_id": str(self.reviewed_by_id),
            "reviewer_accountability_owner_id": str(
                self.reviewer_accountability_owner_id
            ),
            "reviewer_kind": self.reviewer_kind.value,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical review document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete admission review."""

        return self.to_document().digest(
            domain="evidence-admission-review"
        )


@dataclass(frozen=True, slots=True)
class EvidenceAdmissionEvaluator:
    """Apply one policy to every record in a closed evidence ledger."""

    actor_registry: ActorRegistry
    evidence_ledger: EvidenceLedger
    policy: EvidenceAdmissionPolicy

    def __post_init__(self) -> None:
        actor_registry_digest = self.actor_registry.digest()

        if (
            self.evidence_ledger.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "evidence ledger is not bound to "
                "the supplied actor registry"
            )
        if (
            self.policy.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "admission policy is not bound to "
                "the supplied actor registry"
            )

    def review(
        self,
        *,
        key: str,
        reviewed_at: UtcTimestamp,
        reviewed_by_id: ScopedIdentifier,
    ) -> EvidenceAdmissionReview:
        """Review every record without converting findings into claim proof."""

        reviewer = self.actor_registry.require_actor(
            reviewed_by_id
        )
        reviewer_owner_id = self._validate_reviewer(
            reviewer
        )

        if (
            reviewed_at.value
            < self.evidence_ledger.created_at.value
        ):
            raise FoundationError(
                "admission review must not predate "
                "the evidence ledger"
            )
        if reviewed_at.value < self.policy.created_at.value:
            raise FoundationError(
                "admission review must not predate "
                "the admission policy"
            )

        findings_by_record: dict[
            ScopedIdentifier,
            EvidenceAdmissionFinding,
        ] = {}

        for record in self.evidence_ledger.records:
            self._evaluate_record(
                record=record,
                review_key=key,
                reviewed_at=reviewed_at,
                findings_by_record=findings_by_record,
                visiting=set(),
            )

        return EvidenceAdmissionReview(
            review_id=ScopedIdentifier.create(
                namespace="evidence-admission-review",
                key=key,
                namespace_field="review namespace",
                key_field="review key",
            ),
            reviewed_at=reviewed_at,
            reviewed_by_id=reviewer.actor_id,
            reviewer_kind=reviewer.kind,
            reviewer_accountability_owner_id=(
                reviewer_owner_id
            ),
            policy_id=self.policy.policy_id,
            evidence_ledger_id=self.evidence_ledger.ledger_id,
            findings=tuple(
                findings_by_record.values()
            ),
            policy_digest=self.policy.digest(),
            evidence_ledger_digest=(
                self.evidence_ledger.digest()
            ),
            actor_registry_digest=(
                self.actor_registry.digest()
            ),
        )

    @staticmethod
    def _validate_reviewer(
        reviewer: ActorIdentity,
    ) -> ScopedIdentifier:
        if not reviewer.is_active:
            raise FoundationError(
                "admission review requires an active reviewer"
            )
        if reviewer.kind not in _ADMISSION_REVIEWER_KINDS:
            raise FoundationError(
                "admission reviewer must be a service "
                "or system actor"
            )

        owner_id = reviewer.accountability_owner_id

        if owner_id is None:
            raise FoundationError(
                "admission reviewer must identify "
                "an accountable human owner"
            )

        return owner_id

    def _evaluate_record(
        self,
        *,
        record: EvidenceRecord,
        review_key: str,
        reviewed_at: UtcTimestamp,
        findings_by_record: dict[
            ScopedIdentifier,
            EvidenceAdmissionFinding,
        ],
        visiting: set[ScopedIdentifier],
    ) -> EvidenceAdmissionFinding:
        existing = findings_by_record.get(
            record.record_id
        )
        if existing is not None:
            return existing

        if record.record_id in visiting:
            raise FoundationError(
                "evidence admission encountered "
                "a cyclic source graph"
            )

        visiting.add(
            record.record_id
        )

        source_findings = tuple(
            self._evaluate_record(
                record=self.evidence_ledger.require_record(
                    source_id
                ),
                review_key=review_key,
                reviewed_at=reviewed_at,
                findings_by_record=findings_by_record,
                visiting=visiting,
            )
            for source_id in record.source_record_ids
        )

        reasons = self._collect_reasons(
            record=record,
            source_findings=source_findings,
            findings_by_record=findings_by_record,
        )
        outcome = self._outcome_for(
            reasons
        )

        if outcome is EvidenceAdmissionOutcome.ADMITTED:
            reasons.add(
                EvidenceAdmissionReason.ADMITTED_BY_POLICY
            )

        finding = EvidenceAdmissionFinding(
            finding_id=ScopedIdentifier.create(
                namespace="evidence-admission-finding",
                key=(
                    f"{review_key}-"
                    f"{str(record.record_id)}"
                ),
                namespace_field="finding namespace",
                key_field="finding key",
            ),
            reviewed_at=reviewed_at,
            record_id=record.record_id,
            outcome=outcome,
            reasons=tuple(reasons),
            source_record_ids=record.source_record_ids,
            record_digest=record.digest(),
            policy_digest=self.policy.digest(),
            evidence_ledger_digest=(
                self.evidence_ledger.digest()
            ),
        )

        visiting.remove(
            record.record_id
        )
        findings_by_record[
            record.record_id
        ] = finding

        return finding

    def _collect_reasons(
        self,
        *,
        record: EvidenceRecord,
        source_findings: tuple[
            EvidenceAdmissionFinding,
            ...,
        ],
        findings_by_record: dict[
            ScopedIdentifier,
            EvidenceAdmissionFinding,
        ],
    ) -> set[EvidenceAdmissionReason]:
        reasons: set[EvidenceAdmissionReason] = set()

        if not self.policy.allows_kind(
            record.kind
        ):
            reasons.add(
                EvidenceAdmissionReason.KIND_NOT_ALLOWED
            )

        if not self.policy.allows_origin(
            record.origin
        ):
            reasons.add(
                EvidenceAdmissionReason.ORIGIN_NOT_ALLOWED
            )

        if not self.policy.allows_status(
            record.status
        ):
            reasons.add(
                EvidenceAdmissionReason.STATUS_NOT_ALLOWED
            )

        if record.status is EvidenceStatus.INVALIDATED:
            reasons.add(
                EvidenceAdmissionReason.RECORD_INVALIDATED
            )

        if not record.payload_digest.verifies(
            record.payload.to_value()
        ):
            reasons.add(
                EvidenceAdmissionReason.PAYLOAD_DIGEST_MISMATCH
            )

        if (
            record.actor_registry_digest
            != self.actor_registry.digest()
        ):
            reasons.add(
                EvidenceAdmissionReason
                .ACTOR_REGISTRY_BINDING_MISMATCH
            )

        if record.requires_corroboration:
            self._evaluate_corroboration(
                record=record,
                source_findings=source_findings,
                findings_by_record=findings_by_record,
                reasons=reasons,
            )

        if self.policy.requires_human_review(
            record.origin
        ):
            reasons.add(
                EvidenceAdmissionReason
                .ORIGIN_REQUIRES_HUMAN_REVIEW
            )

        return reasons

    def _evaluate_corroboration(
        self,
        *,
        record: EvidenceRecord,
        source_findings: tuple[
            EvidenceAdmissionFinding,
            ...,
        ],
        findings_by_record: dict[
            ScopedIdentifier,
            EvidenceAdmissionFinding,
        ],
        reasons: set[EvidenceAdmissionReason],
    ) -> None:
        if not source_findings:
            reasons.add(
                EvidenceAdmissionReason.CORROBORATION_MISSING
            )
            return

        if any(
            finding.is_excluded
            for finding in source_findings
        ):
            reasons.add(
                EvidenceAdmissionReason.SOURCE_EXCLUDED
            )

        if any(
            finding.requires_human_review
            for finding in source_findings
        ):
            reasons.add(
                EvidenceAdmissionReason
                .SOURCE_REQUIRES_HUMAN_REVIEW
            )

        if (
            self.policy.require_primary_ancestry
            and not self._has_admitted_primary_ancestor(
                record=record,
                findings_by_record=findings_by_record,
                visited=set(),
            )
        ):
            reasons.add(
                EvidenceAdmissionReason
                .USABLE_PRIMARY_ANCESTRY_MISSING
            )

        if (
            not reasons.intersection(
                _EXCLUSION_REASONS
            )
            and not reasons.intersection(
                _HUMAN_REVIEW_REASONS
            )
            and not self.policy.requires_human_review(
                record.origin
            )
        ):
            reasons.add(
                EvidenceAdmissionReason
                .CORROBORATED_BY_ADMITTED_SOURCE
            )

    def _has_admitted_primary_ancestor(
        self,
        *,
        record: EvidenceRecord,
        findings_by_record: dict[
            ScopedIdentifier,
            EvidenceAdmissionFinding,
        ],
        visited: set[ScopedIdentifier],
    ) -> bool:
        if record.record_id in visited:
            return False

        visited.add(
            record.record_id
        )

        for source_id in record.source_record_ids:
            source = self.evidence_ledger.require_record(
                source_id
            )
            finding = findings_by_record.get(
                source_id
            )

            if finding is None:
                raise FoundationError(
                    "source finding was not resolved "
                    "before dependent evidence"
                )

            if (
                source.is_primary
                and source.status.is_usable
                and finding.is_admitted
            ):
                return True

            if self._has_admitted_primary_ancestor(
                record=source,
                findings_by_record=findings_by_record,
                visited=visited,
            ):
                return True

        return False

    @staticmethod
    def _outcome_for(
        reasons: set[EvidenceAdmissionReason],
    ) -> EvidenceAdmissionOutcome:
        if reasons.intersection(
            _EXCLUSION_REASONS
        ):
            return EvidenceAdmissionOutcome.EXCLUDED

        if reasons.intersection(
            _HUMAN_REVIEW_REASONS
        ):
            return (
                EvidenceAdmissionOutcome
                .REQUIRES_HUMAN_REVIEW
            )

        return EvidenceAdmissionOutcome.ADMITTED
