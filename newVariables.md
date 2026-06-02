# New Variables — Milestones 7–10 (Issues 36–46)

> Generated from branch `m7-m10`. All variables listed below are new additions not present in `develop`. Use this reference to avoid naming conflicts when starting Milestone 11.

---

### 1. Supplier (Issue 36)

**Python Model: `Supplier` (`backend/app/modules/supplier/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `SupplierStatus` | Python Enum | Two-value enum: `active` / `inactive`; stored as `String(20)` in DB |
| `SupplierStatus.active` | Enum member | Active supplier status value |
| `SupplierStatus.inactive` | Enum member | Inactive supplier status value |
| `Supplier` | SQLAlchemy Model | ORM class mapped to `supplier` table |
| `Supplier.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `Supplier.public_id` | Model Column (UUID) | Externally-facing UUID identifier |
| `Supplier.garage_id` | Model Column (BigInteger) | FK-like tenant scoping column (no FK constraint) |
| `Supplier.name` | Model Column (String 255) | Supplier company or person name |
| `Supplier.email` | Model Column (String 255, nullable) | Contact email |
| `Supplier.phone` | Model Column (String 50, nullable) | Contact phone number |
| `Supplier.address` | Model Column (Text, nullable) | Postal address |
| `Supplier.payment_terms_days` | Model Column (Integer, nullable) | Net payment terms in days |
| `Supplier.average_delivery_days` | Model Column (Integer, nullable) | Historical average lead time in days |
| `Supplier.reliability_score` | Model Column (Numeric 5,2, nullable) | Percentage score 0–100 for on-time delivery |
| `Supplier.status` | Model Column (String 20) | Stores `SupplierStatus` enum value |
| `Supplier.version` | Model Column (Integer) | Optimistic-lock counter |
| `Supplier.created_at` | Model Column (DateTime TZ) | Row creation timestamp |
| `Supplier.updated_at` | Model Column (DateTime TZ) | Last update timestamp |
| `Supplier.deleted_at` | Model Column (DateTime TZ, nullable) | Soft-delete timestamp |
| `Supplier.prices` | ORM Relationship | One-to-many to `SupplierPartPrice` |
| `SupplierPartPrice` | SQLAlchemy Model | ORM class mapped to `supplier_part_price` table |
| `SupplierPartPrice.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `SupplierPartPrice.supplier_id` | Model Column (BigInteger FK) | Foreign key to `supplier.id` |
| `SupplierPartPrice.part_id` | Model Column (BigInteger FK) | Foreign key to `part.id` |
| `SupplierPartPrice.unit_price_minor` | Model Column (BigInteger) | Unit price in smallest currency unit (centimes) |
| `SupplierPartPrice.currency` | Model Column (String 3) | ISO-4217 currency code, default `MAD` |
| `SupplierPartPrice.effective_from` | Model Column (Date) | Date from which this price is valid |
| `SupplierPartPrice.effective_to` | Model Column (Date, nullable) | Date until which this price is valid; null means current |
| `SupplierPartPrice.created_at` | Model Column (DateTime TZ) | Row creation timestamp |

**TypeScript API (`frontend/src/lib/supplierApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `SupplierStatus` | TS type alias | `'active' \| 'inactive'` union type |
| `Supplier` | TS Interface | Full supplier object returned from API |
| `Supplier.id` | Interface property (string) | Public UUID of the supplier |
| `Supplier.name` | Interface property (string) | Supplier name |
| `Supplier.email` | Interface property (string\|null) | Contact email |
| `Supplier.phone` | Interface property (string\|null) | Contact phone |
| `Supplier.address` | Interface property (string\|null) | Postal address |
| `Supplier.payment_terms_days` | Interface property (number\|null) | Net payment terms in days |
| `Supplier.average_delivery_days` | Interface property (number\|null) | Average lead time in days |
| `Supplier.reliability_score` | Interface property (number\|null) | Reliability percentage score |
| `Supplier.status` | Interface property (SupplierStatus) | Current status |
| `Supplier.version` | Interface property (number) | Optimistic-lock version |
| `Supplier.created_at` | Interface property (string) | ISO-8601 creation timestamp |
| `Supplier.updated_at` | Interface property (string) | ISO-8601 update timestamp |
| `SupplierListResponse` | TS Interface | Paginated list of suppliers |
| `SupplierListResponse.items` | Interface property (Supplier[]) | Array of suppliers on the current page |
| `SupplierListResponse.total` | Interface property (number) | Total matching supplier count |
| `SupplierListResponse.page` | Interface property (number) | Current page number |
| `SupplierListResponse.page_size` | Interface property (number) | Page size |
| `SupplierCreatePayload` | TS Interface | Request body for creating a supplier |
| `SupplierUpdatePayload` | TS Interface | Request body for updating a supplier (includes `version` + optional `status`) |
| `PriceEntry` | TS Interface | Single supplier-part price history record |
| `PriceEntry.id` | Interface property (number) | Numeric ID of the price record |
| `PriceEntry.part_public_id` | Interface property (string) | UUID of the associated part |
| `PriceEntry.part_name` | Interface property (string) | Display name of the part |
| `PriceEntry.part_sku` | Interface property (string) | SKU code of the part |
| `PriceEntry.unit_price_minor` | Interface property (number) | Price in centimes |
| `PriceEntry.currency` | Interface property (string) | ISO-4217 currency code |
| `PriceEntry.effective_from` | Interface property (string) | Start date of the price (ISO date) |
| `PriceEntry.effective_to` | Interface property (string\|null) | End date of the price; null = current |
| `PriceEntry.created_at` | Interface property (string) | Creation timestamp |
| `PriceAddPayload` | TS Interface | Request body for adding a new price entry |
| `PriceAddPayload.part_public_id` | Interface property (string) | UUID of the part to price |
| `PriceAddPayload.unit_price_minor` | Interface property (number) | Price in centimes |
| `PriceAddPayload.currency` | Interface property (string) | Currency code |
| `PriceAddPayload.effective_from` | Interface property (string) | Effective start date |
| `PriceComparisonItem` | TS Interface | One row in the cross-supplier price comparison |
| `PriceComparisonItem.supplier_public_id` | Interface property (string) | UUID of the supplier |
| `PriceComparisonItem.supplier_name` | Interface property (string) | Supplier display name |
| `PriceComparisonItem.average_delivery_days` | Interface property (number\|null) | Lead time |
| `PriceComparisonItem.reliability_score` | Interface property (number\|null) | Reliability score |
| `PriceComparisonItem.unit_price_minor` | Interface property (number) | Price in centimes |
| `PriceComparisonItem.currency` | Interface property (string) | Currency code |
| `PriceComparisonItem.effective_from` | Interface property (string) | Price start date |
| `PriceComparisonItem.effective_to` | Interface property (string\|null) | Price end date |
| `STATUS_LABELS` | TS Constant (`Record<SupplierStatus, string>`) | French display labels for supplier statuses |
| `supplierApi` | TS Constant (object) | API client object with methods: `list`, `create`, `get`, `update`, `delete`, `listPrices`, `addPrice`, `getPartPrices` |

**React State (`frontend/src/pages/suppliers/SupplierPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `STATUS_COLOR` | TS Constant (`Record<SupplierStatus, 'success'\|'default'>`) | MUI chip color mapping for supplier statuses |
| `tab` / `setTab` | React State (number) | Active tab index (0=list, 1=price comparison) |
| `search` / `setSearch` | React State (string) | Full-text search input value |
| `statusFilter` / `setStatusFilter` | React State (SupplierStatus\|'') | Active status filter in the list |
| `formOpen` / `setFormOpen` | React State (boolean) | Controls create/edit dialog visibility |
| `editTarget` / `setEditTarget` | React State (Supplier\|null) | Supplier currently being edited |
| `priceDialogSupplier` / `setPriceDialogSupplier` | React State (Supplier\|null) | Supplier whose price history is open |
| `deleteConfirm` / `setDeleteConfirm` | React State (Supplier\|null) | Supplier pending soft-delete confirmation |
| `partSearch` / `setPartSearch` | React State (string) | Part search string in price-add form |
| `selectedPartId` / `setSelectedPartId` | React State (string) | Selected part public UUID in price-add form |
| `priceMinor` / `setPriceMinor` | React State (string) | Price input value in centimes (string for the input) |
| `currency` / `setCurrency` | React State (string) | Currency input in price-add form |
| `effectiveFrom` / `setEffectiveFrom` | React State (string) | Effective-from date in price-add form |
| `addError` / `setAddError` | React State (string) | Error message in price-add form |
| `selectedPart` / `setSelectedPart` | React State (PartSummary\|null) | Part selected in the price comparison tab |
| `atDate` / `setAtDate` | React State (string) | Historical date for price comparison lookup |
| `['suppliers', ...]` | React Query key | Query key for the supplier list |
| `['supplier-prices', supplier?.id]` | React Query key | Query key for a supplier's price history |
| `['parts', partSearch]` | React Query key | Query key for part search results |
| `['parts-search', partSearch]` | React Query key | Query key for part search in price comparison |
| `['price-comparison', selectedPart?.id, atDate]` | React Query key | Query key for cross-supplier price comparison |

---

### 2. Purchase Order (Issue 37)

**Python Model (`backend/app/modules/purchase_order/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `PurchaseOrderStatus` | Python Enum | Five-value status machine: `draft`, `sent`, `partially_received`, `completed`, `cancelled` |
| `PurchaseOrderStatus.draft` | Enum member | Initial state before sending |
| `PurchaseOrderStatus.sent` | Enum member | Sent to supplier, awaiting delivery |
| `PurchaseOrderStatus.partially_received` | Enum member | Some lines received, not all |
| `PurchaseOrderStatus.completed` | Enum member | All lines fully received |
| `PurchaseOrderStatus.cancelled` | Enum member | Cancelled order |
| `POMatchFlag` | Python Enum | Three-way match flag per line: `ok`, `qty_mismatch`, `inv_mismatch` |
| `POMatchFlag.ok` | Enum member | Quantities and invoice match |
| `POMatchFlag.qty_mismatch` | Enum member | Received quantity differs from ordered |
| `POMatchFlag.inv_mismatch` | Enum member | Invoiced quantity differs from received |
| `PurchaseOrder` | SQLAlchemy Model | ORM class mapped to `purchase_order` table |
| `PurchaseOrder.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `PurchaseOrder.public_id` | Model Column (UUID) | Externally-facing UUID |
| `PurchaseOrder.garage_id` | Model Column (BigInteger) | Tenant scoping column |
| `PurchaseOrder.supplier_id` | Model Column (BigInteger FK) | Foreign key to `supplier.id` |
| `PurchaseOrder.doc_number` | Model Column (String 50, nullable) | Human-readable PO document number |
| `PurchaseOrder.status` | Model Column (String 30) | Current PO status |
| `PurchaseOrder.expected_delivery_date` | Model Column (Date, nullable) | Planned delivery date |
| `PurchaseOrder.notes` | Model Column (Text, nullable) | Free-text notes |
| `PurchaseOrder.total_ht` | Model Column (BigInteger) | Order total excluding tax in centimes |
| `PurchaseOrder.version` | Model Column (Integer) | Optimistic-lock counter |
| `PurchaseOrder.created_at` | Model Column (DateTime TZ) | Creation timestamp |
| `PurchaseOrder.updated_at` | Model Column (DateTime TZ) | Last update timestamp |
| `PurchaseOrder.deleted_at` | Model Column (DateTime TZ, nullable) | Soft-delete timestamp |
| `PurchaseOrder.lines` | ORM Relationship | One-to-many to `PurchaseOrderLine`, eager-loaded |
| `PurchaseOrderLine` | SQLAlchemy Model | ORM class mapped to `purchase_order_line` table |
| `PurchaseOrderLine.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `PurchaseOrderLine.purchase_order_id` | Model Column (BigInteger FK) | Foreign key to `purchase_order.id` |
| `PurchaseOrderLine.part_id` | Model Column (BigInteger FK) | Foreign key to `part.id` |
| `PurchaseOrderLine.quantity_ordered` | Model Column (Integer) | Original ordered quantity |
| `PurchaseOrderLine.unit_price_ht` | Model Column (BigInteger) | Unit price excluding tax in centimes |
| `PurchaseOrderLine.quantity_received` | Model Column (Integer) | Cumulative quantity received to date |
| `PurchaseOrderLine.quantity_invoiced` | Model Column (Integer) | Quantity accounted for on supplier invoices |
| `PurchaseOrderLine.match_flag` | Model Column (String 30) | Three-way match flag string value |

**TypeScript API (`frontend/src/lib/purchaseOrderApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `POStatus` | TS type alias | Union of five PO status strings |
| `POMatchFlag` | TS type alias | `'ok' \| 'qty_mismatch' \| 'inv_mismatch'` |
| `POLine` | TS Interface | Single line within a purchase order |
| `POLine.id` | Interface property (number) | Numeric line ID |
| `POLine.part_id` | Interface property (number) | Numeric part ID |
| `POLine.quantity_ordered` | Interface property (number) | Ordered quantity |
| `POLine.unit_price_ht` | Interface property (number) | Unit price HT in centimes |
| `POLine.quantity_received` | Interface property (number) | Received quantity |
| `POLine.quantity_invoiced` | Interface property (number) | Invoiced quantity |
| `POLine.match_flag` | Interface property (POMatchFlag) | Three-way match result for this line |
| `PurchaseOrder` | TS Interface | Full purchase order object |
| `PurchaseOrder.id` | Interface property (string) | Public UUID |
| `PurchaseOrder.supplier_id` | Interface property (number) | Numeric supplier ID |
| `PurchaseOrder.doc_number` | Interface property (string\|null) | Human-readable document number |
| `PurchaseOrder.status` | Interface property (POStatus) | Current status |
| `PurchaseOrder.expected_delivery_date` | Interface property (string\|null) | ISO date string |
| `PurchaseOrder.notes` | Interface property (string\|null) | Free-text notes |
| `PurchaseOrder.total_ht` | Interface property (number) | Total HT in centimes |
| `PurchaseOrder.version` | Interface property (number) | Optimistic-lock version |
| `PurchaseOrder.created_at` | Interface property (string) | ISO-8601 timestamp |
| `PurchaseOrder.updated_at` | Interface property (string) | ISO-8601 timestamp |
| `PurchaseOrder.lines` | Interface property (POLine[]) | Array of order lines |
| `POListResponse` | TS Interface | Paginated PO list response |
| `POLineInput` | TS Interface | Input shape for creating/updating a PO line |
| `POLineInput.part_public_id` | Interface property (string) | UUID of the part |
| `POLineInput.quantity_ordered` | Interface property (number) | Ordered quantity |
| `POLineInput.unit_price_ht` | Interface property (number) | Unit price HT in centimes |
| `POCreatePayload` | TS Interface | Request body for creating a PO |
| `POCreatePayload.supplier_public_id` | Interface property (string) | Supplier UUID |
| `POCreatePayload.expected_delivery_date` | Interface property (string?, optional) | Delivery date |
| `POCreatePayload.notes` | Interface property (string?, optional) | Notes |
| `POCreatePayload.lines` | Interface property (POLineInput[]) | Order lines |
| `POUpdatePayload` | TS Interface | Request body for updating a PO (requires `version`) |
| `POReceiveLineInput` | TS Interface | Per-line reception input |
| `POReceiveLineInput.line_id` | Interface property (number) | Numeric line ID |
| `POReceiveLineInput.quantity_received` | Interface property (number) | New received quantity |
| `POReceivePayload` | TS Interface | Goods reception payload (version + lines) |
| `POFromAlertPayload` | TS Interface | Create-PO-from-stock-alert payload |
| `POFromAlertPayload.supplier_public_id` | Interface property (string) | Supplier UUID |
| `POFromAlertPayload.unit_price_ht` | Interface property (number) | Unit price HT in centimes |
| `STATUS_LABELS` (PO) | TS Constant (`Record<POStatus, string>`) | French display labels for PO statuses |
| `MATCH_FLAG_LABELS` | TS Constant (`Record<POMatchFlag, string>`) | French display labels for match flags |
| `purchaseOrderApi` | TS Constant (object) | API client with methods for all PO operations |

**React State (`frontend/src/pages/purchase-orders/PurchaseOrderPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `STATUS_COLORS` (PO page) | TS Constant (`Record<POStatus, ...>`) | MUI chip color mapping for PO statuses |
| `MATCH_COLORS` (PO page) | TS Constant (`Record<POMatchFlag, ...>`) | MUI chip color mapping for match flags |
| `pos` / `setPos` | React State (PurchaseOrder[]) | Current page of POs in the list |
| `statusFilter` / `setStatusFilter` (PO) | React State (POStatus\|'') | Active status filter |
| `selectedPO` / `setSelectedPO` | React State (PurchaseOrder\|null) | PO currently shown in detail view |
| `qtys` / `setQtys` (ReceptionDialog) | React State (Record<number, number>) | Quantities to receive keyed by line ID |
| `qtys` / `setQtys` (InvoiceDialog) | React State (Record<number, number>) | Invoiced quantities keyed by line ID |
| `receiveOpen` / `setReceiveOpen` | React State (boolean) | Controls ReceptionDialog visibility |
| `invoiceOpen` / `setInvoiceOpen` | React State (boolean) | Controls InvoiceDialog visibility |
| `actioning` / `setActioning` | React State (boolean) | Busy flag for PO action buttons |

---

### 3. Supplier Invoice / Three-Way Match (Issue 38)

**Python Model (`backend/app/modules/supplier_invoice/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `SupplierInvoiceStatus` | Python Enum | Five-value status machine for supplier invoices |
| `SupplierInvoiceStatus.draft` | Enum member | Invoice not yet posted/matched |
| `SupplierInvoiceStatus.posted` | Enum member | Three-way match has been run |
| `SupplierInvoiceStatus.approved` | Enum member | Approved for payment |
| `SupplierInvoiceStatus.paid` | Enum member | Payment confirmed |
| `SupplierInvoiceStatus.cancelled` | Enum member | Invoice cancelled |
| `SIMatchStatus` | Python Enum | Three-way match result per JSONB line |
| `SIMatchStatus.ok` | Enum member | Quantities and price match |
| `SIMatchStatus.qty_mismatch` | Enum member | Quantity discrepancy detected |
| `SIMatchStatus.price_mismatch` | Enum member | Price discrepancy detected |
| `SupplierInvoice` | SQLAlchemy Model | ORM class mapped to `supplier_invoice` table |
| `SupplierInvoice.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `SupplierInvoice.public_id` | Model Column (UUID) | Externally-facing UUID |
| `SupplierInvoice.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `SupplierInvoice.supplier_id` | Model Column (BigInteger FK) | Foreign key to `supplier.id` |
| `SupplierInvoice.purchase_order_id` | Model Column (BigInteger FK) | Foreign key to `purchase_order.id` |
| `SupplierInvoice.number` | Model Column (String 100) | Supplier's own invoice number |
| `SupplierInvoice.status` | Model Column (String 30) | Current invoice status |
| `SupplierInvoice.lines` | Model Column (JSONB) | Array of line objects (see JSONB keys below) |
| `SupplierInvoice.total_ht` | Model Column (BigInteger) | Total excluding tax in centimes |
| `SupplierInvoice.total_ttc` | Model Column (BigInteger) | Total including tax in centimes |
| `SupplierInvoice.received_at` | Model Column (DateTime TZ, nullable) | When the physical invoice was received |
| `SupplierInvoice.due_date` | Model Column (Date, nullable) | Payment due date |
| `SupplierInvoice.notes` | Model Column (Text, nullable) | Free-text notes |
| `SupplierInvoice.has_discrepancy` | Model Column (Boolean) | True when any line has a mismatch |
| `SupplierInvoice.override_reason` | Model Column (Text, nullable) | Audit log reason when discrepancy is accepted |
| `SupplierInvoice.is_exported` | Model Column (Boolean) | Lock flag set after accounting export |
| `SupplierInvoice.created_by` | Model Column (BigInteger, nullable) | User ID who created the invoice |
| `SupplierInvoice.version` | Model Column (Integer) | Optimistic-lock counter |
| `SupplierInvoice.created_at` | Model Column (DateTime TZ) | Creation timestamp |
| `SupplierInvoice.updated_at` | Model Column (DateTime TZ) | Last update timestamp |
| `SupplierInvoice.deleted_at` | Model Column (DateTime TZ, nullable) | Soft-delete timestamp |

**JSONB line object keys (inside `SupplierInvoice.lines` array):**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `po_line_id` | JSONB key (int) | References `purchase_order_line.id` |
| `description` | JSONB key (str) | Line item description |
| `quantity` | JSONB key (int) | Quantity on this invoice line |
| `unit_price_ht` | JSONB key (int) | Unit price HT in centimes on the invoice |
| `vat_rate` | JSONB key (float) | VAT rate percentage |
| `line_total_ht` | JSONB key (int) | Line total HT in centimes |
| `line_total_ttc` | JSONB key (int) | Line total TTC in centimes |
| `match_status` | JSONB key (str) | Match result for this line (`ok`/`qty_mismatch`/`price_mismatch`) |
| `po_quantity_ordered` | JSONB key (int) | Ordered quantity from the linked PO line |
| `po_quantity_received` | JSONB key (int) | Received quantity from the linked PO line |
| `po_unit_price_ht` | JSONB key (int) | Unit price HT from the PO for comparison |

**TypeScript API (`frontend/src/lib/supplierInvoiceApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `SIStatus` | TS type alias | Union of five supplier invoice status strings |
| `SIMatchStatus` | TS type alias | `'ok' \| 'qty_mismatch' \| 'price_mismatch'` |
| `SILine` | TS Interface | Single invoice line object (mirrors JSONB keys) |
| `SILine.po_line_id` | Interface property (number) | PO line reference |
| `SILine.description` | Interface property (string) | Line description |
| `SILine.quantity` | Interface property (number) | Invoiced quantity |
| `SILine.unit_price_ht` | Interface property (number) | Invoice unit price HT |
| `SILine.vat_rate` | Interface property (number) | VAT rate |
| `SILine.line_total_ht` | Interface property (number) | Line total HT |
| `SILine.line_total_ttc` | Interface property (number) | Line total TTC |
| `SILine.match_status` | Interface property (SIMatchStatus) | Match result |
| `SILine.po_quantity_ordered` | Interface property (number) | PO ordered qty for comparison |
| `SILine.po_quantity_received` | Interface property (number) | PO received qty for comparison |
| `SILine.po_unit_price_ht` | Interface property (number) | PO unit price for comparison |
| `SupplierInvoice` | TS Interface | Full supplier invoice object |
| `SupplierInvoice.id` | Interface property (string) | Public UUID |
| `SupplierInvoice.supplier_id` | Interface property (number) | Numeric supplier ID |
| `SupplierInvoice.purchase_order_id` | Interface property (number) | Numeric PO ID |
| `SupplierInvoice.number` | Interface property (string) | Invoice number |
| `SupplierInvoice.status` | Interface property (SIStatus) | Current status |
| `SupplierInvoice.lines` | Interface property (SILine[]) | Invoice lines array |
| `SupplierInvoice.total_ht` | Interface property (number) | Total HT in centimes |
| `SupplierInvoice.total_ttc` | Interface property (number) | Total TTC in centimes |
| `SupplierInvoice.has_discrepancy` | Interface property (boolean) | Any line has a mismatch |
| `SupplierInvoice.override_reason` | Interface property (string\|null) | Override audit reason |
| `SupplierInvoice.received_at` | Interface property (string\|null) | Receipt timestamp |
| `SupplierInvoice.due_date` | Interface property (string\|null) | Payment due date |
| `SupplierInvoice.notes` | Interface property (string\|null) | Free-text notes |
| `SupplierInvoice.version` | Interface property (number) | Optimistic-lock version |
| `SIListResponse` | TS Interface | Paginated supplier invoice list |
| `SILineInput` | TS Interface | Input shape for an invoice line when creating/updating |
| `SICreatePayload` | TS Interface | Request body for creating a supplier invoice |
| `SICreatePayload.supplier_public_id` | Interface property (string) | Supplier UUID |
| `SICreatePayload.po_public_id` | Interface property (string) | PO UUID |
| `SICreatePayload.number` | Interface property (string) | Invoice number |
| `SICreatePayload.lines` | Interface property (SILineInput[]) | Line inputs |
| `SICreatePayload.received_at` | Interface property (string\|null, optional) | Receipt timestamp |
| `SICreatePayload.due_date` | Interface property (string\|null, optional) | Due date |
| `SICreatePayload.notes` | Interface property (string\|null, optional) | Notes |
| `SIUpdatePayload` | TS Interface | Request body for updating a supplier invoice |
| `SIVersionPayload` | TS Interface | Minimal version payload for state transitions |
| `SIOverridePayload` | TS Interface | Payload for accepting a discrepancy (`version` + `reason`) |
| `AccountingExport` (SI module) | TS Interface | Journal entry export shape returned by the SI accounting-export endpoint |
| `AccountingExport.journal` | Interface property (string) | Journal name |
| `AccountingExport.invoice_number` | Interface property (string) | Invoice number |
| `AccountingExport.supplier_invoice_id` | Interface property (string) | SI public UUID |
| `AccountingExport.purchase_order_id` | Interface property (number) | PO numeric ID |
| `AccountingExport.entries` | Interface property (Array) | Array of `{account, label, debit, credit}` debit/credit entries |
| `STATUS_LABELS` (SI) | TS Constant (`Record<SIStatus, string>`) | French display labels for SI statuses |
| `MATCH_STATUS_LABELS` | TS Constant (`Record<SIMatchStatus, string>`) | French display labels for match statuses |
| `supplierInvoiceApi` | TS Constant (object) | API client for all supplier invoice operations |

**React State (`frontend/src/pages/supplier-invoices/SupplierInvoicePage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `STATUS_COLORS` (SI page) | TS Constant | MUI chip colors for SI statuses |
| `MATCH_COLORS` (SI page) | TS Constant | MUI chip colors for match statuses |
| `MATCH_ICONS` | TS Constant (`Record<SIMatchStatus, JSX.Element>`) | MUI icons for match statuses |
| `invoices` / `setInvoices` | React State (SupplierInvoice[]) | Current page of supplier invoices |
| `selected` / `setSelected` | React State (SupplierInvoice\|null) | SI currently shown in detail view |
| `createOpen` / `setCreateOpen` | React State (boolean) | Controls CreateDialog visibility |
| `acting` / `setActing` (SIDetail) | React State (boolean) | Busy flag during state transitions |
| `overrideOpen` / `setOverrideOpen` | React State (boolean) | Controls OverrideDialog visibility |
| `accountingOpen` / `setAccountingOpen` | React State (boolean) | Controls AccountingExportDialog visibility |
| `uploading` / `setUploading` | React State (boolean) | Busy flag during PDF attachment upload |
| `reason` / `setReason` | React State (string) | Discrepancy override reason text input |
| `suppliers` / `setSuppliers` (CreateDialog) | React State (Supplier[]) | Active suppliers for the create form dropdown |
| `pos` / `setPos` (CreateDialog) | React State (PurchaseOrder[]) | Eligible POs for the create form dropdown |
| `supplierPublicId` / `setSupplierPublicId` | React State (string) | Selected supplier UUID in create form |
| `poPublicId` / `setPoPublicId` | React State (string) | Selected PO UUID in create form |
| `selectedPo` / `setSelectedPo` | React State (PurchaseOrder\|null) | Full PO object for the selected PO |
| `number` / `setNumber` (CreateDialog) | React State (string) | Invoice number input |
| `receivedAt` / `setReceivedAt` | React State (string) | Receipt datetime input |
| `dueDate` / `setDueDate` | React State (string) | Due date input |
| `lines` / `setLines` (CreateDialog) | React State (LineForm[]) | Working set of invoice lines in the create form |
| `LineForm` | Local Interface | Shape of an invoice line within the create dialog |

**Payment model addition (`backend/app/modules/payment/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `Payment.is_exported` | Model Column (Boolean) | Lock flag set after accounting export; added to pre-existing `Payment` model |

---

### 4. Notification (Issues 39/40)

**Python Model (`backend/app/modules/notification/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `NotificationChannel` | Python Enum | `email` / `sms` dispatch channels |
| `NotificationChannel.email` | Enum member | Email delivery channel |
| `NotificationChannel.sms` | Enum member | SMS delivery channel |
| `NotificationStatus` | Python Enum | Log entry lifecycle: `queued`, `sent`, `failed`, `bounced` |
| `NotificationStatus.queued` | Enum member | Notification is waiting to be sent |
| `NotificationStatus.sent` | Enum member | Successfully delivered |
| `NotificationStatus.failed` | Enum member | Permanent failure after all retries |
| `NotificationStatus.bounced` | Enum member | Delivery bounced (email hard bounce) |
| `NotificationTemplate` | SQLAlchemy Model | ORM class mapped to `notification_template` table |
| `NotificationTemplate.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `NotificationTemplate.garage_id` | Model Column (BigInteger) | Tenant scoping; `0` = system default |
| `NotificationTemplate.code` | Model Column (String 100) | Trigger code, e.g. `invoice_issued` |
| `NotificationTemplate.channel` | Model Column (String 20) | `email` or `sms` |
| `NotificationTemplate.locale` | Model Column (String 10) | Locale code, default `fr` |
| `NotificationTemplate.subject` | Model Column (String 500, nullable) | Email subject Jinja2 template |
| `NotificationTemplate.body` | Model Column (Text) | Message body Jinja2 template |
| `NotificationTemplate.active` | Model Column (Boolean) | Whether this template is enabled |
| `NotificationTemplate.updated_at` | Model Column (DateTime TZ) | Last edit timestamp |
| `NotificationLog` | SQLAlchemy Model | ORM class mapped to `notification_log` table |
| `NotificationLog.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `NotificationLog.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `NotificationLog.recipient_id` | Model Column (BigInteger, nullable) | Internal user ID of the recipient |
| `NotificationLog.channel` | Model Column (String 20) | Delivery channel |
| `NotificationLog.template_code` | Model Column (String 100) | Which template was used |
| `NotificationLog.status` | Model Column (String 20) | Current delivery status |
| `NotificationLog.provider_reference` | Model Column (String 255, nullable) | External provider message ID |
| `NotificationLog.sent_at` | Model Column (DateTime TZ, nullable) | Delivery timestamp |
| `NotificationLog.attempts` | Model Column (Integer) | Number of delivery attempts made |
| `NotificationLog.error_detail` | Model Column (Text, nullable) | Last error message string |
| `NotificationLog.created_at` | Model Column (DateTime TZ) | Row creation timestamp |

**Notification Service constants (`backend/app/modules/notification/service.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `_FS_TEMPLATES_DIR` | Python Constant (Path) | Filesystem path to the `notification/templates/` directory |

**TypeScript API (`frontend/src/lib/notificationApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `TriggerEntry` | TS Interface | One notification trigger descriptor |
| `TriggerEntry.code` | Interface property (string) | Machine-readable trigger code |
| `TriggerEntry.label` | Interface property (string) | Human-readable label |
| `TriggerEntry.description` | Interface property (string) | Explanation of when it fires |
| `TriggerEntry.type` | Interface property (`'event'\|'scheduled'`) | Whether it fires on an event or on a schedule |
| `TriggerEntry.channels` | Interface property (string[]) | Which channels support this trigger |
| `NotificationTemplate` (TS) | TS Interface | Template object returned from API |
| `NotificationTemplate.id` | Interface property (number) | Numeric DB ID |
| `NotificationTemplate.garage_id` | Interface property (number) | Tenant; `0` = system default |
| `NotificationTemplate.code` | Interface property (string) | Trigger code |
| `NotificationTemplate.channel` | Interface property (string) | Channel |
| `NotificationTemplate.locale` | Interface property (string) | Locale |
| `NotificationTemplate.subject` | Interface property (string\|null) | Email subject |
| `NotificationTemplate.body` | Interface property (string) | Message body |
| `NotificationTemplate.active` | Interface property (boolean) | Enabled flag |
| `NotificationTemplate.updated_at` | Interface property (string) | ISO-8601 last-edit timestamp |
| `NotificationTemplate.is_override` | Interface property (boolean) | True if this is a per-garage override of a system template |
| `TemplateUpdatePayload` | TS Interface | Request body for updating a notification template |
| `TemplateUpdatePayload.subject` | Interface property (string\|null, optional) | New subject |
| `TemplateUpdatePayload.body` | Interface property (string) | New body |
| `TemplateUpdatePayload.active` | Interface property (boolean) | New enabled flag |
| `PreviewRequest` | TS Interface | Optional Jinja2 context for template preview |
| `PreviewRequest.context` | Interface property (Record<string,string>, optional) | Key-value pairs passed to template renderer |
| `PreviewResponse` | TS Interface | Rendered preview output |
| `PreviewResponse.subject` | Interface property (string\|null) | Rendered email subject |
| `PreviewResponse.body` | Interface property (string) | Rendered message body |
| `notificationApi` | TS Constant (object) | API client for notification template operations |

**React State (`frontend/src/pages/notifications/TemplatesPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `editing` / `setEditing` | React State (NotificationTemplate\|null) | Template currently being edited in dialog |
| `subject` / `setSubject` (EditDialog) | React State (string) | Subject input in the edit dialog |
| `body` / `setBody` (EditDialog) | React State (string) | Body textarea in the edit dialog |
| `active` / `setActive` (EditDialog) | React State (boolean) | Active toggle in the edit dialog |
| `preview` / `setPreview` (EditDialog) | React State (`{subject, body}\|null`) | Rendered preview data |
| `previewLoading` / `setPreviewLoading` | React State (boolean) | Busy flag while fetching preview |
| `previewTab` / `setPreviewTab` | React State (number) | Active tab (0=editor, 1=preview) |
| `byCode` | Local variable (`Record<string, NotificationTemplate[]>`) | Templates grouped by trigger code for rendering |
| `['notification-triggers']` | React Query key | Query key for the list of trigger descriptors |
| `['notification-templates']` | React Query key | Query key for the notification template list |

---

### 5. Inspection (Issue 41)

**Python Model (`backend/app/modules/inspection/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `InspectionItemStatus` | Python Enum | Four-value result per item: `ok`, `attention`, `defective`, `not_applicable` |
| `InspectionItemStatus.ok` | Enum member | Item is in good condition |
| `InspectionItemStatus.attention` | Enum member | Item needs monitoring |
| `InspectionItemStatus.defective` | Enum member | Item is defective |
| `InspectionItemStatus.not_applicable` | Enum member | Item not applicable for this vehicle |
| `InspectionStatus` | Python Enum | Four-value inspection lifecycle: `draft`, `in_progress`, `completed`, `cancelled` |
| `InspectionStatus.draft` | Enum member | Inspection not yet started |
| `InspectionStatus.in_progress` | Enum member | Mechanic is actively filling it in |
| `InspectionStatus.completed` | Enum member | Inspection finalized |
| `InspectionStatus.cancelled` | Enum member | Inspection cancelled |
| `INSPECTION_ALLOWED_TRANSITIONS` | Python Constant (dict) | Module-level state machine transition map |
| `InspectionTemplate` | SQLAlchemy Model | ORM class mapped to `inspection_template` table |
| `InspectionTemplate.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `InspectionTemplate.public_id` | Model Column (UUID) | Externally-facing UUID |
| `InspectionTemplate.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `InspectionTemplate.name` | Model Column (String 255) | Display name of the template |
| `InspectionTemplate.sections` | Model Column (JSONB) | Array of section objects |
| `InspectionTemplate.created_at` | Model Column (DateTime TZ) | Creation timestamp |
| `InspectionTemplate.updated_at` | Model Column (DateTime TZ) | Last update timestamp |
| `InspectionTemplate.deleted_at` | Model Column (DateTime TZ, nullable) | Soft-delete timestamp |
| `InspectionTemplate.version` | Model Column (Integer) | Optimistic-lock counter |
| `InspectionTemplate.created_by_user_id` | Model Column (BigInteger FK, nullable) | User who created the template |
| `Inspection` | SQLAlchemy Model | ORM class mapped to `inspection` table |
| `Inspection.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `Inspection.public_id` | Model Column (UUID) | Externally-facing UUID |
| `Inspection.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `Inspection.repair_order_id` | Model Column (BigInteger FK, nullable) | Linked repair order |
| `Inspection.template_id` | Model Column (BigInteger FK) | FK to `inspection_template.id` |
| `Inspection.mechanic_id` | Model Column (BigInteger FK, nullable) | Assigned mechanic user ID |
| `Inspection.vehicle_id` | Model Column (BigInteger FK, nullable) | Vehicle being inspected |
| `Inspection.status` | Model Column (Enum) | Current inspection status |
| `Inspection.started_at` | Model Column (DateTime TZ, nullable) | Timestamp of first `in_progress` transition |
| `Inspection.completed_at` | Model Column (DateTime TZ, nullable) | Timestamp of `completed` transition |
| `Inspection.created_at` | Model Column (DateTime TZ) | Creation timestamp |
| `Inspection.updated_at` | Model Column (DateTime TZ) | Last update timestamp |
| `Inspection.version` | Model Column (Integer) | Optimistic-lock counter |
| `Inspection.created_by_user_id` | Model Column (BigInteger FK, nullable) | User who created the inspection |
| `InspectionItemResult` | SQLAlchemy Model | ORM class mapped to `inspection_item_result` table |
| `InspectionItemResult.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `InspectionItemResult.inspection_id` | Model Column (BigInteger FK) | FK to `inspection.id` |
| `InspectionItemResult.item_id` | Model Column (String 100) | Template item identifier string |
| `InspectionItemResult.status` | Model Column (Enum) | Result status for this item |
| `InspectionItemResult.notes` | Model Column (Text, nullable) | Mechanic's notes for this item |
| `InspectionItemResult.media_ids` | Model Column (JSONB) | Array of `ro_media.public_id` strings attached to this result |
| `InspectionItemResult.written_at` | Model Column (DateTime TZ) | Client-provided timestamp for last-write-wins conflict resolution |
| `InspectionItemResult.created_at` | Model Column (DateTime TZ) | Row creation timestamp |
| `InspectionItemResult.updated_at` | Model Column (DateTime TZ) | Last update timestamp |
| `InspectionConflictLog` | SQLAlchemy Model | ORM class mapped to `inspection_conflict_log` table |
| `InspectionConflictLog.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `InspectionConflictLog.inspection_id` | Model Column (BigInteger FK) | FK to `inspection.id` |
| `InspectionConflictLog.item_id` | Model Column (String 100) | Template item identifier |
| `InspectionConflictLog.client_written_at` | Model Column (DateTime TZ) | Client-side timestamp that was discarded |
| `InspectionConflictLog.server_written_at` | Model Column (DateTime TZ) | Server-side timestamp that was kept |
| `InspectionConflictLog.discarded_status` | Model Column (String 50) | Status from the losing write |
| `InspectionConflictLog.kept_status` | Model Column (String 50) | Status from the winning write |
| `InspectionConflictLog.resolved_at` | Model Column (DateTime TZ) | When the conflict was resolved |
| `VehicleRecommendation` | SQLAlchemy Model | ORM class mapped to `vehicle_recommendation` table |
| `VehicleRecommendation.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `VehicleRecommendation.public_id` | Model Column (UUID) | Externally-facing UUID |
| `VehicleRecommendation.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `VehicleRecommendation.vehicle_id` | Model Column (BigInteger FK) | FK to `vehicle.id` |
| `VehicleRecommendation.source_inspection_id` | Model Column (BigInteger FK, nullable) | FK to `inspection.id` that produced this recommendation |
| `VehicleRecommendation.item_id` | Model Column (String 100) | Template item identifier |
| `VehicleRecommendation.item_label` | Model Column (String 500) | Human-readable label copied from template |
| `VehicleRecommendation.item_status` | Model Column (String 50) | Status at time of archiving |
| `VehicleRecommendation.status` | Model Column (String 20) | Recommendation lifecycle; default `archived` |
| `VehicleRecommendation.notes` | Model Column(Text, nullable) | Additional notes |
| `VehicleRecommendation.created_at` | Model Column (DateTime TZ) | Creation timestamp |
| `VehicleRecommendation.created_by_user_id` | Model Column (BigInteger FK, nullable) | User who archived this recommendation |
| `InspectionApprovalToken` | SQLAlchemy Model | ORM class mapped to `inspection_approval_token` table |
| `InspectionApprovalToken.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `InspectionApprovalToken.jti` | Model Column (String 36, unique) | JWT `jti` claim; single-use enforcement key |
| `InspectionApprovalToken.inspection_id` | Model Column (BigInteger FK) | FK to `inspection.id` |
| `InspectionApprovalToken.expires_at` | Model Column (DateTime TZ) | Token expiry timestamp |
| `InspectionApprovalToken.used_at` | Model Column (DateTime TZ, nullable) | Timestamp when the token was consumed |
| `InspectionApprovalToken.created_at` | Model Column (DateTime TZ) | Token creation timestamp |

**Inspection Pydantic Schemas (`backend/app/modules/inspection/schemas.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `TemplateItemSchema` | Pydantic BaseModel | Schema for a single checklist item within a template section |
| `TemplateItemSchema.id` | Schema field (str) | Item identifier |
| `TemplateItemSchema.label` | Schema field (str) | Display label |
| `TemplateItemSchema.requires_photo` | Schema field (bool, default False) | Whether a photo is mandatory |
| `TemplateSectionSchema` | Pydantic BaseModel | Schema for a template section containing items |
| `TemplateSectionSchema.id` | Schema field (str) | Section identifier |
| `TemplateSectionSchema.title` | Schema field (str) | Section display title |
| `TemplateSectionSchema.items` | Schema field (List[TemplateItemSchema]) | Items within this section |
| `InspectionTemplateCreateRequest` | Pydantic BaseModel | Create-template request body |
| `InspectionTemplateUpdateRequest` | Pydantic BaseModel | Update-template request body (includes `version`) |
| `InspectionTemplateSummary` | Pydantic BaseModel | Template summary for list responses |
| `InspectionTemplateListResponse` | Pydantic BaseModel | Paginated template list response |
| `InspectionCreateRequest` | Pydantic BaseModel | Create-inspection request |
| `InspectionCreateRequest.template_public_id` | Schema field (str) | UUID of template to use |
| `InspectionCreateRequest.mechanic_id` | Schema field (int, optional) | Assigned mechanic |
| `InspectionCreateRequest.repair_order_public_id` | Schema field (str, optional) | Linked RO UUID |
| `InspectionCreateRequest.vehicle_id` | Schema field (int, optional) | Vehicle ID |
| `InspectionStatusTransitionRequest` | Pydantic BaseModel | Status change request (`new_status` field) |
| `ItemResultPayload` | Pydantic BaseModel | Single item result in a bulk sync |
| `ItemResultPayload.item_id` | Schema field (str) | Template item identifier |
| `ItemResultPayload.status` | Schema field (str) | Result status string |
| `ItemResultPayload.notes` | Schema field (str, optional) | Mechanic notes |
| `ItemResultPayload.media_ids` | Schema field (List[str]) | Attached media UUIDs |
| `ItemResultPayload.written_at` | Schema field (datetime, optional) | Client timestamp for LWW |
| `BulkResultsRequest` | Pydantic BaseModel | Batch sync request (list of `ItemResultPayload`) |
| `ItemResultResponse` | Pydantic BaseModel | Single item result in API response |
| `ConflictLogEntry` | Pydantic BaseModel | One conflict log record in bulk sync response |
| `ConflictLogEntry.item_id` | Schema field (str) | Conflicted item ID |
| `ConflictLogEntry.client_written_at` | Schema field (datetime) | Client timestamp |
| `ConflictLogEntry.server_written_at` | Schema field (datetime) | Server timestamp |
| `ConflictLogEntry.discarded_status` | Schema field (str) | Losing status |
| `ConflictLogEntry.kept_status` | Schema field (str) | Winning status |
| `BulkResultsResponse` | Pydantic BaseModel | Response for bulk sync (`synced` count + `conflicts` list) |
| `InspectionSummary` | Pydantic BaseModel | Lightweight inspection for list responses |
| `InspectionDetail` | Pydantic BaseModel | Full inspection with results for detail view |
| `InspectionDetail.template_sections` | Schema field (Any) | Denormalized template sections stored on the detail |
| `InspectionListResponse` | Pydantic BaseModel | Paginated inspection list response |
| `DeclinedItemPayload` | Pydantic BaseModel | One declined item for the archive-recommendations endpoint |
| `ArchiveDeclinedRequest` | Pydantic BaseModel | Archive declined items request (`vehicle_id` + `declined_items`) |
| `VehicleRecommendationResponse` | Pydantic BaseModel | API response for a vehicle recommendation |
| `ConvertToRORequest` | Pydantic BaseModel | Link-inspection-to-RO request (`repair_order_public_id`) |
| `GenerateApprovalLinkResponse` | Pydantic BaseModel | Returns `token` and `expires_at` |
| `ApprovalPublicItem` | Pydantic BaseModel | Public-facing item in the customer approval page |
| `ApprovalPublicItem.actionable` | Schema field (bool) | True when the item needs a customer decision |
| `ApprovalPublicSection` | Pydantic BaseModel | Public-facing section in the customer approval page |
| `ApprovalPublicInspection` | Pydantic BaseModel | Full public-facing inspection payload for customer approval |
| `ApprovalPublicInspection.vehicle_info` | Schema field (str) | Formatted vehicle string |
| `ApprovalPublicInspection.mechanic_name` | Schema field (str) | Mechanic display name |
| `ApprovalItemDecision` | Pydantic BaseModel | One customer decision (`item_id` + `decision`) |
| `ProcessApprovalRequest` | Pydantic BaseModel | Customer approval submission (list of decisions) |
| `ProcessApprovalResponse` | Pydantic BaseModel | Returns `repair_tasks_created` and `recommendations_archived` counts |

**Inspection Service domain errors (`backend/app/modules/inspection/service.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `TemplateNotFoundError` | Exception class | Raised when a template public UUID does not exist |
| `TemplateVersionConflictError` | Exception class | Raised when template version submitted does not match DB |
| `InspectionNotFoundError` | Exception class | Raised when an inspection public UUID does not exist |
| `InvalidInspectionStatusTransitionError` | Exception class | Raised when a requested transition is not allowed |
| `InspectionAlreadyLinkedError` | Exception class | Raised when trying to link an already-linked inspection to a RO |
| `TokenInvalidError` | Exception class | Raised when the approval JWT is malformed or unknown |
| `TokenExpiredError` | Exception class | Raised when the approval JWT has expired |
| `TokenAlreadyUsedError` | Exception class | Raised when the approval JWT has already been consumed |

**TypeScript API (`frontend/src/lib/inspectionApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `PUBLIC_BASE` | TS Constant (string) | Base URL for unauthenticated approval endpoints |
| `InspectionItemStatus` | TS type alias | Union of four item status strings |
| `InspectionStatus` | TS type alias | Union of four inspection status strings |
| `ITEM_STATUS_LABELS` | TS Constant (`Record<InspectionItemStatus, string>`) | French labels for item statuses |
| `ITEM_STATUS_COLORS` | TS Constant (`Record<InspectionItemStatus, ...>`) | MUI color names for item statuses |
| `INSPECTION_STATUS_LABELS` | TS Constant (`Record<InspectionStatus, string>`) | French labels for inspection statuses |
| `INSPECTION_ALLOWED_TRANSITIONS` | TS Constant (`Record<InspectionStatus, InspectionStatus[]>`) | Client-side transition map mirroring backend |
| `TemplateItem` | TS Interface | Single checklist item in a template section |
| `TemplateItem.id` | Interface property (string) | Item identifier |
| `TemplateItem.label` | Interface property (string) | Display label |
| `TemplateItem.requires_photo` | Interface property (boolean) | Whether photo is required |
| `TemplateSection` | TS Interface | Section containing items |
| `TemplateSection.id` | Interface property (string) | Section identifier |
| `TemplateSection.title` | Interface property (string) | Section title |
| `TemplateSection.items` | Interface property (TemplateItem[]) | Items array |
| `InspectionTemplate` | TS Interface | Full template object from API |
| `InspectionTemplateListResponse` | TS Interface | Paginated template list |
| `ItemResult` | TS Interface | Single item result in an inspection |
| `ItemResult.item_id` | Interface property (string) | Item identifier |
| `ItemResult.status` | Interface property (InspectionItemStatus) | Result status |
| `ItemResult.notes` | Interface property (string\|null) | Notes |
| `ItemResult.media_ids` | Interface property (string[]) | Attached media UUIDs |
| `ItemResult.written_at` | Interface property (string) | LWW timestamp |
| `InspectionDetail` (TS) | TS Interface | Full inspection object with results |
| `InspectionDetail.template_sections` | Interface property (TemplateSection[]) | Denormalized template sections |
| `InspectionSummary` (TS) | TS Interface | Lightweight inspection for list views |
| `InspectionListResponse` (TS) | TS Interface | Paginated inspection list |
| `ItemResultPayload` (TS) | TS Interface | Item result payload for batch sync |
| `BulkResultsResponse` (TS) | TS Interface | Sync response with `synced` count and `conflicts` array |
| `VehicleRecommendation` (TS) | TS Interface | Vehicle recommendation API object |
| `DeclinedItemPayload` (TS) | TS Interface | Archive-declined-item input |
| `ApprovalLinkResponse` | TS Interface | Returns `token` and `expires_at` strings |
| `ApprovalPublicItem` (TS) | TS Interface | Public item for customer approval page |
| `ApprovalPublicItem.actionable` | Interface property (boolean) | Whether the customer must decide on this item |
| `ApprovalPublicSection` (TS) | TS Interface | Public section for customer approval page |
| `ApprovalPublicSection.section_id` | Interface property (string) | Section identifier |
| `ApprovalPublicSection.section_title` | Interface property (string) | Section title |
| `ApprovalPublicInspection` (TS) | TS Interface | Full public inspection for customer approval |
| `ApprovalPublicInspection.inspection_id` | Interface property (string) | Inspection UUID |
| `ApprovalPublicInspection.vehicle_info` | Interface property (string) | Formatted vehicle description |
| `ApprovalPublicInspection.mechanic_name` | Interface property (string) | Mechanic display name |
| `ApprovalDecision` | TS Interface | Customer decision for one item |
| `ApprovalDecision.item_id` | Interface property (string) | Item identifier |
| `ApprovalDecision.decision` | Interface property (`'approved'\|'rejected'`) | Customer's choice |
| `ProcessApprovalResponse` (TS) | TS Interface | Returns `repair_tasks_created` and `recommendations_archived` |
| `inspectionApi` | TS Constant (object) | API client for all inspection operations |

**Offline Store (`frontend/src/lib/inspectionOfflineStore.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `PendingResult` | TS Interface | Shape of a locally-stored item result awaiting sync |
| `PendingResult.inspectionId` | Interface property (string) | Inspection UUID (part of composite key) |
| `PendingResult.itemId` | Interface property (string) | Template item identifier (part of composite key) |
| `PendingResult.status` | Interface property (string) | Item status |
| `PendingResult.notes` | Interface property (string\|null) | Notes |
| `PendingResult.mediaIds` | Interface property (string[]) | Attached media UUIDs |
| `PendingResult.writtenAt` | Interface property (string) | ISO-8601 LWW timestamp |
| `PendingResult.synced` | Interface property (boolean) | Whether this result has been confirmed by the server |
| `DB_NAME` | TS Constant (string) | IndexedDB database name: `'xpert-erp-inspections'` |
| `DB_VERSION` | TS Constant (number) | IndexedDB schema version: `1` |
| `STORE` | TS Constant (string) | IndexedDB object store name: `'pending_results'` |
| `inspectionOfflineStore` | TS Constant (object) | IndexedDB API wrapper with `saveResult`, `getPending`, `getAll`, `markSynced`, `clearSynced` |

**React State (`frontend/src/pages/inspections/InspectionExecutionPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `TOUCH_BTN` | TS Constant (object) | MUI `sx` styles for touch-friendly buttons |
| `STATUS_ICONS` (execution page) | TS Constant (`Record<InspectionItemStatus, ReactElement>`) | Icons for each item status |
| `LocalResults` | TS Type alias | `Record<string, {status, notes, mediaIds, writtenAt}>` — in-memory working copy |
| `isOnline` / `setIsOnline` | React State (boolean) | Network connectivity status |
| `localResults` / `setLocalResults` | React State (LocalResults) | In-memory result buffer pending sync |
| `syncError` / `setSyncError` | React State (string\|null) | Error message from a failed sync attempt |
| `syncSuccess` / `setSyncSuccess` | React State (boolean) | Flag for showing sync success snackbar |
| `completeOpen` / `setCompleteOpen` | React State (boolean) | Confirm-complete dialog visibility |
| `approvalLinkCopied` / `setApprovalLinkCopied` | React State (boolean) | Clipboard-copy success flag |
| `pdfLoading` / `setPdfLoading` | React State (boolean) | Busy flag during PDF report download |
| `syncInProgress` | React Ref (boolean) | Ref guard preventing concurrent sync calls |
| `notesOpen` / `setNotesOpen` (ItemRow) | React State (boolean) | Notes text field expand/collapse |
| `notes` / `setNotes` (ItemRow) | React State (string) | Notes text field value |
| `open` / `setOpen` (SectionCard) | React State (boolean) | Section accordion expand/collapse |
| `['inspection', publicId]` | React Query key | Query key for a single inspection detail |
| `['inspections']` | React Query key | Query key for the inspection list (used for invalidation) |

**React State (`frontend/src/pages/inspections/InspectionApprovalPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `STATUS_ICONS` (approval page) | TS Constant (Record) | Icons for item statuses on the approval page |
| `STATUS_LABELS` (approval page) | TS Constant (Record) | French labels for item statuses on the approval page |
| `decisions` / `setDecisions` | React State (`Record<string, 'approved'\|'rejected'>`) | Customer decisions keyed by item_id |
| `submitted` / `setSubmitted` | React State (boolean) | Whether the approval form has been submitted |
| `['approval', token]` | React Query key | Query key for the public approval inspection data |

**React State (`frontend/src/pages/inspections/InspectionTemplatesPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `createOpen` / `setCreateOpen` | React State (boolean) | Create-template dialog visibility |
| `deleteTarget` / `setDeleteTarget` | React State (string\|null) | UUID of template pending deletion |
| `name` / `setName` (CreateTemplateDialog) | React State (string) | Template name input |
| `sections` / `setSections` (CreateTemplateDialog) | React State (TemplateSection[]) | Working sections in the create form |
| `['inspection-templates']` | React Query key | Query key for the inspection template list |

**React State (`frontend/src/pages/inspections/InspectionsListPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `statusFilter` / `setStatusFilter` (InspectionsListPage) | React State (InspectionStatus\|'') | Active status filter |
| `createOpen` / `setCreateOpen` (InspectionsListPage) | React State (boolean) | Create-inspection dialog visibility |
| `templateId` / `setTemplateId` (CreateInspectionDialog) | React State (string) | Selected template UUID |
| `['inspections', statusFilter, page]` | React Query key | Query key for the paginated inspection list |

---

### 6. Media / RO Media (Issues 42/43/44)

**Python Model (`backend/app/modules/media/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `RoMedia` | SQLAlchemy Model | ORM class mapped to `ro_media` table for uploaded inspection/RO photos |
| `RoMedia.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `RoMedia.public_id` | Model Column (UUID) | Externally-facing UUID |
| `RoMedia.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `RoMedia.inspection_id` | Model Column (BigInteger FK, nullable) | FK to `inspection.id` |
| `RoMedia.ro_id` | Model Column (BigInteger FK, nullable) | FK to `repair_order.id` |
| `RoMedia.uploader_id` | Model Column (BigInteger FK, nullable) | FK to `app_user.id` |
| `RoMedia.storage_key` | Model Column (Text) | Internal S3 object key; never exposed to clients |
| `RoMedia.mime_type` | Model Column (String 127) | MIME type of the uploaded file |
| `RoMedia.size_bytes` | Model Column (BigInteger) | File size in bytes |
| `RoMedia.caption` | Model Column (Text, nullable) | Optional caption |
| `RoMedia.archived` | Model Column (Boolean) | Whether the file has been moved to cold storage |
| `RoMedia.archive_storage_key` | Model Column (Text, nullable) | S3 key in the archive bucket |
| `RoMedia.archived_at` | Model Column (DateTime TZ, nullable) | When the file was archived |
| `RoMedia.uploaded_at` | Model Column (DateTime TZ) | Original upload timestamp |
| `RoMedia.deleted_at` | Model Column (DateTime TZ, nullable) | Soft-delete timestamp |
| `MediaUploadSession` | SQLAlchemy Model | ORM class mapped to `ro_media_upload_session` for in-flight S3 multipart uploads |
| `MediaUploadSession.id` | Model Column (UUID, PK) | Session identifier (also the public ID) |
| `MediaUploadSession.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `MediaUploadSession.inspection_id` | Model Column (BigInteger FK, nullable) | FK to `inspection.id` |
| `MediaUploadSession.ro_id` | Model Column (BigInteger FK, nullable) | FK to `repair_order.id` |
| `MediaUploadSession.uploader_id` | Model Column (BigInteger FK, nullable) | FK to `app_user.id` |
| `MediaUploadSession.filename` | Model Column (String 512) | Original filename |
| `MediaUploadSession.mime_type` | Model Column (String 127) | MIME type |
| `MediaUploadSession.total_size_bytes` | Model Column (BigInteger) | Total expected file size |
| `MediaUploadSession.chunk_size_bytes` | Model Column (Integer) | Size of each chunk in bytes |
| `MediaUploadSession.total_chunks` | Model Column (Integer) | Total number of chunks |
| `MediaUploadSession.received_parts` | Model Column (JSONB) | Array of `{part_number, etag}` objects for completed parts |
| `MediaUploadSession.storage_key` | Model Column (Text) | S3 object key for this upload |
| `MediaUploadSession.s3_upload_id` | Model Column (Text) | AWS S3 multipart upload ID |
| `MediaUploadSession.status` | Model Column (String 20) | Session state: `pending`, `complete`, or `aborted` |
| `MediaUploadSession.expires_at` | Model Column (DateTime TZ) | When the session expires |
| `MediaUploadSession.created_at` | Model Column (DateTime TZ) | Session creation timestamp |

**Media Pydantic Schemas (`backend/app/modules/media/schemas.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `UploadSessionCreate` | Pydantic BaseModel | Create-session request |
| `UploadSessionCreate.inspection_public_id` | Schema field (str) | Inspection UUID this upload belongs to |
| `UploadSessionCreate.filename` | Schema field (str, max 512) | Original filename |
| `UploadSessionCreate.mime_type` | Schema field (str, max 127) | MIME type |
| `UploadSessionCreate.total_size_bytes` | Schema field (int, gt 0) | Total file size in bytes |
| `UploadSessionCreate.caption` | Schema field (str, optional) | Optional caption |
| `UploadSessionOut` | Pydantic BaseModel | Create-session response |
| `UploadSessionOut.session_id` | Schema field (str) | Session public UUID |
| `UploadSessionOut.chunk_size_bytes` | Schema field (int) | Chunk size to use |
| `UploadSessionOut.total_chunks` | Schema field (int) | Total chunks expected |
| `UploadSessionOut.received_part_numbers` | Schema field (list[int]) | Already-received part numbers for resume |
| `UploadSessionOut.status` | Schema field (str) | Session status |
| `UploadSessionOut.expires_at` | Schema field (datetime) | Expiry timestamp |
| `PartUploadOut` | Pydantic BaseModel | Response after uploading one chunk |
| `PartUploadOut.part_number` | Schema field (int) | The part number just received |
| `PartUploadOut.received_part_numbers` | Schema field (list[int]) | Updated list of all received parts |
| `RoMediaOut` | Pydantic BaseModel | Completed media record response |
| `RoMediaOut.media_id` | Schema field (str) | Public UUID of the media record |
| `RoMediaOut.mime_type` | Schema field (str) | MIME type |
| `RoMediaOut.size_bytes` | Schema field (int) | File size |
| `RoMediaOut.caption` | Schema field (str\|None) | Caption |
| `RoMediaOut.uploaded_at` | Schema field (datetime) | Upload timestamp |
| `RoMediaOut.signed_url` | Schema field (str) | Pre-signed S3 URL for direct access |
| `SignedUrlResponse` | Pydantic BaseModel | Signed URL refresh response |
| `SignedUrlResponse.media_id` | Schema field (str) | Media UUID |
| `SignedUrlResponse.url` | Schema field (str) | New pre-signed URL |
| `SignedUrlResponse.expires_in_seconds` | Schema field (int) | Expiry window in seconds |

**TypeScript API (`frontend/src/lib/mediaApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `UploadSessionInfo` | TS Interface | Upload session state from API |
| `UploadSessionInfo.session_id` | Interface property (string) | Session UUID |
| `UploadSessionInfo.chunk_size_bytes` | Interface property (number) | Chunk size |
| `UploadSessionInfo.total_chunks` | Interface property (number) | Total chunks |
| `UploadSessionInfo.received_part_numbers` | Interface property (number[]) | Already-received part numbers |
| `UploadSessionInfo.status` | Interface property (string) | Session status |
| `UploadSessionInfo.expires_at` | Interface property (string) | Expiry ISO timestamp |
| `MediaOut` | TS Interface | Completed media record |
| `MediaOut.media_id` | Interface property (string) | Media UUID |
| `MediaOut.mime_type` | Interface property (string) | MIME type |
| `MediaOut.size_bytes` | Interface property (number) | File size in bytes |
| `MediaOut.caption` | Interface property (string\|null) | Caption |
| `MediaOut.uploaded_at` | Interface property (string) | Upload timestamp |
| `MediaOut.signed_url` | Interface property (string) | Pre-signed access URL |
| `SignedUrlResponse` (TS) | TS Interface | Signed URL refresh response |
| `UploadOptions` | TS Interface | Options object for `mediaApi.uploadFile()` |
| `UploadOptions.inspectionPublicId` | Interface property (string) | Inspection UUID for association |
| `UploadOptions.filename` | Interface property (string) | Original filename |
| `UploadOptions.mimeType` | Interface property (string) | MIME type |
| `UploadOptions.caption` | Interface property (string?, optional) | Caption |
| `UploadOptions.sessionId` | Interface property (string?, optional) | Existing session to resume |
| `UploadOptions.onProgress` | Interface property (function?, optional) | Progress callback `(loaded, total) => void` |
| `mediaApi` | TS Constant (object) | API client for media upload/download operations |

**Image Compressor (`frontend/src/lib/imageCompressor.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `CompressOptions` | TS Interface | Options for the client-side compressor |
| `CompressOptions.maxDimension` | Interface property (number) | Max length of the longest edge in pixels |
| `CompressOptions.quality` | Interface property (number) | JPEG/WebP quality 0–1 |
| `CompressOptions.outputMime` | Interface property (`'image/jpeg'\|'image/webp'`) | Output format |
| `DEFAULT_OPTS` | TS Constant (CompressOptions) | Default compression settings: 1920px, 0.85 quality, JPEG |
| `compressAndStripExif` | TS exported function | Compresses a file, strips all EXIF metadata via canvas redraw |

**React Component (`frontend/src/components/inspections/MediaUploadButton.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `PendingUpload` | Local Interface | Tracks an in-progress upload (`sessionId`, `progress`, `error`) |
| `PendingUpload.sessionId` | Interface property (string?, optional) | Resume session ID |
| `PendingUpload.progress` | Interface property (number) | Upload progress 0–100 |
| `PendingUpload.error` | Interface property (string?, optional) | Error message if upload failed |
| `pending` / `setPending` | React State (PendingUpload\|null) | Current upload state; null when idle |

---

### 7. KPI Snapshot (Issue 45)

**Python Model (`backend/app/modules/kpi/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `KpiSnapshot` | SQLAlchemy Model | ORM class mapped to `kpi_snapshot` table |
| `KpiSnapshot.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `KpiSnapshot.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `KpiSnapshot.snapshot_date` | Model Column (Date) | Date of the snapshot |
| `KpiSnapshot.kpi_code` | Model Column (String 80) | KPI identifier string (e.g. `revenue_mtd`, `open_repair_orders_count`) |
| `KpiSnapshot.value` | Model Column (Numeric 24,4, nullable) | Scalar KPI value |
| `KpiSnapshot.meta` | Model Column (JSONB, nullable) | Supplementary data (e.g. top-N arrays) |
| `KpiSnapshot.computed_at` | Model Column (DateTime TZ) | When this snapshot was computed |

**KPI Pydantic Schemas (`backend/app/modules/kpi/schemas.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `KpiValueOut` | Pydantic BaseModel | Single KPI value in the live endpoint response |
| `KpiValueOut.value` | Schema field (float\|None) | Scalar value |
| `KpiValueOut.meta` | Schema field (Any, optional) | Supplementary JSON data |
| `KpiLiveResponse` | Pydantic BaseModel | Full live KPI response |
| `KpiLiveResponse.garage_id` | Schema field (int) | Tenant |
| `KpiLiveResponse.computed_at` | Schema field (datetime) | Computation time |
| `KpiLiveResponse.refresh_interval_seconds` | Schema field (int) | Client polling interval hint |
| `KpiLiveResponse.kpis` | Schema field (dict[str, KpiValueOut]) | All KPI codes and their values |
| `KpiSnapshotOut` | Pydantic BaseModel | Single persisted KPI snapshot record |
| `KpiSnapshotOut.snapshot_date` | Schema field (date) | Snapshot date |
| `KpiSnapshotOut.kpi_code` | Schema field (str) | KPI identifier |
| `KpiSnapshotOut.value` | Schema field (Decimal\|None) | Scalar value |
| `KpiSnapshotOut.meta` | Schema field (Any\|None) | Supplementary data |
| `KpiTrendResponse` | Pydantic BaseModel | Trend query response |
| `KpiTrendResponse.kpi_code` | Schema field (str) | Which KPI is trended |
| `KpiTrendResponse.from_date` | Schema field (date) | Range start |
| `KpiTrendResponse.to_date` | Schema field (date) | Range end |
| `KpiTrendResponse.points` | Schema field (list[KpiSnapshotOut]) | Ordered data points |
| `AnalyticsTrendPoint` | Pydantic BaseModel | One date/value data point for chart rendering |
| `MechanicProductivityEntry` | Pydantic BaseModel | Per-mechanic productivity summary |
| `MechanicProductivityEntry.name` | Schema field (str) | Mechanic display name |
| `MechanicProductivityEntry.completed_count` | Schema field (int) | Completed repair orders in period |
| `MechanicProductivityEntry.avg_duration_h` | Schema field (float\|None) | Average repair duration in hours |
| `AnalyticsResponse` | Pydantic BaseModel | Full analytics response for the charts API |
| `AnalyticsResponse.revenue_trend` | Schema field (list[AnalyticsTrendPoint]) | Daily revenue series |
| `AnalyticsResponse.repair_count_trend` | Schema field (list[AnalyticsTrendPoint]) | Daily repair count series |
| `AnalyticsResponse.mechanic_productivity` | Schema field (list[MechanicProductivityEntry]) | Per-mechanic data |

**TypeScript API (`frontend/src/lib/kpiApi.ts`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `KpiValue` | TS Interface | Single KPI value object |
| `KpiValue.value` | Interface property (number\|null) | Scalar value |
| `KpiValue.meta` | Interface property (unknown, optional) | Supplementary data |
| `KpiLiveResponse` (TS) | TS Interface | Live endpoint response |
| `KpiLiveResponse.garage_id` | Interface property (number) | Tenant |
| `KpiLiveResponse.computed_at` | Interface property (string) | Computation ISO timestamp |
| `KpiLiveResponse.refresh_interval_seconds` | Interface property (number) | Polling interval |
| `KpiLiveResponse.kpis` | Interface property (`Record<string, KpiValue>`) | KPI map |
| `KpiSnapshotPoint` | TS Interface | Single historical snapshot for trend chart |
| `KpiSnapshotPoint.snapshot_date` | Interface property (string) | Snapshot date (ISO) |
| `KpiSnapshotPoint.kpi_code` | Interface property (string) | KPI code |
| `KpiSnapshotPoint.value` | Interface property (number\|null) | Value |
| `KpiTrendResponse` (TS) | TS Interface | Trend query response |
| `KpiTrendResponse.kpi_code` | Interface property (string) | Which KPI |
| `KpiTrendResponse.from_date` | Interface property (string) | Start date |
| `KpiTrendResponse.to_date` | Interface property (string) | End date |
| `KpiTrendResponse.points` | Interface property (KpiSnapshotPoint[]) | Data points |
| `TopCustomerEntry` | TS Interface | One row in the top-10 customers table |
| `TopCustomerEntry.rank` | Interface property (number) | Rank (1-based) |
| `TopCustomerEntry.customer_id` | Interface property (string) | Customer UUID |
| `TopCustomerEntry.name` | Interface property (string) | Customer name |
| `TopCustomerEntry.revenue_minor` | Interface property (number) | Revenue in centimes |
| `TopSupplierEntry` | TS Interface | One row in the top-10 suppliers table |
| `TopSupplierEntry.rank` | Interface property (number) | Rank |
| `TopSupplierEntry.supplier_id` | Interface property (string) | Supplier UUID |
| `TopSupplierEntry.name` | Interface property (string) | Supplier name |
| `TopSupplierEntry.spend_minor` | Interface property (number) | Spend in centimes |
| `AnalyticsTrendPoint` (TS) | TS Interface | Date/value pair for chart data |
| `MechanicProductivityEntry` (TS) | TS Interface | Per-mechanic productivity row |
| `AnalyticsResponse` (TS) | TS Interface | Full analytics API response |
| `ExportTable` | TS type alias | `'top_customers' \| 'top_suppliers' \| 'low_stock_alerts'` |
| `ExportFormat` | TS type alias | `'csv' \| 'xlsx'` |
| `kpiApi` | TS Constant (object) | API client with `getLive`, `getTrend`, `getAnalytics`, `getExportUrl`, `downloadExport` |

**React State (`frontend/src/pages/kpi/KpiDashboardPage.tsx`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `Period` | TS type alias | `'today'\|'week'\|'month'\|'quarter'\|'year'\|'custom'` |
| `PERIOD_LABELS` | TS Constant (`Record<Period, string>`) | French labels for period buttons |
| `BAR_COLORS` | TS Constant (string[]) | Array of hex colors for mechanic productivity chart bars |
| `period` / `setPeriod` | React State (Period) | Active dashboard period selection |
| `customFrom` / `setCustomFrom` | React State (string) | Custom range start date |
| `customTo` / `setCustomTo` | React State (string) | Custom range end date |
| `loading` (ExportButtons) / `setLoading` | React State (boolean) | Busy flag for export download |
| `['kpi', 'live']` | React Query key | Query key for the live KPI endpoint |
| `['kpi', 'analytics', from, to]` | React Query key | Query key for the analytics endpoint |
| `['kpi', 'snapshots', 'outstanding', from, to]` | React Query key | Query key for the outstanding balance trend |

---

### 8. Accounting Export (Issue 46)

**Python Model (`backend/app/modules/accounting_export/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `AccountingExportStatus` | Python Enum | Three-value export job status |
| `AccountingExportStatus.pending` | Enum member | Export job queued |
| `AccountingExportStatus.completed` | Enum member | Export ZIP generated and stored |
| `AccountingExportStatus.failed` | Enum member | Export job failed |
| `AccountingExportFormat` | Python Enum | Four supported accounting software formats |
| `AccountingExportFormat.sage` | Enum member | Sage format |
| `AccountingExportFormat.cegid` | Enum member | Cegid format |
| `AccountingExportFormat.ebp` | Enum member | EBP format |
| `AccountingExportFormat.generic_csv` | Enum member | Generic CSV format |
| `AccountingExport` | SQLAlchemy Model | ORM class mapped to `accounting_export` table |
| `AccountingExport.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `AccountingExport.public_id` | Model Column (String 36) | UUID stored as string (SQLite compat) |
| `AccountingExport.garage_id` | Model Column (BigInteger) | Tenant scoping |
| `AccountingExport.period_start` | Model Column (String 10) | Export period start date (YYYY-MM-DD) |
| `AccountingExport.period_end` | Model Column (String 10) | Export period end date (YYYY-MM-DD) |
| `AccountingExport.format` | Model Column (String 20) | Export format string |
| `AccountingExport.status` | Model Column (String 20) | Job status string |
| `AccountingExport.file_storage_key` | Model Column (Text, nullable) | S3 key of the generated ZIP file |
| `AccountingExport.exported_by` | Model Column (BigInteger, nullable) | User ID who triggered the export |
| `AccountingExport.exported_at` | Model Column (DateTime TZ, nullable) | When the export completed |
| `AccountingExport.record_counts` | Model Column (JSONB, nullable) | Counts of exported records per type |
| `AccountingExport.error_message` | Model Column (Text, nullable) | Error detail if the export failed |
| `AccountingExport.created_at` | Model Column (DateTime TZ) | Job creation timestamp |
| `AccountingExport.updated_at` | Model Column (DateTime TZ) | Last update timestamp |

**Accounting Export Pydantic Schemas (`backend/app/modules/accounting_export/schemas.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `AccountingExportCreateRequest` | Pydantic BaseModel | Create-export request |
| `AccountingExportCreateRequest.period_start` | Schema field (date) | Start of the accounting period |
| `AccountingExportCreateRequest.period_end` | Schema field (date) | End of the accounting period |
| `AccountingExportCreateRequest.format` | Schema field (str\|None, optional) | Override for `CFG_ACCOUNTING_FORMAT` |
| `AccountingExportOut` | Pydantic BaseModel | Export job response |
| `AccountingExportOut.public_id` | Schema field (str) | Export UUID |
| `AccountingExportOut.garage_id` | Schema field (int) | Tenant |
| `AccountingExportOut.period_start` | Schema field (str) | Period start |
| `AccountingExportOut.period_end` | Schema field (str) | Period end |
| `AccountingExportOut.format` | Schema field (str) | Format |
| `AccountingExportOut.status` | Schema field (str) | Job status |
| `AccountingExportOut.file_storage_key` | Schema field (str\|None) | S3 key |
| `AccountingExportOut.exported_by` | Schema field (int\|None) | User ID |
| `AccountingExportOut.exported_at` | Schema field (datetime\|None) | Completion time |
| `AccountingExportOut.record_counts` | Schema field (`dict[str, Any]\|None`) | Per-type export counts |
| `AccountingExportOut.error_message` | Schema field (str\|None) | Error detail |
| `AccountingExportOut.created_at` | Schema field (datetime) | Creation timestamp |
| `AccountingExportOut.updated_at` | Schema field (datetime) | Last update timestamp |
| `AccountingExportListResponse` | Pydantic BaseModel | Paginated export list response |
| `AccountingExportListResponse.items` | Schema field (list[AccountingExportOut]) | Export jobs on this page |
| `AccountingExportListResponse.total` | Schema field (int) | Total count |
| `AccountingExportListResponse.page` | Schema field (int) | Current page |
| `AccountingExportListResponse.page_size` | Schema field (int) | Page size |
| `AccountingExportPreviewResponse` | Pydantic BaseModel | Pre-export preview for re-export risk detection |
| `AccountingExportPreviewResponse.already_exported_invoices` | Schema field (int) | Count of already-exported invoices in the period |
| `AccountingExportPreviewResponse.already_exported_payments` | Schema field (int) | Count of already-exported payments in the period |
| `AccountingExportPreviewResponse.already_exported_supplier_invoices` | Schema field (int) | Count of already-exported supplier invoices in the period |
| `AccountingExportPreviewResponse.pending_invoices` | Schema field (int) | Invoices not yet exported |
| `AccountingExportPreviewResponse.pending_payments` | Schema field (int) | Payments not yet exported |
| `AccountingExportPreviewResponse.pending_supplier_invoices` | Schema field (int) | Supplier invoices not yet exported |
| `AccountingExportPreviewResponse.warning` | Schema field (str\|None) | Human-readable re-export warning |

**Accounting Export Service (`backend/app/modules/accounting_export/service.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `AccountingExportNotFoundError` | Exception class | Raised when an export public UUID is not found |
| `AccountingExportInvalidFormatError` | Exception class | Raised when an unsupported format string is provided |
| `_VALID_FORMATS` | Python Constant (set) | Set of valid format strings: `{"sage","cegid","ebp","generic_csv"}` |

**`Invoice.is_exported` (added to pre-existing `invoice` table via migration 0027)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `Invoice.is_exported` | Model Column (Boolean) | Lock flag on the existing `Invoice` model; set after accounting export |

---

### 9. Config / Core (`backend/app/core/config.py`)

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `s3_bucket_media` | Config field (str) | S3 bucket name for media (photos/videos) |
| `cfg_po_match_tolerance_percent` | Config field (float, default 5.0) | Percentage tolerance for three-way match price comparison |
| `cfg_upload_chunk_size_bytes` | Config field (int, default 5 MB) | S3 multipart upload minimum chunk size |
| `cfg_photo_archive_after_days` | Config field (int, default 90) | Days after upload before photo is moved to cold storage |
| `cfg_image_max_dimension` | Config field (int, default 1920) | Client-side image compression target (longest edge, px) |
| `cfg_image_quality` | Config field (int, default 85) | Client-side JPEG/WebP compression quality (0–100) |
| `cfg_media_session_ttl_hours` | Config field (int, default 24) | Hours before an incomplete upload session expires |
| `s3_bucket_media_archive` | Config field (str, default '') | S3 bucket for cold-storage archived media; falls back to `s3_bucket_media` |
| `cfg_inspection_approval_expiry_days` | Config field (int, default 7) | Days a customer approval JWT link stays valid |
| `cfg_kpi_refresh_interval_seconds` | Config field (int, default 300) | Live KPI endpoint Redis cache TTL |
| `cfg_kpi_workshop_capacity` | Config field (int, default 10) | Number of workshop bays for occupancy KPI |
| `cfg_accounting_format` | Config field (str, default `"generic_csv"`) | Default accounting export format |
| `cfg_notification_max_retries` | Config field (int, default 3) | Maximum notification delivery retry attempts |
| `cfg_quiet_hours_start` | Config field (str, default `"22:00"`) | HH:MM start of notification quiet window |
| `cfg_quiet_hours_end` | Config field (str, default `"08:00"`) | HH:MM end of notification quiet window |
| `cfg_reminder_delay_1_days` | Config field (int, default 7) | Days after due date for first reminder notification |
| `cfg_reminder_delay_2_days` | Config field (int, default 14) | Days after due date for second reminder notification |
| `cfg_reminder_delay_3_days` | Config field (int, default 30) | Days after due date for third reminder notification |
| `cfg_sms_provider` | Config field (str, default '') | SMS provider label (e.g. `"vonage"`) |
| `cfg_sms_api_url` | Config field (str, default '') | SMS provider base API URL |
| `cfg_sms_api_key` | Config field (str, default '') | SMS provider API key or bearer token |
| `cfg_sms_from` | Config field (str, default '') | SMS sender ID or E.164 number |
| `cfg_config_cache_ttl_seconds` | Config field (int, default 60) | Redis cache TTL in seconds for DB-backed CFG_* settings |

---

### 10. Runtime Config / GarageSetting (Issue 54)

**Python Model (`backend/app/modules/config/models.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `GarageSetting` | SQLAlchemy Model | ORM class mapped to `garage_setting` table |
| `GarageSetting.id` | Model Column (BigIntPK) | Auto-increment primary key |
| `GarageSetting.garage_id` | Model Column (BigInteger) | Tenant scoping; `0` = global default |
| `GarageSetting.key` | Model Column (String 100) | CFG_* key name |
| `GarageSetting.value` | Model Column (Text) | String value (caller casts to correct type) |
| `GarageSetting.description` | Model Column (Text, nullable) | Human-readable description |
| `GarageSetting.updated_at` | Model Column (DateTime TZ) | Last write timestamp |
| `GarageSetting.updated_by` | Model Column (BigInteger, nullable) | User ID who last updated the setting |

**Pydantic Schemas (`backend/app/modules/config/schemas.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `GarageSettingOut` | Pydantic BaseModel | API response for a single setting row |
| `GarageSettingUpsertRequest` | Pydantic BaseModel | Request body for PUT /settings/{key} |
| `GarageSettingListResponse` | Pydantic BaseModel | Paginated list of settings |

**SettingsService (`backend/app/modules/config/service.py`)**

| Variable Name | Type/Location | Brief Description |
|---|---|---|
| `_CACHE_PREFIX` | Python Constant (str) | Redis key prefix: `"cfg"` |
| `_GLOBAL_GARAGE_ID` | Python Constant (int) | Sentinel for global default garage: `0` |
| `SettingsService` | Python Class | DB + Redis backed service for runtime settings |
| `SettingsService.get_setting` | Method | Get string value; checks Redis → DB → env → default |
| `SettingsService.get_int` | Method | Typed int getter |
| `SettingsService.get_bool` | Method | Typed bool getter (`true/1/yes/on` → True) |
| `SettingsService.get_float` | Method | Typed float getter |
| `SettingsService.upsert_setting` | Method | Write setting to DB and invalidate Redis cache |
| `SettingsService.delete_setting` | Method | Remove DB row and invalidate cache |
| `SettingsService.list_settings` | Method | List all settings for a garage_id |
| `get_settings_service` | Python function | Convenience factory for FastAPI dependency injection |
