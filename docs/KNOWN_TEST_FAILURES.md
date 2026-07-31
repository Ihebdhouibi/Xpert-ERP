# Xpert-ERP — Known Backend Test Failures

> **Purpose:** Track pre-existing `pytest` failures on `backend/`, their root cause, and fix priority — so they don't get re-investigated from scratch or mistaken for regressions.
> **Date recorded:** 2026-07-30
> **Baseline:** 118 failed / 508 passed (full `pytest -q` run on `backend/`)
> **Status:** Not caused by any specific feature branch — confirmed via `git stash` comparison against a clean tree. Not urgent, but should be planned.

---

## 1. Summary by root cause

| # | Root cause | Files affected | Count | Priority |
|---|---|---|---|---|
| 1 | Test-env mock bug (rate limiter vs. `AsyncMock`) | `test_invoice.py`, `test_quotation.py`, `test_customer_endpoints.py`, `test_payment.py`, `test_advance_payment.py`, `test_auth_endpoints.py`, others using the shared HTTP `client` fixture | ~60+ | **P1 — fix first** |
| 2 | Genuine RBAC catalog gap | `test_permission_codes.py` | 1 | **P1 — small, real bug** |
| 3 | Stale business-rule assumptions (money/credit logic) | `test_credit_limit.py` | 5 | **P2 — verify code vs. test, then fix** |
| 4 | Stale schema expectations | `test_customer_service.py` | 19 | **P2** |
| 5 | Assertion drift (cost calculations) | `test_repair_order_service.py`, `test_repair_order_endpoints.py` | 11 | **P2** |
| 6 | Other business-logic drift | `test_document_sequence.py`, `test_stock.py`, `test_purchase_order.py`, `test_auth_service.py`, `test_documents.py` | ~8 | **P2** |
| 7 | Output/formatting drift (PDF, OCR) | `test_pdf.py`, `test_pdf_report.py`, `test_ocr_pipeline.py` | 16 | **P3 — low business risk** |

---

## 2. Details

### P1 — Fix first

**1. Rate-limiter / mock_redis test bug**
The shared test fixtures mock Redis with `AsyncMock`. The rate-limiter compares a mocked value against an `int`:
```
TypeError: '>' not supported between instances of 'AsyncMock' and 'int'
```
This happens in `app/core/rate_limit.py` and throws before `/api/v1/auth/login` can even return a token, so **every HTTP-level test that calls the shared `_login()` helper fails**, regardless of what it's actually testing. Fixing the mock (make it return a real int for the incr/expire path, e.g. a proper `fakeredis`-style stub instead of a bare `AsyncMock`) will likely resolve the majority of the 118 failures in one shot and give real signal on the rest.

**2. Missing permission-catalog entry**
`test_every_router_permission_code_is_in_the_catalog` — some `require_permission("...")` call in a router uses a code that was never added to `backend/app/modules/rbac/permissions.py`. This is a real inconsistency: that permission can be enforced by the endpoint but can't be assigned to a role via the admin UI. Should be a small, self-contained fix — find the offending code and either register it in the catalog or fix the typo.

### P2 — Business-logic drift (verify before fixing)

These protect financial/business correctness (credit limits, balance ledger, cost totals, sequences) and currently give **zero test coverage** in their affected areas. For each one, determine whether the *test* is stale (a rule changed intentionally and the test wasn't updated) or the *code* has an actual regression — do not just adjust assertions to match current output without checking which side is right.

- `test_credit_limit.py`: e.g. `test_issue_invoice_posts_debit_event` fails because `issue_invoice` now requires `due_at` to be set before issuing, but the test helper `_make_draft_invoice` doesn't set it. Looks like intentional rule added after the test was written — needs test update.
- `test_customer_service.py`: `CustomerCreateRequest` requires `fiscal_id`/`phone_e164` to be strings, but tests pass `None` explicitly. Check whether the schema should be `Optional[str]` or whether the tests are wrong.
- `test_repair_order_service.py` / `test_repair_order_endpoints.py`: e.g. test expects `actual_cost_minor == 2500`, code returns `3000`. Needs investigation — could be an intentional cost-calculation change (fee, remise, tva) or a real regression.
- `test_document_sequence.py`, `test_stock.py`, `test_purchase_order.py`, `test_auth_service.py`, `test_documents.py`: smaller, one-off drift — triage individually.

### P3 — Low business risk

- `test_pdf.py`, `test_pdf_report.py`: PDF template rendering assertions (HTML content, headers).
- `test_ocr_pipeline.py`: mocked OCR engine interface drift.

These are about output formatting, not money or access control — fine to defer.

---

## 3. How this was verified as pre-existing

Confirmed via `git stash` (stash working changes → rerun the specific failing test files → compare failure list → `git stash pop`) against the tree before the repair-order → invoice/BL linkage feature (commit `bc3f047`). The following files were spot-checked this way and reproduce **identically** with and without that feature's changes: `test_invoice.py`, `test_repair_order_service.py`, `test_repair_order_endpoints.py`, `test_permission_codes.py`. The remaining files were spot-checked individually (not via full diff) and their failures were confirmed unrelated by inspecting each traceback's actual cause (see section 2) — none touch the delivery-note/invoice/repair-order linkage code.

## 4. Next time you pick this up

1. Run `cd backend && python -m pytest -q --no-cov --tb=no` to get the current failure count/list.
2. Start with the rate-limiter mock fix (P1.1) — re-run the suite afterward, since it will likely shrink this list significantly and may invalidate parts of the P2/P3 breakdown above.
3. Update or delete this file once the list has meaningfully changed — it's a snapshot, not a live tracker.
