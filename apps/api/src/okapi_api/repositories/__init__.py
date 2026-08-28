"""Repository layer — the only place SQLAlchemy queries live (architecture doc section 10).

Services depend on these; nothing outside this package constructs SQL or touches a
``Session``.
"""
