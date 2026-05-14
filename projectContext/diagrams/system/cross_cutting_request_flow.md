# Cross-Cutting: End-to-End Request Flow with Logging and Audit

```mermaid
sequenceDiagram
    autonumber
    participant U as User browser
    participant LB as Reverse proxy
    participant API as FastAPI
    participant SRV as Module service
    participant REP as Repository
    participant DB as PostgreSQL
    participant LOG as Per-component logger
    participant AUD as Audit writer

    U->>LB: HTTPS request
    LB->>API: Forward with X-Request-Id
    API->>API: Authn (JWT) + Authz (permission)
    API->>SRV: Call service method (DTO)
    SRV->>REP: Repository query or write
    REP->>DB: SQL with transaction
    DB-->>REP: Result
    REP-->>SRV: Domain object
    SRV->>AUD: Record sensitive event (if any)
    SRV->>LOG: Structured event
    SRV-->>API: Result DTO
    API-->>LB: JSON response + X-Request-Id
    LB-->>U: Response
```

Every request carries an `X-Request-Id` (generated at the proxy if absent). The id is bound to the structured logger and to every audit log entry written during the request, making post-hoc correlation cheap.
