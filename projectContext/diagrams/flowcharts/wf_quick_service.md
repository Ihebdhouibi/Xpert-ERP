# Workflow — Quick Service

Short-cycle services such as oil change, battery replacement, tire service.

```mermaid
flowchart TD
    A[Customer requests quick service] --> B[Quick diagnosis]
    B --> C[Immediate quotation displayed]
    C --> D{Customer accepts}
    D -- no --> Z[Cancelled]
    D -- yes --> E[Service performed]
    E --> F[Parts consumed from stock]
    F --> G[Invoice generated]
    G --> H[Direct payment recorded]
    H --> I[Vehicle delivered]
    I --> J[Receipt issued]
```

No full Repair Order workflow is required; the service may still create a minimal OR for history and KPI tracking.
