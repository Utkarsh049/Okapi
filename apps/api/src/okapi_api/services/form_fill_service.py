"""FormFillService — AI form auto-completion (architecture doc section 5.3).

For each target field: Gate.check(actor=AI_AGENT, source_field, "read"); on allow,
LLMExtractionService.draft_value; if the field requires sign-off the draft is marked
``pending_signoff`` (blocks submission), else ``auto_approved``.
"""


class FormFillService:
    """Form auto-fill orchestration. Wire dependencies in during implementation."""
