"""Tests for canonical MissionProof identifiers."""

import pytest

from ix_missionproof.foundation import CanonicalKey, FoundationError, ScopedIdentifier


def test_canonical_key_normalizes_human_text() -> None:
    key = CanonicalKey.from_text("  Human Authority / Review  ", field_name="key")

    assert key.value == "human-authority-review"
    assert str(key) == "human-authority-review"


def test_canonical_key_rejects_noncanonical_direct_construction() -> None:
    with pytest.raises(FoundationError, match="lowercase alphanumeric"):
        CanonicalKey("Human Authority")


def test_scoped_identifier_round_trips() -> None:
    identifier = ScopedIdentifier.create(namespace="Evidence Record", key="Run 0042")

    assert str(identifier) == "evidence-record:run-0042"
    assert ScopedIdentifier.parse(str(identifier)) == identifier


def test_scoped_identifier_requires_exactly_one_separator() -> None:
    with pytest.raises(FoundationError, match="namespace:key"):
        ScopedIdentifier.parse("evidence:claim:extra")
