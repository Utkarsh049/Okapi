"""Scripted end-to-end demo of the Okapi deterministic core.

Prereqs: the API is running (``make run`` or docker compose), OPA is reachable,
and ``scripts/seed.py`` has been run against the same database.

Run: uv run --package okapi-api python scripts/demo.py
"""

import os
import sys
import textwrap

import httpx
from sqlalchemy import text

from okapi_api.db.session import SessionFactory

BASE = os.environ.get("OKAPI_BASE_URL", "http://localhost:8000")
API = f"{BASE}/api/v1"
PASSWORD = "okapi-dev"


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _token(client: httpx.Client, email: str) -> str:
    resp = client.post(f"{API}/auth/token", data={"username": email, "password": PASSWORD})
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    client = httpx.Client(timeout=10.0)

    _hr("1. Tokens — one human clinician, one AI agent")
    clinician = _token(client, "clinician@okapi.dev")
    researcher = _token(client, "researcher@okapi.dev")
    agent = _token(client, "agent@okapi.dev")
    print("got tokens for clinician@, researcher@, agent@")

    _hr("2. Create a document + register three fields")
    doc = client.post(
        f"{API}/documents",
        json={"title": "Demo Patient Record (scripted)", "doc_type": "patient_record"},
        headers=_headers(clinician),
    ).json()
    doc_id = doc["id"]
    fields = {}
    for key, category, signoff in [
        ("patient.diagnosis", "phi", True),
        ("patient.care_plan", "clinical", False),
        ("study.cohort_size", "research", False),
    ]:
        f = client.post(
            f"{API}/documents/{doc_id}/fields",
            json={
                "field_key": key,
                "category": category,
                "requires_signoff": signoff,
                "value": f"{key} :: v1",
            },
            headers=_headers(clinician),
        ).json()
        fields[key] = f
        print(f"registered {key} ({category}) -> {f['id']}")

    _hr("3. Edit patient.care_plan twice — a hash-chained version history")
    fid = fields["patient.care_plan"]["id"]
    v2 = client.patch(
        f"{API}/documents/{doc_id}/fields/{fid}",
        json={"new_value": "care_plan :: v2", "amendment_note": "adjust dose"},
        headers=_headers(clinician),
    ).json()
    v3 = client.patch(
        f"{API}/documents/{doc_id}/fields/{fid}",
        json={"new_value": "care_plan :: v3", "amendment_note": "add review date"},
        headers=_headers(clinician),
    ).json()
    print(f"v2={v2['id']} parents={v2['parent_version_id']}")
    print(f"v3={v3['id']} parents={v3['parent_version_id']}")

    _hr("4. Reconcile two parallel edits into a merge node (two parents)")
    merge = client.patch(
        f"{API}/documents/{doc_id}/fields/{fid}",
        json={
            "new_value": "care_plan :: merged",
            "parent_version_ids": [v3["id"], v2["id"]],
        },
        headers=_headers(clinician),
    ).json()
    print(f"merge={merge['id']} parents={merge['parent_version_id']}  <- 2 parents")

    _hr("5. Lineage DAG for the document")
    lineage = client.get(f"{API}/documents/{doc_id}/lineage", headers=_headers(clinician)).json()
    print(f"{len(lineage['nodes'])} nodes, {len(lineage['edges'])} edges")
    for e in lineage["edges"]:
        parent, child = e["parent_version_id"][:8], e["child_version_id"][:8]
        print(f"  {parent} -> {child}  edge_hash={e['edge_hash'][:16]}")

    _hr("6. Field-scoped read — researcher sees only research fields")
    r = client.post(
        f"{API}/documents/{doc_id}/query",
        json={"question": "summarise the record"},
        headers=_headers(researcher),
    ).json()
    print(f"allowed : {r['allowed_fields']}")
    print(f"withheld: {r['withheld_fields']}")
    print(f"answer  : {r['answer']}")

    _hr("7. Compliance in action — AI agent blocked from PHI")
    ra = client.post(
        f"{API}/documents/{doc_id}/query",
        json={"question": "diagnosis?"},
        headers=_headers(agent),
    ).json()
    print(f"AI allowed : {ra['allowed_fields']}")
    print(f"AI withheld: {ra['withheld_fields']}  <- patient.diagnosis denied by hipaa.rego")

    _hr("8. Integrity — tamper a value directly in Postgres, then re-verify")
    before = client.get(f"{API}/documents/{doc_id}/integrity", headers=_headers(clinician)).json()
    print(f"before tamper: ok={before['ok']} merkle_root={before['merkle_root'][:16]}")
    with SessionFactory() as session:
        session.execute(
            text(
                "UPDATE field_versions SET value = 'HAND-EDITED' "
                "WHERE id = (SELECT child_version_id FROM lineage_edges "
                "            JOIN field_versions fv ON fv.id = lineage_edges.child_version_id "
                "            JOIN fields f ON f.id = fv.field_id WHERE f.document_id = :d LIMIT 1)"
            ),
            {"d": doc_id},
        )
        session.commit()
    after = client.get(f"{API}/documents/{doc_id}/integrity", headers=_headers(clinician)).json()
    mismatches = len(after["value_hash_mismatches"])
    print(f"after tamper : ok={after['ok']}  value_hash_mismatches={mismatches}")

    _hr("9. Audit log — every decision, human vs AI")
    audit = client.get(
        f"{API}/audit", params={"document_id": doc_id}, headers=_headers(clinician)
    ).json()
    humans = sum(1 for a in audit if a["actor_type"] == "human")
    ai = sum(1 for a in audit if a["actor_type"] == "ai_agent")
    denies = sum(1 for a in audit if a["decision"] == "deny")
    print(f"{len(audit)} rows for this document — {humans} human, {ai} ai_agent, {denies} deny")

    print(textwrap.dedent("""
            10. Policy-as-code (manual): edit packages/policies/rbac.rego, restart OPA,
                re-run step 6 — the outcome changes with no application code change.
            """))
    client.close()


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - demo aid
        print(f"\nHTTP {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        sys.exit(1)
