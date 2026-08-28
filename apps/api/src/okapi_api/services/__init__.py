"""Service layer — orchestration and domain logic.

Services take their dependencies (repository, gate, policy client) via constructor
injection so each is unit-testable with mocks (architecture doc section 10).
Services never see a SQLAlchemy ``Session`` directly.
"""
