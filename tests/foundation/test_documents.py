"""Tests for immutable canonical JSON documents."""

import pytest

from ix_missionproof.foundation import (
    CanonicalJsonDocument,
    FoundationError,
    JsonArray,
    JsonObject,
)


def test_document_captures_snapshot_without_retaining_mutable_payload() -> None:
    evidence: JsonArray = ["test-result"]
    payload: JsonObject = {"evidence": evidence, "approved": False}
    document = CanonicalJsonDocument.from_value(payload)

    evidence.append("human-review")

    assert str(document) == '{"approved":false,"evidence":["test-result"]}'
    assert document.to_value() == {"approved": False, "evidence": ["test-result"]}


def test_document_preserves_whitespace_inside_json_strings() -> None:
    document = CanonicalJsonDocument.from_value({"summary": "two  spaces"})

    assert str(document) == '{"summary":"two  spaces"}'
    assert document.require_object()["summary"] == "two  spaces"


def test_to_value_returns_fresh_mutable_copy() -> None:
    document = CanonicalJsonDocument.from_value({"decision": {"outcome": "defer"}})
    first = document.require_object()
    second = document.require_object()

    first["decision"] = {"outcome": "allow"}

    assert second == {"decision": {"outcome": "defer"}}
    assert document.require_object() == {"decision": {"outcome": "defer"}}


def test_document_requires_canonical_encoding() -> None:
    with pytest.raises(FoundationError, match="canonical JSON encoding"):
        CanonicalJsonDocument('{ "z": 1, "a": 2 }')


def test_document_rejects_duplicate_object_keys() -> None:
    with pytest.raises(FoundationError, match="duplicate object key: claim"):
        CanonicalJsonDocument('{"claim":"first","claim":"second"}')


def test_document_rejects_nonstandard_numeric_constants() -> None:
    with pytest.raises(FoundationError, match="invalid numeric constant: NaN"):
        CanonicalJsonDocument('{"score":NaN}')


def test_document_requires_object_root_when_requested() -> None:
    document = CanonicalJsonDocument.from_value(["observation"])

    with pytest.raises(FoundationError, match="root must be an object"):
        document.require_object()


def test_document_digest_is_domain_separated() -> None:
    document = CanonicalJsonDocument.from_value({"status": "recorded"})

    evidence_digest = document.digest(domain="evidence-record")
    claim_digest = document.digest(domain="claim-record")

    assert evidence_digest.verifies(document.to_value()) is True
    assert evidence_digest.value != claim_digest.value
