"""Fresh-state execution release certificates for IX-MissionProof."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from ix_missionproof.authority.capabilities import CapabilityCatalog
from ix_missionproof.authority.decisions import (
    ActionAuthorizationDecision,
    ActionAuthorizationDecisionStatus,
)
from ix_missionproof.authority.grants import (
    AuthorityGrant,
    AuthorityGrantLedger,
)
from ix_missionproof.authority.requests import (
    ActionAuthorizationEvaluation,
    ActionAuthorizationOutcome,
    ActionAuthorizationRequest,
)
from ix_missionproof.authority.state import AuthorityStateSnapshot
from ix_missionproof.foundation import (
    ActorIdentity,
    ActorKind,
    ActorRegistry,
    CanonicalJsonDocument,
    CanonicalKey,
    ContentDigest,
    FoundationError,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
)


class ActionExecutionReleasePath(StrEnum):
    """Paths through which an exact action may reach execution release."""

    AUTOMATIC_PREFLIGHT = "automatic-preflight"
    HUMAN_APPROVAL = "human-approval"


@dataclass(frozen=True, slots=True)
class ActionExecutionRelease:
    """A short-lived release bound to one exact action and fresh authority state."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-execution-release-v1"
    )

    release_id: ScopedIdentifier
    released_at: UtcTimestamp
    valid_until: UtcTimestamp
    released_by_id: ScopedIdentifier
    release_path: ActionExecutionReleasePath
    requester_id: ScopedIdentifier
    request_id: ScopedIdentifier
    evaluation_id: ScopedIdentifier
    decision_id: ScopedIdentifier | None
    grant_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    target_id: ScopedIdentifier
    action_digest: ContentDigest
    request_digest: ContentDigest
    evaluation_digest: ContentDigest
    decision_digest: ContentDigest | None
    grant_digest: ContentDigest
    grant_ledger_digest: ContentDigest
    authority_state_digest: ContentDigest
    actor_registry_digest: ContentDigest
    capability_catalog_digest: ContentDigest

    def __post_init__(self) -> None:
        if not isinstance(self.release_id, ScopedIdentifier):
            raise FoundationError(
                "release_id must be a ScopedIdentifier"
            )
        if self.release_id.namespace != CanonicalKey(
            "action-execution-release"
        ):
            raise FoundationError(
                "release_id namespace must be action-execution-release"
            )
        if not isinstance(self.released_at, UtcTimestamp):
            raise FoundationError(
                "released_at must be a UtcTimestamp"
            )
        if not isinstance(self.valid_until, UtcTimestamp):
            raise FoundationError(
                "valid_until must be a UtcTimestamp"
            )
        if self.valid_until.value <= self.released_at.value:
            raise FoundationError(
                "valid_until must be later than released_at"
            )
        if not isinstance(self.released_by_id, ScopedIdentifier):
            raise FoundationError(
                "released_by_id must be a ScopedIdentifier"
            )
        if not isinstance(
            self.release_path,
            ActionExecutionReleasePath,
        ):
            raise FoundationError(
                "release_path must be an ActionExecutionReleasePath"
            )

        expected_identifiers = (
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
            (
                "grant_id",
                self.grant_id,
                CanonicalKey("authority-grant"),
            ),
            (
                "capability_id",
                self.capability_id,
                CanonicalKey("capability"),
            ),
        )

        for field_name, identifier, expected_namespace in expected_identifiers:
            if not isinstance(identifier, ScopedIdentifier):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )
            if identifier.namespace != expected_namespace:
                raise FoundationError(
                    f"{field_name} namespace must be "
                    f"{expected_namespace.value}"
                )

        if not isinstance(self.requester_id, ScopedIdentifier):
            raise FoundationError(
                "requester_id must be a ScopedIdentifier"
            )
        if not isinstance(self.target_id, ScopedIdentifier):
            raise FoundationError(
                "target_id must be a ScopedIdentifier"
            )

        if self.release_path is ActionExecutionReleasePath.HUMAN_APPROVAL:
            if self.decision_id is None:
                raise FoundationError(
                    "human-approval release requires a decision_id"
                )
            if self.decision_digest is None:
                raise FoundationError(
                    "human-approval release requires a decision_digest"
                )
        elif self.decision_id is not None or self.decision_digest is not None:
            raise FoundationError(
                "automatic-preflight release must not contain human "
                "decision data"
            )

        if self.decision_id is not None:
            if not isinstance(self.decision_id, ScopedIdentifier):
                raise FoundationError(
                    "decision_id must be a ScopedIdentifier or None"
                )
            if self.decision_id.namespace != CanonicalKey(
                "action-authorization-decision"
            ):
                raise FoundationError(
                    "decision_id namespace must be "
                    "action-authorization-decision"
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
                "grant_ledger_digest",
                self.grant_ledger_digest,
                CanonicalKey("authority-grant-ledger"),
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

        if self.decision_digest is not None:
            if not isinstance(self.decision_digest, ContentDigest):
                raise FoundationError(
                    "decision_digest must be a ContentDigest or None"
                )
            if self.decision_digest.domain != CanonicalKey(
                "action-authorization-decision"
            ):
                raise FoundationError(
                    "decision_digest domain must be "
                    "action-authorization-decision"
                )

    @classmethod
    def issue(
        cls,
        *,
        key: str,
        released_at: UtcTimestamp,
        valid_until: UtcTimestamp,
        released_by_id: ScopedIdentifier,
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
        decision: ActionAuthorizationDecision | None,
        grant: AuthorityGrant,
        grant_ledger: AuthorityGrantLedger,
        authority_state: AuthorityStateSnapshot,
        actor_registry: ActorRegistry,
        capability_catalog: CapabilityCatalog,
    ) -> ActionExecutionRelease:
        """Issue a release only after a fresh revocation-aware authority check."""

        issuer = actor_registry.require_actor(released_by_id)
        cls._validate_release_issuer(issuer)

        cls._validate_request_evaluation_binding(
            request=request,
            evaluation=evaluation,
        )
        cls._validate_grant_binding(
            request=request,
            evaluation=evaluation,
            grant=grant,
            grant_ledger=grant_ledger,
            actor_registry=actor_registry,
            capability_catalog=capability_catalog,
        )

        release_path = cls._validate_release_path(
            request=request,
            evaluation=evaluation,
            decision=decision,
            grant=grant,
            actor_registry=actor_registry,
        )

        cls._validate_fresh_authority_state(
            released_at=released_at,
            valid_until=valid_until,
            evaluation=evaluation,
            decision=decision,
            grant=grant,
            grant_ledger=grant_ledger,
            authority_state=authority_state,
        )

        return cls(
            release_id=ScopedIdentifier.create(
                namespace="action-execution-release",
                key=key,
                namespace_field="release namespace",
                key_field="release key",
            ),
            released_at=released_at,
            valid_until=valid_until,
            released_by_id=released_by_id,
            release_path=release_path,
            requester_id=request.requester_id,
            request_id=request.request_id,
            evaluation_id=evaluation.evaluation_id,
            decision_id=(
                decision.decision_id
                if decision is not None
                else None
            ),
            grant_id=grant.grant_id,
            capability_id=request.capability_id,
            target_id=request.target_id,
            action_digest=request.action_digest,
            request_digest=request.digest(),
            evaluation_digest=evaluation.digest(),
            decision_digest=(
                decision.digest()
                if decision is not None
                else None
            ),
            grant_digest=grant.digest(),
            grant_ledger_digest=grant_ledger.digest(),
            authority_state_digest=authority_state.digest(),
            actor_registry_digest=actor_registry.digest(),
            capability_catalog_digest=capability_catalog.digest(),
        )

    @staticmethod
    def _validate_release_issuer(
        issuer: ActorIdentity,
    ) -> None:
        if not issuer.is_active:
            raise FoundationError(
                "execution release requires an active release issuer"
            )
        if issuer.kind not in {
            ActorKind.SERVICE,
            ActorKind.SYSTEM,
        }:
            raise FoundationError(
                "execution release must be issued by a service or system actor"
            )
        if not issuer.has_accountability_owner:
            raise FoundationError(
                "machine release issuer must identify an accountable "
                "human owner"
            )

    @staticmethod
    def _validate_request_evaluation_binding(
        *,
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
    ) -> None:
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
        if evaluation.capability_id != request.capability_id:
            raise FoundationError(
                "evaluation capability does not match the request"
            )
        if evaluation.target_id != request.target_id:
            raise FoundationError(
                "evaluation target does not match the request"
            )

    @staticmethod
    def _validate_grant_binding(
        *,
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
        grant: AuthorityGrant,
        grant_ledger: AuthorityGrantLedger,
        actor_registry: ActorRegistry,
        capability_catalog: CapabilityCatalog,
    ) -> None:
        ledger_grant = grant_ledger.require_grant(grant.grant_id)
        if ledger_grant.digest() != grant.digest():
            raise FoundationError(
                "supplied grant does not match the grant ledger"
            )
        if evaluation.grant_id != grant.grant_id:
            raise FoundationError(
                "evaluation does not reference the supplied grant"
            )
        if evaluation.grant_digest != grant.digest():
            raise FoundationError(
                "evaluation grant digest does not match the grant"
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

        actor_registry_digest = actor_registry.digest()
        capability_catalog_digest = capability_catalog.digest()

        if grant.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "grant is not bound to the supplied actor registry"
            )
        if evaluation.actor_registry_digest != actor_registry_digest:
            raise FoundationError(
                "evaluation is not bound to the supplied actor registry"
            )
        if grant.capability_catalog_digest != capability_catalog_digest:
            raise FoundationError(
                "grant is not bound to the supplied capability catalog"
            )
        if (
            evaluation.capability_catalog_digest
            != capability_catalog_digest
        ):
            raise FoundationError(
                "evaluation is not bound to the supplied capability catalog"
            )

        capability = capability_catalog.require_capability(
            request.capability_id
        )
        if grant.capability_digest != capability.digest():
            raise FoundationError(
                "grant capability digest does not match the catalog"
            )

    @staticmethod
    def _validate_release_path(
        *,
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
        decision: ActionAuthorizationDecision | None,
        grant: AuthorityGrant,
        actor_registry: ActorRegistry,
    ) -> ActionExecutionReleasePath:
        if evaluation.outcome is ActionAuthorizationOutcome.BLOCK:
            raise FoundationError(
                "blocked authorization preflight cannot receive "
                "an execution release"
            )

        if evaluation.outcome is ActionAuthorizationOutcome.ALLOW:
            if decision is not None:
                raise FoundationError(
                    "automatic-preflight release must not include "
                    "a human decision"
                )
            return ActionExecutionReleasePath.AUTOMATIC_PREFLIGHT

        if decision is None:
            raise FoundationError(
                "human-review preflight requires an approved human decision"
            )

        ActionExecutionRelease._validate_decision_binding(
            request=request,
            evaluation=evaluation,
            decision=decision,
            grant=grant,
            actor_registry=actor_registry,
        )
        return ActionExecutionReleasePath.HUMAN_APPROVAL

    @staticmethod
    def _validate_decision_binding(
        *,
        request: ActionAuthorizationRequest,
        evaluation: ActionAuthorizationEvaluation,
        decision: ActionAuthorizationDecision,
        grant: AuthorityGrant,
        actor_registry: ActorRegistry,
    ) -> None:
        if (
            decision.status
            is not ActionAuthorizationDecisionStatus.APPROVED
        ):
            raise FoundationError(
                "execution release requires an approved human decision"
            )
        if decision.request_id != request.request_id:
            raise FoundationError(
                "decision does not reference the supplied request"
            )
        if decision.request_digest != request.digest():
            raise FoundationError(
                "decision request digest does not match the request"
            )
        if decision.evaluation_id != evaluation.evaluation_id:
            raise FoundationError(
                "decision does not reference the supplied evaluation"
            )
        if decision.evaluation_digest != evaluation.digest():
            raise FoundationError(
                "decision evaluation digest does not match the evaluation"
            )
        if decision.grant_id != grant.grant_id:
            raise FoundationError(
                "decision does not reference the supplied grant"
            )
        if decision.grant_digest != grant.digest():
            raise FoundationError(
                "decision grant digest does not match the grant"
            )
        if decision.capability_id != request.capability_id:
            raise FoundationError(
                "decision capability does not match the request"
            )
        if decision.target_id != request.target_id:
            raise FoundationError(
                "decision target does not match the request"
            )
        if decision.action_digest != request.action_digest:
            raise FoundationError(
                "decision action digest does not match the request"
            )
        if decision.actor_registry_digest != actor_registry.digest():
            raise FoundationError(
                "decision is not bound to the supplied actor registry"
            )

    @staticmethod
    def _validate_fresh_authority_state(
        *,
        released_at: UtcTimestamp,
        valid_until: UtcTimestamp,
        evaluation: ActionAuthorizationEvaluation,
        decision: ActionAuthorizationDecision | None,
        grant: AuthorityGrant,
        grant_ledger: AuthorityGrantLedger,
        authority_state: AuthorityStateSnapshot,
    ) -> None:
        grant_ledger_digest = grant_ledger.digest()
        if authority_state.grant_ledger_digest != grant_ledger_digest:
            raise FoundationError(
                "authority state is not bound to the supplied grant ledger"
            )

        latest_prior_event = evaluation.evaluated_at
        if (
            decision is not None
            and decision.decided_at.value > latest_prior_event.value
        ):
            latest_prior_event = decision.decided_at

        if authority_state.evaluated_at.value < latest_prior_event.value:
            raise FoundationError(
                "execution release requires authority state evaluated "
                "after the latest evaluation or human decision"
            )
        if released_at.value < authority_state.evaluated_at.value:
            raise FoundationError(
                "released_at must not precede the fresh authority state"
            )
        if valid_until.value <= released_at.value:
            raise FoundationError(
                "valid_until must be later than released_at"
            )

        state = authority_state.require_state(grant.grant_id)
        if not state.permits_use:
            raise FoundationError(
                f"authority grant is {state.status.value} in the "
                "fresh authority state"
            )
        if state.grant_digest != grant.digest():
            raise FoundationError(
                "fresh authority-state grant digest does not match the grant"
            )
        if not grant.is_time_effective(released_at):
            raise FoundationError(
                "authority grant must be time-effective when release is issued"
            )

        if (
            grant.expires_at is not None
            and valid_until.value > grant.expires_at.value
        ):
            raise FoundationError(
                "execution release must not outlive the authority grant"
            )

    @property
    def required_human_approval(self) -> bool:
        """Return whether this release depends on a human approval."""

        return self.release_path is ActionExecutionReleasePath.HUMAN_APPROVAL

    @property
    def single_use(self) -> bool:
        """Return the fixed one-action release policy."""

        return True

    def is_time_effective(
        self,
        at: UtcTimestamp,
    ) -> bool:
        """Return whether the release is inside its short-lived time window."""

        if not isinstance(at, UtcTimestamp):
            raise FoundationError(
                "at must be a UtcTimestamp"
            )
        return (
            self.released_at.value
            <= at.value
            < self.valid_until.value
        )

    def matches_request(
        self,
        request: ActionAuthorizationRequest,
    ) -> bool:
        """Return whether the release covers the exact immutable request."""

        return (
            self.request_id == request.request_id
            and self.requester_id == request.requester_id
            and self.grant_id == request.grant_id
            and self.capability_id == request.capability_id
            and self.target_id == request.target_id
            and self.action_digest == request.action_digest
            and self.request_digest == request.digest()
        )

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this release."""

        return {
            "action_digest": self.action_digest.to_payload(),
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "authority_state_digest": (
                self.authority_state_digest.to_payload()
            ),
            "capability_catalog_digest": (
                self.capability_catalog_digest.to_payload()
            ),
            "capability_id": str(self.capability_id),
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
            "evaluation_digest": self.evaluation_digest.to_payload(),
            "evaluation_id": str(self.evaluation_id),
            "grant_digest": self.grant_digest.to_payload(),
            "grant_id": str(self.grant_id),
            "grant_ledger_digest": (
                self.grant_ledger_digest.to_payload()
            ),
            "release_id": str(self.release_id),
            "release_path": self.release_path.value,
            "released_at": self.released_at.isoformat(),
            "released_by_id": str(self.released_by_id),
            "request_digest": self.request_digest.to_payload(),
            "request_id": str(self.request_id),
            "requester_id": str(self.requester_id),
            "required_human_approval": self.required_human_approval,
            "schema": self.SCHEMA.value,
            "single_use": self.single_use,
            "target_id": str(self.target_id),
            "valid_until": self.valid_until.isoformat(),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical execution-release document."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete execution release."""

        return self.to_document().digest(
            domain="action-execution-release"
        )
