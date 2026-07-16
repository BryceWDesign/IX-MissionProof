"""Revocation-aware per-action authorization preflight for IX-MissionProof."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.authority.capabilities import (
    CapabilityCatalog,
    CapabilityDefinition,
)
from ix_missionproof.authority.grants import (
    AuthorityGrant,
    AuthorityGrantLedger,
)
from ix_missionproof.authority.state import (
    AuthorityGrantState,
    AuthorityStateSnapshot,
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


class ActionAuthorizationOutcome(StrEnum):
    """Possible results of deterministic action preflight."""

    ALLOW = "allow"
    REQUIRE_HUMAN_REVIEW = "require-human-review"
    BLOCK = "block"

    @property
    def permits_execution(self) -> bool:
        """Return whether execution may proceed without another decision."""

        return self is ActionAuthorizationOutcome.ALLOW


class ActionAuthorizationReason(StrEnum):
    """Stable reason codes emitted by action authorization preflight."""

    ACTIVE_GRANT = "active-grant"
    SEPARATE_HUMAN_AUTHORIZATION_REQUIRED = (
        "separate-human-authorization-required"
    )
    REQUESTER_NOT_REGISTERED = "requester-not-registered"
    REQUESTER_NOT_ACTIVE = "requester-not-active"
    CAPABILITY_NOT_FOUND = "capability-not-found"
    CAPABILITY_DISABLED = "capability-disabled"
    ACTOR_KIND_NOT_PERMITTED = "actor-kind-not-permitted"
    GRANT_NOT_FOUND = "grant-not-found"
    GRANT_NOT_ACTIVE = "grant-not-active"
    GRANT_REQUESTER_MISMATCH = "grant-requester-mismatch"
    GRANT_CAPABILITY_MISMATCH = "grant-capability-mismatch"
    TARGET_TYPE_MISMATCH = "target-type-mismatch"
    TARGET_NOT_COVERED = "target-not-covered"
    REQUIRED_EVIDENCE_MISSING = "required-evidence-missing"
    ACTOR_REGISTRY_BINDING_MISMATCH = "actor-registry-binding-mismatch"
    CAPABILITY_CATALOG_BINDING_MISMATCH = (
        "capability-catalog-binding-mismatch"
    )
    CAPABILITY_BINDING_MISMATCH = "capability-binding-mismatch"
    AUTHORITY_STATE_BINDING_MISMATCH = "authority-state-binding-mismatch"


_BLOCKING_REASONS = frozenset(
    reason
    for reason in ActionAuthorizationReason
    if reason
    not in {
        ActionAuthorizationReason.ACTIVE_GRANT,
        ActionAuthorizationReason.SEPARATE_HUMAN_AUTHORIZATION_REQUIRED,
    }
)


def _normalize_record_ids(
    values: Iterable[ScopedIdentifier],
) -> tuple[ScopedIdentifier, ...]:
    normalized: set[ScopedIdentifier] = set()

    for index, value in enumerate(values):
        if not isinstance(value, ScopedIdentifier):
            raise FoundationError(
                f"evidence_record_ids[{index}] must be a ScopedIdentifier"
            )
        if value.namespace != CanonicalKey("record"):
            raise FoundationError(
                "evidence_record_ids must identify record values"
            )
        normalized.add(value)

    return tuple(sorted(normalized, key=str))


@dataclass(frozen=True, slots=True)
class ActionAuthorizationRequest:
    """One exact proposed action submitted for authority preflight."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-authorization-request-v1"
    )

    request_id: ScopedIdentifier
    requested_at: UtcTimestamp
    requester_id: ScopedIdentifier
    grant_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    target_id: ScopedIdentifier
    action: CanonicalJsonDocument
    action_digest: ContentDigest
    evidence_record_ids: tuple[ScopedIdentifier, ...]
    justification: str
    metadata: CanonicalJsonDocument

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, ScopedIdentifier):
            raise FoundationError("request_id must be a ScopedIdentifier")
        if self.request_id.namespace != CanonicalKey(
            "action-authorization-request"
        ):
            raise FoundationError(
                "request_id namespace must be action-authorization-request"
            )
        if not isinstance(self.requested_at, UtcTimestamp):
            raise FoundationError("requested_at must be a UtcTimestamp")
        if not isinstance(self.requester_id, ScopedIdentifier):
            raise FoundationError("requester_id must be a ScopedIdentifier")
        if not isinstance(self.grant_id, ScopedIdentifier):
            raise FoundationError("grant_id must be a ScopedIdentifier")
        if self.grant_id.namespace != CanonicalKey("authority-grant"):
            raise FoundationError(
                "grant_id namespace must be authority-grant"
            )
        if not isinstance(self.capability_id, ScopedIdentifier):
            raise FoundationError(
                "capability_id must be a ScopedIdentifier"
            )
        if self.capability_id.namespace != CanonicalKey("capability"):
            raise FoundationError(
                "capability_id namespace must be capability"
            )
        if not isinstance(self.target_id, ScopedIdentifier):
            raise FoundationError("target_id must be a ScopedIdentifier")
        if not isinstance(self.action, CanonicalJsonDocument):
            raise FoundationError(
                "action must be a CanonicalJsonDocument"
            )

        self.action.require_object()

        if not isinstance(self.action_digest, ContentDigest):
            raise FoundationError(
                "action_digest must be a ContentDigest"
            )
        if self.action_digest.domain != CanonicalKey("proposed-action"):
            raise FoundationError(
                "action_digest domain must be proposed-action"
            )
        if not self.action_digest.verifies(self.action.to_value()):
            raise FoundationError(
                "action_digest does not match the proposed action"
            )

        object.__setattr__(
            self,
            "evidence_record_ids",
            _normalize_record_ids(self.evidence_record_ids),
        )
        object.__setattr__(
            self,
            "justification",
            require_text(
                self.justification,
                field_name="justification",
            ),
        )

        if not isinstance(self.metadata, CanonicalJsonDocument):
            raise FoundationError(
                "metadata must be a CanonicalJsonDocument"
            )

        self.metadata.require_object()

    @classmethod
    def create(
        cls,
        *,
        key: str,
        requested_at: UtcTimestamp,
        requester_id: ScopedIdentifier,
        grant_id: ScopedIdentifier,
        capability_id: ScopedIdentifier,
        target_id: ScopedIdentifier,
        action: JsonObject,
        evidence_record_ids: Iterable[ScopedIdentifier],
        justification: str,
        metadata: JsonObject | None = None,
    ) -> ActionAuthorizationRequest:
        """Capture an exact proposed action as an immutable request."""

        action_document = CanonicalJsonDocument.from_value(action)

        return cls(
            request_id=ScopedIdentifier.create(
                namespace="action-authorization-request",
                key=key,
                namespace_field="request namespace",
                key_field="request key",
            ),
            requested_at=requested_at,
            requester_id=requester_id,
            grant_id=grant_id,
            capability_id=capability_id,
            target_id=target_id,
            action=action_document,
            action_digest=action_document.digest(
                domain="proposed-action"
            ),
            evidence_record_ids=tuple(evidence_record_ids),
            justification=justification,
            metadata=CanonicalJsonDocument.from_value(metadata or {}),
        )

    def to_payload(self) -> JsonObject:
        """Return the deterministic JSON representation of this request."""

        evidence_payload: JsonArray = [
            str(record_id)
            for record_id in self.evidence_record_ids
        ]

        return {
            "action": self.action.to_value(),
            "action_digest": self.action_digest.to_payload(),
            "capability_id": str(self.capability_id),
            "evidence_record_ids": evidence_payload,
            "grant_id": str(self.grant_id),
            "justification": self.justification,
            "metadata": self.metadata.to_value(),
            "request_id": str(self.request_id),
            "requested_at": self.requested_at.isoformat(),
            "requester_id": str(self.requester_id),
            "schema": self.SCHEMA.value,
            "target_id": str(self.target_id),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical request document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete request."""

        return self.to_document().digest(
            domain="action-authorization-request"
        )


@dataclass(frozen=True, slots=True)
class ActionAuthorizationEvaluation:
    """Deterministic preflight result for one action request."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-authorization-evaluation-v1"
    )

    evaluation_id: ScopedIdentifier
    evaluated_at: UtcTimestamp
    request_id: ScopedIdentifier
    requester_id: ScopedIdentifier
    grant_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    target_id: ScopedIdentifier
    outcome: ActionAuthorizationOutcome
    reasons: tuple[ActionAuthorizationReason, ...]
    request_digest: ContentDigest
    authority_state_digest: ContentDigest
    actor_registry_digest: ContentDigest
    capability_catalog_digest: ContentDigest
    grant_digest: ContentDigest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_id, ScopedIdentifier):
            raise FoundationError(
                "evaluation_id must be a ScopedIdentifier"
            )
        if self.evaluation_id.namespace != CanonicalKey(
            "action-authorization-evaluation"
        ):
            raise FoundationError(
                "evaluation_id namespace must be "
                "action-authorization-evaluation"
            )
        if not isinstance(self.evaluated_at, UtcTimestamp):
            raise FoundationError(
                "evaluated_at must be a UtcTimestamp"
            )

        for field_name, identifier in (
            ("request_id", self.request_id),
            ("requester_id", self.requester_id),
            ("grant_id", self.grant_id),
            ("capability_id", self.capability_id),
            ("target_id", self.target_id),
        ):
            if not isinstance(identifier, ScopedIdentifier):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )

        if not isinstance(
            self.outcome,
            ActionAuthorizationOutcome,
        ):
            raise FoundationError(
                "outcome must be an ActionAuthorizationOutcome"
            )

        declared_reasons = tuple(self.reasons)
        if not declared_reasons:
            raise FoundationError(
                "authorization reasons must not be empty"
            )

        for reason in declared_reasons:
            if not isinstance(reason, ActionAuthorizationReason):
                raise FoundationError(
                    "reasons must contain "
                    "ActionAuthorizationReason values"
                )

        reasons = tuple(
            sorted(
                set(declared_reasons),
                key=lambda reason: reason.value,
            )
        )
        object.__setattr__(self, "reasons", reasons)
        self._validate_outcome_reasons()

        expected_digests = (
            (
                "request_digest",
                self.request_digest,
                CanonicalKey("action-authorization-request"),
            ),
            (
                "authority_state_digest",
                self.authority_state_digest,
                CanonicalKey("authority-state-snapshot"),
            ),
            (
                "actor_registry_digest",
                self.actor_registry_digest,
                CanonicalKey("actor-registry"),
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

        if self.grant_digest is not None:
            if not isinstance(self.grant_digest, ContentDigest):
                raise FoundationError(
                    "grant_digest must be a ContentDigest or None"
                )
            if self.grant_digest.domain != CanonicalKey(
                "authority-grant"
            ):
                raise FoundationError(
                    "grant_digest domain must be authority-grant"
                )

    def _validate_outcome_reasons(self) -> None:
        reason_set = set(self.reasons)

        if self.outcome is ActionAuthorizationOutcome.ALLOW:
            if reason_set != {
                ActionAuthorizationReason.ACTIVE_GRANT
            }:
                raise FoundationError(
                    "allow evaluations require only the "
                    "active-grant reason"
                )
            return

        if (
            self.outcome
            is ActionAuthorizationOutcome.REQUIRE_HUMAN_REVIEW
        ):
            expected = {
                ActionAuthorizationReason.ACTIVE_GRANT,
                ActionAuthorizationReason
                .SEPARATE_HUMAN_AUTHORIZATION_REQUIRED,
            }
            if reason_set != expected:
                raise FoundationError(
                    "human-review evaluations require an active "
                    "grant and the separate-human-authorization "
                    "reason"
                )
            return

        if not reason_set.intersection(_BLOCKING_REASONS):
            raise FoundationError(
                "block evaluations require at least one "
                "blocking reason"
            )

    @property
    def permits_execution(self) -> bool:
        """Return whether this result permits immediate execution."""

        return self.outcome.permits_execution

    @property
    def requires_human_review(self) -> bool:
        """Return whether a separate human decision is still required."""

        return (
            self.outcome
            is ActionAuthorizationOutcome.REQUIRE_HUMAN_REVIEW
        )

    @property
    def blocked(self) -> bool:
        """Return whether this preflight blocks the requested action."""

        return self.outcome is ActionAuthorizationOutcome.BLOCK

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this evaluation."""

        reason_payload: JsonArray = [
            reason.value
            for reason in self.reasons
        ]

        return {
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "authority_state_digest": (
                self.authority_state_digest.to_payload()
            ),
            "blocked": self.blocked,
            "capability_catalog_digest": (
                self.capability_catalog_digest.to_payload()
            ),
            "capability_id": str(self.capability_id),
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_id": str(self.evaluation_id),
            "grant_digest": (
                self.grant_digest.to_payload()
                if self.grant_digest is not None
                else None
            ),
            "grant_id": str(self.grant_id),
            "outcome": self.outcome.value,
            "permits_execution": self.permits_execution,
            "reasons": reason_payload,
            "request_digest": self.request_digest.to_payload(),
            "request_id": str(self.request_id),
            "requester_id": str(self.requester_id),
            "requires_human_review": self.requires_human_review,
            "schema": self.SCHEMA.value,
            "target_id": str(self.target_id),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical evaluation document."""

        return CanonicalJsonDocument.from_value(self.to_payload())

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete evaluation."""

        return self.to_document().digest(
            domain="action-authorization-evaluation"
        )


@dataclass(frozen=True, slots=True)
class ActionAuthorizationEvaluator:
    """Evaluate requests against revocation-aware authority state."""

    actor_registry: ActorRegistry
    capability_catalog: CapabilityCatalog
    grant_ledger: AuthorityGrantLedger
    authority_state: AuthorityStateSnapshot

    def __post_init__(self) -> None:
        if (
            self.authority_state.grant_ledger_digest
            != self.grant_ledger.digest()
        ):
            raise FoundationError(
                "authority state is not bound to the supplied "
                "grant ledger"
            )

    def evaluate(
        self,
        request: ActionAuthorizationRequest,
        *,
        key: str,
    ) -> ActionAuthorizationEvaluation:
        """Evaluate a request without granting separate human authority."""

        if (
            request.requested_at.value
            > self.authority_state.evaluated_at.value
        ):
            raise FoundationError(
                "authority state must not predate the action request"
            )

        actor = self.actor_registry.actor_for(
            request.requester_id
        )
        capability = self.capability_catalog.capability_for(
            request.capability_id
        )
        grant = self.grant_ledger.grant_for(request.grant_id)
        state = self.authority_state.state_for(request.grant_id)

        reasons = self._collect_reasons(
            request=request,
            actor=actor,
            capability=capability,
            grant=grant,
            state=state,
        )
        outcome = self._outcome_for(reasons)

        return ActionAuthorizationEvaluation(
            evaluation_id=ScopedIdentifier.create(
                namespace="action-authorization-evaluation",
                key=key,
                namespace_field="evaluation namespace",
                key_field="evaluation key",
            ),
            evaluated_at=self.authority_state.evaluated_at,
            request_id=request.request_id,
            requester_id=request.requester_id,
            grant_id=request.grant_id,
            capability_id=request.capability_id,
            target_id=request.target_id,
            outcome=outcome,
            reasons=tuple(reasons),
            request_digest=request.digest(),
            authority_state_digest=self.authority_state.digest(),
            actor_registry_digest=self.actor_registry.digest(),
            capability_catalog_digest=(
                self.capability_catalog.digest()
            ),
            grant_digest=(
                grant.digest()
                if grant is not None
                else None
            ),
        )

    def _collect_reasons(
        self,
        *,
        request: ActionAuthorizationRequest,
        actor: ActorIdentity | None,
        capability: CapabilityDefinition | None,
        grant: AuthorityGrant | None,
        state: AuthorityGrantState | None,
    ) -> set[ActionAuthorizationReason]:
        reasons: set[ActionAuthorizationReason] = set()

        self._check_actor(
            actor,
            capability,
            reasons,
        )
        self._check_capability(
            capability,
            request,
            reasons,
        )
        self._check_grant(
            grant,
            state,
            request,
            capability,
            reasons,
        )

        if reasons.intersection(_BLOCKING_REASONS):
            return reasons

        reasons.add(ActionAuthorizationReason.ACTIVE_GRANT)

        if (
            grant is not None
            and grant.requires_runtime_authorization
        ):
            reasons.add(
                ActionAuthorizationReason
                .SEPARATE_HUMAN_AUTHORIZATION_REQUIRED
            )

        return reasons

    @staticmethod
    def _check_actor(
        actor: ActorIdentity | None,
        capability: CapabilityDefinition | None,
        reasons: set[ActionAuthorizationReason],
    ) -> None:
        if actor is None:
            reasons.add(
                ActionAuthorizationReason.REQUESTER_NOT_REGISTERED
            )
            return

        if not actor.is_active:
            reasons.add(
                ActionAuthorizationReason.REQUESTER_NOT_ACTIVE
            )

        if (
            capability is not None
            and actor.kind
            not in capability.permitted_actor_kinds
        ):
            reasons.add(
                ActionAuthorizationReason.ACTOR_KIND_NOT_PERMITTED
            )

    @staticmethod
    def _check_capability(
        capability: CapabilityDefinition | None,
        request: ActionAuthorizationRequest,
        reasons: set[ActionAuthorizationReason],
    ) -> None:
        if capability is None:
            reasons.add(
                ActionAuthorizationReason.CAPABILITY_NOT_FOUND
            )
            return

        if not capability.enabled:
            reasons.add(
                ActionAuthorizationReason.CAPABILITY_DISABLED
            )

        if request.target_id.namespace != capability.target_type:
            reasons.add(
                ActionAuthorizationReason.TARGET_TYPE_MISMATCH
            )

        if (
            capability.requires_evidence
            and not request.evidence_record_ids
        ):
            reasons.add(
                ActionAuthorizationReason
                .REQUIRED_EVIDENCE_MISSING
            )

    def _check_grant(
        self,
        grant: AuthorityGrant | None,
        state: AuthorityGrantState | None,
        request: ActionAuthorizationRequest,
        capability: CapabilityDefinition | None,
        reasons: set[ActionAuthorizationReason],
    ) -> None:
        if grant is None:
            reasons.add(
                ActionAuthorizationReason.GRANT_NOT_FOUND
            )
            return

        if state is None or not state.permits_use:
            reasons.add(
                ActionAuthorizationReason.GRANT_NOT_ACTIVE
            )

        if grant.grantee_id != request.requester_id:
            reasons.add(
                ActionAuthorizationReason
                .GRANT_REQUESTER_MISMATCH
            )

        if grant.capability_id != request.capability_id:
            reasons.add(
                ActionAuthorizationReason
                .GRANT_CAPABILITY_MISMATCH
            )

        if not grant.covers_target(request.target_id):
            reasons.add(
                ActionAuthorizationReason.TARGET_NOT_COVERED
            )

        if (
            grant.actor_registry_digest
            != self.actor_registry.digest()
        ):
            reasons.add(
                ActionAuthorizationReason
                .ACTOR_REGISTRY_BINDING_MISMATCH
            )

        if (
            grant.capability_catalog_digest
            != self.capability_catalog.digest()
        ):
            reasons.add(
                ActionAuthorizationReason
                .CAPABILITY_CATALOG_BINDING_MISMATCH
            )

        if (
            capability is not None
            and grant.capability_digest != capability.digest()
        ):
            reasons.add(
                ActionAuthorizationReason
                .CAPABILITY_BINDING_MISMATCH
            )

        if (
            state is not None
            and state.grant_digest != grant.digest()
        ):
            reasons.add(
                ActionAuthorizationReason
                .AUTHORITY_STATE_BINDING_MISMATCH
            )

    @staticmethod
    def _outcome_for(
        reasons: set[ActionAuthorizationReason],
    ) -> ActionAuthorizationOutcome:
        if reasons.intersection(_BLOCKING_REASONS):
            return ActionAuthorizationOutcome.BLOCK

        if (
            ActionAuthorizationReason
            .SEPARATE_HUMAN_AUTHORIZATION_REQUIRED
            in reasons
        ):
            return (
                ActionAuthorizationOutcome
                .REQUIRE_HUMAN_REVIEW
            )

        return ActionAuthorizationOutcome.ALLOW
