"""Seed the demo database with users, a document, and starting field versions.

Idempotent: users that already exist are reused; the demo document is created once.
Run with: uv run --package okapi-api python scripts/seed.py
"""

from dataclasses import dataclass

from sqlalchemy import select

from okapi_api.core.hashing import hash_value
from okapi_api.core.security import hash_password
from okapi_api.db.session import SessionFactory
from okapi_api.models import Document, Field, FieldVersion, User

DEV_PASSWORD = "okapi-dev"
DEMO_DOC_TITLE = "Demo Patient Record"


@dataclass(frozen=True)
class UserSpec:
    email: str
    full_name: str
    role: str
    attributes: dict[str, object]


@dataclass(frozen=True)
class FieldSpec:
    field_key: str
    field_type: str
    requires_signoff: bool
    category: str
    value: str


USERS = [
    UserSpec(
        "clinician@okapi.dev",
        "Dr. Casey Lin",
        "clinician",
        {"department": "cardiology", "clearance_level": 3, "employment_type": "full_time"},
    ),
    UserSpec(
        "researcher@okapi.dev",
        "Robin Shah",
        "researcher",
        {"department": "research", "clearance_level": 2, "employment_type": "contractor"},
    ),
    UserSpec(
        "compliance@okapi.dev",
        "Sam Okoro",
        "compliance_officer",
        {"department": "compliance", "clearance_level": 5, "employment_type": "full_time"},
    ),
    UserSpec(
        "agent@okapi.dev",
        "Okapi Extraction Agent",
        "ai_agent",
        # clearance_level 3 matches abac.rego's phi threshold -- lets a fully
        # delegated agent (see /auth/delegate) actually clear ABAC too, not just
        # the HIPAA delegation check, so the full success path is demonstrable.
        {"department": "platform", "clearance_level": 3, "employment_type": "service_account"},
    ),
]

FIELDS = [
    FieldSpec("patient.diagnosis", "text", True, "phi", "Hypertension, stage 2"),
    FieldSpec(
        "patient.care_plan", "text", False, "clinical", "Initiate ACE inhibitor; review in 4 weeks"
    ),
    FieldSpec("study.cohort_size", "number", False, "research", "248"),
]


def main() -> None:
    with SessionFactory() as session:
        users: dict[str, User] = {}
        for spec in USERS:
            user = session.scalars(select(User).where(User.email == spec.email)).first()
            if user is None:
                user = User(
                    email=spec.email,
                    full_name=spec.full_name,
                    role=spec.role,
                    password_hash=hash_password(DEV_PASSWORD),
                    attributes=dict(spec.attributes),
                )
                session.add(user)
                session.flush()
            else:
                user.password_hash = hash_password(DEV_PASSWORD)
                user.attributes = dict(spec.attributes)
                user.role = spec.role
                session.flush()
            users[spec.role] = user

        owner = users["clinician"]
        doc = session.scalars(select(Document).where(Document.title == DEMO_DOC_TITLE)).first()
        if doc is None:
            doc = Document(title=DEMO_DOC_TITLE, doc_type="patient_record", created_by=owner.id)
            session.add(doc)
            session.flush()
            for fspec in FIELDS:
                field = Field(
                    document_id=doc.id,
                    field_key=fspec.field_key,
                    field_type=fspec.field_type,
                    requires_signoff=fspec.requires_signoff,
                    category=fspec.category,
                )
                session.add(field)
                session.flush()
                session.add(
                    FieldVersion(
                        field_id=field.id,
                        value=fspec.value,
                        value_hash=hash_value(fspec.value),
                        parent_version_id=[],
                        created_by=owner.id,
                        status="active",
                    )
                )

        session.commit()

        print(f"Seed complete. document_id={doc.id}")
        for role, user in users.items():
            print(f"  {role:18} {user.email}  (password: {DEV_PASSWORD})")


if __name__ == "__main__":
    main()
