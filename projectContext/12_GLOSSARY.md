# 12 — Glossary

Domain and technical terms used across the planning corpus. Where a term has a French equivalent that appears in the Cahier des Charges, both are listed.

---

## Business / domain

| Term                              | Definition                                                                                                |
|-----------------------------------|------------------------------------------------------------------------------------------------------------|
| Cahier des Charges                | Functional specification document (the French source documents in this folder).                            |
| Garage / Workshop                 | The physical site where vehicles are received, inspected, and repaired.                                    |
| GMS / DMS                         | Garage Management System / Dealer Management System; the category Xpert-ERP belongs to.                    |
| Repair Order (OR)                 | "Ordre de Réparation". The central operational entity for a single repair job on a vehicle.                |
| Quotation                         | "Devis". A pre-invoice proposal sent to the customer for approval.                                         |
| Invoice                           | "Facture". The legally binding commercial document for completed work and parts.                           |
| Credit Note                       | "Avoir". A document that cancels or refunds part of an invoice.                                            |
| Delivery Note                     | "Bon de livraison". A document acknowledging parts handover.                                               |
| Warranty                          | "Garantie". Coverage extended to a repair or a part.                                                       |
| Purchase Request (PR)             | "Demande d'achat". An internal request to procure parts.                                                   |
| Purchase Order (PO)               | "Bon de commande fournisseur". A confirmed order sent to a supplier.                                       |
| Reception                         | The act of receiving ordered parts from a supplier.                                                        |
| Supplier Invoice                  | "Facture fournisseur". An invoice from the supplier to the garage.                                         |
| Three-way match                   | Cross-check of ordered quantities, received quantities, and invoiced quantities for discrepancies.         |
| Cash Session                      | A cashier's open period during which payments are recorded; closed at end of day.                          |
| Cash Closing                      | "Clôture de caisse". The end-of-day reconciliation of physical cash and recorded payments.                 |
| Z Report                          | The end-of-day cash closing report.                                                                       |
| Deposit / Acompte                 | An advance payment from a customer, deducted on final invoice.                                             |
| Outstanding balance               | "Encours". The total amount owed by a customer at a point in time.                                         |
| Credit limit                      | The maximum outstanding balance permitted for a customer before sales are blocked.                         |
| Reminder ladder                   | The escalating sequence of unpaid-invoice reminders.                                                       |
| Comeback                          | A vehicle returning shortly after a previous repair for the same or related issue.                         |
| Immobilization duration           | The total time a vehicle is held in the workshop on an OR; a workshop KPI.                                 |
| Digital Vehicle Inspection        | A checklist-based inspection performed on a tablet, with photos and a generated diagnostic report.         |
| GED                               | "Gestion Électronique de Documents". Electronic Document Management; here, structured archive + OCR.       |
| OCR                               | Optical Character Recognition; PaddleOCR 3.x in this project.                                              |
| KPI                               | Key Performance Indicator; revenue, margin, occupancy, etc.                                                |
| RBAC                              | Role-Based Access Control.                                                                                |
| Tenant / Garage tenancy           | The isolation boundary in multi-garage deployments; one garage_id per tenant.                              |
| Fleet / Company customer          | A customer that is a company and owns multiple vehicles.                                                   |

---

## Statuses (selected)

| Entity         | Status             | Meaning                                                              |
|----------------|--------------------|-----------------------------------------------------------------------|
| Repair Order   | created            | Reception has opened the OR; no diagnosis yet.                       |
| Repair Order   | diagnosis          | Mechanic is diagnosing.                                              |
| Repair Order   | in_repair          | Work is underway.                                                   |
| Repair Order   | paused_parts       | Waiting for parts.                                                  |
| Repair Order   | paused_approval    | Waiting for customer approval (additional repair).                  |
| Repair Order   | finished           | Work complete, awaiting delivery.                                   |
| Repair Order   | delivered          | Vehicle returned to customer.                                       |
| Repair Order   | cancelled          | OR closed without delivery.                                         |
| Quotation      | draft              | Editable in-place.                                                  |
| Quotation      | sent               | Sent to customer; awaiting response.                                |
| Quotation      | approved           | Customer approved.                                                  |
| Quotation      | rejected           | Customer declined.                                                  |
| Quotation      | converted          | Converted to invoice or OR.                                         |
| Quotation      | archived           | No further action.                                                  |
| Quotation      | expired            | Past `valid_until`.                                                 |
| Invoice        | draft              | Editable; no number assigned.                                       |
| Invoice        | issued             | Number assigned; immutable except via credit note.                  |
| Invoice        | partially_paid     | Some payments received; balance > 0.                                |
| Invoice        | paid               | Balance == 0.                                                       |
| Invoice        | overdue            | Past `due_at` and unpaid or partially paid.                         |
| Invoice        | cancelled          | Cancelled (pre-issue) or via credit note (post-issue).              |
| Purchase Order | draft              | Editable; not sent.                                                 |
| Purchase Order | sent               | Sent to supplier.                                                   |
| Purchase Order | partially_received | At least one line partially received.                               |
| Purchase Order | completed          | Fully received.                                                     |
| Purchase Order | cancelled          | Cancelled.                                                          |

---

## Technical

| Term                       | Definition                                                                                                |
|----------------------------|------------------------------------------------------------------------------------------------------------|
| Modular monolith           | One deployable process with strict internal module boundaries; alternative to microservices.              |
| Domain event               | An in-process pub/sub message representing a business fact (e.g., `InvoicePaid`).                          |
| Outbox pattern             | Persisting a domain event in the DB transaction so it can be published reliably out-of-band.              |
| Optimistic concurrency     | Each row has a `version`; updates must match the version held by the client.                              |
| Idempotency key            | Header attached to write requests so duplicates are safe to retry.                                        |
| Document sequence          | Numbered series per document type, per year, per garage; gap-free.                                        |
| Money minor units          | Currency amount stored as integer in the smallest unit (cents/centimes).                                  |
| Banker's rounding          | "Round half to even"; preferred for financial totals.                                                     |
| Materialized view          | A precomputed query result stored as a table for fast reads; refreshed on data change.                    |
| Soft delete                | Marking a row with `deleted_at` rather than physical deletion.                                            |
| WAL                        | Postgres Write-Ahead Log; the basis of point-in-time recovery.                                           |
| pg_basebackup              | Tool to take a base backup of a Postgres cluster.                                                          |
| RPO                        | Recovery Point Objective; maximum acceptable data loss measured in time.                                  |
| RTO                        | Recovery Time Objective; maximum acceptable downtime to restore service.                                  |
| SLA                        | Service Level Agreement; the externally-promised availability target.                                     |
| SSE                        | Server-Sent Events; one-way realtime push from server to browser.                                         |
| JWT                        | JSON Web Token; carries identity and claims.                                                              |
| Argon2id                   | Modern password hashing algorithm; the default for this project.                                          |
| OWASP ASVS                 | Application Security Verification Standard; the security baseline aimed at L2.                            |
| CSP                        | Content Security Policy; an HTTP header restricting what the browser may execute.                         |
| C4 model                   | A way to describe software architecture at four levels (context, container, component, code).             |
| TanStack Query             | The chosen server-state library for the React frontend.                                                   |
| WeasyPrint                 | The chosen PDF generation library; renders from HTML/CSS.                                                 |
| PaddleOCR                  | The chosen OCR engine (mandated, v3.x).                                                                   |
| Alembic                    | The migrations tool for SQLAlchemy.                                                                       |
| Pydantic v2                | The validation library used for request and response schemas.                                             |
| Vite                       | The dev server and bundler for the React app.                                                             |
| Playwright                 | The end-to-end browser test framework.                                                                    |
| k6                         | The performance testing tool.                                                                             |

---

## Acronyms

| Acronym | Expansion                                |
|---------|------------------------------------------|
| CRM     | Customer Relationship Management         |
| ERP     | Enterprise Resource Planning             |
| GMS     | Garage Management System                 |
| DMS     | Dealer Management System                 |
| OR      | Ordre de Réparation (Repair Order)       |
| PO      | Purchase Order                           |
| PR      | Purchase Request                         |
| RBAC    | Role-Based Access Control                |
| TVA     | Taxe sur la Valeur Ajoutée (French VAT)  |
| VAT     | Value Added Tax                          |
| GED     | Gestion Électronique de Documents        |
| TPE     | Terminal de Paiement Électronique        |
| VIN     | Vehicle Identification Number            |
| KPI     | Key Performance Indicator                |
| RPO     | Recovery Point Objective                 |
| RTO     | Recovery Time Objective                  |
| SLA     | Service Level Agreement                  |
| SSE     | Server-Sent Events                       |
| JWT     | JSON Web Token                           |
