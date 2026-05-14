# 07 — Module Breakdown

One section per business module. Each section: purpose, scope, key entities (link to [04_DATABASE_DESIGN.md](04_DATABASE_DESIGN.md)), key workflows (link to flowcharts), permissions (link to [06_RBAC_DESIGN.md](06_RBAC_DESIGN.md)), and notable edge cases.

---

## M.1 — Auth and RBAC

**Purpose.** Authenticate users, enforce permissions, and emit audit on sensitive identity events.

**Scope.** Login, refresh, logout, password reset, user CRUD, role assignment, permission catalog browse, 2FA hooks (post-MVP), session idle timeout, account lockout.

**Entities.** `app_user`, `role`, `permission`, `user_role`, `role_permission`, `audit_log`.

**Workflows.** See [diagrams/sequence/seq_login_and_refresh.md](diagrams/sequence/seq_login_and_refresh.md).

**Edge cases.**

- Concurrent role change while user has an active token: permission re-checked on refresh; access tokens valid until expiry (short).
- Email change: requires reverification.
- Locked account self-reset: only the password reset path can clear it; the lockout window cannot be shortened by repeated requests.
- Deactivated user: revokes all refresh tokens immediately; in-flight access tokens are denied via a deny-list in Redis.

---

## M.2 — Customer (CRM)

**Purpose.** The customer record and its operational state: balance, history, segmentation, fidelity, reminders.

**Scope.** CRUD, search, ledger (`customer_balance_event`), credit limit and outstanding, segmentation, loyalty points, communication preferences, merge duplicates.

**Entities.** `customer`, `customer_contact`, `customer_balance_event`.

**Workflows.**

- Credit limit check on quotation and invoice issuance — see [diagrams/flowcharts/wf_customer_credit_limit.md](diagrams/flowcharts/wf_customer_credit_limit.md).
- Reminder ladder — see [diagrams/flowcharts/wf_customer_account_followup.md](diagrams/flowcharts/wf_customer_account_followup.md).
- Customer segmentation — see [diagrams/flowcharts/wf_customer_segmentation.md](diagrams/flowcharts/wf_customer_segmentation.md).
- Loyalty — see [diagrams/flowcharts/wf_customer_loyalty.md](diagrams/flowcharts/wf_customer_loyalty.md).

**Edge cases.**

- Two reception agents register the same customer at the same time: an idempotency check on `(phone or email, fiscal_id)` triggers a merge prompt.
- Company customer with many vehicles: fleet view aggregates outstanding per company.
- A customer that exists in two garages of the same chain (Phase 12) is two distinct records by design; cross-garage profile merging is out of scope.

---

## M.3 — Vehicle

**Purpose.** Vehicle records, history, mileage, maintenance reminders.

**Scope.** CRUD, search by registration or VIN, ownership transfer, maintenance and technical inspection due dates, full history view.

**Entities.** `vehicle`.

**Workflows.**

- Vehicle history — see [diagrams/flowcharts/wf_vehicle_history.md](diagrams/flowcharts/wf_vehicle_history.md).
- Vehicle reception (entry into a repair order) — see [diagrams/flowcharts/wf_vehicle_reception.md](diagrams/flowcharts/wf_vehicle_reception.md).

**Edge cases.**

- Re-registration (vehicle changes plate): tracked as an alias, not a new record.
- Ownership change: previous owner remains linked to historical repair orders; new owner is the active owner.
- Imported vehicle without local registration yet: VIN serves as the primary identifier until plate is assigned.

---

## M.4 — Repair Order (OR) and Workshop

**Purpose.** The hub of operations. Every repair flows through here.

**Scope.** Create OR, assign mechanic, manage labor and parts lines, status transitions, time tracking, photos, comments, kanban view, generate PDF.

**Entities.** `repair_order`, `ro_labor_line`, `ro_part_line`, `ro_status_event`, `ro_time_entry`, `ro_media`, `ro_comment`.

**Status machine.** See [diagrams/state/repair_order.md](diagrams/state/repair_order.md).

**Workflows.**

- Main flow — see [diagrams/flowcharts/wf_main_business_flow.md](diagrams/flowcharts/wf_main_business_flow.md).
- Standard repair invoicing — see [diagrams/flowcharts/wf_standard_repair_invoicing.md](diagrams/flowcharts/wf_standard_repair_invoicing.md).
- Quick service (oil change, tires) — see [diagrams/flowcharts/wf_quick_service.md](diagrams/flowcharts/wf_quick_service.md).
- Additional repair discovery (mid-repair finding) — see [diagrams/flowcharts/wf_additional_repair_discovery.md](diagrams/flowcharts/wf_additional_repair_discovery.md).
- Comeback / repair failure — see [diagrams/flowcharts/wf_comeback_and_failure.md](diagrams/flowcharts/wf_comeback_and_failure.md).
- Workshop performance — see [diagrams/flowcharts/wf_workshop_performance.md](diagrams/flowcharts/wf_workshop_performance.md).

**Edge cases.**

- Mechanic forgets to stop timer at end of day: a max session duration triggers an auto-pause and an audit entry.
- Mechanic reassigned mid-repair: prior time entries stay attached to the original mechanic; new entries to the new one.
- Two mechanics on the same OR: each has independent time entries; total = sum.
- OR cancelled mid-repair: stock reservations released; part lines kept (audit) but not consumed; labor entries kept as cost record.

---

## M.5 — Inspection (Digital Vehicle Inspection)

**Purpose.** Standardized checklist-based inspection with photos and PDF report.

**Scope.** Inspection templates, inspection execution on tablet (offline tolerant), photo/video capture, diagnostic PDF, customer approval link.

**Entities.** `inspection_template`, `inspection`, `inspection_item_result`, `document` (for media), `ocr_extraction` (not used here directly).

**Workflows.**

- Digital inspection — see [diagrams/flowcharts/wf_digital_inspection.md](diagrams/flowcharts/wf_digital_inspection.md).
- Photo and media management — see [diagrams/flowcharts/wf_media_management.md](diagrams/flowcharts/wf_media_management.md).

**Edge cases.**

- Tablet loses connectivity mid-inspection: data persisted locally (IndexedDB) and syncs when back online; conflict resolution last-write-wins per item with audit.
- Customer rejects part of a recommended list: rejected items become "archived recommendation" tied to the vehicle, surfaced on the next visit.
- Inspection without an OR (walk-in pre-purchase inspection): the inspection can be standalone and converted to an OR later.

---

## M.6 — Inventory and Stock

**Purpose.** Parts catalog, stock movements, valuation, reservations, low-stock alerts.

**Scope.** Part CRUD, stock movement entry, stock level view, reservation lifecycle, low-stock alerts, equivalent parts, supplier-part pricing.

**Entities.** `part`, `stock_movement`, `stock_level_view` (materialized), `part_supplier_price`, `part_equivalence`.

**Workflows.**

- Parts / inventory main flow — see [diagrams/flowcharts/wf_parts_inventory.md](diagrams/flowcharts/wf_parts_inventory.md).
- Part reservation — see [diagrams/flowcharts/wf_part_reservation.md](diagrams/flowcharts/wf_part_reservation.md).
- Part returns — see [diagrams/flowcharts/wf_part_returns.md](diagrams/flowcharts/wf_part_returns.md).
- Low stock alert — see [diagrams/flowcharts/wf_low_stock_alert.md](diagrams/flowcharts/wf_low_stock_alert.md).

**Edge cases.**

- Negative stock attempt: rejected unless explicit override + reason + audit. Useful for cash-and-carry scenarios.
- Adjustment with zero quantity: rejected.
- Reservation expires (OR cancelled or aged): scheduled job releases stale reservations after CFG window.
- Two repair orders reserving the last of a part simultaneously: serialized by row lock; second one gets a clear error and a suggestion of equivalent parts.

---

## M.7 — Quotation

**Purpose.** Pre-invoice proposal that the customer approves or rejects.

**Scope.** Draft, send by email with signed link, customer approve/reject, convert to OR or invoice, archive expired, history.

**Entities.** `quotation`, `quotation_line`.

**Status machine.** See [diagrams/state/quotation.md](diagrams/state/quotation.md).

**Workflows.**

- Quotation to invoice — see [diagrams/flowcharts/wf_quotation_to_invoice.md](diagrams/flowcharts/wf_quotation_to_invoice.md).

**Edge cases.**

- Quotation auto-expires after `CFG_QUOTATION_VALIDITY_DAYS` and moves to `expired`.
- Customer approves an expired quotation via stale link: rejected with friendly UI; reception can re-issue.
- Parts prices changed between draft and approval: quotation totals are locked at issuance; on conversion to invoice, the user is warned if the underlying part price changed (informational).
- Approval link is single-use; second click shows the result of the first.

---

## M.8 — Invoice

**Purpose.** Legal commercial document. Once issued, immutable except via credit note.

**Scope.** Create from RO or quotation, edit while draft, issue (assigns doc number), generate PDF, status updates from payments, cancel via credit note.

**Entities.** `invoice`, `invoice_line`, `credit_note`.

**Status machine.** See [diagrams/state/invoice.md](diagrams/state/invoice.md).

**Workflows.**

- Standard repair invoicing — see [diagrams/flowcharts/wf_standard_repair_invoicing.md](diagrams/flowcharts/wf_standard_repair_invoicing.md).
- Invoice cancellation / credit note — see [diagrams/flowcharts/wf_invoice_cancellation.md](diagrams/flowcharts/wf_invoice_cancellation.md).
- Margin calculation — see [diagrams/flowcharts/wf_margin_calculation.md](diagrams/flowcharts/wf_margin_calculation.md).
- Document generation — see [diagrams/flowcharts/wf_document_generation.md](diagrams/flowcharts/wf_document_generation.md).
- Fleet / company billing — see [diagrams/flowcharts/wf_fleet_billing.md](diagrams/flowcharts/wf_fleet_billing.md).

**Edge cases.**

- Two users attempt to issue the same invoice number: document_sequence is row-locked; second request waits then gets the next number.
- Issuing while outstanding > threshold: blocked unless `invoice.credit_limit.override` permission and a justification is captured.
- Currency mismatch between invoice and customer's preferred currency: default to garage currency; allow override per invoice.
- Discount above `CFG_MAX_LINE_DISCOUNT_PERCENT` requires `invoice.discount.apply` permission.

---

## M.9 — Payment, Deposit, Cash Register

**Purpose.** Record money in and out; close the cashier's session at end of day.

**Scope.** Payment recording per method, partial payments, deposits, cash session open/close, Z report, refunds.

**Entities.** `payment`, `deposit`, `cash_session`.

**Workflows.**

- Cash register main flow — see [diagrams/flowcharts/wf_cash_register.md](diagrams/flowcharts/wf_cash_register.md).
- Partial payment — see [diagrams/flowcharts/wf_partial_payment.md](diagrams/flowcharts/wf_partial_payment.md).
- Advance payment / deposit — see [diagrams/flowcharts/wf_advance_payment.md](diagrams/flowcharts/wf_advance_payment.md).
- Cash register closing — see [diagrams/flowcharts/wf_cash_register_closing.md](diagrams/flowcharts/wf_cash_register_closing.md).
- Customer refund — see [diagrams/flowcharts/wf_customer_refund.md](diagrams/flowcharts/wf_customer_refund.md).

**Edge cases.**

- Payment recorded against a paid invoice: rejected; suggest overpayment refund path.
- Payment in a different currency than the invoice: blocked in MVP; reserved for multi-currency scope.
- Cash session left open overnight: a warning email to admin at midnight; can be closed by admin from another device.
- Discrepancy on cash count: required reason; audit-logged; admin can post a journal correction.

---

## M.10 — Supplier and Purchasing

**Purpose.** Manage suppliers, RFQ, purchase orders, receptions, and supplier invoices with three-way match.

**Scope.** Supplier CRUD, price history, RFQ to multiple suppliers, comparison, PO creation/sending, partial reception, supplier invoice attach and validate.

**Entities.** `supplier`, `purchase_order`, `purchase_order_line`, `po_reception`, `po_reception_line`, `supplier_invoice`, `part_supplier_price`.

**Status machine.** See [diagrams/state/purchase_order.md](diagrams/state/purchase_order.md).

**Workflows.**

- Supplier purchase request — see [diagrams/flowcharts/wf_supplier_purchase_request.md](diagrams/flowcharts/wf_supplier_purchase_request.md).
- Supplier price comparison — see [diagrams/flowcharts/wf_supplier_price_comparison.md](diagrams/flowcharts/wf_supplier_price_comparison.md).
- Purchase order reception — see [diagrams/flowcharts/wf_purchase_order_reception.md](diagrams/flowcharts/wf_purchase_order_reception.md).
- Supplier invoice — see [diagrams/flowcharts/wf_supplier_invoice.md](diagrams/flowcharts/wf_supplier_invoice.md).
- Purchase & supplier overview — see [diagrams/flowcharts/wf_purchase_supplier_overview.md](diagrams/flowcharts/wf_purchase_supplier_overview.md).

**Edge cases.**

- Reception of more than ordered: warned; allowed only with override and a reason.
- Supplier invoice arrives before reception: held in `pending_reception`; alert raised.
- Supplier price change vs. last known: alert in the comparison view.

---

## M.11 — Notifications and Reminders

**Purpose.** All outbound communication, templated, logged, scheduled.

**Scope.** Email and SMS adapters, templates per trigger and locale, scheduler, delivery log with retry, quiet hours.

**Entities.** `notification`, `notification_template`.

**Workflows.**

- Customer notification main flow — see [diagrams/flowcharts/wf_customer_notification.md](diagrams/flowcharts/wf_customer_notification.md).

**Edge cases.**

- Provider outage: backoff with retry; surface as alert after N attempts.
- Customer has no email and no SMS: the trigger is logged as undeliverable and surfaced on the customer profile.
- Quiet hours: messages queued and dispatched at the next allowed window.
- A customer can opt out per channel; transactional messages (vehicle ready, payment receipt) override marketing opt-out but not channel-level opt-out.

---

## M.12 — Document Management (GED) and OCR

**Purpose.** Structured archive of business documents and OCR-driven ingestion of registration cards and IDs.

**Scope.** Upload, categorize, archive lifecycle, search, OCR pipeline with confidence thresholds and human review.

**Entities.** `document`, `ocr_extraction`.

**Workflows.**

- Document generation — see [diagrams/flowcharts/wf_document_generation.md](diagrams/flowcharts/wf_document_generation.md).
- Document management — see [diagrams/flowcharts/wf_document_management.md](diagrams/flowcharts/wf_document_management.md).
- OCR pipeline — see [diagrams/sequence/seq_ocr_pipeline.md](diagrams/sequence/seq_ocr_pipeline.md).

**Edge cases.**

- Low-quality scan: OCR low confidence → human review required.
- Document deleted by user: soft-delete; physical deletion only after retention window.
- Two scans of the same document (duplicate detection by sha256): deduplicated with a note linking to the original.

---

## M.13 — Reporting and Analytics

**Purpose.** Operational and financial KPIs; exports to PDF/Excel; accounting export.

**Scope.** KPI dashboard, scheduled snapshots for trends, period reports, accounting export with lock-on-export semantics.

**Entities.** `kpi_snapshot`. Read-only views over operational tables.

**Workflows.**

- Accounting export — see [diagrams/flowcharts/wf_accounting_export.md](diagrams/flowcharts/wf_accounting_export.md).
- Analytics and reporting — see [diagrams/flowcharts/wf_analytics_reporting.md](diagrams/flowcharts/wf_analytics_reporting.md).

**Edge cases.**

- KPI recomputation under heavy load: KPIs are read from snapshots for trends; "today" comes from a small live aggregate that uses pre-aggregated counters.
- Re-export of an already-exported period: blocked unless admin override and clear marking on the new export.

---

## M.14 — Administration and Security

**Purpose.** System configuration, audit, backup, security alerts.

**Scope.** Settings UI, audit log viewer, backup status, security alerts (failed login bursts, unusual export volume, after-hours admin actions).

**Entities.** `audit_log`, settings rows on `garage`.

**Workflows.**

- Admin and security — see [diagrams/flowcharts/wf_admin_security.md](diagrams/flowcharts/wf_admin_security.md).
- Audit and traceability — see [diagrams/flowcharts/wf_audit_traceability.md](diagrams/flowcharts/wf_audit_traceability.md).

**Edge cases.**

- Admin disables 2FA on their own account: requires a second admin approval (post-MVP if needed).
- Settings change that affects pricing or VAT: requires admin confirmation with a clear "effective from" timestamp.

---

## M.15 — Multi-garage

**Purpose.** Run several garages on one deployment, isolated data, optional cross-garage admin reporting.

**Scope.** Garage entity, tenant resolution middleware, per-garage CFG, super-admin role, isolation tests.

**Entities.** `garage` and a `garage_id` column on every primary table.

**Workflows.** Activated only in Phase 12; described in [00_PLAN_OF_EXECUTION.md](00_PLAN_OF_EXECUTION.md) §M12.

**Edge cases.**

- Super-admin viewing another garage: every read includes a banner indicating cross-tenant context; audit includes `target_garage_id` distinct from `user.garage_id`.
- Per-garage VAT and currency: documents render in garage currency; exports normalize when consolidated.
