"""Integration tests verifying the empirical benchmark and evaluation harness (Phase 11)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import Engine

pytestmark = pytest.mark.integration


def test_benchmark_harness_execution(engine: Engine, tmp_path: Path) -> None:
    """Verifies that scripts/benchmark.py executes hermetically and exports valid reports."""
    json_out = tmp_path / "test_benchmark_results.json"
    md_out = tmp_path / "test_benchmark_results.md"

    env = dict(os.environ)
    env["OKAPI_DATABASE_URL"] = str(engine.url)

    cmd = [
        sys.executable,
        "scripts/benchmark.py",
        "--quick",
        "--out",
        str(json_out),
        "--md",
        str(md_out),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, f"Benchmark script failed with stderr:\n{result.stderr}"

    # Verify JSON export
    assert json_out.exists(), "JSON output file was not generated"
    with open(json_out) as f:
        data = json.load(f)

    assert data["benchmark_suite"] == "Okapi Empirical Performance Harness"
    assert data["mode"] == "quick"
    assert "comparative_matrix" in data
    assert data["comparative_matrix"]["tamper_detection_rate_pct"]["okapi"] == 100.0
    assert data["comparative_matrix"]["policy_violation_prevention_pct"]["okapi"] == 100.0
    assert data["comparative_matrix"]["zero_leakage_phi_isolation_pct"]["okapi"] == 100.0

    # Ensure results cover all categories
    categories = {r["category"] for r in data["results"]}
    assert "Verification Gate" in categories
    assert "Data Core Write" in categories
    assert "Cryptographic Integrity" in categories
    assert "Reactive Invalidation" in categories
    assert "Semantic RAG" in categories
    assert "Comparative Baseline" in categories

    # Verify Markdown export
    assert md_out.exists(), "Markdown output file was not generated"
    with open(md_out) as f:
        md_content = f.read()

    assert "# Okapi Empirical Benchmark & Evaluation Report" in md_content
    assert "## 1. Executive Performance Summary" in md_content
    assert "## 2. Security & Architectural Baseline Comparison Matrix" in md_content
    assert "## 3. Patent Mechanisms Validated" in md_content
