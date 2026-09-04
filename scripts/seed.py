"""Seed the database with users, multi-regime documents, and initial field versions.

Idempotent: users and documents that already exist are safely updated or reused.
Supports HIPAA clinical trials, DPDP digital consultations, CDSCO pharmaceutical lot
release records, and draft forms for AI autofill demonstration.

Run with:
    uv run --package okapi-api python scripts/seed.py
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from okapi_api.core.config import get_settings
from okapi_api.core.hashing import compute_merkle_root, hash_value, sign_merkle_root
from okapi_api.core.security import hash_password
from okapi_api.db.session import SessionFactory
from okapi_api.models import Document, Field, FieldEmbedding, FieldVersion, User
from okapi_api.services.embedding_service import EmbeddingService

DEV_PASSWORD = "okapi-dev"


@dataclass(frozen=True)
class UserSpec:
    email: str
    full_name: str
    role: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class FieldSpec:
    field_key: str
    field_type: str
    requires_signoff: bool
    category: str
    value: str


@dataclass(frozen=True)
class DocSpec:
    title: str
    doc_type: str
    owner_role: str
    compliance_meta: dict[str, Any]
    fields: list[FieldSpec]


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
        {"department": "platform", "clearance_level": 3, "employment_type": "service_account"},
    ),
    UserSpec(
        "auditor@okapi.dev",
        "Dr. Priya Sharma",
        "auditor",
        {"department": "quality_assurance", "clearance_level": 4, "employment_type": "full_time"},
    ),
    UserSpec(
        "chemist@okapi.dev",
        "Alex Chen",
        "chemist",
        {"department": "manufacturing", "clearance_level": 1, "employment_type": "full_time"},
    ),
]

DOCUMENTS = [
    # 1. Baseline Demo Record
    DocSpec(
        title="Demo Patient Record",
        doc_type="patient_record",
        owner_role="clinician",
        compliance_meta={
            "baa_active": True,
            "deidentified": False,
        },
        fields=[
            FieldSpec("patient.diagnosis", "text", True, "phi", "Hypertension, stage 2"),
            FieldSpec(
                "patient.care_plan",
                "text",
                False,
                "clinical",
                "Initiate ACE inhibitor; review in 4 weeks",
            ),
            FieldSpec("study.cohort_size", "number", False, "research", "248"),
        ],
    ),
    # 2. HIPAA Clinical Trial & Patient Health Record
    DocSpec(
        title="Clinical Trial Patient Record (CT-8924)",
        doc_type="clinical_trial",
        owner_role="clinician",
        compliance_meta={
            "baa_active": True,
            "deidentified": False,
            "irb_waiver": False,
        },
        fields=[
            FieldSpec("patient.identifier", "text", False, "phi", "PT-908234"),
            FieldSpec(
                "patient.diagnosis",
                "text",
                True,
                "phi",
                "Severe Coronary Artery Disease with unstable angina",
            ),
            FieldSpec(
                "patient.medications",
                "text",
                True,
                "phi",
                "Atorvastatin 40mg daily, Metoprolol 50mg BID, Aspirin 81mg",
            ),
            FieldSpec(
                "patient.care_plan",
                "text",
                False,
                "clinical",
                "Cardiac catheterization scheduled; titrate beta blocker and monitor hemodynamics.",
            ),
            FieldSpec(
                "patient.vital_signs",
                "text",
                False,
                "clinical",
                "BP: 142/88 mmHg, HR: 78 bpm, SpO2: 98%, BMI: 27.4",
            ),
            FieldSpec("study.cohort_id", "text", False, "research", "CARDIO-PHASE3-GROUP-B"),
            FieldSpec(
                "study.primary_endpoint_status",
                "text",
                False,
                "research",
                "Target LDL reduction achieved (>50% baseline)",
            ),
        ],
    ),
    # 3. DPDP Regulated Digital Teleconsultation Record
    DocSpec(
        title="DPDP Digital Health Consultation (TC-4102)",
        doc_type="teleconsult_record",
        owner_role="clinician",
        compliance_meta={
            "consent_status": "granted",
            "consent_purposes": ["treatment", "telehealth_consultation"],
            "is_minor": False,
            "parental_consent": None,
        },
        fields=[
            FieldSpec("patient.national_id", "text", True, "phi", "IND-AADHAAR-XXXX-8912"),
            FieldSpec(
                "patient.consent_agreement",
                "text",
                False,
                "clinical",
                "Consent granted for digital consultation under DPDP Act 2023 Sec 6.",
            ),
            FieldSpec(
                "consultation.chief_complaint",
                "text",
                False,
                "clinical",
                "Persistent migraine and photophobia for 3 weeks",
            ),
            FieldSpec(
                "consultation.treatment_notes",
                "text",
                False,
                "clinical",
                "Prescribe Sumatriptan 50mg PRN; follow up in 14 days via portal.",
            ),
            FieldSpec(
                "consultation.billing_summary",
                "text",
                False,
                "administrative",
                "Consultation fee: INR 1500, Paid via UPI",
            ),
        ],
    ),
    # 4. CDSCO Regulated Pharmaceutical Lot Release
    DocSpec(
        title="CDSCO Lot Release Record (LOT-AZ-2026-08)",
        doc_type="batch_release",
        owner_role="auditor",
        compliance_meta={
            "batch_status": "in_review",
            "is_lot_release": True,
        },
        fields=[
            FieldSpec("lot.identifier", "text", False, "compliance", "LOT-AZ-2026-08-BIO"),
            FieldSpec(
                "lot.active_ingredient_purity",
                "text",
                True,
                "compliance",
                "99.84% (Spec: >= 99.50% via HPLC)",
            ),
            FieldSpec(
                "lot.sterility_assay",
                "text",
                True,
                "compliance",
                "Pass — No microbial growth observed at 14 days",
            ),
            FieldSpec(
                "lot.dissolution_rate",
                "text",
                False,
                "compliance",
                "94.2% release at 30 minutes (USP Apparatus 2)",
            ),
            FieldSpec(
                "lot.release_certification",
                "text",
                True,
                "compliance",
                "Batch meets Schedule M / CDSCO lot release criteria. Pending QP release signoff.",
            ),
        ],
    ),
    # 5. Target Inpatient Discharge Summary Form (For AI Form Autofill Demo)
    DocSpec(
        title="Hospital Inpatient Discharge Summary Form",
        doc_type="form_draft",
        owner_role="clinician",
        compliance_meta={
            "baa_active": True,
            "deidentified": False,
        },
        fields=[
            FieldSpec(
                "form.patient_summary",
                "text",
                False,
                "clinical",
                "Patient stabilized following acute coronary event.",
            ),
            FieldSpec(
                "form.discharge_medications",
                "text",
                True,
                "phi",
                "Atorvastatin 40mg, Metoprolol 50mg BID, Aspirin 81mg",
            ),
            FieldSpec(
                "form.discharge_instructions",
                "text",
                True,
                "clinical",
                "Avoid strenuous activity for 2 weeks; urgent clinic visit if "
                "chest discomfort recurs.",
            ),
        ],
    ),
]


def main() -> None:
    settings = get_settings()
    embed_service = EmbeddingService()

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
                user.full_name = spec.full_name
                session.flush()
            users[spec.role] = user

        created_docs: list[Document] = []
        for doc_spec in DOCUMENTS:
            owner = users.get(doc_spec.owner_role, users["clinician"])
            doc = session.scalars(select(Document).where(Document.title == doc_spec.title)).first()

            if doc is None:
                doc = Document(
                    title=doc_spec.title,
                    doc_type=doc_spec.doc_type,
                    created_by=owner.id,
                )
                session.add(doc)
                session.flush()

            # Apply compliance metadata
            for k, v in doc_spec.compliance_meta.items():
                setattr(doc, k, v)
            session.flush()

            for fspec in doc_spec.fields:
                field = session.scalars(
                    select(Field).where(
                        Field.document_id == doc.id,
                        Field.field_key == fspec.field_key,
                    )
                ).first()

                if field is None:
                    field = Field(
                        document_id=doc.id,
                        field_key=fspec.field_key,
                        field_type=fspec.field_type,
                        requires_signoff=fspec.requires_signoff,
                        category=fspec.category,
                    )
                    session.add(field)
                    session.flush()
                else:
                    field.field_type = fspec.field_type
                    field.requires_signoff = fspec.requires_signoff
                    field.category = fspec.category
                    session.flush()

                head_version = session.scalars(
                    select(FieldVersion)
                    .where(FieldVersion.field_id == field.id)
                    .order_by(FieldVersion.created_at.desc())
                ).first()

                if head_version is None:
                    v_hash = hash_value(fspec.value)
                    head_version = FieldVersion(
                        field_id=field.id,
                        value=fspec.value,
                        value_hash=v_hash,
                        parent_version_id=[],
                        created_by=owner.id,
                        status="active",
                    )
                    session.add(head_version)
                    session.flush()

                    # Save embedding
                    vector = embed_service.embed_text(fspec.value)
                    embedding = FieldEmbedding(
                        field_version_id=head_version.id,
                        embedding=vector,
                        chunk_text=fspec.value,
                        model_name=embed_service.model_name,
                    )
                    session.add(embedding)
                    session.flush()

            # Compute and sign Merkle root for the document
            root = compute_merkle_root([])
            doc.merkle_root = root
            doc.merkle_signature = sign_merkle_root(root, settings.merkle_secret)
            session.flush()
            created_docs.append(doc)

        session.commit()

        print("=" * 70)
        print("🌱 OKAPI SYNTHETIC CORPUS SEED COMPLETE")
        print("=" * 70)
        print("\nRegistered Users:")
        for spec in USERS:
            user = users[spec.role]
            print(
                f"  [{user.role.upper():<18}] {user.email:<24} {user.full_name:<20} "
                f"(Clearance: {user.attributes.get('clearance_level')})"
            )

        print("\nRegistered Multi-Regime Documents:")
        for d in created_docs:
            print(f"  • {d.title:<48} [Type: {d.doc_type}] (ID: {d.id})")
        print("=" * 70)


if __name__ == "__main__":
    main()
