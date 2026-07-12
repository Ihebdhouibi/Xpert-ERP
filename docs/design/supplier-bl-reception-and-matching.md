# Design — Supplier Bon de livraison: reception, PO link & 3-way match

**Status:** DESIGN (approved decisions below) · **Branch:** `feat/ocr-document-foundation`
**Date:** 2026-06-29
**Scope:** the supplier/achats side only (Fournisseur → Garage). The customer-side
`delivery_note` module is unrelated.

## 1. Goal

Turn an incoming supplier **Bon de livraison (BL)** into a first-class record that:
1. is **always linked to a Bon de commande (PO)**,
2. drives **stock-in** and the PO's `quantity_received`,
3. carries the supplier's **BL number** as the **correlation key** so the later
   supplier **facture** can be reconciled in a full 3-way match
   (*ordered ↔ received ↔ invoiced*).

## 2. Approved decisions

| # | Decision | Choice |
|---|---|---|
| Factures scope | customer vs supplier | **Supplier only** |
| Out-of-scope categories | remove vs hide | **UI-hide** (enum kept; done in `0055`) |
| Supplier owner types | which to add | **`supplier` (Fournisseur)** + **`purchase_order` (Bon de commande)** (done in `0055`) |
| BL → PO link | optional vs mandatory | **Mandatory**: a BL must link to exactly one PO before extraction |
| Phone-order PO | seed from OCR vs manual | **Manual entry first** (create a full PO, then OCR + match) |
| Over-delivery / extra item | block vs allow | **Allow + flag for review** (offer to add extra line to PO) |
| BL number uniqueness | none vs unique | **Unique per (garage, supplier)**, duplicate → warn + override |

## 3. Domain model & cardinality

```
Bon de commande (PO)  1 ───< N  Bon de livraison (BL)     one PO, many BLs
Bon de livraison      N ───> 1  Bon de commande           every BL → exactly one PO (mandatory)
PO line               1 ───< N  BL line                   one ordered line received over several BLs
```

Example (the 50 / 5×10 case): PO line `quantity_ordered = 50`; BL₁…BL₅ deliver 10
each → `po_line.quantity_received` accumulates 10→20→…→50; PO status flips
`sent → partially_received → completed` automatically.

## 4. Data model (new)

Today reception only bumps `purchase_order_line.quantity_received` and writes a
stock movement — there is **no stored BL**. Introduce two tables.

### `supplier_delivery_note` (the BL record)
| Column | Notes |
|---|---|
| `id`, `public_id`, `garage_id` | standard |
| `purchase_order_id` | FK → purchase_order, **NOT NULL** (the mandatory link) |
| `supplier_id` | denormalised from the PO |
| `bl_number` | supplier's BL number — **correlation key**; **UNIQUE(garage_id, supplier_id, bl_number)** |
| `bl_date` | date on the slip |
| `document_id` | FK → `document` (the uploaded GED file / OCR source) |
| `status` | `draft → confirmed → cancelled` |
| `received_at`, `received_by`, `notes` | audit |
| `has_discrepancy`, `discrepancy_note` | set when over/extra (decision: allow+flag) |

### `supplier_delivery_note_line`
| Column | Notes |
|---|---|
| `id`, `supplier_delivery_note_id` | FK → BL |
| `po_line_id` | FK → purchase_order_line (which ordered line this delivers); **nullable** for extra items not on the PO |
| `part_id` | resolved part (nullable for untracked) |
| `description`, `quantity_received`, `condition` | |
| `match_flag` | `ok` / `over` / `extra` (item not on PO) |

**Rollup:** `purchase_order_line.quantity_received` = Σ `bl_line.quantity_received`
across confirmed BLs for that PO line (the existing field becomes the aggregate).

**Relationship to existing modules:**
- `purchase_order` — unchanged schema; `quantity_received` now fed by BLs.
- `document` — the uploaded BL file; `owner_entity_type='purchase_order'`,
  `owner_entity_id=PO.id`; the BL record references it via `document_id`.
- `supplier_invoice` — its lines already carry `po_line_id`; for the 3-way match
  we add the ability to resolve a facture's BL references via `bl_number`.

## 5. Workflows

### 5.1 Upload & mandatory PO link
1. Upload BL → `Catégorie = Bon de livraison` (`supplier_delivery_note`).
2. `Type propriétaire = Bon de commande` → **PO picker** (searchable:
   *n° BC · fournisseur · date · reste à recevoir*) — replaces the raw
   "ID propriétaire" field.
3. No matching PO (phone order) → **"+ Créer un nouveau bon de commande"** →
   inline **full PO creation (manual lines)** → BL links to the new PO.
4. **Hard gate:** extraction/ingest is blocked until a PO is selected or created.

### 5.2 Extraction & matching (OCR)
5. OCR the BL → `bl_number`, `bl_date`, lines (ref/désignation, qty delivered).
6. Match BL lines → PO lines by SKU; propose `quantity_received` per line.
   - exact, partial (qty < ordered), **over** (qty > remaining) → `over`,
     **extra** (SKU not on PO) → `extra`.

### 5.3 Confirm reception
7. On confirm:
   - create `supplier_delivery_note` (+ lines), enforcing `bl_number` uniqueness
     (warn + override on duplicate),
   - **stock IN** movement per line (`ref_type='supplier_delivery_note'`,
     `ref_id=BL.public_id`, `reason` carries `bl_number`),
   - bump each `po_line.quantity_received`,
   - recompute PO status,
   - if any `over`/`extra` → set `has_discrepancy`, surface review (offer to add
     extra line to the PO).

### 5.4 Downstream — facture 3-way match
8. Supplier facture (OCR'd separately) references BL numbers → resolve each to a
   `supplier_delivery_note` via `bl_number` → gives PO + received qty →
   **3-way match**: ordered (PO) ↔ received (BL) ↔ invoiced (facture), flagging
   qty/price discrepancies (reuse `CFG_PO_MATCH_TOLERANCE_PERCENT`).

## 6. BL status machine

```
draft  ──confirm──►  confirmed  ──cancel/reverse──►  cancelled
  └── cancel ──► cancelled
```
- `draft`: editable, no stock impact.
- `confirmed`: stock moved, PO rollup updated, `bl_number` locked.
- `cancelled`: reverses stock movements + decrements the PO rollup.

## 7. UI/UX changes
- Upload dialog: when `Bon de livraison` / owner `Bon de commande` → **PO picker**
  + **"Créer un nouveau BC"**; mandatory before continuing.
- New **BL reception screen**: BL header (number/date) + line-matching grid
  against the PO lines (proposed quantities, discrepancy flags), Confirm action.
- PO detail: list its linked BLs + reception progress (`received / ordered`).

## 8. Suggested implementation phases
1. **Foundation** *(done — `0055`)*: category `supplier_delivery_note`, owner
   types `supplier` / `purchase_order`, scoped dropdowns.
2. **Data model + service**: the two tables + migration; create/confirm/cancel
   BL; stock-in + PO rollup; `bl_number` uniqueness. *(manual, no OCR yet)*
3. **Frontend**: PO picker + create-new (manual) + BL reception/matching screen.
4. **OCR**: BL extractor + auto-match BL↔PO lines + over/extra flagging.
5. **Facture loop**: extract BL refs from supplier factures + 3-way match by
   `bl_number`.

Phases 2–3 already deliver useful **manual BL reception against a PO**; OCR (4)
and the facture loop (5) build on top.

## 9. Open items / out of scope (for now)
- Units / quantity normalization between BL and PO (assume same unit initially).
- Multi-page BLs spanning OCR pages (preview already paginates).
- Whether to keep the **existing manual reception endpoint** alongside BL-driven
  reception (recommended: keep it as a no-document fallback).
- Supplier identity resolution when OCR reads a supplier not yet in the system →
  resolved by §11 (HITL match-or-create).

## 10. BL OCR extraction schema (refined)

Formats vary widely (e.g. label is "N° de la pièce" vs "Numéro"; "Code" vs
"Référence"; "P.U. Net" vs "P.U. H.T."), so the extractor must be
**label-flexible** (heuristic/LLM, like the supplier-invoice extractor), not a
fixed template.

**Header**
- `numero_bl` — N° / Numéro / N° de la pièce — **correlation key** (unique per
  supplier, warn on duplicate).
- `date_bl` — date / date de livraison.
- `fournisseur` — the **issuer** → drives supplier resolution (§11).
- `reference_commande` — order/PO ref if printed → used to auto-suggest the PO.
- `immatriculation` — vehicle plate when present → optional link to vehicle/RO.
- `total_ht`, `tva`, `total_ttc` — when present (valued BLs).
- **Client is always `GARAGE MOTORS UTILITAIRE`** (our garage). **"AL DELIVERY"
  is the delivery/transport company, NOT the client** — do not treat it as the
  client; at most use the client line to confirm the BL is addressed to us.

**Lines** (`lignes`, each):
- `code` / `reference` — supplier part ref.
- `designation_article` — description.
- `quantite` — **may be decimal** (e.g. 0,20).
- `pu_brut` — gross/list unit price.
- `pu_net` — net unit price (after discount).
- `montant_ht` — line total.
- (`reste_a_livrer`, `conditionnement` captured when present.)

Must support **plain BLs** (no prices/totals) and **decimal quantities**.

Proposed review-page schema keys for `supplier_delivery_note`:
`numero_bl, date_bl, fournisseur, reference_commande, immatriculation,
total_ht, tva, total_ttc, lignes` (each line: code, designation_article,
quantite, pu_brut, pu_net, montant_ht).

## 11. Supplier resolution — HITL (Human In The Loop)

On extraction, resolve the extracted `fournisseur` against the supplier list:
- **Match found** → **pre-select** the supplier, but **require user
  confirmation** — never apply silently (HITL).
- **No match** → offer **"Créer un profil fournisseur"** inline, then select the
  new one.

Reuses `supplierApi.list({ search })` / `supplierApi.create`; the supplier form
can be extracted from `SupplierPage` (same pattern as the PO create dialog).

## 12. Line → PO matching
- **Manual map for now**: the user maps each BL line to a PO line / catalog part
  (the supplier `code` ≠ the garage's internal SKU). Auto/fuzzy matching by
  code or désignation is a later enhancement.
