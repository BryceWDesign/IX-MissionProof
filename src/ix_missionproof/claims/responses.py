"""Human responses to immutable claim-posture alerts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.alerts import (
    ClaimPostureAlert,
    ClaimPostureAlertDocket,
    ClaimPostureAlertSeverity,
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

_RESPONSE_LEDGER_PRODUCER_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertResponseAction(StrEnum):
    """Permitted human responses to one current claim alert."""

    ACKNOWLEDGE = "acknowledge"
    OPEN_INVESTIGATION = "open-investigation"
    ESCALATE = "escalate"
    DEFER = "defer"

    @property
    def requires_assignment(self) -> bool:
        """Return whether the action requires a human assignee."""

        return self in {
            ClaimPostureAlertResponseAction.OPEN_INVESTIGATION,
            ClaimPostureAlertResponseAction.ESCALATE,
        }

    @property
    def requires_due_at(self) -> bool:
        """Return whether the action requires a future review time."""

        return self in {
            ClaimPostureAlertResponseAction.OPEN_INVESTIGATION,
            ClaimPostureAlertResponseAction.ESCALATE,
            ClaimPostureAlertResponseAction.DEFER,
        }

    @property
    def is_escalation(self) -> bool:
        """Return whether the alert was explicitly escalated."""

        return self is ClaimPostureAlertResponseAction.ESCALATE


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


def _validate_response_ledger_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "alert-response ledger producer must be active"
        )
    if producer.kind not in _RESPONSE_LEDGER_PRODUCER_KINDS:
        raise FoundationError(
            "alert-response ledger producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "alert-response ledger producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertResponse:
    """One human response bound to an exact immutable alert."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-response-v1"
    )

    response_id: ScopedIdentifier
    responded_at: UtcTimestamp
    responded_by_id: ScopedIdentifier
    action: ClaimPostureAlertResponseAction
    rationale: str
    alert_id: ScopedIdentifier
    claim_id: ScopedIdentifier
    alert_severity: ClaimPostureAlertSeverity
    assigned_to_id: ScopedIdentifier | None
    review_due_at: UtcTimestamp | None
    alert_digest: ContentDigest
    docket_digest: ContentDigest
    current_posture_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        object.__setattr__(
            self,
            "rationale",
            require_text(
                self.rationale,
                field_name="rationale",
            ),
        )

        self._validate_action_semantics()

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "response_id",
                self.response_id,
                "claim-posture-alert-response",
            ),
            (
                "responded_by_id",
                self.responded_by_id,
                "human",
            ),
            (
                "alert_id",
                self.alert_id,
                "claim-posture-alert",
            ),
            (
                "claim_id",
                self.claim_id,
                "claim",
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
            )

        _require_optional_identifier(
            self.assigned_to_id,
            field_name="assigned_to_id",
            namespace="human",
        )

        if not isinstance(
            self.responded_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "responded_at must be a UtcTimestamp"
            )
        if (
            self.review_due_at is not None
            and not isinstance(
                self.review_due_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "review_due_at must be a UtcTimestamp or None"
            )
        if not isinstance(
            self.action,
            ClaimPostureAlertResponseAction,
        ):
            raise FoundationError(
                "action must be a ClaimPostureAlertResponseAction"
            )
        if not isinstance(
            self.alert_severity,
            ClaimPostureAlertSeverity,
        ):
            raise FoundationError(
                "alert_severity must be a ClaimPostureAlertSeverity"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "alert_digest",
                self.alert_digest,
                "claim-posture-alert",
            ),
            (
                "docket_digest",
                self.docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "current_posture_digest",
                self.current_posture_digest,
                "claim-posture",
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

        _require_optional_digest(
            self.delta_snapshot_digest,
            field_name="delta_snapshot_digest",
            domain="claim-posture-delta-snapshot",
        )

    def _validate_action_semantics(self) -> None:
        if (
            self.action.requires_assignment
            and self.assigned_to_id is None
        ):
            raise FoundationError(
                f"{self.action.value} response requires "
                "an assigned human"
            )

        if (
            not self.action.requires_assignment
            and self.assigned_to_id is not None
        ):
            raise FoundationError(
                f"{self.action.value} response must not "
                "declare an assignee"
            )

        if (
            self.action.requires_due_at
            and self.review_due_at is None
        ):
            raise FoundationError(
                f"{self.action.value} response requires review_due_at"
            )

        if (
            not self.action.requires_due_at
            and self.review_due_at is not None
        ):
            raise FoundationError(
                f"{self.action.value} response must not "
                "declare review_due_at"
            )

        if (
            self.review_due_at is not None
            and self.review_due_at.value
            <= self.responded_at.value
        ):
            raise FoundationError(
                "review_due_at must be later than responded_at"
            )

        if (
            self.alert_severity
            is ClaimPostureAlertSeverity.CRITICAL
            and self.action is ClaimPostureAlertResponseAction.DEFER
        ):
            raise FoundationError(
                "critical claim-posture alerts must not be deferred"
            )

    @classmethod
    def respond(
        cls,
        *,
        key: str,
        responded_at: UtcTimestamp,
        responded_by_id: ScopedIdentifier,
        action: ClaimPostureAlertResponseAction,
        rationale: str,
        alert: ClaimPostureAlert,
        docket: ClaimPostureAlertDocket,
        actor_registry: ActorRegistry,
        assigned_to_id: ScopedIdentifier | None = None,
        review_due_at: UtcTimestamp | None = None,
    ) -> ClaimPostureAlertResponse:
        """Record a human response without resolving or hiding the alert."""

        cls._validate_bindings(
            responded_at=responded_at,
            alert=alert,
            docket=docket,
            actor_registry=actor_registry,
        )

        responder = actor_registry.require_actor(
            responded_by_id
        )
        cls._validate_human_actor(
            responder,
            role="alert responder",
        )

        if assigned_to_id is not None:
            assignee = actor_registry.require_actor(
                assigned_to_id
            )
            cls._validate_human_actor(
                assignee,
                role="alert assignee",
            )

        return cls(
            response_id=ScopedIdentifier.create(
                namespace="claim-posture-alert-response",
                key=key,
                namespace_field="response namespace",
                key_field="response key",
            ),
            responded_at=responded_at,
            responded_by_id=responder.actor_id,
            action=action,
            rationale=rationale,
            alert_id=alert.alert_id,
            claim_id=alert.claim_id,
            alert_severity=alert.severity,
            assigned_to_id=assigned_to_id,
            review_due_at=review_due_at,
            alert_digest=alert.digest(),
            docket_digest=docket.digest(),
            current_posture_digest=(
                alert.current_posture_digest
            ),
            current_snapshot_digest=(
                alert.current_snapshot_digest
            ),
            delta_snapshot_digest=(
                alert.delta_snapshot_digest
            ),
            claim_catalog_digest=(
                alert.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_bindings(
        *,
        responded_at: UtcTimestamp,
        alert: ClaimPostureAlert,
        docket: ClaimPostureAlertDocket,
        actor_registry: ActorRegistry,
    ) -> None:
        docket_alert = docket.require_alert(
            alert.claim_id
        )

        if docket_alert.alert_id != alert.alert_id:
            raise FoundationError(
                "alert does not belong to the supplied docket"
            )
        if docket_alert.digest() != alert.digest():
            raise FoundationError(
                "alert digest does not match the supplied docket"
            )
        if responded_at.value < docket.generated_at.value:
            raise FoundationError(
                "alert response must not predate the alert docket"
            )

        actor_registry_digest = actor_registry.digest()

        if (
            alert.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "alert is not bound to the supplied actor registry"
            )
        if (
            docket.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "alert docket is not bound to "
                "the supplied actor registry"
            )
        if (
            alert.current_snapshot_digest
            != docket.current_snapshot_digest
        ):
            raise FoundationError(
                "alert is not bound to the docket's "
                "current posture snapshot"
            )
        if (
            alert.delta_snapshot_digest
            != docket.delta_snapshot_digest
        ):
            raise FoundationError(
                "alert is not bound to the docket's "
                "posture-delta snapshot"
            )
        if (
            alert.claim_catalog_digest
            != docket.claim_catalog_digest
        ):
            raise FoundationError(
                "alert is not bound to the docket's claim catalog"
            )

    @staticmethod
    def _validate_human_actor(
        actor: ActorIdentity,
        *,
        role: str,
    ) -> None:
        if not actor.is_eligible_for_human_authority:
            raise FoundationError(
                f"{role} must be an active human actor"
            )

    @property
    def acknowledges_alert(self) -> bool:
        """Return whether the response explicitly acknowledges the alert."""

        return self.action is (
            ClaimPostureAlertResponseAction.ACKNOWLEDGE
        )

    @property
    def opens_investigation(self) -> bool:
        """Return whether the response opens an investigation."""

        return self.action is (
            ClaimPostureAlertResponseAction.OPEN_INVESTIGATION
        )

    @property
    def escalates_alert(self) -> bool:
        """Return whether the response escalates the alert."""

        return self.action.is_escalation

    @property
    def defers_response(self) -> bool:
        """Return whether further review was deferred to a future time."""

        return self.action is (
            ClaimPostureAlertResponseAction.DEFER
        )

    @property
    def resolves_alert(self) -> bool:
        """Return false because only posture change removes an alert."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because alert responses do not mutate claim posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because alert responses grant no action authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic alert-response representation."""

        return {
            "acknowledges_alert": self.acknowledges_alert,
            "action": self.action.value,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "alert_digest": self.alert_digest.to_payload(),
            "alert_id": str(self.alert_id),
            "alert_severity": self.alert_severity.value,
            "assigned_to_id": (
                str(self.assigned_to_id)
                if self.assigned_to_id is not None
                else None
            ),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claim_id": str(self.claim_id),
            "claims_certification": self.claims_certification,
            "current_posture_digest": (
                self.current_posture_digest.to_payload()
            ),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "defers_response": self.defers_response,
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
                if self.delta_snapshot_digest is not None
                else None
            ),
            "docket_digest": self.docket_digest.to_payload(),
            "escalates_alert": self.escalates_alert,
            "grants_authority": self.grants_authority,
            "opens_investigation": self.opens_investigation,
            "rationale": self.rationale,
            "resolves_alert": self.resolves_alert,
            "responded_at": self.responded_at.isoformat(),
            "responded_by_id": str(self.responded_by_id),
            "response_id": str(self.response_id),
            "review_due_at": (
                self.review_due_at.isoformat()
                if self.review_due_at is not None
                else None
            ),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical response document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete human response."""

        return self.to_document().digest(
            domain="claim-posture-alert-response"
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertResponseLedger:
    """Immutable history of human responses to one alert docket."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-response-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    docket_id: ScopedIdentifier
    responses: tuple[ClaimPostureAlertResponse, ...]
    docket_digest: ContentDigest
    current_snapshot_digest: ContentDigest
    delta_snapshot_digest: ContentDigest | None
    claim_catalog_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_metadata()
        self._validate_digests()

        responses = tuple(
            self.responses
        )
        self._validate_responses(
            responses
        )

        ordered = tuple(
            sorted(
                responses,
                key=lambda response: (
                    response.responded_at.value,
                    str(response.response_id),
                ),
            )
        )
        self._validate_sequences(
            ordered
        )

        object.__setattr__(
            self,
            "responses",
            ordered,
        )

    def _validate_metadata(self) -> None:
        _require_identifier(
            self.ledger_id,
            field_name="ledger_id",
            namespace="claim-posture-alert-response-ledger",
        )
        _require_identifier(
            self.docket_id,
            field_name="docket_id",
            namespace="claim-posture-alert-docket",
        )

        if not isinstance(
            self.created_at,
            UtcTimestamp,
        ):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(
            self.producer_id,
            ScopedIdentifier,
        ):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )
        if not isinstance(
            self.producer_kind,
            ActorKind,
        ):
            raise FoundationError(
                "producer_kind must be an ActorKind"
            )
        if self.producer_kind not in (
            _RESPONSE_LEDGER_PRODUCER_KINDS
        ):
            raise FoundationError(
                "alert-response ledger producer must be "
                "a service or system actor"
            )
        if self.producer_id.namespace != CanonicalKey(
            self.producer_kind.value
        ):
            raise FoundationError(
                "producer_id namespace must match producer_kind"
            )

        _require_identifier(
            self.producer_accountability_owner_id,
            field_name="producer_accountability_owner_id",
            namespace="human",
        )

    def _validate_digests(self) -> None:
        _require_digest(
            self.docket_digest,
            field_name="docket_digest",
            domain="claim-posture-alert-docket",
        )
        _require_digest(
            self.current_snapshot_digest,
            field_name="current_snapshot_digest",
            domain="claim-posture-snapshot",
        )
        _require_optional_digest(
            self.delta_snapshot_digest,
            field_name="delta_snapshot_digest",
            domain="claim-posture-delta-snapshot",
        )
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

    def _validate_responses(
        self,
        responses: tuple[ClaimPostureAlertResponse, ...],
    ) -> None:
        for index, response in enumerate(
            responses
        ):
            if not isinstance(
                response,
                ClaimPostureAlertResponse,
            ):
                raise FoundationError(
                    f"responses[{index}] must be a "
                    "ClaimPostureAlertResponse"
                )
            if response.responded_at.value > self.created_at.value:
                raise FoundationError(
                    "alert-response ledger must not predate "
                    "a contained response"
                )
            if response.docket_digest != self.docket_digest:
                raise FoundationError(
                    "every response must bind the same alert docket"
                )
            if (
                response.current_snapshot_digest
                != self.current_snapshot_digest
            ):
                raise FoundationError(
                    "every response must bind the same "
                    "current posture snapshot"
                )
            if (
                response.delta_snapshot_digest
                != self.delta_snapshot_digest
            ):
                raise FoundationError(
                    "every response must bind the same "
                    "posture-delta snapshot"
                )
            if (
                response.claim_catalog_digest
                != self.claim_catalog_digest
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same claim catalog"
                )
            if (
                response.actor_registry_digest
                != self.actor_registry_digest
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same actor registry"
                )

        response_ids = tuple(
            response.response_id
            for response in responses
        )

        if len(response_ids) != len(
            set(response_ids)
        ):
            raise FoundationError(
                "alert-response ledger must contain "
                "unique response IDs"
            )

    @staticmethod
    def _validate_sequences(
        responses: tuple[ClaimPostureAlertResponse, ...],
    ) -> None:
        latest_by_alert: dict[
            ScopedIdentifier,
            ClaimPostureAlertResponse,
        ] = {}

        for response in responses:
            previous = latest_by_alert.get(
                response.alert_id
            )

            if previous is not None:
                if (
                    previous.claim_id != response.claim_id
                    or previous.alert_digest
                    != response.alert_digest
                ):
                    raise FoundationError(
                        "response history for one alert must "
                        "preserve its alert and claim bindings"
                    )
                if (
                    previous.responded_at.value
                    >= response.responded_at.value
                ):
                    raise FoundationError(
                        "responses for one alert must use "
                        "strictly increasing response times"
                    )
                if (
                    previous.action
                    is ClaimPostureAlertResponseAction.ESCALATE
                    and response.action
                    is ClaimPostureAlertResponseAction.DEFER
                ):
                    raise FoundationError(
                        "an escalated alert must not later be deferred"
                    )

            latest_by_alert[
                response.alert_id
            ] = response

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        docket: ClaimPostureAlertDocket,
        actor_registry: ActorRegistry,
        responses: Iterable[ClaimPostureAlertResponse] = (),
    ) -> ClaimPostureAlertResponseLedger:
        """Create a response ledger bound to one immutable alert docket."""

        producer = actor_registry.require_actor(
            producer_id
        )
        producer_owner_id = (
            _validate_response_ledger_producer(
                producer
            )
        )

        if docket.actor_registry_digest != actor_registry.digest():
            raise FoundationError(
                "alert docket is not bound to "
                "the supplied actor registry"
            )
        if created_at.value < docket.generated_at.value:
            raise FoundationError(
                "alert-response ledger must not predate "
                "the alert docket"
            )

        response_tuple = tuple(
            responses
        )

        cls._validate_docket_membership(
            docket=docket,
            responses=response_tuple,
        )

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-response-ledger"
                ),
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer.actor_id,
            producer_kind=producer.kind,
            producer_accountability_owner_id=(
                producer_owner_id
            ),
            docket_id=docket.docket_id,
            responses=response_tuple,
            docket_digest=docket.digest(),
            current_snapshot_digest=(
                docket.current_snapshot_digest
            ),
            delta_snapshot_digest=(
                docket.delta_snapshot_digest
            ),
            claim_catalog_digest=(
                docket.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_docket_membership(
        *,
        docket: ClaimPostureAlertDocket,
        responses: tuple[ClaimPostureAlertResponse, ...],
    ) -> None:
        for response in responses:
            alert = docket.require_alert(
                response.claim_id
            )

            if alert.alert_id != response.alert_id:
                raise FoundationError(
                    "response references an alert absent "
                    "from the supplied docket"
                )
            if alert.digest() != response.alert_digest:
                raise FoundationError(
                    "response alert digest does not match "
                    "the supplied docket"
                )

    def responses_for_alert(
        self,
        alert_id: ScopedIdentifier,
    ) -> tuple[ClaimPostureAlertResponse, ...]:
        """Return ordered human responses for one exact alert."""

        return tuple(
            response
            for response in self.responses
            if response.alert_id == alert_id
        )

    def latest_for_alert(
        self,
        alert_id: ScopedIdentifier,
    ) -> ClaimPostureAlertResponse | None:
        """Return the latest human response for an alert."""

        responses = self.responses_for_alert(
            alert_id
        )

        return responses[-1] if responses else None

    def unresponded_alerts(
        self,
        *,
        docket: ClaimPostureAlertDocket,
    ) -> tuple[ClaimPostureAlert, ...]:
        """Return alerts without any bound human response."""

        self._require_bound_docket(
            docket
        )

        return tuple(
            alert
            for alert in docket.alerts
            if self.latest_for_alert(
                alert.alert_id
            )
            is None
        )

    def alerts_requiring_escalation(
        self,
        *,
        docket: ClaimPostureAlertDocket,
    ) -> tuple[ClaimPostureAlert, ...]:
        """Return critical alerts lacking an explicit escalation."""

        self._require_bound_docket(
            docket
        )

        requiring_escalation: list[
            ClaimPostureAlert
        ] = []

        for alert in docket.alerts:
            if (
                alert.severity
                is not ClaimPostureAlertSeverity.CRITICAL
            ):
                continue

            latest = self.latest_for_alert(
                alert.alert_id
            )

            if (
                latest is None
                or not latest.escalates_alert
            ):
                requiring_escalation.append(
                    alert
                )

        return tuple(
            requiring_escalation
        )

    def active_alerts(
        self,
        *,
        docket: ClaimPostureAlertDocket,
    ) -> tuple[ClaimPostureAlert, ...]:
        """Return all docket alerts regardless of response history."""

        self._require_bound_docket(
            docket
        )

        return docket.alerts

    def _require_bound_docket(
        self,
        docket: ClaimPostureAlertDocket,
    ) -> None:
        if docket.docket_id != self.docket_id:
            raise FoundationError(
                "response ledger references a different alert docket"
            )
        if docket.digest() != self.docket_digest:
            raise FoundationError(
                "response ledger is not bound to "
                "the supplied alert docket"
            )

    @property
    def response_count(self) -> int:
        """Return the number of recorded human responses."""

        return len(
            self.responses
        )

    @property
    def resolves_alerts(self) -> bool:
        """Return false because responses never clear active alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because response history does not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because response history grants no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def append(
        self,
        response: ClaimPostureAlertResponse,
        *,
        created_at: UtcTimestamp,
        docket: ClaimPostureAlertDocket,
    ) -> ClaimPostureAlertResponseLedger:
        """Return the next immutable response-ledger snapshot."""

        self._require_bound_docket(
            docket
        )

        if created_at.value < self.created_at.value:
            raise FoundationError(
                "next alert-response ledger snapshot "
                "must not predate the current snapshot"
            )

        self._validate_docket_membership(
            docket=docket,
            responses=(
                response,
            ),
        )

        return ClaimPostureAlertResponseLedger(
            ledger_id=self.ledger_id,
            created_at=created_at,
            producer_id=self.producer_id,
            producer_kind=self.producer_kind,
            producer_accountability_owner_id=(
                self.producer_accountability_owner_id
            ),
            docket_id=self.docket_id,
            responses=(
                *self.responses,
                response,
            ),
            docket_digest=self.docket_digest,
            current_snapshot_digest=(
                self.current_snapshot_digest
            ),
            delta_snapshot_digest=(
                self.delta_snapshot_digest
            ),
            claim_catalog_digest=(
                self.claim_catalog_digest
            ),
            actor_registry_digest=(
                self.actor_registry_digest
            ),
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic response-ledger representation."""

        response_payloads: JsonArray = [
            response.to_payload()
            for response in self.responses
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "changes_claim_state": self.changes_claim_state,
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "created_at": self.created_at.isoformat(),
            "current_snapshot_digest": (
                self.current_snapshot_digest.to_payload()
            ),
            "delta_snapshot_digest": (
                self.delta_snapshot_digest.to_payload()
                if self.delta_snapshot_digest is not None
                else None
            ),
            "docket_digest": self.docket_digest.to_payload(),
            "docket_id": str(self.docket_id),
            "grants_authority": self.grants_authority,
            "ledger_id": str(self.ledger_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "resolves_alerts": self.resolves_alerts,
            "response_count": self.response_count,
            "responses": response_payloads,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical response-ledger document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete response ledger."""

        return self.to_document().digest(
            domain="claim-posture-alert-response-ledger"
        )
