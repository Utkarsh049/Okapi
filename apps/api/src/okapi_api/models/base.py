"""Declarative base for all Okapi ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata target for models and Alembic autogenerate."""
