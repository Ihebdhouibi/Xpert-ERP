# Sequence — Record Payment

```mermaid
sequenceDiagram
    autonumber
    participant SPA as React SPA
    participant API as FastAPI
    participant PAY as payment service
    participant INVO as invoice service
    participant CUST as customer service
    participant CASH as cash_register service
    participant DB as PostgreSQL
    participant EVT as event bus
    participant LOG as payment logger
    participant AUD as Audit writer

    SPA->>API: POST /api/v1/payments (invoiceId, method, amount, reference)
    API->>API: AuthZ: payment.record
    API->>PAY: record(input)
    PAY->>CASH: current_open_session(garageId)
    CASH-->>PAY: cashSessionId
    PAY->>DB: BEGIN
    PAY->>DB: INSERT payment(cash_session_id, ...)
    PAY->>INVO: apply_payment(invoiceId, amount)
    INVO->>DB: UPDATE invoice (paid_amount, outstanding, status)
    INVO-->>PAY: new status
    PAY->>CUST: write balance_event(delta=-amount)
    CUST->>DB: INSERT customer_balance_event; UPDATE outstanding
    PAY->>DB: COMMIT
    PAY->>AUD: event=payment_recorded
    PAY->>EVT: publish PaymentReceived
    PAY->>LOG: info payment_recorded
    PAY-->>API: dto
    API-->>SPA: 201 Created
```
