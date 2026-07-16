"""Deterministic transitions between current claim-posture snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.postures import (
    ClaimPosture,
    ClaimPostureSnapshot,
    ClaimPostureStatus,
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

_DELTA_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureTransition(StrEnum):
    """Primary classification of one claim-posture transition."""

    UNCHANGED = "unchanged"
    NEWLY_SUPPORTED = "newly-supported"
    SUPPORT_LOST = "support-lost"
    NEW_ADVERSE_SIGNAL = "new-adverse-signal"
    ADVERSE_SIGNAL_CLEARED = "adverse-signal-cleared"
    ATTENTION_OPENED = "attention-opened"
    ATTENTION_CLEARED = "attention-cleared"
    STATUS_CHANGED = "status-changed"

    @property
    def is_changed(self) -> bool:
        """Return whether the current posture differs from the prior posture."""

        return self is not ClaimPostureTransition.UNCHANGED


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


def _validate_delta_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "claim-posture delta producer must be active"
        )
    if producer.kind not in _DELTA_PRODUCER_KINDS:
        raise FoundationError(
            "claim-posture delta producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "claim-posture delta producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureDelta:
    """One exact transition between two temporal claim postures."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-delta-v1"
    )

    delta_id: ScopedIdentifier
    compared_at: UtcTimestamp
    claim_id: ScopedIdentifier
    transition: ClaimPostureTransition
    previous_status: ClaimPostureStatus
    current_status: ClaimPostureStatus
    previous_posture_id: ScopedIdentifier
    current_posture_id: ScopedIdentifier
    previous_captured_at: UtcTimestamp
    current_captured_at: UtcTimestamp
    previous_posture_digest: ContentDigest
    current_posture_digest: ContentDigest
    previous_snapshot_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()
        self._validate_transition()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "delta_id",
                self.delta_id,
                "claim-posture-delta",
            ),
            (
                "claim_id",
                self.claim_id,
                "claim",
            ),
            (
                "previous_posture_id",
                self.previous_posture_id,
                "claim-posture",
            ),
            (
                "current_posture_id",
                self.current_posture_id,
                "claim-posture",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        for field_name, value in (
            (
                "compared_at",
                self.compared_at,
            ),
            (
                "previous_captured_at",
                self.previous_captured_at,
            ),
            (
                "current_captured_at",
                self.current_captured_at,
            ),
        ):
            if not isinstance(
                value,
                UtcTimestamp,
            ):
                raise FoundationError(
                    f"{field_name} must be a UtcTimestamp"
                )

        if not isinstance(
            self.transition,
            ClaimPostureTransition,
        ):
            raise FoundationError(
                "transition must be a ClaimPostureTransition"
            )
        if not isinstance(
            self.previous_status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "previous_status must be a ClaimPostureStatus"
            )
        if not isinstance(
            self.current_status,
            ClaimPostureStatus,
        ):
            raise FoundationError(
                "current_status must be a ClaimPostureStatus"
            )

        if (
            self.current_captured_at.value
            <= self.previous_captured_at.value
        ):
            raise FoundationError(
                "current posture snapshot must be newer "
                "than the previous snapshot"
            )
        if (
            self.compared_at.value
            < self.current_captured_at.value
        ):
            raise FoundationError(
                "posture comparison must not predate "
                "the current posture snapshot"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "previous_posture_digest",
                self.previous_posture_digest,
                "claim-posture",
            ),
            (
                "current_posture_digest",
                self.current_posture_digest,
                "claim-posture",
            ),
            (
                "previous_snapshot_digest",
                self.previous_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "current_snapshot_digest",
                self.current_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "claim_catalog_digest",
                self.claim_catalog_digest,
                "claim-catalog",
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                "actor-registry",
            ),
        ):
            _require_digest(
                value,
                field_name=field_name,
                domain=domain,
            )

    def _validate_transition(self) -> None:
        expected = self.classify(
            previous_status=self.previous_status,
            current_status=self.current_status,
        )

        if self.transition is not expected:
            raise FoundationError(
                "claim-posture transition does not match "
                "the previous and current statuses"
            )

    @classmethod
    def compare(
        cls,
        *,
        key: str,
        compared_at: UtcTimestamp,
        previous: ClaimPosture,
        current: ClaimPosture,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
    ) -> ClaimPostureDelta:
        """Compare one claim across two bound posture snapshots."""

        cls._validate_bindings(
            compared_at=compared_at,
            previous=previous,
            current=current,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
        )

        return cls(
            delta_id=ScopedIdentifier.create(
                namespace="claim-posture-delta",
                key=key,
                namespace_field="delta namespace",
                key_field="delta key",
            ),
            compared_at=compared_at,
            claim_id=current.claim_id,
            transition=cls.classify(
                previous_status=previous.status,
                current_status=current.status,
            ),
            previous_status=previous.status,
            current_status=current.status,
            previous_posture_id=previous.posture_id,
            current_posture_id=current.posture_id,
            previous_captured_at=previous.captured_at,
            current_captured_at=current.captured_at,
            previous_posture_digest=previous.digest(),
            current_posture_digest=current.digest(),
            previous_snapshot_digest=previous_snapshot.digest(),
            current_snapshot_digest=current_snapshot.digest(),
            claim_catalog_digest=current_snapshot.claim_catalog_digest,
            actor_registry_digest=current_snapshot.actor_registry_digest,
        )

    @staticmethod
    def _validate_bindings(
        *,
        compared_at: UtcTimestamp,
        previous: ClaimPosture,
        current: ClaimPosture,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
    ) -> None:
        if previous.claim_id != current.claim_id:
            raise FoundationError(
                "claim posture comparison requires "
                "the same claim identifier"
            )
        if (
            previous_snapshot.claim_catalog_id
            != current_snapshot.claim_catalog_id
        ):
            raise FoundationError(
                "posture snapshots reference different claim catalogs"
            )
        if (
            previous_snapshot.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "posture snapshots are not bound to "
                "the same claim catalog"
            )
        if (
            previous_snapshot.actor_registry_digest
            != current_snapshot.actor_registry_digest
        ):
            raise FoundationError(
                "posture snapshots are not bound to "
                "the same actor registry"
            )
        if (
            current_snapshot.captured_at.value
            <= previous_snapshot.captured_at.value
        ):
            raise FoundationError(
                "current posture snapshot must be newer "
                "than the previous snapshot"
            )
        if compared_at.value < current_snapshot.captured_at.value:
            raise FoundationError(
                "posture comparison must not predate "
                "the current posture snapshot"
            )

        bound_previous = previous_snapshot.require_posture(
            previous.claim_id
        )
        bound_current = current_snapshot.require_posture(
            current.claim_id
        )

        if bound_previous.digest() != previous.digest():
            raise FoundationError(
                "previous posture does not match "
                "the previous snapshot"
            )
        if bound_current.digest() != current.digest():
            raise FoundationError(
                "current posture does not match "
                "the current snapshot"
            )

    @staticmethod
    def classify(
        *,
        previous_status: ClaimPostureStatus,
        current_status: ClaimPostureStatus,
    ) -> ClaimPostureTransition:
        """Classify a posture transition with deterministic precedence."""

        if previous_status is current_status:
            return ClaimPostureTransition.UNCHANGED

        if (
            previous_status.is_supported
            and not current_status.is_supported
        ):
            return ClaimPostureTransition.SUPPORT_LOST

        if (
            not previous_status.is_supported
            and current_status.is_supported
        ):
            return ClaimPostureTransition.NEWLY_SUPPORTED

        if (
            not previous_status.has_adverse_signal
            and current_status.has_adverse_signal
        ):
            return ClaimPostureTransition.NEW_ADVERSE_SIGNAL

        if (
            previous_status.has_adverse_signal
            and not current_status.has_adverse_signal
        ):
            return ClaimPostureTransition.ADVERSE_SIGNAL_CLEARED

        if (
            not previous_status.requires_human_attention
            and current_status.requires_human_attention
        ):
            return ClaimPostureTransition.ATTENTION_OPENED

        if (
            previous_status.requires_human_attention
            and not current_status.requires_human_attention
        ):
            return ClaimPostureTransition.ATTENTION_CLEARED

        return ClaimPostureTransition.STATUS_CHANGED

    @property
    def status_changed(self) -> bool:
        """Return whether the posture status changed."""

        return self.previous_status is not self.current_status

    @property
    def support_lost(self) -> bool:
        """Return whether prior support is absent from the current posture."""

        return (
            self.previous_status.is_supported
            and not self.current_status.is_supported
        )

    @property
    def newly_supported(self) -> bool:
        """Return whether the current posture newly supports the claim."""

        return (
            not self.previous_status.is_supported
            and self.current_status.is_supported
        )

    @property
    def new_adverse_signal(self) -> bool:
        """Return whether the current posture newly became adverse."""

        return (
            not self.previous_status.has_adverse_signal
            and self.current_status.has_adverse_signal
        )

    @property
    def adverse_signal_cleared(self) -> bool:
        """Return whether a prior adverse posture is no longer current."""

        return (
            self.previous_status.has_adverse_signal
            and not self.current_status.has_adverse_signal
        )

    @property
    def attention_opened(self) -> bool:
        """Return whether human attention newly became necessary."""

        return (
            not self.previous_status.requires_human_attention
            and self.current_status.requires_human_attention
        )

    @property
    def attention_cleared(self) -> bool:
        """Return whether a prior attention requirement was resolved."""

        return (
            self.previous_status.requires_human_attention
            and not self.current_status.requires_human_attention
        )

    @property
    def requires_human_attention(self) -> bool:
        """Return whether the current posture requires human attention."""

        return self.current_status.requires_human_attention

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because posture transitions remain temporal."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because posture transitions never grant authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic posture-delta representation."""

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "adverse_signal_cleared": (
                self.adverse_signal_cleared
            ),
            "attention_cleared": self.attention_cleared,
            "attention_opened": self.attention_opened,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "compared_at": self.compared_at.isoformat(),
            "current_captured_at": (
                self.current_captured_at.isoformat()
            ),
            "current_posture_digest": (
                self.current_posture_digest.to_payload()
            ),
            "current_posture_id": str(
                self.current_posture_id
            ),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "current_status": self.current_status.value,
            "delta_id": str(self.delta_id),
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "grants_authority": self.grants_authority,
            "new_adverse_signal": self.new_adverse_signal,
            "newly_supported": self.newly_supported,
            "previous_captured_at": (
                self.previous_captured_at.isoformat()
            ),
            "previous_posture_digest": (
                self.previous_posture_digest.to_payload()
            ),
            "previous_posture_id": str(
                self.previous_posture_id
            ),
            "previous_snapshot_digest": (
                self.previous_snapshot_digest.to_payload()
            ),
            "previous_status": self.previous_status.value,
            "requires_human_attention": (
                self.requires_human_attention
            ),
            "schema": self.SCHEMA.value,
            "status_changed": self.status_changed,
            "support_lost": self.support_lost,
            "transition": self.transition.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical posture-delta document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete posture transition."""

        return self.to_document().digest(
            domain="claim-posture-delta"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureDeltaSnapshot:
    """Catalog-wide transition report between two posture snapshots."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-delta-snapshot-v1"
    )

    snapshot_id: ScopedIdentifier
    compared_at: UtcTimestamp
    produced_by_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    claim_catalog_id: ScopedIdentifier
    previous_snapshot_id: ScopedIdentifier
    current_snapshot_id: ScopedIdentifier
    deltas: tuple[ClaimPostureDelta, ...]
    claim_catalog_digest: ContentDigest
    previous_snapshot_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        deltas = tuple(
            self.deltas
        )
        self._validate_deltas(
            deltas
        )

        object.__setattr__(
            self,
            "deltas",
            tuple(
                sorted(
                    deltas,
                    key=lambda delta: str(
                        delta.claim_id
                    ),
                )
            ),
        )

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "snapshot_id",
                self.snapshot_id,
                "claim-posture-delta-snapshot",
            ),
            (
                "claim_catalog_id",
                self.claim_catalog_id,
                "claim-catalog",
            ),
            (
                "previous_snapshot_id",
                self.previous_snapshot_id,
                "claim-posture-snapshot",
            ),
            (
                "current_snapshot_id",
                self.current_snapshot_id,
                "claim-posture-snapshot",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        if not isinstance(
            self.compared_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "compared_at must be a UtcTimestamp"
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
        if self.producer_kind not in _DELTA_PRODUCER_KINDS:
            raise FoundationError(
                "claim-posture delta producer must be "
                "a service or system actor"
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
        for field_name, value, domain in (
            (
                "claim_catalog_digest",
                self.claim_catalog_digest,
                "claim-catalog",
            ),
            (
                "previous_snapshot_digest",
                self.previous_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "current_snapshot_digest",
                self.current_snapshot_digest,
                "claim-posture-snapshot",
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                "actor-registry",
            ),
        ):
            _require_digest(
                value,
                field_name=field_name,
                domain=domain,
            )

    def _validate_deltas(
        self,
        deltas: tuple[ClaimPostureDelta, ...],
    ) -> None:
        for index, delta in enumerate(
            deltas
        ):
            if not isinstance(
                delta,
                ClaimPostureDelta,
            ):
                raise FoundationError(
                    f"deltas[{index}] must be a ClaimPostureDelta"
                )
            if delta.compared_at != self.compared_at:
                raise FoundationError(
                    "every posture delta must use "
                    "the snapshot comparison time"
                )
            if (
                delta.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every posture delta must bind "
                    "the claim catalog"
                )
            if (
                delta.previous_snapshot_digest
                != self.previous_snapshot_digest
            ):
                raise FoundationError(
                    "every posture delta must bind "
                    "the previous posture snapshot"
                )
            if (
                delta.current_snapshot_digest
                != self.current_snapshot_digest
            ):
                raise FoundationError(
                    "every posture delta must bind "
                    "the current posture snapshot"
                )
            if (
                delta.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every posture delta must bind "
                    "the actor registry"
                )

        delta_ids = tuple(
            delta.delta_id
            for delta in deltas
        )
        if len(delta_ids) != len(
            set(delta_ids)
        ):
            raise FoundationError(
                "posture-delta snapshot must contain "
                "unique delta IDs"
            )

        claim_ids = tuple(
            delta.claim_id
            for delta in deltas
        )
        if len(claim_ids) != len(
            set(claim_ids)
        ):
            raise FoundationError(
                "posture-delta snapshot must contain "
                "one delta per claim"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        compared_at: UtcTimestamp,
        produced_by_id: ScopedIdentifier,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
        actor_registry: ActorRegistry,
    ) -> ClaimPostureDeltaSnapshot:
        """Compare every claim across two catalog-bound snapshots."""

        producer = actor_registry.require_actor(
            produced_by_id
        )
        producer_owner_id = _validate_delta_producer(
            producer
        )

        cls._validate_bindings(
            compared_at=compared_at,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            actor_registry=actor_registry,
        )

        previous_claim_ids = {
            posture.claim_id
            for posture in previous_snapshot.postures
        }
        current_claim_ids = {
            posture.claim_id
            for posture in current_snapshot.postures
        }

        if previous_claim_ids != current_claim_ids:
            raise FoundationError(
                "posture snapshots must contain "
                "the same catalog claim set"
            )

        deltas = tuple(
            ClaimPostureDelta.compare(
                key=(
                    f"{key}-"
                    f"{str(current.claim_id)}"
                ),
                compared_at=compared_at,
                previous=previous_snapshot.require_posture(
                    current.claim_id
                ),
                current=current,
                previous_snapshot=previous_snapshot,
                current_snapshot=current_snapshot,
            )
            for current in current_snapshot.postures
        )

        return cls(
            snapshot_id=ScopedIdentifier.create(
                namespace="claim-posture-delta-snapshot",
                key=key,
                namespace_field="snapshot namespace",
                key_field="snapshot key",
            ),
            compared_at=compared_at,
            produced_by_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            claim_catalog_id=current_snapshot.claim_catalog_id,
            previous_snapshot_id=previous_snapshot.snapshot_id,
            current_snapshot_id=current_snapshot.snapshot_id,
            deltas=deltas,
            claim_catalog_digest=(
                current_snapshot.claim_catalog_digest
            ),
            previous_snapshot_digest=previous_snapshot.digest(),
            current_snapshot_digest=current_snapshot.digest(),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        compared_at: UtcTimestamp,
        previous_snapshot: ClaimPostureSnapshot,
        current_snapshot: ClaimPostureSnapshot,
        actor_registry: ActorRegistry,
    ) -> None:
        actor_registry_digest = actor_registry.digest()

        if (
            previous_snapshot.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "previous posture snapshot is not bound "
                "to the supplied actor registry"
            )
        if (
            current_snapshot.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "current posture snapshot is not bound "
                "to the supplied actor registry"
            )
        if (
            previous_snapshot.claim_catalog_id
            != current_snapshot.claim_catalog_id
        ):
            raise FoundationError(
                "posture snapshots reference different claim catalogs"
            )
        if (
            previous_snapshot.claim_catalog_digest
            != current_snapshot.claim_catalog_digest
        ):
            raise FoundationError(
                "posture snapshots are not bound "
                "to the same claim catalog"
            )
        if (
            current_snapshot.captured_at.value
            <= previous_snapshot.captured_at.value
        ):
            raise FoundationError(
                "current posture snapshot must be newer "
                "than the previous snapshot"
            )
        if compared_at.value < current_snapshot.captured_at.value:
            raise FoundationError(
                "posture comparison must not predate "
                "the current posture snapshot"
            )

    @property
    def total_count(self) -> int:
        """Return the total number of compared claims."""

        return len(
            self.deltas
        )

    @property
    def changed_count(self) -> int:
        """Return the number of changed claim postures."""

        return sum(
            delta.status_changed
            for delta in self.deltas
        )

    @property
    def unchanged_count(self) -> int:
        """Return the number of unchanged claim postures."""

        return self.total_count - self.changed_count

    @property
    def support_lost_count(self) -> int:
        """Return the number of claims that lost current support."""

        return sum(
            delta.support_lost
            for delta in self.deltas
        )

    @property
    def newly_supported_count(self) -> int:
        """Return the number of claims newly supported."""

        return sum(
            delta.newly_supported
            for delta in self.deltas
        )

    @property
    def new_adverse_signal_count(self) -> int:
        """Return the number of claims with a new adverse posture."""

        return sum(
            delta.new_adverse_signal
            for delta in self.deltas
        )

    @property
    def adverse_signal_cleared_count(self) -> int:
        """Return the number of claims whose adverse posture cleared."""

        return sum(
            delta.adverse_signal_cleared
            for delta in self.deltas
        )

    @property
    def attention_opened_count(self) -> int:
        """Return the number of claims newly requiring attention."""

        return sum(
            delta.attention_opened
            for delta in self.deltas
        )

    @property
    def attention_cleared_count(self) -> int:
        """Return the number of claims whose attention state cleared."""

        return sum(
            delta.attention_cleared
            for delta in self.deltas
        )

    @property
    def has_material_regression(self) -> bool:
        """Return whether support was lost or a new adverse signal appeared."""

        return (
            self.support_lost_count > 0
            or self.new_adverse_signal_count > 0
        )

    @property
    def establishes_absolute_truth(self) -> bool:
        """Return false because snapshot comparison remains temporal."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because posture comparison never grants authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def delta_for(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureDelta | None:
        """Return the posture transition for one claim."""

        for delta in self.deltas:
            if delta.claim_id == claim_id:
                return delta

        return None

    def require_delta(
        self,
        claim_id: ScopedIdentifier,
    ) -> ClaimPostureDelta:
        """Return a posture delta or fail when absent."""

        delta = self.delta_for(
            claim_id
        )

        if delta is None:
            raise FoundationError(
                "posture-delta snapshot does not contain "
                f"claim: {claim_id}"
            )

        return delta

    def changed_deltas(
        self,
    ) -> tuple[ClaimPostureDelta, ...]:
        """Return all claim postures that changed."""

        return tuple(
            delta
            for delta in self.deltas
            if delta.status_changed
        )

    def support_lost_deltas(
        self,
    ) -> tuple[ClaimPostureDelta, ...]:
        """Return claims that lost current support."""

        return tuple(
            delta
            for delta in self.deltas
            if delta.support_lost
        )

    def new_adverse_signal_deltas(
        self,
    ) -> tuple[ClaimPostureDelta, ...]:
        """Return claims with newly adverse current posture."""

        return tuple(
            delta
            for delta in self.deltas
            if delta.new_adverse_signal
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic delta-snapshot representation."""

        delta_payloads: JsonArray = [
            delta.to_payload()
            for delta in self.deltas
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "adverse_signal_cleared_count": (
                self.adverse_signal_cleared_count
            ),
            "attention_cleared_count": (
                self.attention_cleared_count
            ),
            "attention_opened_count": (
                self.attention_opened_count
            ),
            "changed_count": self.changed_count,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_catalog_id": str(self.claim_catalog_id),
            "claims_certification": self.claims_certification,
            "compared_at": self.compared_at.isoformat(),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "current_snapshot_id": str(
                self.current_snapshot_id
            ),
            "deltas": delta_payloads,
            "establishes_absolute_truth": (
                self.establishes_absolute_truth
            ),
            "grants_authority": self.grants_authority,
            "has_material_regression": (
                self.has_material_regression
            ),
            "new_adverse_signal_count": (
                self.new_adverse_signal_count
            ),
            "newly_supported_count": (
                self.newly_supported_count
            ),
            "previous_snapshot_digest": (
                self.previous_snapshot_digest.to_payload()
            ),
            "previous_snapshot_id": str(
                self.previous_snapshot_id
            ),
            "produced_by_id": str(self.produced_by_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_kind": self.producer_kind.value,
            "schema": self.SCHEMA.value,
            "snapshot_id": str(self.snapshot_id),
            "support_lost_count": self.support_lost_count,
            "total_count": self.total_count,
            "unchanged_count": self.unchanged_count,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical delta-snapshot document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete posture comparison."""

        return self.to_document().digest(
            domain="claim-posture-delta-snapshot"
        )
