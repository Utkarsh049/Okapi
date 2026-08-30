"""Declarative base and shared enum column types for all Okapi ORM models."""

import enum

from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase

from okapi_shared.enums import ActorType, Decision, ReferenceStatus


class Base(DeclarativeBase):
    """Shared metadata target for models and Alembic autogenerate."""


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Persist the enum *value* ("human"), not its name ("HUMAN"), to match OPA/JSON."""
    return [str(member.value) for member in enum_cls]


# Native PG enum types, each bound to the metadata once so Alembic creates it a
# single time even though several tables reference it.
actor_type_enum = Enum(
    ActorType, name="actor_type", metadata=Base.metadata, values_callable=_enum_values
)
decision_enum = Enum(
    Decision, name="decision", metadata=Base.metadata, values_callable=_enum_values
)
reference_status_enum = Enum(
    ReferenceStatus, name="reference_status", metadata=Base.metadata, values_callable=_enum_values
)
