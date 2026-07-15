"""Domain-separated content digests for MissionProof records."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from ix_missionproof.foundation.errors import FoundationError
from ix_missionproof.foundation.identifiers import CanonicalKey
from ix_missionproof.foundation.serialization import JsonObject, JsonValue, canonical_json_bytes
from ix_missionproof.foundation.text import require_text

_SHA256_ALGORITHM = "sha256"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_SCHEMA = "ix-missionproof-digest/v1"


def _coerce_domain(value: CanonicalKey | str) -> CanonicalKey:
    if isinstance(value, CanonicalKey):
        return value
    return CanonicalKey.from_text(value, field_name="digest domain")


@dataclass(frozen=True, slots=True, order=True)
class ContentDigest:
    """A SHA-256 fingerprint bound to an explicit semantic domain."""

    algorithm: str
    domain: CanonicalKey
    value: str

    def __post_init__(self) -> None:
        algorithm = require_text(self.algorithm, field_name="digest algorithm").lower()
        if algorithm != _SHA256_ALGORITHM:
            raise FoundationError(f"unsupported digest algorithm: {algorithm}")
        if not isinstance(self.domain, CanonicalKey):
            raise FoundationError("digest domain must be a CanonicalKey")
        digest_value = require_text(self.value, field_name="digest value").lower()
        if not _SHA256_PATTERN.fullmatch(digest_value):
            raise FoundationError("digest value must be 64 lowercase hexadecimal characters")
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "value", digest_value)

    @classmethod
    def from_payload(
        cls,
        payload: JsonValue,
        *,
        domain: CanonicalKey | str,
    ) -> ContentDigest:
        """Hash a payload inside a versioned, domain-separated envelope."""

        canonical_domain = _coerce_domain(domain)
        envelope: JsonObject = {
            "domain": canonical_domain.value,
            "payload": payload,
            "schema": _DIGEST_SCHEMA,
        }
        value = hashlib.sha256(canonical_json_bytes(envelope)).hexdigest()
        return cls(
            algorithm=_SHA256_ALGORITHM,
            domain=canonical_domain,
            value=value,
        )

    @classmethod
    def parse(cls, value: str, *, field_name: str = "digest") -> ContentDigest:
        """Parse the canonical ``algorithm:domain:value`` representation."""

        normalized = require_text(value, field_name=field_name)
        algorithm, separator, remainder = normalized.partition(":")
        domain, second_separator, digest_value = remainder.partition(":")
        if (
            separator != ":"
            or second_separator != ":"
            or not all((algorithm, domain, digest_value))
        ):
            raise FoundationError(f"{field_name} must use the form algorithm:domain:value")
        return cls(
            algorithm=algorithm,
            domain=CanonicalKey(domain),
            value=digest_value,
        )

    def verifies(self, payload: JsonValue) -> bool:
        """Return whether the payload reproduces this domain-bound digest."""

        candidate = self.from_payload(payload, domain=self.domain)
        return hmac.compare_digest(self.value, candidate.value)

    def to_payload(self) -> JsonObject:
        """Return the explicit JSON representation of this digest record."""

        return {
            "algorithm": self.algorithm,
            "domain": self.domain.value,
            "value": self.value,
        }

    def __str__(self) -> str:
        return f"{self.algorithm}:{self.domain}:{self.value}"
