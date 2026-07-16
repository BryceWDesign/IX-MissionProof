"""Action-bound human authorization decisions for IX-MissionProof."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.authority.grants import AuthorityGrant
from ix_missionproof.authority.requests import (
    ActionAuthorizationEvaluation,
    ActionAuthorizationOutcome,
    ActionAuthorizationRequest,
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


class ActionAuthorizationDecisionStatus(StrEnum):
    """Human dispositions for an action requiring separate authorization."""

    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"

    @property
    def is_terminal(self) -> bool:
        """Return whether no later decision may replace this disposition."""

        return self in {
            ActionAuthorizationDecisionStatus.APPROVED,
            ActionAuthorizationDecisionStatus.REJECTED,
        }


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


@dataclass(frozen=True, slots=True)
class ActionAuthorizationDecision:
    """A human decision bound to one exact request, action, and preflight."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-authorization-decision-v1"
    )

    decision_id: ScopedIdentifier
    decided_at: UtcTimestamp
    decided_by_id: ScopedIdentifier
    request_id: ScopedIdentifier
    evaluation_id: ScopedIdentifier
    grant_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    target_id: ScopedIdentifier
    action_digest: ContentDigest
    status: ActionAuthorizationDecisionStatus
    rationale: str
    supporting_record_ids: tuple[ScopedIdentifier, ...]
    request_digest: ContentDigest
    evaluation_digest: ContentDigest
    grant_digest: ContentDigest
    actor_registry_digest: ContentDigest
    authority_state_digest: ContentDigest
    capability_catalog_digest: ContentDigest

    def __post_init__(self) -> None:
        if not isinstance(self.decision_id, ScopedIdentifier):
            raise FoundationError("decision_id must be a ScopedIdentifier")
        if self.decision_id.namespace != CanonicalKey(
            "action-authorization-decision"
        ):
            raise FoundationError(
                "decision_id namespace must be action-authorization-decision"
            )
        if not isinstance(self.decided_at, UtcTimestamp):
            raise FoundationError("decided_at must be a UtcTimestamp")
        if not isinstance(self.decided_by_id, ScopedIdentifier):
            raise FoundationError("decided_by_id must be a ScopedIdentifier")
        if self.decided_by_id.namespace != CanonicalKey("human"):
            raise FoundationError("decided_by_id must identify a human actor")

        for field_name, identifier, expected_namespace in (
            (
                "request_id",
                self.request_id,
                CanonicalKey("action-authorization-request"),
            ),
            (
                "evaluation_id",
                self.evaluation_id,
                CanonicalKey("action-authorization-evaluation"),
            ),
            ("grant_id", self.grant_id, CanonicalKey("authority-grant")),
            ("capability_id", self.capability_id, CanonicalKey("capability")),
        ):
            if not isinstance(identifier, ScopedIdentifier):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )
            if identifier.namespace != expected_namespace:
                raise FoundationError(
                    f"{field_name} namespace must be "
                    f"{expected_namespace.value}"
                )

        if not isinstance(self.target_id, ScopedIdentifier):
            raise FoundationError("target_id must be a ScopedIdentifier")
        if not isinstance(self.status, ActionAuthorizationDecisionStatus):
            raise FoundationError(
                "status must be an ActionAuthorizationDecisionStatus"
            )

        object.__setattr__(
            self,
            "rationale",
            require_text(self.rationale, field_name="rationale"),
        )
        supporting_record_ids = _normalize_record_ids(
            self.supporting_record_ids
        )
        if not supporting_record_ids:
            raise FoundationError(
                "action authorization decisions require at least one "
                "supporting record"
            )
        object.__setattr__(
            self,
            "supporting_record_ids",
            supporting_record_ids,
        )

        expected_digests = (
            (
                "action_digest",
                self.action_digest,
                CanonicalKey("proposed-action"),
            ),
            (
                "request_digest",
                self.request_digest,
                CanonicalKey("action-authorization-request"),
            ),
            (
                "evaluation_digest",
                self.evaluation_digest,
                CanonicalKey("action-authorization-evaluation"),
            ),
            (
                "grant_digest",
                self.grant_digest,
                CanonicalKey("authority-grant"),
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                CanonicalKey("actor-registry"),
            ),
            (
                "authority_state_digest",
                self.authority_state_digest,
                CanonicalKey("authority-state-snapshot"),
            ),
            (
                "capability_catalog_digest",
                self.capability_catalog_digest,
                CanonicalKey("capability-catalog"),
            ),
        )

        for field_name, digest, expected_domain in expected_digests:
            if not isinstance(digest, ContentDigest):
                raise FoundationError(
                    f"{field_name} must be a ContentDigest"
                )
            if digest.domain != expected_domain:
                raise FoundationError(
                    f"{field_name} domain must be "
                    f"{expected_domain.value}"
                )

    @classmethod
    def decide(
        cls,
        *,
        key: str,
        decided_at: UtcTimestamp,
        decided_by_id: ScopedIdentifier,
        status: ActionAuthorizationDecisionStatus,
        rationale: str,
        supporting_record_ids: Iterable[ScopedIdentifier],
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
        grant: AuthorityGrant,
        actor_registry: ActorRegistry,
    ) -> ActionAuthorizationDecision:
        """Record a human decision without creating an execution release."""

        cls._validate_bound_review(
            request=request,
            evaluation=evaluation,
            grant=grant,
            actor_registry=actor_registry,
        )
        reviewer = actor_registry.require_actor(decided_by_id)
        cls._validate_reviewer(
            reviewer=reviewer,
            request=request,
            grant=grant,
        )
        cls._validate_decision_time(
            decided_at=decided_at,
            evaluation=evaluation,
            grant=grant,
        )

        return cls(
            decision_id=ScopedIdentifier.create(
                namespace="action-authorization-decision",
                key=key,
                namespace_field="decision namespace",
                key_field="decision key",
            ),
            decided_at=decided_at,
            decided_by_id=decided_by_id,
            request_id=request.request_id,
            evaluation_id=evaluation.evaluation_id,
            grant_id=grant.grant_id,
            capability_id=request.capability_id,
            target_id=request.target_id,
            action_digest=request.action_digest,
            status=status,
            rationale=rationale,
            supporting_record_ids=tuple(supporting_record_ids),
            request_digest=request.digest(),
            evaluation_digest=evaluation.digest(),
            grant_digest=grant.digest(),
            actor_registry_digest=actor_registry.digest(),
            authority_state_digest=evaluation.authority_state_digest,
            capability_catalog_digest=(
                evaluation.capability_catalog_digest
            ),
        )

    @staticmethod
    def _validate_bound_review(
        *,
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
        grant: AuthorityGrant,
        actor_registry: ActorRegistry,
    ) -> None:
        if evaluation.outcome is not (
            ActionAuthorizationOutcome.REQUIRE_HUMAN_REVIEW
        ):
            raise FoundationError(
                "human action decisions require a preflight outcome of "
                "require-human-review; blocked preflight cannot be overridden"
            )
        if evaluation.request_id != request.request_id:
            raise FoundationError(
                "evaluation does not reference the supplied request"
            )
        if evaluation.request_digest != request.digest():
            raise FoundationError(
                "evaluation request digest does not match the request"
            )
        if evaluation.requester_id != request.requester_id:
            raise FoundationError(
                "evaluation requester does not match the request"
            )
        if evaluation.grant_id != grant.grant_id:
            raise FoundationError(
                "evaluation does not reference the supplied grant"
            )
        if evaluation.grant_digest != grant.digest():
            raise FoundationError(
                "evaluation grant digest does not match the grant"
            )
        if evaluation.capability_id != request.capability_id:
            raise FoundationError(
                "evaluation capability does not match the request"
            )
        if evaluation.target_id != request.target_id:
            raise FoundationError(
                "evaluation target does not match the request"
            )
        if grant.grantee_id != request.requester_id:
            raise FoundationError(
                "grant grantee does not match the requester"
            )
        if grant.capability_id != request.capability_id:
            raise FoundationError(
                "grant capability does not match the request"
            )
        if not grant.covers_target(request.target_id):
            raise FoundationError(
                "grant does not cover the requested target"
            )
        if evaluation.actor_registry_digest != actor_registry.digest():
            raise FoundationError(
                "evaluation is not bound to the supplied actor registry"
            )
        if grant.actor_registry_digest != actor_registry.digest():
            raise FoundationError(
                "grant is not bound to the supplied actor registry"
            )

    @staticmethod
    def _validate_reviewer(
        *,
        reviewer: ActorIdentity,
        request: ActionAuthorizationRequest,
        grant: AuthorityGrant,
    ) -> None:
        if not reviewer.is_eligible_for_human_authority:
            raise FoundationError(
                "action authorization decisions require an active "
                "human actor"
            )
        if reviewer.actor_id == request.requester_id:
            raise FoundationError(
                "an action requester must not authorize its own action"
            )
        if reviewer.actor_id != grant.granted_by_id:
            raise FoundationError(
                "action authorization must be decided by the original "
                "human grantor"
            )

    @staticmethod
    def _validate_decision_time(
        *,
        decided_at: UtcTimestamp,
        evaluation: ActionAuthorizationEvaluation,
        grant: AuthorityGrant,
    ) -> None:
        if decided_at.value < evaluation.evaluated_at.value:
            raise FoundationError(
                "decided_at must not precede preflight evaluation"
            )
        if not grant.is_time_effective(decided_at):
            raise FoundationError(
                "the authority grant must remain time-effective when "
                "the decision is made"
            )

    @property
    def approves_action(self) -> bool:
        """Return whether the human decision approves the proposed action."""

        return self.status is ActionAuthorizationDecisionStatus.APPROVED

    @property
    def rejects_action(self) -> bool:
        """Return whether the human decision rejects the proposed action."""

        return self.status is ActionAuthorizationDecisionStatus.REJECTED

    @property
    def defers_action(self) -> bool:
        """Return whether the human decision leaves the action unresolved."""

        return self.status is ActionAuthorizationDecisionStatus.DEFERRED

    @property
    def releases_execution(self) -> bool:
        """Return false because a later fresh release gate is required."""

        return False

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this human decision."""

        supporting_payload: JsonArray = [
            str(record_id)
            for record_id in self.supporting_record_ids
        ]
        return {
            "action_digest": self.action_digest.to_payload(),
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "approves_action": self.approves_action,
            "authority_state_digest": (
                self.authority_state_digest.to_payload()
            ),
            "capability_catalog_digest": (
                self.capability_catalog_digest.to_payload()
            ),
            "capability_id": str(self.capability_id),
            "decided_at": self.decided_at.isoformat(),
            "decided_by_id": str(self.decided_by_id),
            "decision_id": str(self.decision_id),
            "defers_action": self.defers_action,
            "evaluation_digest": self.evaluation_digest.to_payload(),
            "evaluation_id": str(self.evaluation_id),
            "grant_digest": self.grant_digest.to_payload(),
            "grant_id": str(self.grant_id),
            "rationale": self.rationale,
            "rejects_action": self.rejects_action,
            "releases_execution": self.releases_execution,
            "request_digest": self.request_digest.to_payload(),
            "request_id": str(self.request_id),
            "schema": self.SCHEMA.value,
            "status": self.status.value,
            "supporting_record_ids": supporting_payload,
            "target_id": str(self.target_id),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical decision document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete human decision."""

        return self.to_document().digest(
            domain="action-authorization-decision"
        )


@dataclass(frozen=True, slots=True)
class ActionAuthorizationDecisionLedger:
    """Immutable history of human action-authorization decisions."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-authorization-decision-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    decisions: tuple[ActionAuthorizationDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.ledger_id, ScopedIdentifier):
            raise FoundationError(
                "ledger_id must be a ScopedIdentifier"
            )
        if self.ledger_id.namespace != CanonicalKey(
            "action-authorization-decision-ledger"
        ):
            raise FoundationError(
                "ledger_id namespace must be "
                "action-authorization-decision-ledger"
            )
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )

        decisions = tuple(self.decisions)
        for index, decision in enumerate(decisions):
            if not isinstance(
                decision,
                ActionAuthorizationDecision,
            ):
                raise FoundationError(
                    f"decisions[{index}] must be an "
                    "ActionAuthorizationDecision"
                )
            if decision.decided_at.value > self.created_at.value:
                raise FoundationError(
                    "decision ledger must not predate a contained decision"
                )

        decision_ids = tuple(
            decision.decision_id
            for decision in decisions
        )
        if len(decision_ids) != len(set(decision_ids)):
            raise FoundationError(
                "decision ledger must contain unique decision IDs"
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
        self._validate_decision_sequences(ordered)
        object.__setattr__(
            self,
            "decisions",
            ordered,
        )

    @staticmethod
    def _validate_decision_sequences(
        decisions: tuple[ActionAuthorizationDecision, ...],
    ) -> None:
        latest_by_evaluation: dict[
            ScopedIdentifier,
            ActionAuthorizationDecision,
        ] = {}

        for decision in decisions:
            previous = latest_by_evaluation.get(
                decision.evaluation_id
            )
            if previous is not None:
                if (
                    previous.evaluation_digest
                    != decision.evaluation_digest
                    or previous.request_id != decision.request_id
                    or previous.request_digest
                    != decision.request_digest
                    or previous.grant_id != decision.grant_id
                    or previous.grant_digest
                    != decision.grant_digest
                    or previous.action_digest
                    != decision.action_digest
                ):
                    raise FoundationError(
                        "decision sequence must preserve one bound "
                        "evaluation, request, grant, and action"
                    )
                if previous.decided_at == decision.decided_at:
                    raise FoundationError(
                        "decisions for one evaluation must use strictly "
                        "increasing decision times"
                    )
                if previous.status.is_terminal:
                    raise FoundationError(
                        "terminal action authorization decisions must "
                        "not be replaced"
                    )

            latest_by_evaluation[
                decision.evaluation_id
            ] = decision

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        decisions: Iterable[ActionAuthorizationDecision],
    ) -> ActionAuthorizationDecisionLedger:
        """Create a deterministic action-decision ledger snapshot."""

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace=(
                    "action-authorization-decision-ledger"
                ),
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            decisions=tuple(decisions),
        )

    def decisions_for_evaluation(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> tuple[ActionAuthorizationDecision, ...]:
        """Return the ordered decision history for one evaluation."""

        return tuple(
            decision
            for decision in self.decisions
            if decision.evaluation_id == evaluation_id
        )

    def latest_for_evaluation(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> ActionAuthorizationDecision | None:
        """Return the latest decision for an evaluation, when present."""

        decisions = self.decisions_for_evaluation(
            evaluation_id
        )
        return decisions[-1] if decisions else None

    def require_terminal_decision(
        self,
        evaluation_id: ScopedIdentifier,
    ) -> ActionAuthorizationDecision:
        """Return an approved or rejected decision for an evaluation."""

        decision = self.latest_for_evaluation(
            evaluation_id
        )
        if decision is None:
            raise FoundationError(
                "decision ledger does not contain a decision for "
                f"evaluation: {evaluation_id}"
            )
        if not decision.status.is_terminal:
            raise FoundationError(
                "action authorization decision is "
                f"{decision.status.value}"
            )
        return decision

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this ledger."""

        decision_payloads: JsonArray = [
            decision.to_payload()
            for decision in self.decisions
        ]
        return {
            "created_at": self.created_at.isoformat(),
            "decisions": decision_payloads,
            "ledger_id": str(self.ledger_id),
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
            domain="action-authorization-decision-ledger"
        )
