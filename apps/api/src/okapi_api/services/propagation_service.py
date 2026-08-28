"""PropagationService — dependent-document flagging (architecture doc section 4.5).

``flag_dependents(field_id)`` walks ``field_references`` and sets ``status='stale'``
on every field that references the one just edited. Synchronous in the prototype;
becomes an async fan-out post-prototype (architecture doc section 11).
"""


class PropagationService:
    """Staleness propagation. Wire the field repository in during implementation."""
