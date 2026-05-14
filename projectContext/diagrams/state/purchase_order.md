# State Machine — Purchase Order

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> sent : send to supplier
    sent --> partially_received : first reception with some quantity
    sent --> completed : full reception in one go
    partially_received --> completed : last reception completes order
    sent --> cancelled : cancel before reception
    draft --> cancelled : abandon
    completed --> [*]
    cancelled --> [*]
```

Receptions update `purchase_order_line.quantity_received`. The PO becomes `completed` when every line's received equals ordered (or supplier-shortship is closed by admin).
