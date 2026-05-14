# 09 — Testing Strategy

Per [Context.md](Context.md): "Always run unit tests after each implemented feature and store the results under `docs/tests/testForFeatureX`." This document defines what those tests look like, what coverage means, and how the testing pyramid is balanced.

---

## 1. Pyramid

```
                  E2E (Playwright)        5 to 10 percent
            Integration (API + DB)        25 to 30 percent
                Unit (service + UI)       60 to 70 percent
```

- **Unit** — pure logic, fast, isolated. Repositories mocked; business services and rendering components tested directly.
- **Integration** — real database, real FastAPI app, real Redis container. Tests run inside a transaction that rolls back, or against an ephemeral schema.
- **End-to-end** — Playwright against a docker-composed stack, scripted as user journeys (M5+: Quotation to Invoice; M9: Inspection on tablet; M6: Cash closing).

---

## 2. Coverage targets

Per layer, measured on changed code in a PR (line + branch):

| Layer        | New-code target | Project floor |
|--------------|------------------|---------------|
| Unit         | 90%              | 85%           |
| Integration  | 80%              | 70%           |
| End-to-end   | named journeys complete | per-phase list in [02_MILESTONES.md](02_MILESTONES.md) |

Coverage is a useful signal, not a goal. A PR that lowers coverage requires a comment explaining why. A PR that raises it without adding meaningful assertions does not pass review.

---

## 3. Test pyramid by module

For each module, the test set includes:

1. **Domain unit tests** — every state machine transition (legal and illegal), every money/VAT calculation, every permission decision.
2. **Repository tests** — happy path queries and the corner cases (sort stability, pagination boundaries, soft-delete filtering, tenancy filter).
3. **Service tests** — orchestration logic; events emitted; audit entries written; logs at the right level.
4. **API tests** — request validation, status codes, optimistic concurrency (`If-Match`), idempotency key, permission gates.
5. **UI unit tests** — components in isolation with mocked queries.
6. **E2E** — one or two user journeys per module, the ones that map directly to the workflows in [diagrams/flowcharts/](diagrams/flowcharts/).

---

## 4. Edge cases checklist (per [Context.md](Context.md))

A feature is not done until each of these has been considered and either tested or explicitly waived with a recorded reason:

- Empty state (no data, fresh install).
- Single-item state (boundary).
- Maximum-allowed input (string length, file size, list count).
- Concurrent edit by two users (optimistic concurrency).
- Concurrent insert that should be deduplicated.
- Network failure mid-request from a tablet (retry, idempotency).
- Permission denied path.
- Tenancy isolation (the other garage cannot see/affect).
- Currency mismatch / unknown currency.
- VAT rate change between draft and issue.
- Timezone edge: midnight at the boundary, DST transition.
- Soft-delete restored entity behaves correctly.
- Document number gap-freeness under concurrent issuance.
- Stock cannot go negative; reservations released on cancellation.
- Audit log entry exists for every sensitive action.

This list is the minimum. Module-specific edges live in [07_MODULE_BREAKDOWN.md](07_MODULE_BREAKDOWN.md).

---

## 5. Fixtures and data

- **Factories** (factory-boy or hand-rolled) for every domain entity. One factory per module, exposing a `.build()` and `.create()` API.
- **Anonymized seeds** for staging from a sanitization script that rewrites PII and shrinks volumes.
- **Time** is injected via a clock service; tests freeze time with `freezegun` (or its async equivalent) where needed.

---

## 6. Performance tests

Per [01_SOFTWARE_CONCEPTION.md](01_SOFTWARE_CONCEPTION.md), p95 < 2s for typical operations.

- **k6** scripts under `tests/perf/` exercise the hot endpoints with the capacity assumptions.
- A nightly job runs the perf suite against a staging-sized dataset and posts results.
- Each module that introduces a hot endpoint adds a perf scenario before it is declared done.

---

## 7. Security tests

- **Static**: ruff + bandit + semgrep on Python; eslint-plugin-security on JS.
- **Dependency**: pip-audit + npm-audit per build; Dependabot or Renovate weekly.
- **Container**: Trivy scan on every image build.
- **Dynamic**: OWASP ZAP baseline scan against staging weekly.
- **Auth fuzz**: a permanent test that exhaustively tries every endpoint without a token and with a low-privilege token, asserting status codes.

---

## 8. UI and accessibility tests

- Component snapshot tests are avoided; explicit assertion-based tests using react-testing-library.
- **axe-core** runs in CI against the built UI for major flows; violations break the build.
- **Visual regression** with Playwright + per-PR screenshots on the key pages (login, dashboard, repair order detail, invoice PDF preview).

---

## 9. End-to-end journeys (minimum)

These are mandatory by milestone (per [02_MILESTONES.md](02_MILESTONES.md)):

- M1: login + permission gate denial + admin creates user.
- M2: create customer with two vehicles and search by registration.
- M3: open RO, assign mechanic, transition to in_repair, upload photo, transition to finished.
- M4: create part, record stock-in, reserve via RO, consume.
- M5: create quotation, send email, approve via link, convert to invoice, generate PDF.
- M6: record cash payment, close cash session, download Z report.
- M7: create PO, partial reception, attach supplier invoice.
- M8: trigger overdue invoice reminder; verify delivery log.
- M9: complete inspection on tablet offline-tolerant; PDF generated.
- M10: dashboard updates after a new payment; export accounting CSV.
- M11: upload registration card; OCR extracts; user confirms; vehicle created.
- M12: cross-tenant isolation; super-admin sees both garages; non-admin cannot.

---

## 10. Test artefacts

Per [Context.md](Context.md), test reports go under `docs/tests/testForFeatureX/`. Each report contains:

- Date and commit SHA.
- Test counts and outcomes by suite.
- Coverage summary.
- Notable edge cases verified.
- Known gaps and links to follow-up tickets.

---

## 11. Bug investigation

Per [Context.md](Context.md), bug logs go under `docs/bugs/bugX/`. Each bug folder contains:

- Reproduction steps.
- Logs around the time of failure (request_id-correlated).
- Hypothesis log: what was tried and what was learned.
- Root cause when found.
- Fix and the test added to prevent regression.

---

## 12. Flaky test policy

- A test failing intermittently is opened as a bug.
- It is **quarantined**, not deleted: marked with a stable marker (`@pytest.mark.flaky` or `test.skip()` with a TODO and ticket id), removed from the gating set, and tracked in `docs/bugs/`.
- Quarantine duration is capped (e.g., 14 days). After that, either fix or delete with a written justification.
- A test that is quarantined twice in a year is presumed defective and is rewritten or removed.
