from okapi_api.models import Base


def test_metadata_has_core_tables() -> None:
    expected = {
        "users",
        "documents",
        "fields",
        "field_versions",
        "lineage_edges",
        "field_references",
        "compliance_rules",
        "audit_log",
    }
    assert expected <= set(Base.metadata.tables)
