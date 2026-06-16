# Merge decision log — `origin/frontend` → `develop`

**Date:** 2026-06-16
**Integration branch:** `integration/frontend-merge` (off `develop`)
**Merge base:** `a2f2a5a`
**Author work merged in:** colleague's `origin/frontend` (23 commits): *bon de retour*, *avoir fournisseur* (supplier credit note), multi-BL→invoice, accounting export, achats/commerciale reworks, EUR/20%-VAT switch, several bug fixes.

This file records the non-obvious choices made while resolving the merge, for later reference.

---

## Branch sequencing

- `develop` was **fast-forwarded to OCR** first (OCR fully contained `develop`; zero-risk FF). This put all OCR/tablet/cash work on `develop` as the baseline.
- The colleague's branch was then merged on a throwaway `integration/frontend-merge` branch so `develop` stays clean until the merge is verified.

## Migrations

- Collision: both branches added `0034/0035/0036` (different content).
- **Ours kept** as `0034–0040`. **His renumbered** and re-pointed onto our head `0040`:
  - `0034_add_remise_tva_to_ro_part_line` → **`0041`** (down_revision `0040`)
  - `0035_create_bon_de_retour` → **`0042`** (down_revision `0041`)
  - `0036_bon_de_retour_extras` → **`0043`** (down_revision `0042`)
- Result: single Alembic head `0043`, chain `0039 → 0040 → 0041 → 0042 → 0043`.

## Currency & VAT — **EUR + 20%, config-driven (intended)**

- Decision: standardize on **EUR + 20% VAT** as the default, ideally sourced from config (CFG_*) so per-garage currency/VAT remains possible for the future multi-garage milestone (M12).
- **What was actually applied in this merge:** his EUR/20% behavior was taken as-is (it works today). The values are still **hardcoded in several frontend pages** (e.g. `(€)` labels, `* 100` euro parsing, 20% default VAT).
- **Follow-up (tracked, not done here):** centralize currency symbol + default VAT rate into a single config source (frontend constant fed by backend CFG, backend VAT default) and replace the hardcoded literals. Files with hardcoded EUR/VAT include: `PartsPage`, `StockPage`, `PurchaseOrderPage`, `SupplierInvoicePage`, `AdvancePaymentsPage`, repair-order/quotation/invoice line entry.

## Money input widgets — **his euro `TextField`s**

- Chose his per-page euro `<TextField type="number">` inputs over our reusable `MoneyField` (this is how he fixed the "price ×10 in devis" bug).
- Consequence: `MoneyField` import removed where it became unused (`StockPage`, `SupplierInvoicePage`).
- Note: `MoneyField` (minor-unit, no float rounding) remains the cleaner long-term approach and pairs naturally with the config-driven currency follow-up above.

## Supplier DELETE permission — **`supplier.delete` (granular), with split frontend gates**

- Backend `DELETE /suppliers/{id}` keeps the dedicated **`supplier.delete`** permission (ours; stricter than his `supplier.update`).
- Frontend `SupplierPage`: the single permission gate was **split** so the *edit* button is gated by `supplier.update` and the *delete* button by `supplier.delete` — matching the backend exactly (combined strengths rather than picking one).

## RBAC catalog

- Kept our single-source-of-truth approach (`seed.py` imports `PERMISSIONS` from `rbac/permissions.py`).
- Added his new codes to the canonical catalog so routers + drift-guard test + seed agree:
  `bon_de_retour.{read,create,update,confirm,cancel,reverse}` and
  `supplier_credit_note.{read,create,issue,void}`.
- Role grants (`_INVENTORY_MANAGER`) for these came from his side via auto-merge; super_admin/admin inherit via `_ALL`.

## Notable feature-union resolutions (kept BOTH sides)

- **`invoice/service.py`**: kept our `create_invoice_from_ocr`, credit-limit check, advance auto-apply, credit-note-on-cancel **and** his `create_invoice_from_delivery_notes` + batched list query. Extended his batch query to also batch **vehicle labels** (avoids N+1 *and* keeps list enrichment).
- **`RepairOrderDetailPage`**: kept our stock-sync (`part_public_id`) **and** his editable price + remise/tva + two-row layout.
- **`InvoicesPage`**: kept our customer-assign + delete actions column **and** his multi-BL create dialog (aliased `qc = queryClient` to keep his references working).
- **`SupplierInvoicePage`**: kept our OCR-prefill `createOpen` **and** his CSV/PDF accounting-export menu.
- **`docker-compose.yml`**: kept both our S3/MinIO and his SMTP/Mailpit env blocks.

## Bug fixed during merge

- `AdvancePaymentsPage` (his branch): query referenced an undefined `customerId`; the state is `lookupCustomerId`. Corrected the three references.

## Pre-existing issues found (NOT caused by this merge — flagged for follow-up)

- **Frontend `tsc` build is broken on `develop`**: `tsconfig.json` sets `"ignoreDeprecations": "6.0"`, which the pinned TypeScript 5.7.3 rejects; plus ~38 pre-existing strict-mode errors (mostly unused imports, a few type issues in `QuotationCreatePage`, `RepairOrderCreatePage`, `VehicleEditPage`, `DashboardPage`). The app builds via Vite/esbuild, which doesn't enforce these. The merge adds **no new** type errors. Worth a dedicated cleanup pass.
