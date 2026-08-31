"""Performance benchmark suite for Okapi's core write and verification paths.

Measures latency of the operations the architecture doc calls out as needing to stay
fast under load: field version writes (through the full Gate -> versioning -> lineage
-> Merkle-sign pipeline), and Merkle anti-tamper verification as version history grows.
Uses a stub policy client (no live OPA needed) so this only requires a database.

Run: uv run --package okapi-api python scripts/benchmark.py
Requires OKAPI_DATABASE_URL (or .env) pointing at a reachable Postgres, same as seed.py.
"""

import argparse
import json
import statistics
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from okapi_api.core.security import hash_password
from okapi_api.db.session import SessionFactory
from okapi_api.gate.gate import Gate
from okapi_api.gate.policy_client import StubPolicyClient
from okapi_api.models import Document, User
from okapi_api.repositories.audit_repository import AuditRepository
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.edit_service import EditService
from okapi_api.services.integrity_service import IntegrityService
from okapi_api.services.lineage_service import LineageService
from okapi_api.services.propagation_service import PropagationService
from okapi_api.services.versioning_service import VersioningService
from okapi_shared.contracts import GateActor
from okapi_shared.enums import ActorType


@dataclass
class BenchmarkResult:
    name: str
    unit: str
    samples: list[float] = field(default_factory=list)

    @property
    def min(self) -> float:
        return min(self.samples)

    @property
    def p50(self) -> float:
        return statistics.median(self.samples)

    @property
    def p95(self) -> float:
        ordered = sorted(self.samples)
        idx = max(0, int(len(ordered) * 0.95) - 1)
        return ordered[idx]

    @property
    def max(self) -> float:
        return max(self.samples)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "unit": self.unit,
            "n": len(self.samples),
            "min": round(self.min, 3),
            "p50": round(self.p50, 3),
            "p95": round(self.p95, 3),
            "max": round(self.max, 3),
        }


def _time_ms(fn: Callable[[], object]) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000.0


def _run(name: str, unit: str, iterations: int, fn: Callable[[], object]) -> BenchmarkResult:
    result = BenchmarkResult(name=name, unit=unit)
    for _ in range(iterations):
        result.samples.append(_time_ms(fn))
    return result


def benchmark_edit_pipeline(session, field_id: uuid.UUID, actor: GateActor, iterations: int) -> BenchmarkResult:
    """Full write path: Gate.check_write -> versioning -> lineage -> Merkle re-sign."""
    fields_repo = FieldRepository(session)
    gate = Gate(StubPolicyClient(), AuditRepository(session))
    edit = EditService(
        gate,
        VersioningService(fields_repo),
        LineageService(fields_repo),
        PropagationService(fields_repo),
        fields_repo,
    )
    field = fields_repo.get_field(field_id)
    document = DocumentRepository(session).get(field.document_id)

    def _write() -> None:
        edit.apply_edit(actor=actor, document=document, field=field, new_value=f"v-{uuid.uuid4()}")

    result = _run("field_edit_pipeline (gate+version+lineage+merkle)", "ms", iterations, _write)
    session.commit()
    return result


def benchmark_integrity_verification(
    session, field_id: uuid.UUID, actor: GateActor, version_counts: list[int]
) -> list[BenchmarkResult]:
    """Merkle verification latency as document version history grows."""
    fields_repo = FieldRepository(session)
    docs_repo = DocumentRepository(session)
    gate = Gate(StubPolicyClient(), AuditRepository(session))
    edit = EditService(
        gate,
        VersioningService(fields_repo),
        LineageService(fields_repo),
        PropagationService(fields_repo),
        fields_repo,
    )
    field = fields_repo.get_field(field_id)
    document = docs_repo.get(field.document_id)
    integrity = IntegrityService(fields=fields_repo, docs=docs_repo)

    results: list[BenchmarkResult] = []
    written = 0
    for target in version_counts:
        while written < target:
            edit.apply_edit(actor=actor, document=document, field=field, new_value=f"v-{written}")
            written += 1
        session.commit()
        result = _run(
            f"integrity.verify @ {target} versions", "ms", 5, lambda: integrity.verify(document.id)
        )
        results.append(result)
    return results


def _print_table(results: list[BenchmarkResult]) -> None:
    header = f"{'benchmark':45} {'n':>4} {'min':>8} {'p50':>8} {'p95':>8} {'max':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.name:45} {len(r.samples):>4} {r.min:>7.2f}{r.unit[0]} {r.p50:>7.2f}{r.unit[0]} "
            f"{r.p95:>7.2f}{r.unit[0]} {r.max:>7.2f}{r.unit[0]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Okapi performance benchmark suite")
    parser.add_argument("--edit-iterations", type=int, default=50)
    parser.add_argument(
        "--verify-at", type=int, nargs="+", default=[10, 100, 500], help="version counts to sample"
    )
    parser.add_argument("--out", type=str, default=None, help="optional path to write JSON results")
    args = parser.parse_args()

    with SessionFactory() as session:
        owner = User(
            email=f"bench-{uuid.uuid4()}@okapi.dev",
            full_name="Benchmark Runner",
            role="clinician",
            password_hash=hash_password("bench"),
            attributes={"clearance_level": 5},
        )
        session.add(owner)
        session.flush()

        doc = Document(
            title=f"Benchmark Run {datetime.now(UTC).isoformat()}",
            doc_type="benchmark",
            created_by=owner.id,
        )
        session.add(doc)
        session.flush()

        fields_repo = FieldRepository(session)
        field = fields_repo.register_field(document_id=doc.id, field_key="benchmark.value")
        session.commit()

        actor = GateActor(
            sub=str(owner.id),
            role="clinician",
            actor_type=ActorType.HUMAN,
            attributes={"clearance_level": 5},
        )

        print(f"\nOkapi Benchmark Suite — document={doc.id}\n")

        edit_result = benchmark_edit_pipeline(session, field.id, actor, args.edit_iterations)
        verify_results = benchmark_integrity_verification(session, field.id, actor, args.verify_at)

        all_results = [edit_result, *verify_results]
        _print_table(all_results)

        if args.out:
            payload = {
                "run_at": datetime.now(UTC).isoformat(),
                "document_id": str(doc.id),
                "results": [r.as_dict() for r in all_results],
            }
            with open(args.out, "w") as f:
                json.dump(payload, f, indent=2)
            print(f"\nResults written to {args.out}")


if __name__ == "__main__":
    main()
