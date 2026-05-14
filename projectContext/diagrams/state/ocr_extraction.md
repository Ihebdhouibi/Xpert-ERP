# State Machine — OCR Extraction

```mermaid
stateDiagram-v2
    [*] --> pending : document queued for OCR
    pending --> completed : engine returns fields with confidence >= threshold
    pending --> needs_review : engine returns fields with confidence < threshold
    needs_review --> confirmed : human reviewer approves and applies
    needs_review --> rejected : human reviewer rejects
    completed --> confirmed : auto-confirmed if policy allows
    completed --> rejected : reviewer rejects despite high confidence
    confirmed --> [*]
    rejected --> [*]
```

Default policy: even `completed` extractions require human confirmation for `registration_card` and `id` categories. Auto-confirmation is opt-in per category by config.
