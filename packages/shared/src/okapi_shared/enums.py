"""Enumerations shared across Okapi layers.

These mirror the ``ENUM`` types in the core PostgreSQL schema (architecture doc
section 4.1) so the same names are used end to end.
"""

from enum import StrEnum


class ActorType(StrEnum):
    """Who originated a request. Recorded on every gate decision and audit row."""

    HUMAN = "human"
    AI_AGENT = "ai_agent"


class Decision(StrEnum):
    """Outcome of a gate check. Append-only in the audit log."""

    ALLOW = "allow"
    DENY = "deny"


class EdgeAction(StrEnum):
    """The action a caller wants to perform on a field, passed to the gate."""

    READ = "read"
    WRITE = "write"
    SIGNOFF = "signoff"


class ReferenceStatus(StrEnum):
    """State of a cross-document field reference (drives propagation, mechanism 4.5)."""

    CURRENT = "current"
    STALE = "stale"
