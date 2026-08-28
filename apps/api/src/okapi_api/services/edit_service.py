"""EditService — orchestrates the write/edit flow (architecture doc section 5.2).

Gate.check for ``action="write"`` -> VersioningService.create_version ->
LineageService.link (hash-chain the edge) -> PropagationService.flag_dependents.
The write is recorded as an amendment, never an overwrite.
"""


class EditService:
    """Write-path orchestration. Wire dependencies in during implementation."""
