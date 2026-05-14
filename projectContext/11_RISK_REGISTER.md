# 11 — Risk Register

Risks that can derail or reshape the schedule, the design, or the production operation. Reviewed at the start of every milestone.

Scoring: **Likelihood** L1 (rare) → L5 (almost certain). **Impact** I1 (low) → I5 (severe). **Score** = L × I. Mitigations are concrete, not aspirational.

---

## R-01 — OCR accuracy on real-world scans

- **Likelihood:** L4. **Impact:** I4. **Score:** 16.
- **Why:** Registration cards and IDs vary by issuing region, photo quality, glare, paper wear. PaddleOCR is strong but never perfect. Below-threshold extractions force human review, eroding the time saved.
- **Mitigation:**
  - Enforce a confidence threshold per field, not per document (`CFG_OCR_CONFIDENCE_THRESHOLD`).
  - Always require human confirmation before writing back to vehicle/customer.
  - Maintain a labeled gold set per region and rerun on every PaddleOCR upgrade.
  - Build the OCR engine adapter so a future swap (or a regional fine-tune) is local to one file.
- **Triggers a re-plan if:** field-level accuracy on the gold set drops below 80% after tuning.

---

## R-02 — Accounting export format target unconfirmed

- **Likelihood:** L4. **Impact:** I3. **Score:** 12.
- **Why:** Sage, Cegid, EBP, and generic CSV all use different schemas. Picking the wrong one or building all of them is wasted effort.
- **Mitigation:**
  - At M10 start, the target accounting software must be confirmed.
  - Internal export model is normalized; per-target adapters live behind one interface.
  - The first deployment targets one format; others added when a customer needs them.

---

## R-03 — Multi-garage tenancy added late

- **Likelihood:** L3. **Impact:** I5. **Score:** 15.
- **Why:** Adding `garage_id` and tenant filters after the fact is invasive: every query, every UI page, every migration must be revisited.
- **Mitigation:**
  - `garage_id NOT NULL` on every primary table from M0.
  - Repository base class injects `WHERE garage_id = :current_garage`.
  - A static rule (custom lint or test) fails the build on any query without a tenancy filter.
  - Integration tests with two seeded garages verify isolation on every PR.

---

## R-04 — Document numbering races

- **Likelihood:** L3. **Impact:** I4. **Score:** 12.
- **Why:** Two users issuing invoices simultaneously must not get the same number or skip numbers (legal requirement in many jurisdictions).
- **Mitigation:**
  - `document_sequence` table with a row-level lock per `(garage_id, doc_type, year)`.
  - Issuance always inside the same transaction that writes the document.
  - Load test simulates 10 concurrent issuers; passing this test is a M5 exit criterion.

---

## R-05 — Money correctness (rounding, currency)

- **Likelihood:** L3. **Impact:** I5. **Score:** 15.
- **Why:** Cent-level errors compound across invoices, payments, and exports. Float arithmetic is the most common cause.
- **Mitigation:**
  - All amounts as `BIGINT` minor units + `currency`.
  - Centralized money library with banker's rounding; no ad-hoc math in services.
  - Property-based tests on VAT, discount, and partial-payment math.
  - Cross-validation: sum of payments equals invoice paid_amount; sum of session payments equals session totals.

---

## R-06 — Stock valuation method dispute

- **Likelihood:** L3. **Impact:** I3. **Score:** 9.
- **Why:** FIFO vs weighted average affects margin reporting; choosing late leads to retroactive recomputation.
- **Mitigation:**
  - Choice made at M4 start; default to weighted average (simpler, less storage).
  - Both methods are computable from `stock_movement` table; switching costs a recompute job, not a schema change.

---

## R-07 — Mechanic tablet offline UX

- **Likelihood:** L4. **Impact:** I3. **Score:** 12.
- **Why:** Workshops have spotty Wi-Fi. A tablet UI that fails on transient outages is a daily friction point.
- **Mitigation:**
  - Inspection workflow uses IndexedDB for local persistence; sync on reconnect.
  - Photo upload is resumable; deduplicated by sha256.
  - Each tablet identifies itself; conflicts on the same inspection item resolve last-write-wins with audit.
  - Acceptance: complete an inspection with the network forced off for 5 minutes; sync recovers without data loss.

---

## R-08 — PDF rendering edge cases

- **Likelihood:** L3. **Impact:** I2. **Score:** 6.
- **Why:** WeasyPrint depends on cairo/pango; locale fonts and special characters can render poorly.
- **Mitigation:**
  - Pin font set; ship fonts in the container image.
  - Test PDFs for every locale at M5 exit.
  - Golden-file tests for a representative invoice PDF.

---

## R-09 — Backup and restore not actually tested

- **Likelihood:** L3. **Impact:** I5. **Score:** 15.
- **Why:** Untested backups are a common failure mode; the only thing worse than not backing up is believing you do.
- **Mitigation:**
  - Quarterly restore drill into an isolated environment.
  - RPO / RTO targets measured and documented (see [10_DEPLOYMENT_DEVOPS.md](10_DEPLOYMENT_DEVOPS.md)).
  - Drill outcomes recorded under `docs/runbooks/`.

---

## R-10 — Audit log gaps on sensitive actions

- **Likelihood:** L2. **Impact:** I4. **Score:** 8.
- **Why:** A missing audit entry on a sensitive action defeats the purpose. Easy to forget when adding new endpoints.
- **Mitigation:**
  - Audit annotation pattern at the service layer: every "sensitive" service method declares an audit event in code.
  - Test rule: every endpoint that mutates a high-risk entity is matched to an audit event by a static check.
  - Quarterly audit-log review samples actions to verify completeness.

---

## R-11 — Permission gaps after role changes

- **Likelihood:** L3. **Impact:** I3. **Score:** 9.
- **Why:** Granting permissions piecemeal accumulates over time; an under-scoped role can quietly leak access.
- **Mitigation:**
  - Permission catalog versioned; new permissions added with explicit defaults.
  - Periodic review of effective permissions per user.
  - Integration tests assert that each role can hit exactly its expected endpoints.

---

## R-12 — Dependency on a single SMS provider

- **Likelihood:** L3. **Impact:** I3. **Score:** 9.
- **Why:** Provider outages or pricing changes can stop notifications.
- **Mitigation:**
  - Generic notification adapter interface; provider behind it.
  - At least one fallback provider planned.
  - Quiet failure: notifications are best-effort with retry; never block the user flow.

---

## R-13 — GDPR / local privacy compliance

- **Likelihood:** L3. **Impact:** I4. **Score:** 12.
- **Why:** Customer PII is sensitive. Retention, right to erasure, and consent must be honored.
- **Mitigation:**
  - Retention windows configurable (`CFG_RETENTION_*`).
  - Erasure endpoint for admin: anonymizes personal fields, preserves accounting record integrity (legal retention beats erasure for invoices).
  - Data export endpoint: a customer can receive their personal data on request.
  - No PII in logs; structured logger redacts fields by name.

---

## R-14 — Cross-tenant data leak (Phase 12)

- **Likelihood:** L2. **Impact:** I5. **Score:** 10.
- **Why:** A single missed tenancy filter in a complex query path can cross garages.
- **Mitigation:**
  - Repository base class enforces filter; raw SQL is reviewed and rare.
  - Automated isolation test: two garages, identical seed data, every endpoint asserted to return only one garage's rows.
  - Code review checklist explicitly checks tenancy on every new query.

---

## R-15 — Schedule slippage from unknowns

- **Likelihood:** L4. **Impact:** I3. **Score:** 12.
- **Why:** Every project of this size discovers requirements mid-flight (the brief literally says "more workflows will be added").
- **Mitigation:**
  - 20% buffer in every milestone estimate (already implicit in the parallel-execution maths in [02_MILESTONES.md](02_MILESTONES.md)).
  - Phase exit gates protect downstream phases from upstream slippage.
  - Out-of-scope items go to a backlog with effort estimates rather than being absorbed silently.

---

## R-16 — Performance regression as data grows

- **Likelihood:** L3. **Impact:** I3. **Score:** 9.
- **Why:** A query that is fast at 1k rows is not necessarily fast at 1M. Lists, search, and dashboards are the usual victims.
- **Mitigation:**
  - Capacity assumptions documented in [01_SOFTWARE_CONCEPTION.md](01_SOFTWARE_CONCEPTION.md).
  - k6 nightly perf suite at the assumed scale.
  - Explain-analyze required for any query that touches > 10k rows on production-sized data.

---

## R-17 — Vendor lock-in on object storage

- **Likelihood:** L2. **Impact:** I2. **Score:** 4.
- **Why:** Object storage APIs are mostly S3-compatible, but lifecycle and pre-signed URL semantics vary.
- **Mitigation:** All storage access through a single adapter; MinIO used in dev as a smoke test against the S3-compatible surface.

---

## R-18 — Frontend bundle bloat on tablets

- **Likelihood:** L3. **Impact:** I2. **Score:** 6.
- **Why:** Workshop tablets are often modest hardware; a slow JS bundle hurts daily UX.
- **Mitigation:**
  - Route-split per feature.
  - Bundle budget per route (warn at 250 KB gzipped, fail at 400 KB).
  - Workshop view uses a smaller component subset; do not pull MUI DataGrid into the tablet path.

---

## R-19 — VAT and legal mention misalignment

- **Likelihood:** L3. **Impact:** I3. **Score:** 9.
- **Why:** Legal mentions and VAT formatting differ between France, Belgium, Morocco, etc. The market scope is not yet final.
- **Mitigation:**
  - All legal mentions stored as templated, per-locale, per-garage text. No hard-coded strings.
  - VAT rates and rules per locale, table-driven.
  - First deployment confirms the target market before M5 exit.

---

## R-20 — Knowledge concentrated in one engineer

- **Likelihood:** L4. **Impact:** I3. **Score:** 12.
- **Why:** Small teams concentrate critical knowledge fast; a single absence becomes blocking.
- **Mitigation:**
  - Pair programming on critical paths (auth, document numbering, money library).
  - Architectural decisions recorded here in `projectContext/`.
  - Runbooks under `docs/runbooks/` written before they are needed.

---

## Aggregate

The risks with the highest score (15–16) — OCR accuracy, multi-garage late, money correctness, backup/restore unverified — must each have a named owner before the start of the milestone that touches them. The risk register is reviewed at every milestone gate.
