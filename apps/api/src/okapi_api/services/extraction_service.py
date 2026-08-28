"""ExtractionService — LLM-backed key-data extraction (architecture doc section 3).

The one place a model call sits on the write path: reading unstructured text supplied
with a field registration and proposing a structured value. Deterministic mechanisms
(gate, hash chain, DAG) never call a model.
"""


class ExtractionService:
    """LLM extraction. Wire the Anthropic client in during implementation."""
