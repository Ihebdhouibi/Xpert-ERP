# Deployment View (C4 Level 4)

```mermaid
flowchart TB
    subgraph Internet
        U[Users browsers and tablets]
    end

    subgraph Edge[Edge]
        LB[Reverse proxy + TLS<br/>Nginx or Traefik]
    end

    subgraph App[Application host]
        Web[Nginx<br/>serves SPA]
        Api1[FastAPI container]
        Wkr1[Worker container]
        Red[Redis container]
    end

    subgraph DataLayer[Data layer]
        PG[(PostgreSQL<br/>primary)]
        PGS[(PostgreSQL<br/>standby - optional)]
        S3[(Object storage<br/>S3 compatible)]
    end

    subgraph BackupZone[Backup]
        Snap[(Cloud snapshot store)]
    end

    U --> LB
    LB --> Web
    LB --> Api1
    Api1 --> PG
    Api1 --> S3
    Api1 --> Red
    Wkr1 --> PG
    Wkr1 --> S3
    Wkr1 --> Red
    PG -. WAL .-> PGS
    PG -. base + WAL .-> Snap
    S3 -. lifecycle .-> Snap
```

This is the single-host topology — the default for one garage. The same containers run on Kubernetes for multi-garage or scale; see [03_ARCHITECTURE.md](../../03_ARCHITECTURE.md) §5.2.
