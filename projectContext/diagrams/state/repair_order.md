# State Machine — Repair Order

```mermaid
stateDiagram-v2
    [*] --> created : reception opens OR
    created --> diagnosis : mechanic begins
    diagnosis --> in_repair : approved scope
    in_repair --> paused_parts : waiting for parts
    in_repair --> paused_approval : additional work needs approval
    paused_parts --> in_repair : parts received
    paused_approval --> in_repair : customer approves
    paused_approval --> cancelled : customer rejects
    in_repair --> finished : work done
    finished --> delivered : vehicle handed back
    finished --> in_repair : rework required
    diagnosis --> cancelled : customer cancels
    in_repair --> cancelled : admin cancels
    delivered --> [*]
    cancelled --> [*]
```

Transitions are gated by permission `repair_order.transition` (cancel requires `repair_order.transition.cancel`). Every transition writes a `ro_status_event` row and an `audit_log` entry.
