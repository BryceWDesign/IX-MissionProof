"""Catalog-wide current claim posture snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.history import (
    ClaimResolutionHistory,
    ClaimResolutionHistoryEntry,
)
from ix_missionproof.claims.resolutions import ClaimResolutionStatus
from ix_missionproof.claims.specifications import (
    ClaimCatalog,
    ClaimSpecification,
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

_POSTURE_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureSource(StrEnum):
    """Source from which one current claim posture was established."""

    NO_RESOLUTION = "no-resolution"
    RESOLUTION_HISTORY = "resolution-history"


class ClaimPostureStatus(StrEnum):
    """Current catalog-visible posture of one bounded claim."""

    UNEVALUATED = "unevaluated"
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not-supported"
    DEFERRED = "deferred"
    AWAITING_ADJUDICATION = "awaiting-adjudication"
    INCOMPLETE_EVIDENCE = "incomplete-evidence"
    EVIDENCE_REVIEW_OPEN = "evidence-review-open"
    FALSIFICATION_SIGNAL = "falsification-signal"

    @property
    def is_supported(self) -> bool:
        """Return whether the newest evaluation is human-supported."""

        return self is ClaimPostureStatus.SUPPORTED

    @property
    def is_terminal_for_current_evaluation(self) -> bool:
        """Return whether the current evaluation has a terminal judgment."""

        return self in {
            ClaimPostureStatus.SUPPORTED,
            ClaimPostureStatus.NOT_SUPPORTED,
        }

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the current posture still requires attention."""

        return self in {
            ClaimPostureStatus.UNEVALUATED,
            ClaimPostureStatus.DEFERRED,
            ClaimPostureStatus.AWAITING_ADJUDICATION,
            ClaimPostureStatus.INCOMPLETE_EVIDENCE,
            ClaimPostureStatus.EVIDENCE_REVIEW_OPEN,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
        }

    @property
    def has_adverse_signal(self) -> bool:
        """Return whether the current posture is adverse to the claim."""

        return self in {
            ClaimPostureStatus.NOT_SUPPORTED,
            ClaimPostureStatus.FALSIFICATION_SIGNAL,
        }


_RESOLUTION_TO_POSTURE: Final[
    dict[ClaimResolutionStatus, ClaimPostureStatus]
] = {
    ClaimResolutionStatus.SUPPORTED: ClaimPostureStatus.SUPPORTED,
    ClaimResolutionStatus.NOT_SUPPORTED: ClaimPostureStatus.NOT_SUPPORTED,
    ClaimResolutionStatus.DEFERRED: ClaimPostureStatus.DEFERRED,
    ClaimResolutionStatus.AWAITING_ADJUDICATION: (
        ClaimPostureStatus.AWAITING_ADJUDICATION
    ),
    ClaimResolutionStatus.INCOMPLETE_EVIDENCE: (
        ClaimPostureStatus.INCOMPLETE_EVIDENCE
    ),
    ClaimResolutionStatus.EVIDENCE_REVIEW_OPEN: (
        ClaimPostureStatus.EVIDENCE_REVIEW_OPEN
    ),
    ClaimResolutionStatus.FALSIFICATION_SIGNAL: (
        ClaimPostureStatus.FALSIFICATION_SIGNAL
    ),
}


def _require_identifier(
    value: ScopedIdentifier,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if not isinstance(value, ScopedIdentifier):
        raise FoundationError(
            f"{field_name} must be a ScopedIdentifier"
        )
    if value.namespace != CanonicalKey(namespace):
        raise FoundationError(
            f"{field_name} namespace must be {namespace}"
        )


def _require_optional_identifier(
    value: ScopedIdentifier | None,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if value is None:
        return

    _require_identifier(
        value,
        field_name=field_name,
        namespace=namespace,
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


def _validate_posture_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "claim-posture producer must be active"
        )
    if producer.kind not in _POSTURE_PRODUCER_KINDS:
        raise FoundationError(
            "claim-posture producer must be a service "
            "or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "claim-posture producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPosture:
    """Current temporal posture of one bounded claim."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-v1"
    )

    posture_id: ScopedIdentifier
    captured_at: UtcTimestamp
    claim_id: ScopedIdentifier
    status: ClaimPostureStatus
    source: ClaimPostureSource
    current_history_entry_id: ScopedIdentifier | None
    current_evaluation_id: ScopedIdentifier | None
    current_resolution_id: ScopedIdentifier | None
    current_evaluated_at: UtcTimestamp | None
    current_resolved_at: UtcTimestamp | None
    claim_digest: ContentDigest
    current_history_entry_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    history_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_source_semantics()

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.posture_id,
            field_name="posture_id",
            namespace="claim-posture",
        )
        _require_identifier(
            self.claim_id,
            field_name="claim_id",
            namespace="claim",
        )
        _require_optional_identifier(
            self.current_history_entry_id,
            field_name="current_history_entry_id",
            namespace="claim-resolution-history-entry",
        )
        _require_optional_identifier(
            self.current_evaluation_id,
            field_name="current_evaluation_id",
            namespace="claim-evidence-evaluation",
        )
        _require_optional_identifier(
            self.current_resolution_id,
            field_name="current_resolution_id",
            namespace="claim-resolution",
        )

        if not isinstance(
            self.captured_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "captured_at must be a UtcTimestamp"
            )
        if (
            self.current_evaluated_at is not None
            and not isinstance(
                self.current_evaluated_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "current_evaluated_at must be "
                "a UtcTimestamp or None"
            )
        if (
            self.current_resolved_at is not None
            and not isinstance(
                self.current_resolved_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "current_resolved_at must be "
                "a UtcTimestamp or None"
            )
        if not isinstance(
            self.status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "status must be a ClaimPostureStatus"
            )
        if not isinstance(
            self.source,
            ClaimPostureSource,
        ):
            raise FoundationError(
                "source must be a ClaimPostureSource"
            )

    def _validate_digests(self) -> None:
        _require_digest(
            self.claim_digest,
            field_name="claim_digest",
            domain="claim-specification",
        )
        _require_optional_digest(
            self.current_history_entry_digest,
            field_name="current_history_entry_digest",
            domain="claim-resolution-history-entry",
        )
        _require_digest(
            self.claim_catalog_digest,
            field_name="claim_catalog_digest",
            domain="claim-catalog",
        )
        _require_digest(
            self.history_digest,
            field_name="history_digest",
            domain="claim-resolution-history",
        )

    def _validate_source_semantics(self) -> None:
        resolution_values = (
            self.current_history_entry_id,
            self.current_evaluation_id,
            self.current_resolution_id,
            self.current_evaluated_at,
            self.current_resolved_at,
            self.current_history_entry_digest,
        )
        resolution_fields_present = tuple(
            value is not None
            for value in resolution_values
        )

        if self.source is ClaimPostureSource.NO_RESOLUTION:
            if self.status is not ClaimPostureStatus.UNEVALUATED:
                raise FoundationError(
                    "no-resolution posture must be unevaluated"
                )
            if any(resolution_fields_present):
                raise FoundationError(
                    "no-resolution posture must not contain "
                    "current resolution data"
                )
            return

        if not all(resolution_fields_present):
            raise FoundationError(
                "resolution-history posture requires complete "
                "current resolution data"
            )
        if self.status is ClaimPostureStatus.UNEVALUATED:
            raise FoundationError(
                "resolution-history posture must not be unevaluated"
            )

        current_evaluated_at = self.current_evaluated_at
        current_resolved_at = self.current_resolved_at

        if (
            current_evaluated_at is None
            or current_resolved_at is None
        ):
            raise FoundationError(
                "resolution-history posture requires "
                "evaluation and resolution times"
            )
        if (
            current_resolved_at.value
            < current_evaluated_at.value
        ):
            raise FoundationError(
                "current resolution must not predate "
                "the current evaluation"
            )
        if (
            self.captured_at.value
            < current_resolved_at.value
        ):
            raise FoundationError(
                "claim posture must not predate "
                "the current resolution"
            )

    @classmethod
    def capture(
        cls,
        *,
        key: str,
        captured_at: UtcTimestamp,
        claim: ClaimSpecification,
        claim_catalog: ClaimCatalog,
        history: ClaimResolutionHistory,
    ) -> ClaimPosture:
        """Capture the newest evaluated posture for one catalog claim."""

        cls._validate_bindings(
            captured_at=captured_at,
            claim=claim,
            claim_catalog=claim_catalog,
            history=history,
        )
        current = history.current_for_claim(
            claim.claim_id
        )

        if current is None:
            return cls(
                posture_id=ScopedIdentifier.create(
                    namespace="claim-posture",
                    key=key,
                    namespace_field="posture namespace",
                    key_field="posture key",
                ),
                captured_at=captured_at,
                claim_id=claim.claim_id,
                status=ClaimPostureStatus.UNEVALUATED,
                source=ClaimPostureSource.NO_RESOLUTION,
                current_history_entry_id=None,
                current_evaluation_id=None,
                current_resolution_id=None,
                current_evaluated_at=None,
                current_resolved_at=None,
                claim_digest=claim.digest(),
                current_history_entry_digest=None,
                claim_catalog_digest=claim_catalog.digest(),
                history_digest=history.digest(),
            )

        cls._validate_current_entry(
            claim=claim,
            current=current,
        )

        return cls(
            posture_id=ScopedIdentifier.create(
                namespace="claim-posture",
                key=key,
                namespace_field="posture namespace",
                key_field="posture key",
            ),
            captured_at=captured_at,
            claim_id=claim.claim_id,
            status=_RESOLUTION_TO_POSTURE[
                current.status
            ],
            source=ClaimPostureSource.RESOLUTION_HISTORY,
            current_history_entry_id=current.entry_id,
            current_evaluation_id=current.evaluation_id,
            current_resolution_id=current.resolution_id,
            current_evaluated_at=(
                current.evaluation_evaluated_at
            ),
            current_resolved_at=(
                current.resolution_resolved_at
            ),
            claim_digest=claim.digest(),
            current_history_entry_digest=current.digest(),
            claim_catalog_digest=claim_catalog.digest(),
            history_digest=history.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        captured_at: UtcTimestamp,
        claim: ClaimSpecification,
        claim_catalog: ClaimCatalog,
        history: ClaimResolutionHistory,
    ) -> None:
        catalog_claim = claim_catalog.require_claim(
            claim.claim_id
        )

        if catalog_claim.digest() != claim.digest():
            raise FoundationError(
                "claim does not match the supplied claim catalog"
            )
        if history.claim_catalog_id != claim_catalog.catalog_id:
            raise FoundationError(
                "claim history references a different claim catalog"
            )
        if history.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError(
                "claim history is not bound to "
                "the supplied claim catalog"
            )
        if captured_at.value < claim.created_at.value:
            raise FoundationError(
                "claim posture must not predate the claim"
            )
        if captured_at.value < claim_catalog.created_at.value:
            raise FoundationError(
                "claim posture must not predate "
                "the claim catalog"
            )
        if captured_at.value < history.created_at.value:
            raise FoundationError(
                "claim posture must not predate "
                "the claim history"
            )

    @staticmethod
    def _validate_current_entry(
        *,
        claim: ClaimSpecification,
        current: ClaimResolutionHistoryEntry,
    ) -> None:
        if current.claim_id != claim.claim_id:
            raise FoundationError(
                "current history entry references "
                "a different claim"
            )
        if current.claim_digest != claim.digest():
            raise FoundationError(
                "current history-entry claim digest "
                "does not match the claim"
            )

    @property
    def is_supported(self) -> bool:
        """Return whether the newest evaluation is supported."""

        return self.status.is_supported

    @property
    def is_terminal_for_current_evaluation(self) -> bool:
        """Return whether the newest evaluation has a terminal judgment."""

        return self.status.is_terminal_for_current_evaluation

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the current posture requires attention."""

        return self.status.requires_human_attention

    @property
    def has_adverse_signal(self) -> bool:
        """Return whether the current posture is adverse."""

        return self.status.has_adverse_signal

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because posture remains evidence-bound and temporal."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim posture never grants authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic claim-posture representation."""

        return {
            "captured_at": self.captured_at.isoformat(),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_digest": self.claim_digest.to_payload(),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "current_evaluated_at": (
                self.current_evaluated_at.isoformat()
                if self.current_evaluated_at is not None
                else None
            ),
            "current_evaluation_id": (
                str(self.current_evaluation_id)
                if self.current_evaluation_id is not None
                else None
            ),
            "current_history_entry_digest": (
                self.current_history_entry_digest.to_payload()
                if self.current_history_entry_digest is not None
                else None
            ),
            "current_history_entry_id": (
                str(self.current_history_entry_id)
                if self.current_history_entry_id is not None
                else None
            ),
            "current_resolution_id": (
                str(self.current_resolution_id)
                if self.current_resolution_id is not None
                else None
            ),
            "current_resolved_at": (
                self.current_resolved_at.isoformat()
                if self.current_resolved_at is not None
                else None
            ),
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "grants_authority": self.grants_authority,
            "has_adverse_signal": self.has_adverse_signal,
            "history_digest": self.history_digest.to_payload(),
            "is_supported": self.is_supported,
            "is_terminal_for_current_evaluation": (
                self.is_terminal_for_current_evaluation
            ),
            "posture_id": str(self.posture_id),
            "requires_human_attention": (
                self.requires_human_attention
            ),
            "schema": self.SCHEMA.value,
            "source": self.source.value,
            "status": self.status.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical posture document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete claim posture."""

        return self.to_document().digest(
            domain="claim-posture"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureSnapshot:
    """Catalog-wide snapshot of every current bounded claim posture."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    captured_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    claim_catalog_id: ScopedIdentifier
    history_id: ScopedIdentifier
    postures: tuple[ClaimPosture, ...]
    claim_catalog_digest: ContentDigest
    history_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        postures = tuple(
            self.postures
        )
        self._validate_postures(
            postures
        )

        object.__setattr__(
            self,
            "postures",
            tuple(
                sorted(
                    postures,
                    key=lambda posture: str(
                        posture.claim_id
                    ),
                )
            ),
        )

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.snapshot_id,
            field_name="snapshot_id",
            namespace="claim-posture-snapshot",
        )
        _require_identifier(
            self.claim_catalog_id,
            field_name="claim_catalog_id",
            namespace="claim-catalog",
        )
        _require_identifier(
            self.history_id,
            field_name="history_id",
            namespace="claim-resolution-history",
        )

        if not isinstance(
            self.captured_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "captured_at must be a UtcTimestamp"
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
        if self.producer_kind not in _POSTURE_PRODUCER_KINDS:
            raise FoundationError(
                "claim-posture producer must be a service "
                "or system actor"
            )
        if self.produced_by_id.namespace != CanonicalKey(
            self.producer_kind.value
        ):
            raise FoundationError(
                "produced_by_id namespace must match producer_kind"
            )

        _require_identifier(
            self.producer_accountability_owner_id,
            field_name="producer_accountability_owner_id",
            namespace="human",
        )

    def _validate_digests(self) -> None:
        _require_digest(
            self.claim_catalog_digest,
            field_name="claim_catalog_digest",
            domain="claim-catalog",
        )
        _require_digest(
            self.history_digest,
            field_name="history_digest",
            domain="claim-resolution-history",
        )
        _require_digest(
            self.actor_registry_digest,
            field_name="actor_registry_digest",
            domain="actor-registry",
        )

    def _validate_postures(
        self,
        postures: tuple[ClaimPosture, ...],
    ) -> None:
        for index, posture in enumerate(
            postures
        ):
            if not isinstance(
                posture,
                ClaimPosture,
            ):
                raise FoundationError(
                    f"postures[{index}] must be a ClaimPosture"
                )
            if posture.captured_at != self.captured_at:
                raise FoundationError(
                    "every claim posture must use "
                    "the snapshot capture time"
                )
            if (
                posture.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every claim posture must bind "
                    "the claim catalog"
                )
            if posture.history_digest != self.history_digest:
                raise FoundationError(
                    "every claim posture must bind "
                    "the claim history"
                )

        posture_ids = tuple(
            posture.posture_id
            for posture in postures
        )
        if len(posture_ids) != len(
            set(posture_ids)
        ):
            raise FoundationError(
                "claim-posture snapshot must contain "
                "unique posture IDs"
            )

        claim_ids = tuple(
            posture.claim_id
            for posture in postures
        )
        if len(claim_ids) != len(
            set(claim_ids)
        ):
            raise FoundationError(
                "claim-posture snapshot must contain "
                "one posture per claim"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        captured_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        claim_catalog: ClaimCatalog,
        history: ClaimResolutionHistory,
        actor_registry: ActorRegistry,
    ) -> ClaimPostureSnapshot:
        """Capture every catalog claim, including unevaluated claims."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = _validate_posture_producer(
            producer
        )

        cls._validate_bindings(
            captured_at=captured_at,
            claim_catalog=claim_catalog,
            history=history,
            actor_registry=actor_registry,
        )

        postures = tuple(
            ClaimPosture.capture(
                key=(
                    f"{key}-"
                    f"{str(claim.claim_id)}"
                ),
                captured_at=captured_at,
                claim=claim,
                claim_catalog=claim_catalog,
                history=history,
            )
            for claim in claim_catalog.claims
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace="claim-posture-snapshot",
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            captured_at=captured_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            claim_catalog_id=claim_catalog.catalog_id,
            history_id=history.history_id,
            postures=postures,
            claim_catalog_digest=claim_catalog.digest(),
            history_digest=history.digest(),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        captured_at: UtcTimestamp,
        claim_catalog: ClaimCatalog,
        history: ClaimResolutionHistory,
        actor_registry: ActorRegistry,
    ) -> None:
        actor_registry_digest = actor_registry.digest()

        if (
            claim_catalog.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "claim catalog is not bound to "
                "the supplied actor registry"
            )
        if (
            history.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "claim history is not bound to "
                "the supplied actor registry"
            )
        if history.claim_catalog_id != claim_catalog.catalog_id:
            raise FoundationError(
                "claim history references a different "
                "claim catalog"
            )
        if history.claim_catalog_digest != claim_catalog.digest():
            raise FoundationError(
                "claim history is not bound to "
                "the supplied claim catalog"
            )
        if captured_at.value < claim_catalog.created_at.value:
            raise FoundationError(
                "claim-posture snapshot must not predate "
                "the claim catalog"
            )
        if captured_at.value < history.created_at.value:
            raise FoundationError(
                "claim-posture snapshot must not predate "
                "the claim history"
            )

        catalog_claim_ids = {
            claim.claim_id
            for claim in claim_catalog.claims
        }

        for entry in history.entries:
            if entry.claim_id not in catalog_claim_ids:
                raise FoundationError(
                    "claim history contains a claim absent "
                    "from the supplied claim catalog"
                )

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because posture remains temporal and bounded."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because claim posture never grants authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    @property
    def total_count(self) -> int:
        """Return the total number of catalog claims."""

        return len(
            self.postures
        )

    @property
    def supported_count(self) -> int:
        """Return the number of currently supported claims."""

        return sum(
            posture.is_supported
            for posture in self.postures
        )

    @property
    def adverse_count(self) -> int:
        """Return the number of current adverse claim postures."""

        return sum(
            posture.has_adverse_signal
            for posture in self.postures
        )

    @property
    def attention_count(self) -> int:
        """Return the number of claims requiring human attention."""

        return sum(
            posture.requires_human_attention
            for posture in self.postures
        )

    @property
    def unevaluated_count(self) -> int:
        """Return the number of claims without a resolution history."""

        return sum(
            posture.status is ClaimPostureStatus.UNEVALUATED
            for posture in self.postures
        )

    @property
    def all_claims_currently_supported(self) -> bool:
        """Return whether every catalog claim is currently supported."""

        return bool(
            self.postures
        ) and all(
            posture.is_supported
            for posture in self.postures
        )

    def posture_for(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPosture | None:
        """Return the current posture for one claim."""

        for posture in self.postures:
            if posture.claim_id == claim_id:
                return posture

        return None

    def require_posture(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPosture:
        """Return a claim posture or fail when absent."""

        posture = self.posture_for(
            claim_id
        )

        if posture is None:
            raise FoundationError(
                "claim-posture snapshot does not contain "
                f"claim: {claim_id}"
            )

        return posture

    def postures_by_status(
        self,
        status: ClaimPostureStatus,
    ) -> tuple[ClaimPosture, ...]:
        """Return current claim postures with one status."""

        if not isinstance(
            status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "status must be a ClaimPostureStatus"
            )

        return tuple(
            posture
            for posture in self.postures
            if posture.status is status
        )

    def supported_postures(
        self,
    ) -> tuple[ClaimPosture, ...]:
        """Return currently supported claim postures."""

        return tuple(
            posture
            for posture in self.postures
            if posture.is_supported
        )

    def adverse_postures(
        self,
    ) -> tuple[ClaimPosture, ...]:
        """Return currently adverse claim postures."""

        return tuple(
            posture
            for posture in self.postures
            if posture.has_adverse_signal
        )

    def attention_postures(
        self,
    ) -> tuple[ClaimPosture, ...]:
        """Return claim postures requiring human attention."""

        return tuple(
            posture
            for posture in self.postures
            if posture.requires_human_attention
        )

    def unevaluated_postures(
        self,
    ) -> tuple[ClaimPosture, ...]:
        """Return catalog claims with no resolution history."""

        return self.postures_by_status(
            ClaimPostureStatus.UNEVALUATED
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic posture-snapshot representation."""

        posture_payloads: JsonArray = [
            posture.to_payload()
            for posture in self.postures
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "adverse_count": self.adverse_count,
            "all_claims_currently_supported": (
                self.all_claims_currently_supported
            ),
            "attention_count": self.attention_count,
            "captured_at": self.captured_at.isoformat(),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_catalog_id": str(self.claim_catalog_id),
            "claims_certification": self.claims_certification,
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "grants_authority": self.grants_authority,
            "history_digest": self.history_digest.to_payload(),
            "history_id": str(self.history_id),
            "postures": posture_payloads,
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "supported_count": self.supported_count,
            "total_count": self.total_count,
            "unevaluated_count": self.unevaluated_count,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical snapshot document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete posture snapshot."""

        return self.to_document().digest(
            domain="claim-posture-snapshot"
        )
