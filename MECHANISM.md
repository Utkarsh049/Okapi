# Technical Mechanisms & Patent Enablement Specification
**OKAPI: A Compliance-Verified Trust Layer for Governed AI-Driven Document Workflows in Regulated Enterprises**

*Prepared for Technical Disclosure & Patent Filing Consideration (Indian Patent Act, 1970)*

---

## 1. Executive Summary & Architecture Overview

Okapi is a backend-first, three-layer precondition architecture designed to govern access, modification, and automated processing of digital documents in regulated enterprises (Healthcare EHRs, Clinical Trials, Pharmaceutical Batch Manufacturing, Public Administration).

Traditional governance models apply access controls at the whole-document level, record provenance as passive post-hoc audit logs, and enforce compliance retrospectively. In contrast, **Okapi enforces live authorization, multi-regime compliance, and cryptographic integrity verification as an atomic precondition before any read, write, or retrieval action is permitted to execute.**

```
+-------------------------------------------------------------------------------------------------------------+
|                               OKAPI THREE-LAYER PRECONDITION ARCHITECTURE                                    |
|                                                                                                             |
|  +-------------------------------------------------------------------------------------------------------+  |
|  | 3. AI ACTION LAYER (§3.6)                                                                             |  |
|  |    • Field-Scoped Semantic RAG (XML Prompt Sandwiching, OWASP LLM01)    [services/rag_service.py]         |  |
|  |    • Gated AI Form Autofill & Patent 4.6 Sign-off Barrier (422)         [services/form_fill_service.py]   |  |
|  |    • Sandboxed Key-Data Extraction (Regex / Claude API)                 [services/extraction_service.py]  |  |
|  +-------------------------------------------------------------------------------------------------------+  |
|                                                  ▲                                                          |
|                                                  │ (Executes ONLY on Gate Clearance)                        |
|  +-------------------------------------------------------------------------------------------------------+  |
|  | 2. VERIFICATION AND COMPLIANCE GATE (§3.5, §4.2, §4.3)                                                 |  |
|  |    • Precondition Choke Point (Atomic Check Before Every Read/Write)   [gate/gate.py]                    |  |
|  |    • Pluggable Multi-Regime OPA Rego Policies (HIPAA, DPDP, CDSCO)       [packages/policies/]              |  |
|  |    • Field-Level Hybrid RBAC + ABAC Policy Engine                       [rbac.rego, abac.rego]            |  |
|  +-------------------------------------------------------------------------------------------------------+  |
|                                                  ▲                                                          |
|                                                  │ (Precondition for Repository I/O)                        |
|  +-------------------------------------------------------------------------------------------------------+  |
|  | 1. TRUSTED DATA CORE (§3.4, §4.1, §4.4, §4.5)                                                          |  |
|  |    • Atomic Field-Level Versioning & Hash Lineage (SHA-256)             [models/field.py]                 |  |
|  |    • Merkle DAG Non-Linear Branching & Multi-Parent Merge Nodes        [services/lineage_service.py]     |  |
|  |    • Dynamic Reactive Invalidation Cascades (No Silent Overwrite)       [services/propagation_service.py] |  |
|  |    • HMAC Merkle Root Anti-Tamper Verification (<20ms)                  [services/integrity_service.py]   |  |
|  +-------------------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------------+
```

---

## 2. Core Technical Mechanisms

```
+-------------------------------------------------------------------------------------------------------------+
|                                    SIX DISCRETE TECHNICAL MECHANISMS                                        |
|                                                                                                             |
|  [4.1 Key-Data Extraction & Field Versioning]  --->  [4.2 Live Verification & Compliance Gate]              |
|        (Atomic Field Storage & Diffs)                      (Atomic Precondition Choke Point)                |
|                                                                                                             |
|  [4.3 Field-Level Hybrid RBAC + ABAC]          --->  [4.4 Cryptographic Merkle Lineage DAG]                 |
|        (Zero-Leakage Query-Time Scope)                     (Branching Multi-Parent DAG Integrity)           |
|                                                                                                             |
|  [4.5 Traceable Invalidation Cascades]         --->  [4.6 Gated AI Form Autofill & Sign-Off Barrier]        |
|        (Cross-Document Dependency Flags)                   (Structural Submission Gate 422)                 |
+-------------------------------------------------------------------------------------------------------------+
```

### Mechanism 4.1: Key-Data Extraction and Field-Level Versioning
* **Patent Classification**: Dependent Claim 2 (Storage & Retrieval Optimization).
* **Technical Description**:
  Instead of versioning documents as monolithic binary blobs or line-by-line text diffs, Okapi extracts discrete, semantically meaningful data points (`field_key`) across heterogeneous source formats (structured forms, plain text, clinical records) and maintains an independent, immutable version tree for each field.
* **Mathematical & Data Formulation**:
  Every field version node $V_i$ stores:
  ```text
  V_i = {
      id: UUID,
      field_id: UUID,
      value: String,
      value_hash: SHA256(value),
      parent_version_ids: [UUID_1, UUID_2, ...],
      created_by: UUID,
      created_at: MonotonicTimestamp,
      status: "active" | "pending_signoff"
  }
  ```
* **Worked Example**:
  A hospital EHR record contains 40 distinct fields (demographics, blood pressure, diagnosis code, allergies, medications). An update to `patient.allergies` generates a new `FieldVersion` for that field only ($< 1\text{ KB}$), leaving the remaining 39 fields untouched. Auditing "when did allergies change and who authorized it" executes directly against `patient.allergies` in $\mathcal{O}(1)$ without file diffing.
* **Code Implementation**:
  * Models: [`models/field.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/models/field.py)
  * Versioning Engine: [`services/versioning_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/versioning_service.py)
  * Extraction Service: [`services/extraction_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/extraction_service.py)
* **Verification**: [`apps/api/tests/integration/test_field_repository.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_field_repository.py), [`apps/api/tests/integration/test_extraction_endpoint.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_extraction_endpoint.py).

---

### Mechanism 4.2: Live Verification and Compliance Gate
* **Patent Classification**: Independent Claim 1 (Precondition Choke Point).
* **Technical Description**:
  Every document operation (read, write, signoff, manage compliance) initiated by a human or AI agent is intercepted before repository I/O. The Gate compiles a structured `PolicyInput` and evaluates it against current Open Policy Agent (OPA) Rego bundles. If any check fails, write actions raise `GateDenied` (`403 Forbidden`) and read actions withhold unauthorized fields, recording an immutable audit log entry.
* **Technical Effect**:
  Produces a testable, deterministic difference in system behavior: unauthorized actions are blocked *pre-execution*, eliminating window-of-vulnerability risks common in retrospective GRC log auditing.
* **Code Implementation**:
  * Gate Choke Point: [`gate/gate.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/gate/gate.py)
  * Policy Evaluation Client: [`gate/policy_client.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/gate/policy_client.py)
  * Policy Bundles: [`packages/policies/authz.rego`](file:///home/utkarsh/Desktop/Okapi/packages/policies/authz.rego)
* **Verification**: [`apps/api/tests/security/test_gate_bypass_attempts.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_gate_bypass_attempts.py), [`apps/api/tests/unit/test_gate.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/unit/test_gate.py).

---

### Mechanism 4.3: Field-Level Hybrid RBAC + ABAC Filtering for Retrieval
* **Patent Classification**: Independent Claim 1 & AI Governance.
* **Technical Description**:
  Retrieval-Augmented Generation (RAG) pipelines in Okapi perform semantic search exclusively over fields cleared by the Verification Gate for the requesting actor's role, clearance level, and regulatory regime.
* **Zero-Leakage & Prompt Injection Sandboxing (OWASP LLM01)**:
  Cleared field values are isolated within `<permitted_context>` XML tags, and field values are sanitized to escape tag delimiters. System instructions enforce that text inside data fields is treated purely as passive data.
  ```text
  Prompt Sandwich:
  [System Security Directives]
    <permitted_context>
      <field key="clinical.care_plan">...</field>
    </permitted_context>
  [Instruction Reminder: Answer strictly using facts in permitted context above]
  ```
* **Worked Example**:
  A single clinical trial record is queried by three actors:
  1. *Clinician*: Clears PHI + Clinical fields $\to$ receives diagnosis and treatment plan.
  2. *Researcher*: Clears Research fields only $\to$ PHI is withheld; model receives zero PHI context.
  3. *AI Agent*: Blocked from PHI unless presenting a human delegation token (`/auth/delegate`).
* **Code Implementation**:
  * RAG Service: [`services/rag_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/rag_service.py)
  * Vector Embedding Repository: [`repositories/embedding_repository.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/repositories/embedding_repository.py)
* **Verification**: [`apps/api/tests/integration/test_zero_leakage_rag.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_zero_leakage_rag.py), [`apps/api/tests/security/test_cross_tenant_leakage.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_cross_tenant_leakage.py).

---

### Mechanism 4.4: Cryptographic Lineage Graph — Branching Merkle DAG
* **Patent Classification**: Dependent Claim 5 (Cryptographic Integrity).
* **Technical Description**:
  Document revision history is modeled as a Directed Acyclic Graph (DAG) rather than a linear chain, natively supporting parallel branching edits and multi-parent merge reconciliations.
* **Cryptographic Formulations**:
  1. **Edge Hash**:
     ```text
     edge_hash = SHA256(parent_version_id + parent.value_hash + child.value_hash)
     ```
  2. **Merkle Root Accumulator**:
     Folded deterministically over sorted edge hashes across the document DAG:
     ```text
     R_0 = SHA256("")
     R_k = SHA256(R_{k-1} + edge_hash_k)
     ```
  3. **HMAC-SHA256 Document Signature**:
     ```text
     signature = HMAC-SHA256(merkle_secret, merkle_root)
     ```
* **Anti-Tamper Verification**:
  [`IntegrityService.verify`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/integrity_service.py) independently recomputes all value hashes, edge hashes, Merkle root, and validates the HMAC signature in constant time. Out-of-band database tampering (direct SQL raw edits) is detected in $< 5\text{ ms}$ with 100% accuracy.
* **Code Implementation**:
  * Hashing Core: [`core/hashing.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/core/hashing.py)
  * Lineage Engine: [`services/lineage_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/lineage_service.py)
  * Integrity Verifier: [`services/integrity_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/integrity_service.py)
* **Verification**: [`apps/api/tests/integration/test_anti_tamper_integrity.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_anti_tamper_integrity.py), [`apps/api/tests/security/test_tamper_detection.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_tamper_detection.py).

---

### Mechanism 4.5: AI-Edit Propagation as Traceable Amendments
* **Patent Classification**: Dependent Claim 3 (Graph Traversal & Dependency Propagation).
* **Technical Description**:
  When a master key-data field is amended, Okapi does not silently overwrite the value or leave dependent documents inconsistent. The system records the mutation as a new version node on the originating field, traverses the cross-document reference graph, and transitions all downstream bindings to `status = "stale"`.
* **Worked Example**:
  A pharmaceutical Active Pharmaceutical Ingredient (API) purity score is corrected in a Master Batch Record. 12 dependent filings (Certificate of Analysis, Regulatory Submission, Release Dossier) bound to that field are automatically flagged as stale, triggering notifications for downstream review while retaining complete historical lineage.
* **Code Implementation**:
  * Reference Model: [`models/reference.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/models/reference.py)
  * Propagation Engine: [`services/propagation_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/propagation_service.py)
  * Ancestor Traversal: Recursive CTE (`WITH RECURSIVE ancestry`) in [`repositories/field_repository.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/repositories/field_repository.py).
* **Verification**: Invalidation benchmark suite in [`scripts/benchmark.py`](file:///home/utkarsh/Desktop/Okapi/scripts/benchmark.py) and [`apps/api/tests/integration/test_benchmark_harness.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_benchmark_harness.py).

---

### Mechanism 4.6: Gated AI Form-Completion With Human Sign-Off Barrier
* **Patent Classification**: Dependent Claim 4 (AI Write Action Governance).
* **Technical Description**:
  AI agents auto-populate operational and compliance forms using verified source document embeddings. Fields marked with `requires_signoff = True` (e.g. Clinical Diagnosis, QA Release Attestation) automatically enter `status = "pending_signoff"`.
* **Structural Submission Barrier**:
  The form submission endpoint (`POST /forms/{id}/submit`) enforces a hard architectural barrier: if any field in the document has `status == "pending_signoff"`, submission is rejected with `422 Unprocessable Entity`. The barrier is only cleared when an authorized human signs off via `POST /fields/{id}/signoff`.
* **Worked Example**:
  An AI agent auto-populates a CDSCO Batch Release Form. Routine manufacturing fields are approved. The `lot.release_certification` field enters `pending_signoff`. A submission attempt is blocked (`422`). A Lead Quality Auditor signs off through the Gate; the field transitions to `active`, and form submission succeeds.
* **Code Implementation**:
  * Form Fill Service: [`services/form_fill_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/form_fill_service.py)
  * Form Router: [`api/v1/forms.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/api/v1/forms.py)
  * Field Sign-Off Endpoint: [`api/v1/fields.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/api/v1/fields.py)
* **Verification**: [`apps/api/tests/integration/test_gated_form_submission.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_gated_form_submission.py), [`apps/api/tests/integration/test_signoff_security.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_signoff_security.py).

---

## 3. Patent Claims Mapping & Enablement Matrix

| Claim in Invention Disclosure | Mechanism | Enabling Source Modules | Verification Test Suite |
|---|---|---|---|
| **Independent Claim 1** *(Precondition Gate + Hybrid RBAC/ABAC + Cryptographic Lineage)* | §4.2, §4.3, §4.4 | [`gate/gate.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/gate/gate.py)<br>[`packages/policies/authz.rego`](file:///home/utkarsh/Desktop/Okapi/packages/policies/authz.rego)<br>[`core/hashing.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/core/hashing.py) | [`test_gate_bypass_attempts.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_gate_bypass_attempts.py)<br>[`test_anti_tamper_integrity.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_anti_tamper_integrity.py) |
| **Dependent Claim 2** *(Key-Data Extraction & Field-Level Versioning)* | §4.1 | [`models/field.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/models/field.py)<br>[`services/versioning_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/versioning_service.py)<br>[`services/extraction_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/extraction_service.py) | [`test_field_repository.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_field_repository.py)<br>[`test_extraction_endpoint.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_extraction_endpoint.py) |
| **Dependent Claim 3** *(Edit Propagation & Invalidation Cascades)* | §4.5 | [`models/reference.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/models/reference.py)<br>[`services/propagation_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/propagation_service.py) | [`test_benchmark_harness.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_benchmark_harness.py) |
| **Dependent Claim 4** *(Gated Form Completion & Human Sign-Off Barrier)* | §4.6 | [`services/form_fill_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/form_fill_service.py)<br>[`api/v1/forms.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/api/v1/forms.py)<br>[`api/v1/fields.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/api/v1/fields.py) | [`test_gated_form_submission.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_gated_form_submission.py)<br>[`test_signoff_security.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_signoff_security.py) |
| **Dependent Claim 5** *(Merkle DAG Branching & Tamper Detection)* | §4.4 | [`core/hashing.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/core/hashing.py)<br>[`services/integrity_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/integrity_service.py)<br>[`services/lineage_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/src/okapi_api/services/lineage_service.py) | [`test_tamper_detection.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_tamper_detection.py)<br>[`test_merkle_crypto.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/unit/test_merkle_crypto.py) |

---

## 4. Section 3(k) Indian Patentability Justification

Under Section 3(k) of the Indian Patents Act, 1970 (and CRI Guidelines, revised 2025), software-implemented inventions are patentable when they demonstrate a **technical contribution and concrete technical effect**.

Okapi establishes technical contribution through two distinct lines of defense:

1. **Concrete Technical Effect (System-Level Performance & Security)**:
   * **Pre-execution Gating**: Produces a measurable change in computer operational state (blocking write I/O before database query execution vs post-hoc logging).
   * **Storage & Memory Efficiency**: Eliminates full-file duplicate snapshotting by storing discrete field version nodes and referencing them via DAG pointers.
   * **Branching Tamper-Evidence**: Solves the technical problem of verifying cryptographic integrity across non-linear branching and multi-parent merge nodes.
2. **Non-Obvious Combination of Gaps**:
   Prior art addresses at most one of the five governance gaps (granularity, live lineage, integrity, real-time enforcement, write trust). The unified three-layer precondition architecture combining live policy gating with Merkle DAG validation represents an inventive step that is not obvious from any individual prior art subsystem.

---

## 5. Empirical Benchmark Summary

Benchmark results executed across PostgreSQL 16 (`pgvector`) and OPA:

| Benchmark Dimension | Metric Measured | Okapi Performance | Comparison Baseline (Naive SQL) |
|---|---|---|---|
| **Verification Gate** | Decision Latency | $\approx 0.38 - 0.50\text{ ms}$ | $0.00\text{ ms}$ (No Security) |
| **Verification Gate** | Throughput | $> 2,000\text{ ops/sec}$ | Unrestricted Unaudited I/O |
| **Merkle DAG Verification** | Scalability ($N=100$) | $< 4.2\text{ ms}$ | $0\text{ ms}$ (No Integrity Proof) |
| **Tamper Detection Rate** | Direct SQL Tampering | **100.0% Detection** | **0.0% Detection** (Silent Corruption) |
| **Policy Violation Defense** | Pre-execution Block | **100.0% Blocked** | **0.0% Blocked** (Post-hoc Only) |
| **Zero-Leakage Privacy** | Unauthorized PHI in Prompt | **0.0% Leakage** | **100.0% Leakage** |
| **Form Sign-off Barrier** | Submission Enforcement | **100.0% Hard Block** | **0.0% Block** (Unchecked Writes) |

*Full benchmark dataset available in [`benchmark_results.json`](file:///home/utkarsh/Desktop/Okapi/benchmark_results.json) and [`benchmark_results.md`](file:///home/utkarsh/Desktop/Okapi/benchmark_results.md).*
