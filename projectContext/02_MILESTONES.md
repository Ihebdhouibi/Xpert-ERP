# 02 — Milestones

Each phase from [00_PLAN_OF_EXECUTION.md](00_PLAN_OF_EXECUTION.md) is detailed here as a milestone with scope, deliverables, exit criteria, effort, and the work that can be parallelized.

Effort unit: **person-weeks (PW)**, sized for one senior full-stack engineer at full capacity. "PW parallelizable" indicates how much of that effort can be split across two engineers.

---

## M0 — Foundations

**Goal:** repo, tooling, CI/CD, base shell, base database, base logging, base config.

### In scope

- Monorepo layout: `backend/`, `frontend/`, `infra/`, `docs/`, `projectContext/`.
- Python 3.11.0 project with `pyproject.toml`, ruff, mypy, pytest.
- FastAPI skeleton with health check and OpenAPI.
- React project (Vite + TypeScript) with router, base layout, theme.
- PostgreSQL container (docker-compose for dev) and Alembic migrations.
- Per-component structured logging with file-per-component rotation.
- Configuration loader (env + database settings table for runtime-tunable CFG_*).
- CI pipeline (lint, type-check, unit tests, build) on every PR.
- Branch protection: `main`, `stable-testing` protected; PR + green CI required.
- Bootstrapped audit log table and request_id middleware.

### Deliverables

- Running stack locally with `docker compose up`.
- One trivial end-to-end test: a `GET /api/v1/health` invoked from the React app.
- `docs/feature/foundations/` with setup instructions.

### Exit criteria

- New developer can clone, run, and pass tests within 1 day.
- CI green on a representative PR.
- Logs land in per-component files on disk and console.

### Effort

3 PW. Mostly serial.

---

## M1 — Authentication and RBAC

**Goal:** secure login, role-based access, audit log foundation.

### In scope

- User entity (id, email, password_hash with Argon2id, full_name, status).
- Role entity (admin, secretary, mechanic, inventory_manager, accountant) and Permission catalog.
- Many-to-many `user_role` and `role_permission`.
- Login (email + password), logout, password reset (email link), session/JWT strategy with refresh.
- Password policy enforcement; failed-attempt lockout; session idle timeout.
- Permission decorator on FastAPI routes and a permission gate component on the frontend.
- Admin UI: list users, create user, assign roles, deactivate user.
- Audit log writer for: login success, login failure, password change, role assignment, user deactivation.
- See [06_RBAC_DESIGN.md](06_RBAC_DESIGN.md) for the full permission matrix.

### Deliverables

- Working login screen and protected routes.
- `docs/feature/auth/` and `docs/feature/rbac/`.

### Exit criteria

- Admin can create a user with any role; that user can log in and only see allowed modules.
- All sensitive actions appear in the audit log.
- Penetration smoke test (basic): brute-force lockout works, no auth bypass on protected routes.

### Effort

3 PW. Mostly serial.

---

## M2 — Customer and Vehicle

**Goal:** the two foundational master-data modules.

### In scope

- Customer entity: individual and company subtypes, contact details, address, fiscal id, credit limit, segment, status.
- Vehicle entity: registration, VIN, make, model, year, fuel, mileage, owner customer_id, optional second owner.
- Customer-vehicle history view.
- Document upload primitive (entry point for GED): file, mime, size, owner entity, category.
- CRUD UIs with multi-criteria search (name, phone, registration, VIN).
- Per-entity audit on edit and delete.
- Soft delete with admin-only restore.
- See [diagrams/data/erd_customer_vehicle.md](diagrams/data/erd_customer_vehicle.md).

### Deliverables

- Reception can create a customer with one or more vehicles in under 1 minute.
- `docs/feature/customer/` and `docs/feature/vehicle/`.

### Exit criteria

- Search returns < 300ms p95 at the assumed data volume.
- Concurrency: two users editing the same customer surface a conflict cleanly.

### Effort

4 PW. Customer and Vehicle UIs are parallelizable (~1.5 PW saved).

---

## M3 — Repair Order and Workshop

**Goal:** the core workshop entity and its lifecycle.

### In scope

- Repair Order entity: customer_id, vehicle_id, opened_at, status, assigned_mechanic_id, priority, mileage_in, fuel_level_in, notes.
- Status workflow: `created → diagnosis → in_repair → finished → delivered`, with optional `paused_waiting_parts`, `paused_waiting_approval`. See [diagrams/state/repair_order.md](diagrams/state/repair_order.md).
- Labor lines (description, hours, hourly rate) and provisional parts lines (deduction happens in Inventory phase).
- Mechanic-facing tablet view: my repair orders, status update, time tracking start/stop, comment, photo upload.
- Workshop kanban or list view for reception/admin.
- PDF report generation for the OR.
- Linkage to Customer and Vehicle history.
- Audit on status transitions and mechanic reassignment.

### Deliverables

- A mechanic on a tablet can update status, log time, and attach a photo end-to-end.
- `docs/feature/repair_order/` and `docs/feature/workshop/`.

### Exit criteria

- Status transitions are validated against the state machine; illegal transitions return 422.
- Concurrent status updates from two devices produce a clean 409 conflict.

### Effort

5 PW. Tablet UI and workshop kanban are parallelizable (~1.5 PW saved).

---

## M4 — Inventory and Stock

**Goal:** parts catalog, stock movements, reservations, low-stock alerts.

### In scope

- Part (SKU) entity, category, supplier hints, unit of measure, purchase price, selling price.
- Stock movement entity: type (in, out, adjustment, reservation, release), quantity, unit_cost, ref (purchase_order_id or repair_order_id).
- Stock level view (computed via materialized view or aggregation table refreshed on movement).
- Reservation flow: repair order reserves parts; reservation released on completion or cancellation.
- Low-stock alerts (per-SKU threshold) with suggested supplier and reorder quantity.
- Stock valuation report (FIFO or weighted average — choose at M4 start, see [11_RISK_REGISTER.md](11_RISK_REGISTER.md)).
- Equivalent parts: many-to-many on Part.
- Integration with Repair Order (provisional → committed on `in_repair`).

### Deliverables

- Stock value is correct under random ordering of inputs/outputs/adjustments.
- `docs/feature/inventory/`.

### Exit criteria

- 1,000 stock movements processed under 10s in a load test.
- Stock cannot go negative without an explicit override and audit entry.

### Effort

4 PW. Catalog UI and movement engine are parallelizable (~1 PW saved).

---

## M5 — Quotation and Invoice

**Goal:** commercial documents, VAT, discounts, PDF, document numbering.

### In scope

- Quotation entity: header, lines (labor and parts), totals HT/TVA/TTC, discount, validity, status (draft, sent, approved, rejected, converted, archived).
- Invoice entity: header, lines, totals, discount, status (draft, issued, partially_paid, paid, overdue, cancelled).
- Document sequence service: monotonic, gap-free, per type, per year, per garage.
- VAT engine: lines carry VAT rate; totals computed with banker's rounding.
- Discount engine: percent or absolute, per line and per document.
- PDF generation with customizable template (header, footer, logo, legal mentions).
- Conversion: quotation → repair order, quotation → invoice, repair order → invoice.
- Credit notes (post-MVP polish, but model included now).
- Sending quotation by email with a signed approval link.
- See [diagrams/state/quotation.md](diagrams/state/quotation.md) and [diagrams/state/invoice.md](diagrams/state/invoice.md).

### Deliverables

- A complete chain: quote a customer, send the PDF, approve it via link, convert to invoice.
- `docs/feature/quotation/` and `docs/feature/invoice/`.

### Exit criteria

- PDF renders correctly on A4 with VAT breakdown and legal mentions.
- Document number cannot collide under concurrent issuance (load test with parallel issuers).

### Effort

5 PW. Quotation flow and invoice flow are partly parallelizable once the shared document engine is in place (~1 PW saved).

---

## M6 — Finance and Cash Register

**Goal:** payments, partial payments, deposits, cash closing, accounting export.

### In scope

- Payment entity: invoice_id, method (cash, card, transfer, cheque), amount, paid_at, reference.
- Partial payment: invoice paid_amount and outstanding recomputed; invoice status updated.
- Deposit (advance payment) linked to repair order; auto-deducted on final invoice.
- Cash session entity: opened_at, opened_by, closed_at, closed_by, expected_total, counted_total, difference.
- Cash session closing UI: tally per method, record physical count, compute difference, lock session.
- Sales journal and daily Z report PDF.
- Credit note workflow: cancel invoice issues a credit note when invoice is already paid or already exported.
- Refund workflow.
- See [diagrams/flowcharts/wf_cash_register_closing.md](diagrams/flowcharts/wf_cash_register_closing.md).

### Deliverables

- End-of-day cash closing produces a printable Z report and is stored.
- `docs/feature/finance/` and `docs/feature/cash_register/`.

### Exit criteria

- Money invariants hold: sum of payments per invoice equals `paid_amount`; sum of session payments equals session totals.
- Exported records can no longer be modified (only via credit note).

### Effort

4 PW. Cash session UI and payment recording are parallelizable (~1 PW saved).

---

## M7 — Suppliers and Purchasing

**Goal:** supplier management, RFQ, purchase orders, receptions, supplier invoices.

### In scope

- Supplier entity: name, contacts, payment terms, delivery delay, reliability score, history.
- Quotation request to one or many suppliers.
- Price comparison view (price, delay, history, reliability).
- Purchase Order: header, lines, status (draft, sent, partially_received, completed, cancelled).
- Reception flow: full, partial, or rejected; stock updated on receipt.
- Supplier invoice: linked to PO, three-way match (ordered, received, invoiced) with discrepancy flag.
- Price history per part per supplier.
- Equivalent parts mapping reused from M4.
- See [diagrams/state/purchase_order.md](diagrams/state/purchase_order.md).

### Deliverables

- A complete chain: low stock triggers PR, admin approves, PO sent, parts received, supplier invoice attached, stock and accounting updated.
- `docs/feature/supplier/` and `docs/feature/purchasing/`.

### Exit criteria

- Three-way match flags any line where ordered, received, invoiced disagree by more than tolerance.
- Reception updates stock atomically with movement record.

### Effort

4 PW. Catalog of suppliers and the PO flow are parallelizable (~1 PW saved).

---

## M8 — Notifications and Reminders

**Goal:** SMS/email out, templated, logged, scheduled.

### In scope

- Notification adapter interface; pluggable providers (SMTP for email, SMS gateway abstracted).
- Template entity with locale support.
- Trigger catalog: vehicle ready, unpaid invoice reminder (3 levels), maintenance due, technical inspection due, quotation expiring, payment received receipt.
- Delivery log with status (queued, sent, failed, bounced) and provider reference.
- Reminder scheduler (Celery or APScheduler) — choice in [08_TECH_STACK.md](08_TECH_STACK.md).
- Quiet hours configuration per garage.

### Deliverables

- Operator can trigger a manual notification; scheduled triggers fire on time.
- `docs/feature/notifications/`.

### Exit criteria

- A bounced or failed delivery is retried up to N times with backoff and visible in the log.
- No notification is sent during quiet hours.

### Effort

3 PW. Templates UI and scheduler are parallelizable (~0.5 PW saved).

---

## M9 — Digital Inspection and Media

**Goal:** mobile/tablet inspection, photos/videos, diagnostic report, customer approval.

### In scope

- Inspection template entity: sections (tires, brakes, battery, fluids, ...) and items per section with status enum (ok, attention, defective, not applicable) and notes.
- Inspection instance: linked to repair order, completed by mechanic on tablet.
- Photo/video upload with client-side compression and EXIF stripping.
- Diagnostic report PDF generated from completed inspection.
- Send PDF + signed approval link to customer; customer approves or refuses items; approved items convert to repair tasks on the OR.
- Additional discovery workflow: mechanic adds new items mid-repair, OR pauses, additional quotation issued.
- See [diagrams/flowcharts/wf_digital_inspection.md](diagrams/flowcharts/wf_digital_inspection.md).

### Deliverables

- A mechanic completes an inspection on tablet offline-tolerant, syncs when online, generates a PDF.
- `docs/feature/inspection/` and `docs/feature/media/`.

### Exit criteria

- Photos uploaded from a flaky network resume cleanly.
- Customer link is single-use and expires after CFG_QUOTATION_VALIDITY_DAYS.

### Effort

3 PW. Tablet UI and report generator are parallelizable (~0.5 PW saved).

---

## M10 — Reporting and Analytics

**Goal:** KPIs, dashboards, accounting export.

### In scope

- KPIs: revenue (global, period, mechanic), margins (per OR, per part), workshop occupancy, average repair duration, immobilization duration, unpaid invoices, outstanding amount, top customers, top suppliers, comeback rate, quotation conversion.
- Dashboard with charts; period selector; CSV/Excel export.
- Accounting export: sales journal, payment journal, supplier purchases, VAT summary. Format chosen at M10 start (Sage, Cegid, EBP, or generic CSV). Export status: exported records locked.
- Scheduled snapshots (daily) for trend charts.

### Deliverables

- Admin sees a live dashboard updated every CFG_KPI_REFRESH_INTERVAL_SECONDS.
- An accountant exports a clean month-end file.
- `docs/feature/reporting/`.

### Exit criteria

- KPIs recompute under 5s at assumed data volume.
- Export file imports cleanly into the target accounting software (manual verification).

### Effort

4 PW. KPI service and dashboard UI are parallelizable (~1 PW saved).

---

## M11 — Document Management (GED) and OCR

**Goal:** structured archive of documents and PaddleOCR-driven ingestion of registration cards and IDs.

### In scope

- Document entity already exists from M2; M11 adds categories (registration card, ID, insurance, accident photo, repair attachment, invoice, supplier invoice).
- Object storage backend (S3-compatible) with lifecycle rules (hot → archive after CFG_PHOTO_ARCHIVE_AFTER_DAYS).
- Full-text searchable metadata.
- **PaddleOCR 3.x** pipeline: upload → OCR → extract structured fields → human review if confidence < CFG_OCR_CONFIDENCE_THRESHOLD → confirm → write to customer/vehicle.
- Supported document types in v1: registration card (carte grise) and national ID. Others added incrementally.
- Async processing with progress feedback.

### Deliverables

- Upload a scanned registration card; system pre-fills a vehicle form; user confirms; record is created.
- `docs/feature/ged/` and `docs/feature/ocr/`.

### Exit criteria

- OCR confidence threshold is tunable per field, not just per document.
- Below-threshold extractions never auto-write; they always require human confirmation.
- OCR errors are logged with the original image reference for audit.

### Effort

4 PW. OCR pipeline and document UI are parallelizable (~1 PW saved).

---

## M12 — Multi-garage and Hardening

**Goal:** turn the single-tenant deployment into a multi-garage capable one, and harden for production.

### In scope

- Garage entity with name, address, fiscal info, currency, locale, timezone.
- Tenant resolution: every authenticated request resolves to one `garage_id`; super-admin role can switch.
- Row-level filtering verified across every module (a single missing filter is a critical defect at this stage).
- Per-garage configuration (CFG_*).
- Cross-garage admin reporting (super-admin only).
- Performance hardening: query review, index review, N+1 audit, caching where safe.
- Security audit: OWASP ASVS L2 checklist, dependency scan, secret scan, penetration smoke test.
- Backup and restore drill: take a backup, restore into a clean environment, verify integrity.
- Load test at 2x assumed peak.
- Final documentation and operator runbook.

### Deliverables

- Two garages share one deployment; data is fully isolated; super-admin can audit both.
- `docs/feature/multi_garage/` and `docs/feature/hardening/`.

### Exit criteria

- Zero cross-tenant data leaks in an automated isolation test.
- Recovery Time Objective (RTO) and Recovery Point Objective (RPO) measured and documented; see [10_DEPLOYMENT_DEVOPS.md](10_DEPLOYMENT_DEVOPS.md).

### Effort

4 PW. Mostly serial because hardening must happen on a stable codebase.

---

## Parallelism matrix

The simplified version: from M2 onward, two engineers can run two trunks in parallel. The shared blockers are the audit log, document numbering, money/VAT engine, and PDF templating — these should be owned by one engineer to avoid divergence.

| Phase | Sequential PW | Parallel savings | Net PW with 2 engineers |
|-------|---------------|------------------|--------------------------|
| M0    | 3             | 0                | 3                        |
| M1    | 3             | 0                | 3                        |
| M2    | 4             | 1.5              | 2.5                      |
| M3    | 5             | 1.5              | 3.5                      |
| M4    | 4             | 1                | 3                        |
| M5    | 5             | 1                | 4                        |
| M6    | 4             | 1                | 3                        |
| M7    | 4             | 1                | 3                        |
| M8    | 3             | 0.5              | 2.5                      |
| M9    | 3             | 0.5              | 2.5                      |
| M10   | 4             | 1                | 3                        |
| M11   | 4             | 1                | 3                        |
| M12   | 4             | 0                | 4                        |
| Total | 50            | 9.5              | 40.5                     |

With two engineers and disciplined parallel execution, the project lands around **20–22 calendar weeks** for an experienced pair, or **30 calendar weeks** at a more conservative pace including unplanned work and buffers.
