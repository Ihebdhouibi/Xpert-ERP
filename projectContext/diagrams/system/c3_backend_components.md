# Backend Components (C4 Level 3)

```mermaid
flowchart TB
    subgraph API[FastAPI process]
        GW[API Gateway layer<br/>middleware, request_id,<br/>auth, rate limit, CORS]
        subgraph Modules
            AUTH[auth]
            RBAC[rbac]
            CUST[customer]
            VEH[vehicle]
            RO[repair_order]
            INSP[inspection]
            WORK[workshop]
            INV[inventory]
            QUOT[quotation]
            INVO[invoice]
            PAY[payment]
            CASH[cash_register]
            SUP[supplier]
            PO[purchase_order]
            NOTIF[notification]
            DOC[document]
            OCR[ocr]
            REP[reporting]
        end
        subgraph Shared
            AUDIT[audit log writer]
            DOCSEQ[document sequence]
            MONEY[money and VAT engine]
            PDF[PDF rendering]
            CFG[config loader]
            LOG[per-component logger]
            EVT[domain event bus]
        end
        GW --> Modules
        Modules --> Shared
        Modules --> EVT
        EVT --> Modules
    end
```

Each module is a self-contained package: `router.py`, `schemas.py`, `service.py`, `repository.py`, `models.py`, `events.py`, `permissions.py`, `config.py`, `exceptions.py`, `tests/`.

Modules talk to one another only through (a) service calls — same transaction — or (b) domain events — eventual consistency. They never reach into another module's models or repository.
