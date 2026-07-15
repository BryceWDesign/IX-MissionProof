"""Tests for domain-separated content digests."""

import pytest

from ix_missionproof.foundation import ContentDigest, FoundationError, JsonValue


def test_content_digest_is_deterministic_across_mapping_order() -> None:
    first = ContentDigest.from_payload(
        {"claim": "bounded", "approved": False},
        domain="assurance claim",
    )
    second = ContentDigest.from_payload(
        {"approved": False, "claim": "bounded"},
        domain="assurance claim",
    )

    assert first == second
    assert first.algorithm == "sha256"
    assert first.domain.value == "assurance-claim"


def test_content_digest_separates_semantic_domains() -> None:
    payload: JsonValue = {"status": "ready"}

    claim_digest = ContentDigest.from_payload(payload, domain="claim")
    evidence_digest = ContentDigest.from_payload(payload, domain="evidence")

    assert claim_digest.value != evidence_digest.value


def test_content_digest_verifies_exact_payload() -> None:
    digest = ContentDigest.from_payload(
        {"authority": "human", "decision": "defer"},
        domain="authority-decision",
    )

    assert digest.verifies({"authority": "human", "decision": "defer"}) is True
    assert digest.verifies({"authority": "human", "decision": "allow"}) is False


def test_content_digest_round_trips_canonical_text_and_payload() -> None:
    digest = ContentDigest.from_payload({"finding": "unsupported"}, domain="finding")

    assert ContentDigest.parse(str(digest)) == digest
    assert digest.to_payload() == {
        "algorithm": "sha256",
        "domain": "finding",
        "value": digest.value,
    }


def test_content_digest_rejects_unknown_algorithm() -> None:
    with pytest.raises(FoundationError, match="unsupported digest algorithm"):
        ContentDigest(
            algorithm="sha512",
            domain=ContentDigest.from_payload({}, domain="test").domain,
            value="0" * 64,
        )


def test_content_digest_rejects_malformed_text() -> None:
    with pytest.raises(FoundationError, match="algorithm:domain:value"):
        ContentDigest.parse("sha256:missing-value")
