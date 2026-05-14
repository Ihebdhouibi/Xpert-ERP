# 06 — RBAC Design

Role-Based Access Control specification for Xpert-ERP. The system is permission-driven: roles aggregate permissions; permissions gate endpoints and UI elements. Roles are mutable, permissions are a fixed catalog (versioned).

---

## 1. Roles

Seed roles. Admins can create additional roles by combining permissions.

| Role code             | Display name              | Notes                                                              |
|-----------------------|---------------------------|--------------------------------------------------------------------|
| `super_admin`         | Super Administrator       | Cross-garage. Set at platform install only. No business operations.|
| `admin`               | Administrator             | Per-garage admin. Can manage users, settings, finance, all modules.|
| `secretary`           | Secretary / Reception     | CRM, quotations, invoices, cash register, suppliers, scheduling.   |
| `mechanic`            | Mechanic                  | Workshop operations: inspection, status updates, time tracking.    |
| `inventory_manager`   | Inventory Manager         | Parts, stock movements, reception, low-stock alerts.               |
| `accountant`          | Accountant                | Read-only over finance with accounting export rights.              |
| `read_only`           | Read Only                 | Reporting and read views only. Useful for auditors and trainees.   |

A user can hold **multiple roles**; effective permissions are the union.

---

## 2. Permission catalog

Permission codes follow `<resource>.<action>` and `<resource>.<scope>.<action>` where scope matters. Actions: `read`, `create`, `update`, `delete`, `approve`, `export`, `admin`.

### 2.1 Identity, security, system

| Code                          | Purpose                                       |
|-------------------------------|-----------------------------------------------|
| `system.settings.read`        | View garage settings                          |
| `system.settings.update`      | Change garage settings (CFG_*)                |
| `system.backup.manage`        | Trigger backup, view backup status            |
| `audit.read`                  | View audit log                                |
| `users.read`                  | List and view users                           |
| `users.create`                | Create user                                   |
| `users.update`                | Update user details                           |
| `users.deactivate`            | Disable user                                  |
| `roles.read`                  | View roles and permissions                    |
| `roles.assign`                | Assign or revoke roles                        |
| `roles.manage`                | Create or edit roles                          |

### 2.2 CRM

| Code                          | Purpose                                       |
|-------------------------------|-----------------------------------------------|
| `customer.read`               | View customers                                |
| `customer.create`             | Create customer                               |
| `customer.update`             | Edit customer                                 |
| `customer.delete`             | Soft delete                                   |
| `customer.credit_limit.update`| Change credit limit                           |
| `customer.balance.read`       | View ledger and outstanding                   |
| `customer.merge`              | Merge duplicates                              |

### 2.3 Vehicle

| Code                          | Purpose                                       |
|-------------------------------|-----------------------------------------------|
| `vehicle.read`                | View                                          |
| `vehicle.create`              | Create                                        |
| `vehicle.update`              | Edit                                          |
| `vehicle.delete`              | Soft delete                                   |

### 2.4 Repair Order and Workshop

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `repair_order.read`               | View                                          |
| `repair_order.create`             | Create                                        |
| `repair_order.update`             | Edit details                                  |
| `repair_order.delete`             | Soft delete                                   |
| `repair_order.assign`             | Assign or reassign mechanic                   |
| `repair_order.transition`         | Change status (general)                       |
| `repair_order.transition.cancel`  | Move to cancelled                             |
| `repair_order.line.manage`        | Add/edit/remove labor and part lines          |
| `repair_order.time_entry.manage`  | Start/stop time tracking                      |
| `repair_order.media.upload`       | Attach photos and videos                      |
| `inspection.read`                 | View inspections                              |
| `inspection.execute`              | Perform inspection (tablet workflow)          |
| `inspection.template.manage`      | Create or edit templates                      |

### 2.5 Inventory

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `part.read`                       | View parts                                    |
| `part.create`                     | Create part                                   |
| `part.update`                     | Edit part                                     |
| `part.delete`                     | Deactivate (soft delete) part                 |
| `stock.movement.read`             | View movements                                |
| `stock.movement.create`           | Record movement                               |
| `stock.movement.adjust`           | Manual adjustment with reason                 |
| `stock.reservation.manage`        | Reserve or release stock                      |
| `stock.alert.read`                | View low-stock alerts                         |

### 2.6 Quotation and Invoice

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `quotation.read`                  | View                                          |
| `quotation.create`                | Create                                        |
| `quotation.update`                | Edit                                          |
| `quotation.send`                  | Send to customer                              |
| `quotation.approve_on_behalf`     | Internally mark approved                      |
| `quotation.convert`               | Convert to invoice or repair order            |
| `invoice.read`                    | View                                          |
| `invoice.create`                  | Create                                        |
| `invoice.update`                  | Edit (draft only)                             |
| `invoice.issue`                   | Issue (locks document number)                 |
| `invoice.cancel`                  | Cancel or issue credit note                   |
| `invoice.discount.apply`          | Apply discount above standard threshold       |
| `invoice.credit_limit.override`   | Override customer credit limit block          |

### 2.7 Payment and Cash Register

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `payment.read`                    | View payments                                 |
| `payment.record`                  | Record payment                                |
| `payment.cancel`                  | Cancel payment (admin)                        |
| `deposit.record`                  | Record deposit                                |
| `cash_session.open`               | Open cash session                             |
| `cash_session.close`              | Close cash session                            |
| `cash_session.read`               | View session details                          |
| `refund.execute`                  | Execute refund                                |

### 2.8 Supplier and Purchasing

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `supplier.read`                   | View                                          |
| `supplier.create`                 | Create                                        |
| `supplier.update`                 | Edit                                          |
| `purchase_request.create`         | Create PR                                     |
| `purchase_order.create`           | Create PO                                     |
| `purchase_order.approve`          | Approve PR/PO                                 |
| `purchase_order.send`             | Send to supplier                              |
| `purchase_order.reception.record` | Record reception                              |
| `supplier_invoice.record`         | Attach supplier invoice                       |

### 2.9 Notifications

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `notification.read`               | View delivery log                             |
| `notification.send`               | Send manual notification                      |
| `notification.template.manage`    | Edit templates                                |

### 2.10 Documents (GED) and OCR

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `document.read`                   | View document metadata                        |
| `document.download`               | Download via signed URL                       |
| `document.upload`                 | Upload                                        |
| `document.delete`                 | Soft delete                                   |
| `ocr.execute`                     | Run OCR on a document                         |
| `ocr.confirm`                     | Confirm OCR extraction and apply              |

### 2.11 Reporting and Export

| Code                              | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `reporting.dashboard.read`        | KPI dashboard                                 |
| `reporting.revenue.read`          | Revenue reports                               |
| `reporting.workshop.read`         | Workshop KPI                                  |
| `reporting.inventory.read`        | Inventory KPI                                 |
| `reporting.accounting.export`     | Accounting export                             |

---

## 3. Role-to-permission matrix (defaults)

`A` = always, `R` = read-only flavor, `-` = no, `O` = optional (typically granted in small garages where the secretary doubles as inventory or accountant).

| Permission                              | super_admin | admin | secretary | mechanic | inventory_manager | accountant | read_only |
|-----------------------------------------|-------------|-------|-----------|----------|-------------------|------------|-----------|
| system.settings.read                    | A           | A     | R         | -        | -                 | R          | R         |
| system.settings.update                  | A           | A     | -         | -        | -                 | -          | -         |
| system.backup.manage                    | A           | A     | -         | -        | -                 | -          | -         |
| audit.read                              | A           | A     | -         | -        | -                 | R          | R         |
| users.read                              | A           | A     | -         | -        | -                 | -          | R         |
| users.create / update / deactivate      | A           | A     | -         | -        | -                 | -          | -         |
| roles.assign / manage                   | A           | A     | -         | -        | -                 | -          | -         |
| customer.read                           | A           | A     | A         | R        | R                 | A          | R         |
| customer.create / update                | A           | A     | A         | -        | -                 | -          | -         |
| customer.credit_limit.update            | A           | A     | -         | -        | -                 | -          | -         |
| vehicle.read                            | A           | A     | A         | A        | R                 | A          | R         |
| vehicle.create / update                 | A           | A     | A         | -        | -                 | -          | -         |
| repair_order.read                       | A           | A     | A         | A        | A                 | A          | R         |
| repair_order.create / update            | A           | A     | A         | O        | -                 | -          | -         |
| repair_order.assign                     | A           | A     | A         | -        | -                 | -          | -         |
| repair_order.transition                 | A           | A     | A         | A        | -                 | -          | -         |
| repair_order.delete / cancel            | A           | A     | -         | -        | -                 | -          | -         |
| repair_order.line.manage                | A           | A     | A         | O        | -                 | -          | -         |
| repair_order.time_entry.manage          | A           | A     | -         | A        | -                 | -          | -         |
| repair_order.media.upload               | A           | A     | A         | A        | -                 | -          | -         |
| inspection.execute                      | A           | A     | -         | A        | -                 | -          | -         |
| inspection.template.manage              | A           | A     | -         | -        | -                 | -          | -         |
| part.read                               | A           | A     | A         | A        | A                 | A          | R         |
| part.create / update                    | A           | A     | O         | -        | A                 | -          | -         |
| stock.movement.create / adjust          | A           | A     | -         | -        | A                 | -          | -         |
| stock.reservation.manage                | A           | A     | -         | -        | A                 | -          | -         |
| quotation.read                          | A           | A     | A         | R        | -                 | A          | R         |
| quotation.create / update / send        | A           | A     | A         | -        | -                 | -          | -         |
| quotation.convert                       | A           | A     | A         | -        | -                 | -          | -         |
| invoice.read                            | A           | A     | A         | R        | -                 | A          | R         |
| invoice.create / update / issue         | A           | A     | A         | -        | -                 | -          | -         |
| invoice.cancel                          | A           | A     | -         | -        | -                 | -          | -         |
| invoice.discount.apply (>threshold)     | A           | A     | -         | -        | -                 | -          | -         |
| invoice.credit_limit.override           | A           | A     | -         | -        | -                 | -          | -         |
| payment.record                          | A           | A     | A         | -        | -                 | -          | -         |
| payment.cancel                          | A           | A     | -         | -        | -                 | -          | -         |
| deposit.record                          | A           | A     | A         | -        | -                 | -          | -         |
| cash_session.open / close               | A           | A     | A         | -        | -                 | -          | -         |
| refund.execute                          | A           | A     | -         | -        | -                 | -          | -         |
| supplier.read                           | A           | A     | A         | -        | A                 | A          | R         |
| supplier.create / update                | A           | A     | A         | -        | A                 | -          | -         |
| purchase_request.create                 | A           | A     | A         | -        | A                 | -          | -         |
| purchase_order.create / send            | A           | A     | A         | -        | A                 | -          | -         |
| purchase_order.approve                  | A           | A     | -         | -        | -                 | -          | -         |
| purchase_order.reception.record         | A           | A     | -         | -        | A                 | -          | -         |
| supplier_invoice.record                 | A           | A     | A         | -        | -                 | -          | -         |
| notification.read / send                | A           | A     | A         | -        | -                 | -          | R         |
| notification.template.manage            | A           | A     | -         | -        | -                 | -          | -         |
| document.upload / download              | A           | A     | A         | A        | A                 | A          | R         |
| document.delete                         | A           | A     | -         | -        | -                 | -          | -         |
| ocr.execute / confirm                   | A           | A     | A         | A        | A                 | -          | -         |
| reporting.dashboard.read                | A           | A     | A         | R        | R                 | A          | R         |
| reporting.accounting.export             | A           | A     | -         | -        | -                 | A          | -         |

The "O" cells reflect the project brief: in small garages, the secretary may also handle inventory or finance, and a mechanic may add lines. These are toggleable per-user permission grants on top of the role.

---

## 4. Special rules

- **Credit limit threshold modification** (`customer.credit_limit.update`): admin-only, per the Cahier des Charges.
- **Override credit limit block** (`invoice.credit_limit.override`): admin-only; produces a high-severity audit entry.
- **Cancel invoice already paid or exported**: requires `invoice.cancel` AND issuing a credit note; the underlying invoice is never silently mutated.
- **Self-service prohibitions**: a user cannot edit their own roles, deactivate themselves, or close a cash session they did not open (without admin override).
- **Mechanic visibility**: a mechanic only sees repair orders assigned to them or unassigned in their queue; a config flag opens the full list to all mechanics in small workshops.
- **Audit log** is read-only; nothing in the system can mutate or delete entries except the retention job.

---

## 5. UI permission gate

A `<PermissionGate code="invoice.issue">` component wraps any UI element that triggers a permission-bound action. It either renders the children, hides them, or renders a tooltip "you do not have permission" element, depending on the variant. Backend enforcement remains authoritative — UI gating is for usability, not security.

---

## 6. Permission lifecycle

- Catalog is versioned. New permission codes are added in additive migrations.
- A removed code is **deprecated** for at least one major version before deletion; in the interim, the role-permission link is hidden in UI and the backend treats it as no-op.
- Adding a new permission to an existing role is an explicit migration with a description; the migration writes an audit log entry per role updated.

---

## 7. Authentication policy (CFG_PASSWORD_POLICY default)

- Minimum 12 characters.
- At least one of each: upper, lower, digit, symbol.
- Cannot match any of the last 5 passwords.
- 5 failed attempts → 15-minute lockout, with progressive backoff after that.
- TOTP-based 2FA optional, mandatory for admin and super_admin roles (target: M12 if not earlier).
