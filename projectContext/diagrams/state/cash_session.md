# State Machine — Cash Session

```mermaid
stateDiagram-v2
    [*] --> open : cashier opens session
    open --> closed : cashier closes with cash count
    closed --> locked : end-of-day finalization
    locked --> [*]
```

Once `locked`, all payments in the session are immutable except via credit note. Differences between expected and counted cash are stored on the session row with a reason.
