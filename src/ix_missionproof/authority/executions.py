"""Single-use execution receipts and release-consumption ledger."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from ix_missionproof.authority.releases import ActionExecutionRelease
from ix_missionproof.authority.requests import ActionAuthorizationRequest
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
    require_optional_text,
    require_text,
)

_EXECUTOR_KINDS: Final[frozenset[ActorKind]] = frozenset(
    {
        ActorKind.AGENT,
        ActorKind.SERVICE,
        ActorKind.SYSTEM,
        ActorKind.BUILD_SYSTEM,
    }
)


class ActionExecutionStatus(StrEnum):
    """Terminal status recorded for one released action attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMED_OUT = "timed-out"

    @property
    def succeeded(self) -> bool:
        """Return whether the execution completed successfully."""

        return self is ActionExecutionStatus.SUCCEEDED

    @property
    def blocks_progress(self) -> bool:
        """Return whether the outcome prevents normal progress."""

        return self in {
            ActionExecutionStatus.BLOCKED,
            ActionExecutionStatus.TIMED_OUT,
        }


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
class ActionExecutionReceipt:
    """A terminal receipt that consumes one exact execution release."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-execution-receipt-v1"
    )

    receipt_id: ScopedIdentifier
    started_at: UtcTimestamp
    completed_at: UtcTimestamp
    executed_by_id: ScopedIdentifier
    executor_kind: ActorKind
    executor_accountability_owner_id: ScopedIdentifier
    release_id: ScopedIdentifier
    request_id: ScopedIdentifier
    requester_id: ScopedIdentifier
    grant_id: ScopedIdentifier
    capability_id: ScopedIdentifier
    target_id: ScopedIdentifier
    action_digest: ContentDigest
    status: ActionExecutionStatus
    summary: str
    result: CanonicalJsonDocument
    result_digest: ContentDigest
    exit_code: int | None
    stdout_digest: ContentDigest | None
    stderr_digest: ContentDigest | None
    boundary_note: str | None
    evidence_record_ids: tuple[ScopedIdentifier, ...]
    release_digest: ContentDigest
    request_digest: ContentDigest
    actor_registry_digest: ContentDigest

    def __post_init__(self) -> None:
        self._validate_identifiers()
        self._validate_times()
        self._validate_executor()
        self._validate_documents()
        self._validate_digests()
        self._validate_status()

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
            "boundary_note",
            require_optional_text(
                self.boundary_note,
                field_name="boundary_note",
            ),
        )
        object.__setattr__(
            self,
            "evidence_record_ids",
            _normalize_record_ids(
                self.evidence_record_ids
            ),
        )

        self._validate_boundary_note()

    def _validate_identifiers(self) -> None:
        expected_identifiers = (
            (
                "receipt_id",
                self.receipt_id,
                CanonicalKey("action-execution-receipt"),
            ),
            (
                "release_id",
                self.release_id,
                CanonicalKey("action-execution-release"),
            ),
            (
                "request_id",
                self.request_id,
                CanonicalKey("action-authorization-request"),
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

        for field_name, identifier in (
            ("executed_by_id", self.executed_by_id),
            (
                "executor_accountability_owner_id",
                self.executor_accountability_owner_id,
            ),
            ("requester_id", self.requester_id),
            ("target_id", self.target_id),
        ):
            if not isinstance(identifier, ScopedIdentifier):
                raise FoundationError(
                    f"{field_name} must be a ScopedIdentifier"
                )

        if self.executor_accountability_owner_id.namespace != CanonicalKey(
            "human"
        ):
            raise FoundationError(
                "executor_accountability_owner_id must identify "
                "a human actor"
            )

    def _validate_times(self) -> None:
        if not isinstance(self.started_at, UtcTimestamp):
            raise FoundationError(
                "started_at must be a UtcTimestamp"
            )
        if not isinstance(self.completed_at, UtcTimestamp):
            raise FoundationError(
                "completed_at must be a UtcTimestamp"
            )
        if self.completed_at.value < self.started_at.value:
            raise FoundationError(
                "completed_at must not precede started_at"
            )

    def _validate_executor(self) -> None:
        if not isinstance(self.executor_kind, ActorKind):
            raise FoundationError(
                "executor_kind must be an ActorKind"
            )
        if self.executor_kind not in _EXECUTOR_KINDS:
            raise FoundationError(
                "executor_kind must identify an executable "
                "machine actor"
            )
        if self.executed_by_id.namespace != CanonicalKey(
            self.executor_kind.value
        ):
            raise FoundationError(
                "executed_by_id namespace must match executor_kind"
            )
        if (
            self.executed_by_id
            == self.executor_accountability_owner_id
        ):
            raise FoundationError(
                "executor must not be its own accountability owner"
            )

    def _validate_documents(self) -> None:
        if not isinstance(self.result, CanonicalJsonDocument):
            raise FoundationError(
                "result must be a CanonicalJsonDocument"
            )
        self.result.require_object()

    def _validate_digests(self) -> None:
        _require_digest(
            self.action_digest,
            field_name="action_digest",
            domain="proposed-action",
        )
        _require_digest(
            self.result_digest,
            field_name="result_digest",
            domain="action-execution-result",
        )
        _require_digest(
            self.release_digest,
            field_name="release_digest",
            domain="action-execution-release",
        )
        _require_digest(
            self.request_digest,
            field_name="request_digest",
            domain="action-authorization-request",
        )
        _require_digest(
            self.actor_registry_digest,
            field_name="actor_registry_digest",
            domain="actor-registry",
        )
        _require_optional_digest(
            self.stdout_digest,
            field_name="stdout_digest",
            domain="execution-stdout",
        )
        _require_optional_digest(
            self.stderr_digest,
            field_name="stderr_digest",
            domain="execution-stderr",
        )

        if not self.result_digest.verifies(
            self.result.to_value()
        ):
            raise FoundationError(
                "result_digest does not match the execution result"
            )

    def _validate_status(self) -> None:
        if not isinstance(self.status, ActionExecutionStatus):
            raise FoundationError(
                "status must be an ActionExecutionStatus"
            )
        if self.exit_code is not None and not isinstance(
            self.exit_code,
            int,
        ):
            raise FoundationError(
                "exit_code must be an integer or None"
            )

        if (
            self.status is ActionExecutionStatus.SUCCEEDED
            and self.exit_code != 0
        ):
            raise FoundationError(
                "successful execution requires exit_code 0"
            )

        if self.status is ActionExecutionStatus.FAILED:
            if self.exit_code is None or self.exit_code == 0:
                raise FoundationError(
                    "failed execution requires a non-zero exit_code"
                )

        if self.status.blocks_progress and self.exit_code is not None:
            raise FoundationError(
                "blocked and timed-out execution must not "
                "declare an exit_code"
            )

    def _validate_boundary_note(self) -> None:
        if self.status.blocks_progress and self.boundary_note is None:
            raise FoundationError(
                "blocked and timed-out execution require "
                "a boundary_note"
            )

    @classmethod
    def record(
        cls,
        *,
        key: str,
        started_at: UtcTimestamp,
        completed_at: UtcTimestamp,
        executed_by_id: ScopedIdentifier,
        status: ActionExecutionStatus,
        summary: str,
        result: JsonObject,
        exit_code: int | None,
        release: ActionExecutionRelease,
        request: ActionAuthorizationRequest,
        actor_registry: ActorRegistry,
        stdout_digest: ContentDigest | None = None,
        stderr_digest: ContentDigest | None = None,
        boundary_note: str | None = None,
        evidence_record_ids: Iterable[ScopedIdentifier] = (),
    ) -> ActionExecutionReceipt:
        """Record one execution after consuming an exact valid release."""

        executor = actor_registry.require_actor(
            executed_by_id
        )
        executor_owner_id = cls._validate_runtime_executor(
            executor
        )

        cls._validate_release_binding(
            release=release,
            request=request,
            actor_registry=actor_registry,
            started_at=started_at,
        )

        result_document = CanonicalJsonDocument.from_value(
            result
        )

        return cls(
            receipt_id=ScopedIdentifier.create(
                namespace="action-execution-receipt",
                key=key,
                namespace_field="receipt namespace",
                key_field="receipt key",
            ),
            started_at=started_at,
            completed_at=completed_at,
            executed_by_id=executor.actor_id,
            executor_kind=executor.kind,
            executor_accountability_owner_id=(
                executor_owner_id
            ),
            release_id=release.release_id,
            request_id=request.request_id,
            requester_id=request.requester_id,
            grant_id=request.grant_id,
            capability_id=request.capability_id,
            target_id=request.target_id,
            action_digest=request.action_digest,
            status=status,
            summary=summary,
            result=result_document,
            result_digest=result_document.digest(
                domain="action-execution-result"
            ),
            exit_code=exit_code,
            stdout_digest=stdout_digest,
            stderr_digest=stderr_digest,
            boundary_note=boundary_note,
            evidence_record_ids=tuple(
                evidence_record_ids
            ),
            release_digest=release.digest(),
            request_digest=request.digest(),
            actor_registry_digest=actor_registry.digest(),
        )

    @staticmethod
    def _validate_runtime_executor(
        executor: ActorIdentity,
    ) -> ScopedIdentifier:
        if not executor.is_active:
            raise FoundationError(
                "execution requires an active executor"
            )
        if executor.kind not in _EXECUTOR_KINDS:
            raise FoundationError(
                "execution requires an executable machine actor"
            )

        owner_id = executor.accountability_owner_id

        if owner_id is None:
            raise FoundationError(
                "execution actor must identify an accountable "
                "human owner"
            )

        return owner_id

    @staticmethod
    def _validate_release_binding(
        *,
        release: ActionExecutionRelease,
        request: ActionAuthorizationRequest,
        actor_registry: ActorRegistry,
        started_at: UtcTimestamp,
    ) -> None:
        if not release.matches_request(request):
            raise FoundationError(
                "execution release does not match the supplied request"
            )
        if (
            release.actor_registry_digest
            != actor_registry.digest()
        ):
            raise FoundationError(
                "execution release is not bound to the supplied "
                "actor registry"
            )
        if not release.is_time_effective(started_at):
            raise FoundationError(
                "execution must start while the release is "
                "time-effective"
            )
        if started_at.value < request.requested_at.value:
            raise FoundationError(
                "execution must not start before the action request"
            )

    @property
    def succeeded(self) -> bool:
        """Return whether the released action succeeded."""

        return self.status.succeeded

    @property
    def blocks_progress(self) -> bool:
        """Return whether this outcome prevents normal progress."""

        return self.status.blocks_progress

    @property
    def consumes_release(self) -> bool:
        """Return the terminal single-use release-consumption rule."""

        return True

    def to_payload(self) -> JsonObject:
        """Return the deterministic representation of this receipt."""

        evidence_payload: JsonArray = [
            str(record_id)
            for record_id in self.evidence_record_ids
        ]

        return {
            "action_digest": self.action_digest.to_payload(),
            "actor_registry_digest": (
                self.actor_registry_digest.to_payload()
            ),
            "blocks_progress": self.blocks_progress,
            "boundary_note": self.boundary_note,
            "capability_id": str(self.capability_id),
            "completed_at": self.completed_at.isoformat(),
            "consumes_release": self.consumes_release,
            "evidence_record_ids": evidence_payload,
            "executed_by_id": str(self.executed_by_id),
            "executor_accountability_owner_id": str(
                self.executor_accountability_owner_id
            ),
            "executor_kind": self.executor_kind.value,
            "exit_code": self.exit_code,
            "grant_id": str(self.grant_id),
            "receipt_id": str(self.receipt_id),
            "release_digest": self.release_digest.to_payload(),
            "release_id": str(self.release_id),
            "request_digest": self.request_digest.to_payload(),
            "request_id": str(self.request_id),
            "requester_id": str(self.requester_id),
            "result": self.result.to_value(),
            "result_digest": self.result_digest.to_payload(),
            "schema": self.SCHEMA.value,
            "started_at": self.started_at.isoformat(),
            "status": self.status.value,
            "stderr_digest": (
                self.stderr_digest.to_payload()
                if self.stderr_digest is not None
                else None
            ),
            "stdout_digest": (
                self.stdout_digest.to_payload()
                if self.stdout_digest is not None
                else None
            ),
            "succeeded": self.succeeded,
            "summary": self.summary,
            "target_id": str(self.target_id),
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical execution receipt."""

        return CanonicalJsonDocument.from_value(
            self.to_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete execution receipt."""

        return self.to_document().digest(
            domain="action-execution-receipt"
        )


@dataclass(frozen=True, slots=True)
class ActionExecutionLedger:
    """Immutable ledger enforcing one receipt per execution release."""

    SCHEMA: ClassVar[CanonicalKey] = CanonicalKey(
        "action-execution-ledger-v1"
    )

    ledger_id: ScopedIdentifier
    created_at: UtcTimestamp
    producer_id: ScopedIdentifier
    receipts: tuple[ActionExecutionReceipt, ...]

    def __post_init__(self) -> None:
        self._validate_metadata()

        receipts = tuple(self.receipts)
        self._validate_receipts(receipts)

        object.__setattr__(
            self,
            "receipts",
            tuple(
                sorted(
                    receipts,
                    key=lambda receipt: (
                        receipt.started_at.value,
                        str(receipt.receipt_id),
                    ),
                )
            ),
        )

    def _validate_metadata(self) -> None:
        if not isinstance(self.ledger_id, ScopedIdentifier):
            raise FoundationError(
                "ledger_id must be a ScopedIdentifier"
            )
        if self.ledger_id.namespace != CanonicalKey(
            "action-execution-ledger"
        ):
            raise FoundationError(
                "ledger_id namespace must be "
                "action-execution-ledger"
            )
        if not isinstance(self.created_at, UtcTimestamp):
            raise FoundationError(
                "created_at must be a UtcTimestamp"
            )
        if not isinstance(self.producer_id, ScopedIdentifier):
            raise FoundationError(
                "producer_id must be a ScopedIdentifier"
            )

    def _validate_receipts(
        self,
        receipts: tuple[ActionExecutionReceipt, ...],
    ) -> None:
        for index, receipt in enumerate(receipts):
            if not isinstance(
                receipt,
                ActionExecutionReceipt,
            ):
                raise FoundationError(
                    f"receipts[{index}] must be an "
                    "ActionExecutionReceipt"
                )
            if receipt.completed_at.value > self.created_at.value:
                raise FoundationError(
                    "execution ledger must not predate a "
                    "contained receipt"
                )

        receipt_ids = tuple(
            receipt.receipt_id
            for receipt in receipts
        )
        if len(receipt_ids) != len(set(receipt_ids)):
            raise FoundationError(
                "execution ledger must contain unique receipt IDs"
            )

        release_ids = tuple(
            receipt.release_id
            for receipt in receipts
        )
        if len(release_ids) != len(set(release_ids)):
            raise FoundationError(
                "an execution release may be consumed only once"
            )

    @classmethod
    def create(
        cls,
        *,
        key: str,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
        receipts: Iterable[ActionExecutionReceipt] = (),
    ) -> ActionExecutionLedger:
        """Create a deterministic execution-ledger snapshot."""

        return cls(
            ledger_id=ScopedIdentifier.create(
                namespace="action-execution-ledger",
                key=key,
                namespace_field="ledger namespace",
                key_field="ledger key",
            ),
            created_at=created_at,
            producer_id=producer_id,
            receipts=tuple(receipts),
        )

    def receipt_for_release(
        self,
        release_id: ScopedIdentifier,
    ) -> ActionExecutionReceipt | None:
        """Return the receipt that consumed a release, if present."""

        for receipt in self.receipts:
            if receipt.release_id == release_id:
                return receipt
        return None

    def receipt_for_id(
        self,
        receipt_id: ScopedIdentifier,
    ) -> ActionExecutionReceipt | None:
        """Return a receipt by identifier, if present."""

        for receipt in self.receipts:
            if receipt.receipt_id == receipt_id:
                return receipt
        return None

    def require_receipt(
        self,
        receipt_id: ScopedIdentifier,
    ) -> ActionExecutionReceipt:
        """Return a receipt or fail when it is absent."""

        receipt = self.receipt_for_id(
            receipt_id
        )
        if receipt is None:
            raise FoundationError(
                "execution ledger does not contain receipt: "
                f"{receipt_id}"
            )
        return receipt

    def is_release_consumed(
        self,
        release_id: ScopedIdentifier,
    ) -> bool:
        """Return whether a release already has a terminal receipt."""

        return self.receipt_for_release(
            release_id
        ) is not None

    def require_unconsumed(
        self,
        release_id: ScopedIdentifier,
    ) -> None:
        """Fail when an execution release was already consumed."""

        receipt = self.receipt_for_release(
            release_id
        )
        if receipt is not None:
            raise FoundationError(
                f"execution release {release_id} was already "
                f"consumed by {receipt.receipt_id}"
            )

    def append(
        self,
        receipt: ActionExecutionReceipt,
        *,
        created_at: UtcTimestamp,
        producer_id: ScopedIdentifier,
    ) -> ActionExecutionLedger:
        """Return the next ledger snapshot after consuming one release."""

        if not isinstance(
            receipt,
            ActionExecutionReceipt,
        ):
            raise FoundationError(
                "receipt must be an ActionExecutionReceipt"
            )
        if created_at.value < self.created_at.value:
            raise FoundationError(
                "next execution ledger snapshot must not "
                "predate the current snapshot"
            )

        self.require_unconsumed(
            receipt.release_id
        )

        return ActionExecutionLedger(
            ledger_id=self.ledger_id,
            created_at=created_at,
            producer_id=producer_id,
            receipts=(
                *self.receipts,
                receipt,
            ),
        )

    def successful_receipts(
        self,
    ) -> tuple[ActionExecutionReceipt, ...]:
        """Return all successful execution receipts."""

        return tuple(
            receipt
            for receipt in self.receipts
            if receipt.succeeded
        )

    def blocking_receipts(
        self,
    ) -> tuple[ActionExecutionReceipt, ...]:
        """Return receipts that block normal progress."""

        return tuple(
            receipt
            for receipt in self.receipts
            if receipt.blocks_progress
        )

    def canonical_payload(self) -> JsonObject:
        """Return the deterministic representation of this ledger."""

        receipt_payloads: JsonArray = [
            receipt.to_payload()
            for receipt in self.receipts
        ]

        return {
            "created_at": self.created_at.isoformat(),
            "ledger_id": str(self.ledger_id),
            "producer_id": str(self.producer_id),
            "receipts": receipt_payloads,
            "schema": self.SCHEMA.value,
        }

    def to_document(self) -> CanonicalJsonDocument:
        """Return the immutable canonical execution-ledger document."""

        return CanonicalJsonDocument.from_value(
            self.canonical_payload()
        )

    def digest(self) -> ContentDigest:
        """Return a digest covering the complete execution ledger."""

        return self.to_document().digest(
            domain="action-execution-ledger"
        )
