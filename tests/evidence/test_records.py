"""Tests for canonical evidence records and closed ledgers."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from ix_missionproof.evidence import (
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
    ActorStatus,
    FoundationError,
    JsonArray,
    JsonObject,
    ScopedIdentifier,
    UtcTimestamp,
)


def _identifier(
    namespace: str,
    key: str,
) -> ScopedIdentifier:
    return ScopedIdentifier.create(
        namespace=namespace,
        key=key,
    )


@dataclass(frozen=True, slots=True)
class _EvidenceActors:
    human: ActorIdentity
    sensor: ActorIdentity
    service: ActorIdentity
    registry: ActorRegistry


def _actors(
    *,
    registry_key: str = "evidence-actors",
) -> _EvidenceActors:
    human = ActorIdentity.create(
        kind=ActorKind.HUMAN,
        key="reviewer-01",
        display_name="Mission Reviewer",
        roles=("evidence authority",),
    )
    sensor = ActorIdentity.create(
        kind=ActorKind.SENSOR,
        key="runtime-sensor",
        display_name="Runtime Sensor",
        accountability_owner_id=human.actor_id,
    )
    service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="evidence-service",
        display_name="Evidence Service",
        accountability_owner_id=human.actor_id,
    )
    registry = ActorRegistry.create(
        key=registry_key,
        created_at=UtcTimestamp.parse(
            "2026-07-15T22:00:00Z"
        ),
        producer_id=human.actor_id,
        actors=(
            human,
            sensor,
            service,
        ),
    )

    return _EvidenceActors(
        human=human,
        sensor=sensor,
        service=service,
        registry=registry,
    )


def _observation(
    actors: _EvidenceActors,
    *,
    key: str = "runtime-observation",
    created_at: str = "2026-07-15T22:05:00Z",
    status: EvidenceStatus = EvidenceStatus.RECORDED,
) -> EvidenceRecord:
    return EvidenceRecord.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        produced_by_id=actors.sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=status,
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
        ),
        summary="Runtime state was observed directly.",
        payload={
            "mode": "bounded",
            "network_enabled": False,
        },
        actor_registry=actors.registry,
        labels=(
            " Runtime ",
            "Evidence",
            "runtime",
        ),
    )


def _test_result(
    actors: _EvidenceActors,
    *,
    key: str = "unit-test-result",
    created_at: str = "2026-07-15T22:06:00Z",
    status: EvidenceStatus = EvidenceStatus.PASSED,
) -> EvidenceRecord:
    return EvidenceRecord.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        produced_by_id=actors.service.actor_id,
        kind=EvidenceKind.TEST_RESULT,
        origin=EvidenceOrigin.EXECUTED,
        status=status,
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
            _identifier(
                "run",
                "unit-tests-0001",
            ),
        ),
        summary="The bounded unit-test target completed.",
        payload={
            "failed": 0,
            "passed": 42,
            "target": "tests/unit",
        },
        actor_registry=actors.registry,
    )


def _derived_record(
    actors: _EvidenceActors,
    source: EvidenceRecord,
    *,
    key: str = "derived-summary",
    created_at: str = "2026-07-15T22:07:00Z",
) -> EvidenceRecord:
    return EvidenceRecord.create(
        key=key,
        created_at=UtcTimestamp.parse(
            created_at
        ),
        produced_by_id=actors.service.actor_id,
        kind=EvidenceKind.SOURCE_RECORD,
        origin=EvidenceOrigin.DERIVED,
        status=EvidenceStatus.RECORDED,
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
        ),
        summary=(
            "A derived summary of the observed runtime state."
        ),
        payload={
            "summary": "The runtime remained bounded.",
        },
        actor_registry=actors.registry,
        source_record_ids=(
            source.record_id,
        ),
    )


def test_evidence_record_captures_payload_and_accountability() -> None:
    actors = _actors()
    observations: JsonArray = [
        "network-disabled",
    ]
    payload: JsonObject = {
        "observations": observations,
    }

    record = EvidenceRecord.create(
        key="immutable-observation",
        created_at=UtcTimestamp.parse(
            "2026-07-15T22:05:00Z"
        ),
        produced_by_id=actors.sensor.actor_id,
        kind=EvidenceKind.OBSERVATION,
        origin=EvidenceOrigin.OBSERVED,
        status=EvidenceStatus.RECORDED,
        subject_ids=(
            _identifier(
                "system",
                "agent-alpha",
            ),
        ),
        summary="The runtime boundary was observed.",
        payload=payload,
        actor_registry=actors.registry,
    )

    observations.append(
        "later-mutation"
    )

    assert record.payload.require_object() == {
        "observations": [
            "network-disabled",
        ],
    }
    assert record.payload_digest.verifies(
        record.payload.to_value()
    ) is True
    assert (
        record.producer_accountability_owner_id
        == actors.human.actor_id
    )
    assert (
        record.actor_registry_digest
        == actors.registry.digest()
    )
    assert record.is_primary is True
    assert record.requires_corroboration is False
    assert record.establishes_claim is False


def test_evidence_record_payload_and_digest_are_deterministic() -> None:
    actors = _actors()
    record = _observation(
        actors
    )

    assert record.to_payload() == {
        "actor_registry_digest": (
            actors.registry.digest().to_payload()
        ),
        "created_at": "2026-07-15T22:05:00Z",
        "establishes_claim": False,
        "is_primary": True,
        "kind": "observation",
        "labels": [
            "runtime",
            "evidence",
        ],
        "origin": "observed",
        "payload": {
            "mode": "bounded",
            "network_enabled": False,
        },
        "payload_digest": (
            record.payload_digest.to_payload()
        ),
        "produced_by_id": "sensor:runtime-sensor",
        "producer_accountability_owner_id": (
            "human:reviewer-01"
        ),
        "record_id": "record:runtime-observation",
        "requires_corroboration": False,
        "schema": "evidence-record-v1",
        "source_record_ids": [],
        "status": "recorded",
        "subject_ids": [
            "system:agent-alpha",
        ],
        "summary": (
            "Runtime state was observed directly."
        ),
    }
    assert record.digest().verifies(
        record.to_payload()
    ) is True


def test_machine_evidence_producer_requires_accountable_human_owner() -> None:
    actors = _actors()
    unowned_service = ActorIdentity.create(
        kind=ActorKind.SERVICE,
        key="unowned-evidence-service",
        display_name="Unowned Evidence Service",
    )
    registry = ActorRegistry.create(
        key="unowned-evidence-actors",
        created_at=actors.registry.created_at,
        producer_id=actors.human.actor_id,
        actors=(
            actors.human,
            unowned_service,
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "must identify an accountable human owner"
        ),
    ):
        EvidenceRecord.create(
            key="unowned-output",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:05:00Z"
            ),
            produced_by_id=unowned_service.actor_id,
            kind=EvidenceKind.SOURCE_RECORD,
            origin=EvidenceOrigin.OBSERVED,
            status=EvidenceStatus.RECORDED,
            subject_ids=(
                _identifier(
                    "system",
                    "agent-alpha",
                ),
            ),
            summary="Unowned machine output.",
            payload={
                "output": "untrusted",
            },
            actor_registry=registry,
        )


def test_organization_cannot_directly_produce_evidence() -> None:
    actors = _actors()
    organization = ActorIdentity.create(
        kind=ActorKind.ORGANIZATION,
        key="ix-research",
        display_name="IX Research",
    )
    registry = ActorRegistry.create(
        key="organization-evidence-actors",
        created_at=actors.registry.created_at,
        producer_id=actors.human.actor_id,
        actors=(
            actors.human,
            organization,
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "human or executable machine actor"
        ),
    ):
        EvidenceRecord.create(
            key="organization-output",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:05:00Z"
            ),
            produced_by_id=organization.actor_id,
            kind=EvidenceKind.SOURCE_RECORD,
            origin=EvidenceOrigin.OBSERVED,
            status=EvidenceStatus.RECORDED,
            subject_ids=(
                _identifier(
                    "system",
                    "agent-alpha",
                ),
            ),
            summary=(
                "Invalid organization-produced record."
            ),
            payload={
                "output": "invalid",
            },
            actor_registry=registry,
        )


def test_inactive_actor_cannot_produce_new_evidence() -> None:
    actors = _actors()
    suspended_sensor = replace(
        actors.sensor,
        status=ActorStatus.SUSPENDED,
    )
    registry = ActorRegistry.create(
        key="suspended-evidence-actors",
        created_at=actors.registry.created_at,
        producer_id=actors.human.actor_id,
        actors=(
            actors.human,
            suspended_sensor,
        ),
    )

    with pytest.raises(
        FoundationError,
        match="producer must be an active actor",
    ):
        EvidenceRecord.create(
            key="suspended-sensor-output",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:05:00Z"
            ),
            produced_by_id=suspended_sensor.actor_id,
            kind=EvidenceKind.OBSERVATION,
            origin=EvidenceOrigin.OBSERVED,
            status=EvidenceStatus.RECORDED,
            subject_ids=(
                _identifier(
                    "system",
                    "agent-alpha",
                ),
            ),
            summary=(
                "Invalid suspended-sensor evidence."
            ),
            payload={
                "state": "unknown",
            },
            actor_registry=registry,
        )


def test_derived_simulated_imported_and_asserted_records_require_sources() -> None:
    actors = _actors()

    for origin in (
        EvidenceOrigin.DERIVED,
        EvidenceOrigin.SIMULATED,
        EvidenceOrigin.IMPORTED,
        EvidenceOrigin.ASSERTED,
    ):
        with pytest.raises(
            FoundationError,
            match=(
                f"origin {origin.value} requires "
                "at least one source record"
            ),
        ):
            EvidenceRecord.create(
                key=f"unsupported-{origin.value}",
                created_at=UtcTimestamp.parse(
                    "2026-07-15T22:05:00Z"
                ),
                produced_by_id=actors.service.actor_id,
                kind=EvidenceKind.SOURCE_RECORD,
                origin=origin,
                status=EvidenceStatus.RECORDED,
                subject_ids=(
                    _identifier(
                        "system",
                        "agent-alpha",
                    ),
                ),
                summary=(
                    f"Unsupported {origin.value} record."
                ),
                payload={
                    "value": "unsupported",
                },
                actor_registry=actors.registry,
            )


def test_evidence_kind_origin_and_producer_must_agree() -> None:
    actors = _actors()
    source = _observation(
        actors
    )

    with pytest.raises(
        FoundationError,
        match=(
            "observation must not use origin derived"
        ),
    ):
        EvidenceRecord.create(
            key="derived-observation",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:06:00Z"
            ),
            produced_by_id=actors.service.actor_id,
            kind=EvidenceKind.OBSERVATION,
            origin=EvidenceOrigin.DERIVED,
            status=EvidenceStatus.RECORDED,
            subject_ids=source.subject_ids,
            summary=(
                "An observation label applied "
                "to derived material."
            ),
            payload={
                "state": "derived",
            },
            actor_registry=actors.registry,
            source_record_ids=(
                source.record_id,
            ),
        )

    with pytest.raises(
        FoundationError,
        match=(
            "human-attested evidence must be produced "
            "by a human actor"
        ),
    ):
        EvidenceRecord.create(
            key="machine-human-review",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:06:00Z"
            ),
            produced_by_id=actors.service.actor_id,
            kind=EvidenceKind.HUMAN_REVIEW,
            origin=EvidenceOrigin.HUMAN_ATTESTED,
            status=EvidenceStatus.PASSED,
            subject_ids=source.subject_ids,
            summary=(
                "A machine attempted to issue "
                "a human attestation."
            ),
            payload={
                "decision": "approved",
            },
            actor_registry=actors.registry,
        )


def test_outcome_statuses_are_restricted_to_outcome_kinds() -> None:
    actors = _actors()

    with pytest.raises(
        FoundationError,
        match=(
            "observation must not use status passed"
        ),
    ):
        _observation(
            actors,
            status=EvidenceStatus.PASSED,
        )

    assert (
        _test_result(
            actors,
            status=EvidenceStatus.FAILED,
        ).status
        is EvidenceStatus.FAILED
    )


def test_evidence_record_rejects_self_source() -> None:
    actors = _actors()
    record = _observation(
        actors
    )

    with pytest.raises(
        FoundationError,
        match="must not cite itself as a source",
    ):
        replace(
            record,
            origin=EvidenceOrigin.DERIVED,
            source_record_ids=(
                record.record_id,
            ),
        )


def test_evidence_ledger_orders_filters_and_preserves_adverse_records() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    failed_test = _test_result(
        actors,
        created_at="2026-07-15T22:06:00Z",
        status=EvidenceStatus.FAILED,
    )
    derived = _derived_record(
        actors,
        observation,
    )

    ledger = EvidenceLedger.create(
        key="runtime-evidence",
        created_at=UtcTimestamp.parse(
            "2026-07-15T22:10:00Z"
        ),
        producer_id=actors.service.actor_id,
        actor_registry=actors.registry,
        records=(
            derived,
            failed_test,
            observation,
        ),
    )

    assert tuple(
        record.record_id
        for record in ledger.records
    ) == (
        observation.record_id,
        failed_test.record_id,
        derived.record_id,
    )
    assert ledger.require_record(
        observation.record_id
    ) == observation
    assert ledger.records_for_subject(
        _identifier(
            "run",
            "unit-tests-0001",
        )
    ) == (
        failed_test,
    )
    assert ledger.records_by_kind(
        EvidenceKind.TEST_RESULT
    ) == (
        failed_test,
    )
    assert ledger.primary_records() == (
        observation,
        failed_test,
    )
    assert (
        ledger.records_requiring_corroboration()
        == (
            derived,
        )
    )
    assert ledger.adverse_records() == (
        failed_test,
    )


def test_evidence_ledger_rejects_missing_source_record() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    derived = EvidenceRecord.create(
        key="missing-source-summary",
        created_at=UtcTimestamp.parse(
            "2026-07-15T22:07:00Z"
        ),
        produced_by_id=actors.service.actor_id,
        kind=EvidenceKind.SOURCE_RECORD,
        origin=EvidenceOrigin.DERIVED,
        status=EvidenceStatus.RECORDED,
        subject_ids=observation.subject_ids,
        summary=(
            "Derived from a record absent "
            "from the ledger."
        ),
        payload={
            "summary": "unresolved",
        },
        actor_registry=actors.registry,
        source_record_ids=(
            _identifier(
                "record",
                "missing-source",
            ),
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "references missing source "
            "record:missing-source"
        ),
    ):
        EvidenceLedger.create(
            key="missing-source-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:10:00Z"
            ),
            producer_id=actors.service.actor_id,
            actor_registry=actors.registry,
            records=(
                observation,
                derived,
            ),
        )


def test_evidence_ledger_rejects_future_source_record() -> None:
    actors = _actors()
    future_source = _observation(
        actors,
        key="future-observation",
        created_at="2026-07-15T22:08:00Z",
    )
    derived = _derived_record(
        actors,
        future_source,
        created_at="2026-07-15T22:07:00Z",
    )

    with pytest.raises(
        FoundationError,
        match="references a future source",
    ):
        EvidenceLedger.create(
            key="future-source-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:10:00Z"
            ),
            producer_id=actors.service.actor_id,
            actor_registry=actors.registry,
            records=(
                derived,
                future_source,
            ),
        )


def test_evidence_ledger_rejects_source_cycles() -> None:
    actors = _actors()
    first = _observation(
        actors,
        key="cycle-first",
        created_at="2026-07-15T22:05:00Z",
    )
    second = _observation(
        actors,
        key="cycle-second",
        created_at="2026-07-15T22:05:00Z",
    )
    first = replace(
        first,
        kind=EvidenceKind.SOURCE_RECORD,
        origin=EvidenceOrigin.DERIVED,
        source_record_ids=(
            second.record_id,
        ),
    )
    second = replace(
        second,
        kind=EvidenceKind.SOURCE_RECORD,
        origin=EvidenceOrigin.DERIVED,
        source_record_ids=(
            first.record_id,
        ),
    )

    with pytest.raises(
        FoundationError,
        match=(
            "source graph must not contain cycles"
        ),
    ):
        EvidenceLedger.create(
            key="cyclic-evidence-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:10:00Z"
            ),
            producer_id=actors.service.actor_id,
            actor_registry=actors.registry,
            records=(
                first,
                second,
            ),
        )


def test_evidence_ledger_rejects_actor_registry_mismatch() -> None:
    actors = _actors()
    different_actors = _actors(
        registry_key="different-evidence-actors"
    )
    record = _observation(
        actors
    )

    with pytest.raises(
        FoundationError,
        match=(
            "must bind the same actor registry"
        ),
    ):
        EvidenceLedger.create(
            key="mismatched-registry-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:10:00Z"
            ),
            producer_id=(
                different_actors.service.actor_id
            ),
            actor_registry=different_actors.registry,
            records=(
                record,
            ),
        )


def test_evidence_ledger_rejects_duplicate_record_ids() -> None:
    actors = _actors()
    record = _observation(
        actors
    )

    with pytest.raises(
        FoundationError,
        match="unique record IDs",
    ):
        EvidenceLedger.create(
            key="duplicate-record-ledger",
            created_at=UtcTimestamp.parse(
                "2026-07-15T22:10:00Z"
            ),
            producer_id=actors.service.actor_id,
            actor_registry=actors.registry,
            records=(
                record,
                record,
            ),
        )


def test_evidence_ledger_digest_is_independent_of_input_order() -> None:
    actors = _actors()
    observation = _observation(
        actors
    )
    test_result = _test_result(
        actors
    )
    created_at = UtcTimestamp.parse(
        "2026-07-15T22:10:00Z"
    )

    first = EvidenceLedger.create(
        key="stable-evidence-ledger",
        created_at=created_at,
        producer_id=actors.service.actor_id,
        actor_registry=actors.registry,
        records=(
            observation,
            test_result,
        ),
    )
    second = EvidenceLedger.create(
        key="stable-evidence-ledger",
        created_at=created_at,
        producer_id=actors.service.actor_id,
        actor_registry=actors.registry,
        records=(
            test_result,
            observation,
        ),
    )

    assert (
        first.canonical_payload()
        == second.canonical_payload()
    )
    assert first.digest() == second.digest()
