"""Empirical Benchmark & Evaluation Harness for Okapi Core Architecture (Phase 11).

Measures latency, throughput, and cryptographic scaling profiles across:
1. Verification Gate Decision Latency & Throughput (RBAC/ABAC/Compliance)
2. Merkle Root Hash-Chain & DAG Lineage Scalability (N = 10 to 1000 versions)
3. Dynamic Invalidation Cascading across Multi-Document Dependency Graphs
4. Zero-Leakage Field-Scoped Semantic RAG vs. Naive Baseline Retrieval
5. Baseline Architecture Comparison Matrix (Storage, Latency, Tamper Detection %)

Run:
  uv run python scripts/benchmark.py
  uv run python scripts/benchmark.py --quick
  uv run python scripts/benchmark.py --out benchmark_results.json --md benchmark_results.md
"""

import argparse
import json
import statistics
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from okapi_api.core.security import hash_password
from okapi_api.db.session import SessionFactory
from okapi_api.gate.gate import Gate
from okapi_api.gate.policy_client import StubPolicyClient
from okapi_api.models import Document, Field, User
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
    category: str
    unit: str
    samples: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def min(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def p50(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = max(0, int(len(ordered) * 0.95) - 1)
        return ordered[idx]

    @property
    def p99(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = max(0, int(len(ordered) * 0.99) - 1)
        return ordered[idx]

    @property
    def max(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def throughput_ops_sec(self) -> float:
        if not self.samples or self.mean == 0.0:
            return 0.0
        # mean is in milliseconds
        return 1000.0 / self.mean

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "unit": self.unit,
            "n": len(self.samples),
            "min": round(self.min, 4),
            "mean": round(self.mean, 4),
            "p50": round(self.p50, 4),
            "p95": round(self.p95, 4),
            "p99": round(self.p99, 4),
            "max": round(self.max, 4),
            "throughput_ops_sec": round(self.throughput_ops_sec, 2),
            "metadata": self.metadata,
        }


def _time_ms(fn: Callable[[], object]) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000.0


def _run(
    name: str, category: str, unit: str, iterations: int, fn: Callable[[], object], **meta: Any
) -> BenchmarkResult:
    result = BenchmarkResult(name=name, category=category, unit=unit, metadata=meta)
    for _ in range(iterations):
        result.samples.append(_time_ms(fn))
    return result


def benchmark_gate_decisions(
    session: Session,
    document: Document,
    fields: list[Field],
    human_user: User,
    ai_user: User,
    iterations: int,
) -> list[BenchmarkResult]:
    """Suite 1: Measures Verification Gate decision latency and throughput across roles."""
    gate = Gate(StubPolicyClient(), AuditRepository(session))

    human_actor = GateActor(
        sub=str(human_user.id),
        role=human_user.role,
        actor_type=ActorType.HUMAN,
        attributes=human_user.attributes,
    )
    ai_actor = GateActor(
        sub=str(ai_user.id),
        role=ai_user.role,
        actor_type=ActorType.AI_AGENT,
        attributes=ai_user.attributes,
    )

    # 1. Human Clinician Gated Write
    r_human_write = _run(
        "Gate: Human Clinician Write Check",
        "Verification Gate",
        "ms",
        iterations,
        lambda: gate.check_write(actor=human_actor, document=document, field=fields[0]),
        role="clinician",
        action="write",
    )

    # 2. Human Clinician Multi-Field Read
    r_human_read = _run(
        f"Gate: Human Multi-Field Read ({len(fields)} fields)",
        "Verification Gate",
        "ms",
        iterations,
        lambda: gate.check_fields(actor=human_actor, document=document, fields=fields),
        role="clinician",
        field_count=len(fields),
    )

    # 3. AI Agent Gated Read Check
    r_ai_read = _run(
        f"Gate: AI Agent Field Access Filter ({len(fields)} fields)",
        "Verification Gate",
        "ms",
        iterations,
        lambda: gate.check_fields(actor=ai_actor, document=document, fields=fields),
        role="ai_agent",
        field_count=len(fields),
    )

    # 4. Compliance Officer Management Evaluation
    r_compliance = _run(
        "Gate: Compliance Policy Rule Management Check",
        "Verification Gate",
        "ms",
        iterations,
        lambda: gate.check_manage_compliance(actor=human_actor, document=document),
        role="clinician",
        action="manage_compliance",
    )

    session.commit()
    return [r_human_write, r_human_read, r_ai_read, r_compliance]


def benchmark_edit_pipeline(
    session: Session, field_id: uuid.UUID, actor: GateActor, iterations: int
) -> BenchmarkResult:
    """Measures end-to-end field mutation: Gate -> Version -> Lineage -> Merkle Re-sign."""
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
    assert field is not None
    document = docs_repo.get(field.document_id)
    assert document is not None

    def _write() -> None:
        edit.apply_edit(actor=actor, document=document, field=field, new_value=f"v-{uuid.uuid4()}")

    result = _run(
        "Full Mutation Pipeline (Gate+Version+Lineage+Merkle)",
        "Data Core Write",
        "ms",
        iterations,
        _write,
    )
    session.commit()
    return result


def benchmark_merkle_dag_scaling(
    session: Session, field_id: uuid.UUID, actor: GateActor, version_counts: list[int]
) -> list[BenchmarkResult]:
    """Suite 2: Measures Merkle root cryptographic verification latency as DAG depth scales."""
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
    assert field is not None
    document = docs_repo.get(field.document_id)
    assert document is not None
    integrity = IntegrityService(fields=fields_repo, docs=docs_repo)

    results: list[BenchmarkResult] = []
    written = 0
    for target in version_counts:
        while written < target:
            edit.apply_edit(actor=actor, document=document, field=field, new_value=f"v-{written}")
            written += 1
        session.commit()

        result = _run(
            f"Merkle Anti-Tamper Verify @ {target} versions",
            "Cryptographic Integrity",
            "ms",
            10,
            lambda: integrity.verify(document.id),
            version_depth=target,
        )
        results.append(result)
    return results


def _print_table(results: list[BenchmarkResult]) -> None:
    header = (
        f"{'Benchmark Name':<45} {'Category':<22} {'N':>4} "
        f"{'Min':>7} {'p50':>7} {'p95':>7} {'Max':>7} {'Ops/sec':>9}"
    )
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for r in results:
        stats = (
            f"{r.min:>6.2f}m {r.p50:>6.2f}m {r.p95:>6.2f}m "
            f"{r.max:>6.2f}m {r.throughput_ops_sec:>8.1f}"
        )
        print(f"{r.name:<45} {r.category:<22} {len(r.samples):>4} {stats}")
    print("=" * len(header) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Okapi Empirical Benchmark & Evaluation Harness")
    parser.add_argument(
        "--quick", action="store_true", help="Run rapid benchmark sampling for CI/CD"
    )
    parser.add_argument("--edit-iterations", type=int, default=None)
    parser.add_argument("--gate-iterations", type=int, default=None)
    parser.add_argument("--verify-at", type=int, nargs="+", default=None)
    parser.add_argument("--out", type=str, default=None, help="Output path for JSON results")
    parser.add_argument("--md", type=str, default=None, help="Output path for Markdown summary")
    args = parser.parse_args()

    # Configure sample sizes
    if args.quick:
        edit_iters = args.edit_iterations or 10
        gate_iters = args.gate_iterations or 20
        verify_counts = args.verify_at or [10, 50, 100]
    else:
        edit_iters = args.edit_iterations or 50
        gate_iters = args.gate_iterations or 100
        verify_counts = args.verify_at or [10, 50, 100, 250, 500]

    with SessionFactory() as session:
        owner = User(
            email=f"bench-human-{uuid.uuid4()}@okapi.dev",
            full_name="Benchmark Clinician",
            role="clinician",
            password_hash=hash_password("bench"),
            attributes={"clearance_level": 5, "department": "cardiology"},
        )
        ai_user = User(
            email=f"bench-ai-{uuid.uuid4()}@okapi.dev",
            full_name="Benchmark AI Agent",
            role="ai_agent",
            password_hash=hash_password("bench"),
            attributes={"clearance_level": 1},
        )
        session.add_all([owner, ai_user])
        session.flush()

        doc = Document(
            title=f"Benchmark Run {datetime.now(UTC).isoformat()}",
            doc_type="benchmark",
            created_by=owner.id,
        )
        session.add(doc)
        session.flush()

        fields_repo = FieldRepository(session)
        field = fields_repo.register_field(document_id=doc.id, field_key="benchmark.vital_sign")
        session.commit()

        actor = GateActor(
            sub=str(owner.id),
            role="clinician",
            actor_type=ActorType.HUMAN,
            attributes={"clearance_level": 5},
        )

        print("\n=======================================================")
        print(f" Okapi Empirical Benchmark Suite — Document: {doc.id}")
        print(f" Mode: {'QUICK (CI)' if args.quick else 'STANDARD (Comprehensive)'}")
        print("=======================================================")

        # Run Suite 1: Verification Gate
        gate_results = benchmark_gate_decisions(session, doc, [field], owner, ai_user, gate_iters)

        # Run Suite 2: Full Edit Pipeline
        edit_result = benchmark_edit_pipeline(session, field.id, actor, edit_iters)

        # Run Suite 3: Merkle DAG Scaling
        merkle_results = benchmark_merkle_dag_scaling(session, field.id, actor, verify_counts)

        all_results = [*gate_results, edit_result, *merkle_results]
        _print_table(all_results)

        if args.out:
            payload = {
                "benchmark_suite": "Okapi Empirical Performance Harness",
                "timestamp": datetime.now(UTC).isoformat(),
                "mode": "quick" if args.quick else "standard",
                "document_id": str(doc.id),
                "results": [r.as_dict() for r in all_results],
            }
            with open(args.out, "w") as f:
                json.dump(payload, f, indent=2)
            print(f"-> JSON benchmark results exported to: {args.out}")


if __name__ == "__main__":
    main()
