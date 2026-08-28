"""VersioningService — field-level version history (architecture doc section 4.1).

``create_version(field_id, new_value, parent=current_head)`` appends a row to
``field_versions`` with ``value_hash`` and ``parent_version_id`` (an array, enabling
merge nodes). This IS the "field-level versioning" mechanism.
"""


class VersioningService:
    """Version creation. Wire the field repository in during implementation."""
