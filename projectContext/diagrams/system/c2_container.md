# Container View (C4 Level 2)

```mermaid
flowchart TB
    subgraph Browser[User device]
        SPA[React SPA<br/>Vite + TypeScript]
    end

    subgraph Server[Application server]
        API[FastAPI app<br/>Python 3.11]
        Worker[Background worker<br/>APScheduler then Celery]
        Static[Static file server<br/>Nginx]
    end

    subgraph Data[Data layer]
        DB[(PostgreSQL 15+)]
        OBJ[(Object storage<br/>S3 compatible)]
        CACHE[(Redis<br/>cache and queue)]
    end

    subgraph Ext[External]
        SMTP[SMTP relay]
        SMSGW[SMS gateway]
    end

    SPA -->|HTTPS REST| API
    API --> DB
    API --> OBJ
    API --> CACHE
    Worker --> DB
    Worker --> OBJ
    Worker --> CACHE
    Worker --> SMTP
    Worker --> SMSGW
    API --> Worker
    Static --> SPA
```

## Container responsibilities

- **React SPA** — UI, routing, optimistic updates, file upload with resume.
- **FastAPI app** — REST API, authn/authz, transactions, audit and logging.
- **Background worker** — OCR, PDF batches, scheduled reminders, KPI snapshots, backups.
- **PostgreSQL** — transactional source of truth.
- **Object storage** — photos, videos, PDFs, scanned documents.
- **Redis** — cache, sessions, deny-list, Celery broker (post-M8).
- **Static server (Nginx)** — serves the built SPA, terminates TLS, reverse-proxies the API.
