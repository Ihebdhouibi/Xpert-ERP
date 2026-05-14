# Sequence — Cash Session Closing

```mermaid
sequenceDiagram
    autonumber
    participant SPA as React SPA
    participant API as FastAPI
    participant CASH as cash_register service
    participant PDF as PDF service
    participant DB as PostgreSQL
    participant LOG as cash_register logger
    participant AUD as Audit writer

    SPA->>API: POST /api/v1/cash_sessions/{id}:close (counted cash)
    API->>API: AuthZ: cash_session.close
    API->>CASH: close(sessionId, countedCash)
    CASH->>DB: BEGIN
    CASH->>DB: SELECT SUM(payment.amount) per method WHERE cash_session_id=...
    DB-->>CASH: totals per method
    CASH->>CASH: compute expectedCash; difference = countedCash - expectedCash
    CASH->>DB: UPDATE cash_session (closed_at, counted_cash, expected_cash, difference, status=closed)
    CASH->>DB: COMMIT
    CASH->>PDF: render Z report
    PDF-->>CASH: pdf storage_key
    CASH->>AUD: event=cash_session_closed (diff captured)
    CASH->>LOG: info cash_session_closed
    CASH-->>API: dto with z_report
    API-->>SPA: 200

    Note over CASH,DB: End-of-day finalization

    CASH->>DB: UPDATE cash_session set status=locked
    CASH->>AUD: event=cash_session_locked
```
