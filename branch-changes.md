# Branch: prateek/api-security-fixes — All Changes (11 commits)

1. **Rate limiting hardened** — key now hashes the full auth token (was a 32-char
   prefix identical for every user); removed duplicate login-throttling code;
   wired the previously-unused `RateLimiter` onto documents/fields/audit; wired
   the previously-unused field-key validator; added `scripts/benchmark.py`.

2. **Field-write Gate bypass closed** — `register_field`/`extract` auto-register
   could write real field values with zero permission check. Also: RAG now uses
   its own relevance search instead of discarding it; lineage rejects invalid
   parent IDs instead of silently dropping them; Merkle signing uses its own
   secret instead of reusing the JWT secret.

3. **CORS fixed** — `allow_origins="*"` + credentials is invalid per spec.

4. **CI fixed** — no Postgres service meant ~40% of tests (including the
   adversarial security suite) silently skipped on every run.

5. **OPA image fixed** — `opa:latest-rootless` was a stale, broken build (parser
   bug); switched to `opa:latest`. This unblocked real end-to-end testing for
   everything after it.

6. **DPDP/CDSCO compliance wired to OPA** — the Gate never sent OPA the fields
   those regimes check, so they silently allowed everything. Added
   `PATCH /documents/{id}/compliance` (compliance_officer-only) + 10 new
   Document columns + migration. Live-verified: consent withdrawal now actually
   blocks access.

7. **Docs corrected** — removed a false claim about an endpoint that never
   existed; documented the new compliance endpoint; documented `scripts/`.

8. **AI delegation made usable** — `POST /auth/delegate` (clinician/
   compliance_officer only). The HIPAA delegation rule was already correct and
   tested, just unreachable through the real login flow. Live-verified full
   success path.

9. **Flaky test fixed at the root cause** — `get_head_version()` had no
   tiebreaker on `created_at`; versions created in rapid succession could tie.
   Now guarantees strictly increasing timestamps per field.

## Result
Full suite green: **81/81 pytest**, **19/19 OPA policy tests**, `ruff`/`black`/
`mypy --strict` clean. `scripts/demo.py` and `make compose-up` both run
end-to-end for the first time this session.
