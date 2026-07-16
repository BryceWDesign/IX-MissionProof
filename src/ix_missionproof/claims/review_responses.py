"""Human responses to lifecycle checkpoint review obligations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.claims.checkpoint_reviews import (
    ClaimPostureAlertLifecycleReviewDocket,
    ClaimPostureAlertLifecycleReviewDocketStatus,
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

_REVIEW_RESPONSE_LEDGER_PRODUCER_KINDS: Final[
    frozenset[ActorKind]
] = frozenset(
    {
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
    }
)


class ClaimPostureAlertLifecycleReviewResponseAction(StrEnum):
    """Human actions allowed for one open review obligation."""

    ACKNOWLEDGE = "acknowledge"
    ASSIGN_REVIEW = "assign-review"
    ESCALATE = "escalate"
    OPEN_CORRECTIVE_ACTION = "open-corrective-action"

    @property
    def requires_assignment(self) -> bool:
        """Return whether the action requires a human assignee."""

        return self in {
            (
                ClaimPostureAlertLifecycleReviewResponseAction
                .ASSIGN_REVIEW
            ),
            ClaimPostureAlertLifecycleReviewResponseAction.ESCALATE,
            (
                ClaimPostureAlertLifecycleReviewResponseAction
                .OPEN_CORRECTIVE_ACTION
            ),
        }

    @property
    def requires_due_at(self) -> bool:
        """Return whether the action requires a future due time."""

        return self.requires_assignment

    @property
    def progression_rank(self) -> int:
        """Return the nondecreasing operational progression rank."""

        return {
            (
                ClaimPostureAlertLifecycleReviewResponseAction
                .ACKNOWLEDGE
            ): 1,
            (
                ClaimPostureAlertLifecycleReviewResponseAction
                .ASSIGN_REVIEW
            ): 2,
            (
                ClaimPostureAlertLifecycleReviewResponseAction
                .OPEN_CORRECTIVE_ACTION
            ): 3,
            (
                ClaimPostureAlertLifecycleReviewResponseAction
                .ESCALATE
            ): 4,
        }[self]


def _require_identifier(
    value: ScopedIdentifier,
    *,
    field_name: str,
    namespace: str,
) -> None:
    if not isinstance(
        value,
        ScopedIdentifier,
    ):
        raise FoundationError(
            f"{field_name} must be a ScopedIdentifier"
        )
    if value.namespace != CanonicalKey(
        namespace
    ):
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
    if not isinstance(
        value,
        ContentDigest,
    ):
        raise FoundationError(
            f"{field_name} must be a ContentDigest"
        )
    if value.domain != CanonicalKey(
        domain
    ):
        raise FoundationError(
            f"{field_name} domain must be {domain}"
        )


def _validate_response_ledger_producer(
    producer: ActorIdentity,
) -> ScopedIdentifier:
    if not producer.is_active:
        raise FoundationError(
            "review-response ledger producer must be active"
        )
    if producer.kind not in (
        _REVIEW_RESPONSE_LEDGER_PRODUCER_KINDS
    ):
        raise FoundationError(
            "review-response ledger producer must be "
            "a service or system actor"
        )

    owner_id = producer.accountability_owner_id

    if owner_id is None:
        raise FoundationError(
            "review-response ledger producer must identify "
            "an accountable human owner"
        )

    return owner_id


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleReviewResponse:
    """One human action bound to an exact review docket."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-review-response-v1"
    )

    response_id: ScopedIdentifier
    responded_at: UtcTimestamp
    responded_by_id: ScopedIdentifier
    action: ClaimPostureAlertLifecycleReviewResponseAction
    rationale: str
    review_docket_id: ScopedIdentifier
    review_docket_status: (
        ClaimPostureAlertLifecycleReviewDocketStatus
    )
    chain_id: ScopedIdentifier
    generation_count: int
    head_entry_id: ScopedIdentifier
    assigned_to_id: ScopedIdentifier | None
    action_due_at: UtcTimestamp | None
    review_docket_digest: ContentDigest
    chain_digest: ContentDigest
    head_entry_digest: ContentDigest
    current_alert_docket_digest: ContentDigest
    checkpoint_currency_snapshot_digest: ContentDigest
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
                (
                    "claim-posture-alert-lifecycle-"
                    "review-response"
                ),
            ),
            (
                "responded_by_id",
                self.responded_by_id,
                "human",
            ),
            (
                "review_docket_id",
                self.review_docket_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "chain_id",
                self.chain_id,
                (
                    "claim-posture-alert-lifecycle-chain"
                ),
            ),
            (
                "head_entry_id",
                self.head_entry_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
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
            self.action_due_at is not None
            and not isinstance(
                self.action_due_at,
                UtcTimestamp,
            )
        ):
            raise FoundationError(
                "action_due_at must be "
                "a UtcTimestamp or None"
            )
        if not isinstance(
            self.action,
            ClaimPostureAlertLifecycleReviewResponseAction,
        ):
            raise FoundationError(
                "action must be a "
                "ClaimPostureAlertLifecycleReviewResponseAction"
            )
        if not isinstance(
            self.review_docket_status,
            ClaimPostureAlertLifecycleReviewDocketStatus,
        ):
            raise FoundationError(
                "review_docket_status must be a "
                "ClaimPostureAlertLifecycleReviewDocketStatus"
            )
        if isinstance(
            self.generation_count,
            bool,
        ) or not isinstance(
            self.generation_count,
            int,
        ):
            raise FoundationError(
                "generation_count must be an integer"
            )
        if self.generation_count < 1:
            raise FoundationError(
                "generation_count must be at least one"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "review_docket_digest",
                self.review_docket_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "chain_digest",
                self.chain_digest,
                (
                    "claim-posture-alert-lifecycle-chain"
                ),
            ),
            (
                "head_entry_digest",
                self.head_entry_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "current_alert_docket_digest",
                self.current_alert_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "checkpoint_currency_snapshot_digest",
                self.checkpoint_currency_snapshot_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
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

    def _validate_action_semantics(self) -> None:
        if self.review_docket_status is (
            ClaimPostureAlertLifecycleReviewDocketStatus
            .CLEAR
        ):
            raise FoundationError(
                "clear lifecycle-review docket must not "
                "receive a response"
            )

        if (
            self.review_docket_status
            is (
                ClaimPostureAlertLifecycleReviewDocketStatus
                .CORRECTIVE_ACTION_REQUIRED
            )
            and self.action
            not in {
                (
                    ClaimPostureAlertLifecycleReviewResponseAction
                    .ESCALATE
                ),
                (
                    ClaimPostureAlertLifecycleReviewResponseAction
                    .OPEN_CORRECTIVE_ACTION
                ),
            }
        ):
            raise FoundationError(
                "corrective-action review docket requires "
                "escalation or a corrective-action plan"
            )

        if (
            self.review_docket_status
            is not (
                ClaimPostureAlertLifecycleReviewDocketStatus
                .CORRECTIVE_ACTION_REQUIRED
            )
            and self.action
            is (
                ClaimPostureAlertLifecycleReviewResponseAction
                .OPEN_CORRECTIVE_ACTION
            )
        ):
            raise FoundationError(
                "corrective-action plan is only valid for "
                "a rejected continuity review"
            )

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
            and self.action_due_at is None
        ):
            raise FoundationError(
                f"{self.action.value} response requires "
                "action_due_at"
            )

        if (
            not self.action.requires_due_at
            and self.action_due_at is not None
        ):
            raise FoundationError(
                f"{self.action.value} response must not "
                "declare action_due_at"
            )

        if (
            self.action_due_at is not None
            and self.action_due_at.value
            <= self.responded_at.value
        ):
            raise FoundationError(
                "action_due_at must be later than responded_at"
            )

    @classmethod
    def respond(
        cls,
        *,
        key: str,
        responded_at: UtcTimestamp,
        responded_by_id: ScopedIdentifier,
        action: (
            ClaimPostureAlertLifecycleReviewResponseAction
        ),
        rationale: str,
        review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        actor_registry: ActorRegistry,
        assigned_to_id: ScopedIdentifier | None = None,
        action_due_at: UtcTimestamp | None = None,
    ) -> ClaimPostureAlertLifecycleReviewResponse:
        """Record a human action without closing the obligation."""

        actor_registry_digest = actor_registry.digest()

        if (
            review_docket.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "lifecycle-review docket is not bound to "
                "the supplied actor registry"
            )

        if (
            responded_at.value
            < review_docket.generated_at.value
        ):
            raise FoundationError(
                "lifecycle-review response must not predate "
                "the review docket"
            )

        responder = actor_registry.require_actor(
            responded_by_id
        )
        cls._validate_human_actor(
            responder,
            role="lifecycle-review responder",
        )

        if assigned_to_id is not None:
            assignee = actor_registry.require_actor(
                assigned_to_id
            )
            cls._validate_human_actor(
                assignee,
                role="lifecycle-review assignee",
            )

        return cls(
            response_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-"
                    "review-response"
                ),
                key=key,
                namespace_field="response namespace",
                key_field="response key",
            ),
            responded_at=responded_at,
            responded_by_id=responder.actor_id,
            action=action,
            rationale=rationale,
            review_docket_id=review_docket.docket_id,
            review_docket_status=review_docket.status,
            chain_id=review_docket.chain_id,
            generation_count=review_docket.generation_count,
            head_entry_id=review_docket.head_entry_id,
            assigned_to_id=assigned_to_id,
            action_due_at=action_due_at,
            review_docket_digest=review_docket.digest(),
            chain_digest=review_docket.chain_digest,
            head_entry_digest=review_docket.head_entry_digest,
            current_alert_docket_digest=(
                review_docket.current_alert_docket_digest
            ),
            checkpoint_currency_snapshot_digest=(
                review_docket
                .checkpoint_currency_snapshot_digest
            ),
            claim_catalog_digest=(
                review_docket.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry_digest,
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
    def assigns_human(self) -> bool:
        """Return whether the action creates an assignment."""

        return self.assigned_to_id is not None

    @property
    def escalates_review(self) -> bool:
        """Return whether the review obligation was escalated."""

        return self.action is (
            ClaimPostureAlertLifecycleReviewResponseAction
            .ESCALATE
        )

    @property
    def opens_corrective_action(self) -> bool:
        """Return whether corrective action was opened."""

        return self.action is (
            ClaimPostureAlertLifecycleReviewResponseAction
            .OPEN_CORRECTIVE_ACTION
        )

    @property
    def resolves_review_obligation(self) -> bool:
        """Return false because checkpoint state resolves review."""

        return False

    @property
    def accepts_continuity(self) -> bool:
        """Return false because responses cannot accept continuity."""

        return False

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because review actions are not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because review responses cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because responses do not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because responses grant no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic lifecycle-review response."""

        return {
            "accepts_continuity": self.accepts_continuity,
            "action": self.action.value,
            "action_due_at": (
                self.action_due_at.isoformat()
                if self.action_due_at is not None
                else None
            ),
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "approves_underlying_claims": (
                self.approves_underlying_claims
            ),
            "assigned_to_id": (
                str(self.assigned_to_id)
                if self.assigned_to_id is not None
                else None
            ),
            "assigns_human": self.assigns_human,
            "chain_digest": self.chain_digest.to_payload(),
            "chain_id": str(self.chain_id),
            "changes_claim_state": self.changes_claim_state,
            "checkpoint_currency_snapshot_digest": (
                self.checkpoint_currency_snapshot_digest
                .to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "current_alert_docket_digest": (
                self.current_alert_docket_digest.to_payload()
            ),
            "escalates_review": self.escalates_review,
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "head_entry_digest": (
                self.head_entry_digest.to_payload()
            ),
            "head_entry_id": str(self.head_entry_id),
            "opens_corrective_action": (
                self.opens_corrective_action
            ),
            "rationale": self.rationale,
            "resolves_review_obligation": (
                self.resolves_review_obligation
            ),
            "responded_at": self.responded_at.isoformat(),
            "responded_by_id": str(self.responded_by_id),
            "response_id": str(self.response_id),
            "review_docket_digest": (
                self.review_docket_digest.to_payload()
            ),
            "review_docket_id": str(self.review_docket_id),
            "review_docket_status": (
                self.review_docket_status.value
            ),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical response document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete response."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-"
                "review-response"
            )
        )


@dataclass(frozen=True, slots=True)
class ClaimPostureAlertLifecycleReviewResponseLedger:
    """Immutable action history for one exact review docket."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "claim-posture-alert-lifecycle-review-response-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    producer_kind: ActorKind
    producer_accountability_owner_id: ScopedIdentifier
    review_docket_id: ScopedIdentifier
    chain_id: ScopedIdentifier
    generation_count: int
    head_entry_id: ScopedIdentifier
    responses: tuple[
        ClaimPostureAlertLifecycleReviewResponse,
        ...,
    ]
    review_docket_digest: ContentDigest
    chain_digest: ContentDigest
    head_entry_digest: ContentDigest
    current_alert_docket_digest: ContentDigest
    checkpoint_currency_snapshot_digest: ContentDigest
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
        self._validate_sequence(
            ordered
        )

        object.__setattr__(
            self,
            "responses",
            ordered,
        )

    def _validate_metadata(self) -> None:
        for field_name, value, namespace in (
            (
                "ledger_id",
                self.ledger_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-response-ledger"
                ),
            ),
            (
                "review_docket_id",
                self.review_docket_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "chain_id",
                self.chain_id,
                (
                    "claim-posture-alert-lifecycle-chain"
                ),
            ),
            (
                "head_entry_id",
                self.head_entry_id,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
        ):
            _require_identifier(
                value,
                field_name=field_name,
                namespace=namespace,
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
            _REVIEW_RESPONSE_LEDGER_PRODUCER_KINDS
        ):
            raise FoundationError(
                "review-response ledger producer must be "
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

        if isinstance(
            self.generation_count,
            bool,
        ) or not isinstance(
            self.generation_count,
            int,
        ):
            raise FoundationError(
                "generation_count must be an integer"
            )
        if self.generation_count < 1:
            raise FoundationError(
                "generation_count must be at least one"
            )

    def _validate_digests(self) -> None:
        for field_name, value, domain in (
            (
                "review_docket_digest",
                self.review_docket_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "review-docket"
                ),
            ),
            (
                "chain_digest",
                self.chain_digest,
                (
                    "claim-posture-alert-lifecycle-chain"
                ),
            ),
            (
                "head_entry_digest",
                self.head_entry_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "chain-entry"
                ),
            ),
            (
                "current_alert_docket_digest",
                self.current_alert_docket_digest,
                "claim-posture-alert-docket",
            ),
            (
                "checkpoint_currency_snapshot_digest",
                self.checkpoint_currency_snapshot_digest,
                (
                    "claim-posture-alert-lifecycle-"
                    "checkpoint-currency-snapshot"
                ),
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

    def _validate_responses(
        self,
        responses: tuple[
            ClaimPostureAlertLifecycleReviewResponse,
            ...,
        ],
    ) -> None:
        for index, response in enumerate(
            responses
        ):
            if not isinstance(
                response,
                ClaimPostureAlertLifecycleReviewResponse,
            ):
                raise FoundationError(
                    f"responses[{index}] must be a "
                    "ClaimPostureAlertLifecycleReviewResponse"
                )
            if (
                response.responded_at.value
                > self.created_at.value
            ):
                raise FoundationError(
                    "review-response ledger must not predate "
                    "a contained response"
                )
            if (
                response.review_docket_id
                != self.review_docket_id
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same review docket"
                )
            if (
                response.review_docket_digest
                != self.review_docket_digest
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same review-docket digest"
                )
            if response.chain_id != self.chain_id:
                raise FoundationError(
                    "every response must bind "
                    "the same lifecycle chain"
                )
            if response.chain_digest != self.chain_digest:
                raise FoundationError(
                    "every response must bind "
                    "the same lifecycle-chain digest"
                )
            if (
                response.generation_count
                != self.generation_count
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same chain generation"
                )
            if response.head_entry_id != self.head_entry_id:
                raise FoundationError(
                    "every response must bind "
                    "the same chain head"
                )
            if (
                response.head_entry_digest
                != self.head_entry_digest
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same chain-head digest"
                )
            if (
                response.current_alert_docket_digest
                != self.current_alert_docket_digest
            ):
                raise FoundationError(
                    "every response must bind "
                    "the same current alert docket"
                )
            if (
                response
                .checkpoint_currency_snapshot_digest
                != self.checkpoint_currency_snapshot_digest
            ):
                raise FoundationError(
                    "every response must bind the same "
                    "checkpoint-currency snapshot"
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
                "review-response ledger must contain "
                "unique response IDs"
            )

    @staticmethod
    def _validate_sequence(
        responses: tuple[
            ClaimPostureAlertLifecycleReviewResponse,
            ...,
        ],
    ) -> None:
        previous: (
            ClaimPostureAlertLifecycleReviewResponse | None
        ) = None

        for response in responses:
            if previous is not None:
                if (
                    previous.responded_at.value
                    >= response.responded_at.value
                ):
                    raise FoundationError(
                        "lifecycle-review responses must use "
                        "strictly increasing response times"
                    )
                if (
                    response.action.progression_rank
                    < previous.action.progression_rank
                ):
                    raise FoundationError(
                        "lifecycle-review response sequence "
                        "must not regress"
                    )

            previous = response

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        review_docket: (
            ClaimPostureAlertLifecycleReviewDocket
        ),
        actor_registry: ActorRegistry,
        responses: Iterable[
            ClaimPostureAlertLifecycleReviewResponse
        ] = (),
    ) -> ClaimPostureAlertLifecycleReviewResponseLedger:
        """Create an action ledger for one review docket."""

        producer = actor_registry.require_actor(
            producer_id
        )
        producer_owner_id = (
            _validate_response_ledger_producer(
                producer
            )
        )
        actor_registry_digest = actor_registry.digest()

        if (
            review_docket.actor_registry_digest
            != actor_registry_digest
        ):
            raise FoundationError(
                "lifecycle-review docket is not bound to "
                "the supplied actor registry"
            )
        if (
            created_at.value
            < review_docket.generated_at.value
        ):
            raise FoundationError(
                "review-response ledger must not predate "
                "the review docket"
            )

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace=(
                    "claim-posture-alert-lifecycle-"
                    "review-response-ledger"
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
            review_docket_id=review_docket.docket_id,
            chain_id=review_docket.chain_id,
            generation_count=review_docket.generation_count,
            head_entry_id=review_docket.head_entry_id,
            responses=tuple(
                responses
            ),
            review_docket_digest=review_docket.digest(),
            chain_digest=review_docket.chain_digest,
            head_entry_digest=review_docket.head_entry_digest,
            current_alert_docket_digest=(
                review_docket.current_alert_docket_digest
            ),
            checkpoint_currency_snapshot_digest=(
                review_docket
                .checkpoint_currency_snapshot_digest
            ),
            claim_catalog_digest=(
                review_docket.claim_catalog_digest
            ),
            actor_registry_digest=actor_registry_digest,
        )

    @property
    def response_count(self) -> int:
        """Return the number of human responses."""

        return len(
            self.responses
        )

    @property
    def latest_response(
        self,
    ) -> ClaimPostureAlertLifecycleReviewResponse | None:
        """Return the latest human response."""

        return self.responses[-1] if self.responses else None

    @property
    def current_assignee_id(
        self,
    ) -> ScopedIdentifier | None:
        """Return the latest assigned human."""

        latest = self.latest_response

        return (
            latest.assigned_to_id
            if latest is not None
            else None
        )

    @property
    def current_action_due_at(
        self,
    ) -> UtcTimestamp | None:
        """Return the latest action due time."""

        latest = self.latest_response

        return (
            latest.action_due_at
            if latest is not None
            else None
        )

    @property
    def response_recorded(self) -> bool:
        """Return whether any response was recorded."""

        return bool(
            self.responses
        )

    @property
    def escalation_recorded(self) -> bool:
        """Return whether the latest response is escalation."""

        latest = self.latest_response

        return (
            latest is not None
            and latest.escalates_review
        )

    @property
    def corrective_action_opened(self) -> bool:
        """Return whether corrective action is currently opened."""

        latest = self.latest_response

        return (
            latest is not None
            and latest.opens_corrective_action
        )

    @property
    def resolves_review_obligation(self) -> bool:
        """Return false because responses cannot resolve review."""

        return False

    @property
    def accepts_continuity(self) -> bool:
        """Return false because responses cannot accept continuity."""

        return False

    @property
    def approves_underlying_claims(self) -> bool:
        """Return false because review actions are not claim approval."""

        return False

    @property
    def clears_alerts(self) -> bool:
        """Return false because responses cannot clear alerts."""

        return False

    @property
    def changes_claim_state(self) -> bool:
        """Return false because responses do not mutate posture."""

        return False

    @property
    def grants_authority(self) -> bool:
        """Return false because responses grant no authority."""

        return False

    @property
    def claims_certification(self) -> bool:
        """Return false because MissionProof does not self-certify."""

        return False

    def append(
        self,
        response: ClaimPostureAlertLifecycleReviewResponse,
        *,
        created_at: UtcTimestamp,
    ) -> ClaimPostureAlertLifecycleReviewResponseLedger:
        """Return the next immutable response-ledger snapshot."""

        if created_at.value < self.created_at.value:
            raise FoundationError(
                "next review-response ledger snapshot "
                "must not predate the current ledger"
            )

        return ClaimPostureAlertLifecycleReviewResponseLedger(
            ledger_id=self.ledger_id,
            created_at=created_at,
            producer_id=self.producer_id,
            producer_kind=self.producer_kind,
            producer_accountability_owner_id=(
                self.producer_accountability_owner_id
            ),
            review_docket_id=self.review_docket_id,
            chain_id=self.chain_id,
            generation_count=self.generation_count,
            head_entry_id=self.head_entry_id,
            responses=(
                *self.responses,
                response,
            ),
            review_docket_digest=self.review_docket_digest,
            chain_digest=self.chain_digest,
            head_entry_digest=self.head_entry_digest,
            current_alert_docket_digest=(
                self.current_alert_docket_digest
            ),
            checkpoint_currency_snapshot_digest=(
                self.checkpoint_currency_snapshot_digest
            ),
            claim_catalog_digest=self.claim_catalog_digest,
            actor_registry_digest=self.actor_registry_digest,
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic review-response ledger."""

        response_payloads: JsonArray = [
            response.to_payload()
            for response in self.responses
        ]

        return {
            "accepts_continuity": self.accepts_continuity,
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "approves_underlying_claims": (
                self.approves_underlying_claims
            ),
            "chain_digest": self.chain_digest.to_payload(),
            "chain_id": str(self.chain_id),
            "changes_claim_state": self.changes_claim_state,
            "checkpoint_currency_snapshot_digest": (
                self.checkpoint_currency_snapshot_digest
                .to_payload()
            ),
            "claim_catalog_digest": (
                self.claim_catalog_digest.to_payload()
            ),
            "claims_certification": self.claims_certification,
            "clears_alerts": self.clears_alerts,
            "corrective_action_opened": (
                self.corrective_action_opened
            ),
            "created_at": self.created_at.isoformat(),
            "current_action_due_at": (
                self.current_action_due_at.isoformat()
                if self.current_action_due_at is not None
                else None
            ),
            "current_alert_docket_digest": (
                self.current_alert_docket_digest.to_payload()
            ),
            "current_assignee_id": (
                str(self.current_assignee_id)
                if self.current_assignee_id is not None
                else None
            ),
            "escalation_recorded": self.escalation_recorded,
            "generation_count": self.generation_count,
            "grants_authority": self.grants_authority,
            "head_entry_digest": (
                self.head_entry_digest.to_payload()
            ),
            "head_entry_id": str(self.head_entry_id),
            "ledger_id": str(self.ledger_id),
            "producer_accountability_owner_id": str(
                self.producer_accountability_owner_id
            ),
            "producer_id": str(self.producer_id),
            "producer_kind": self.producer_kind.value,
            "resolves_review_obligation": (
                self.resolves_review_obligation
            ),
            "response_count": self.response_count,
            "response_recorded": self.response_recorded,
            "responses": response_payloads,
            "review_docket_digest": (
                self.review_docket_digest.to_payload()
            ),
            "review_docket_id": str(self.review_docket_id),
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical response ledger."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete response ledger."""

        return self.to_document().digest(
            domain=(
                "claim-posture-alert-lifecycle-"
                "review-response-ledger"
            )
        )
