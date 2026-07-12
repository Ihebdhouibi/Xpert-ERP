# Deployment Guide — Xpert-ERP

## Branch → Environment mapping

| Branch | Environment | URL |
|---|---|---|
| `develop` | Development (local) | http://localhost:5173 |
| `staging` | Staging | https://staging.motors-utilitaires.fr |
| `deployment` | Production | https://motors-utilitaires.fr |

## CI/CD pipeline

```
feature/* or fix/* branch
        │
        ▼  (PR opened)
   CI runs (pytest + tsc + eslint)
        │
        ▼  (PR merged to develop)
   develop — local dev, no auto-deploy
        │
        ▼  (merge develop → staging)
   staging branch ──► GitHub Actions CD
        │                builds images → ghcr.io
        │                → Dokploy redeploy webhook (staging env)
        │
        ▼  (merge staging → deployment after validation)
   deployment branch ──► GitHub Actions CD
                          builds images → ghcr.io
                          → Dokploy redeploy webhook (production env)
```

## Required GitHub Secrets

Go to: **GitHub → Settings → Secrets and variables → Actions**

| Secret | Description |
|---|---|
| `DOKPLOY_STAGING_WEBHOOK` | Dokploy redeploy URL for staging (from Dokploy dashboard) |
| `DOKPLOY_PRODUCTION_WEBHOOK` | Dokploy redeploy URL for production (from Dokploy dashboard) |

> `GITHUB_TOKEN` is automatic — no setup needed for ghcr.io push.

## Docker images (ghcr.io)

| Image | Tag | Built from |
|---|---|---|
| `ghcr.io/<owner>/xpert-erp-backend` | `staging` | staging branch |
| `ghcr.io/<owner>/xpert-erp-backend` | `latest` | deployment branch |
| `ghcr.io/<owner>/xpert-erp-frontend` | `staging` | staging branch |
| `ghcr.io/<owner>/xpert-erp-frontend` | `latest` | deployment branch |

## First deployment checklist

- [ ] OVH server provisioned (Ubuntu 22.04, min 4 GB RAM)
- [ ] Dokploy installed (`curl -sSL https://dokploy.com/install.sh | sh`)
- [ ] Domain DNS A record pointing to server IP
- [ ] `.env` file created from `.env.production.template` on the server
- [ ] GitHub Secrets `DOKPLOY_STAGING_WEBHOOK` and `DOKPLOY_PRODUCTION_WEBHOOK` set
- [ ] Admin account created (`docker exec -it xpert_erp_api python seed_admin.py`)
- [ ] MinIO buckets created (Dokploy runs `docker compose up` which creates them via lifecycle)

## Admin account creation (first boot only)

```bash
# SSH into the server
ssh ubuntu@<SERVER_IP>

# Create the admin user (interactive prompt for email/password)
docker exec -it xpert_erp_api python seed_admin.py
```

No demo data is seeded — the database starts empty except for system notification templates (idempotent, auto-run on startup).

## Rollback procedure

If a production deployment fails:

1. In Dokploy dashboard → Services → api / frontend → **Deployments** tab
2. Click the previous successful deployment → **Rollback**
3. Dokploy re-activates the old container (the previous image is still cached)

Database rollback (if migration broke something):
```bash
docker exec -it xpert_erp_api alembic downgrade -1
# Then redeploy the previous backend image via Dokploy
```

## Zero-downtime deployment flow

Dokploy uses Docker's rolling update strategy:
1. New container starts with new image
2. Health check passes (GET `/api/v1/health`)
3. Old container is stopped
4. Database migrations run BEFORE step 1 (via the startup lifespan in `main.py`)

## Environment variables

See [ENV_REFERENCE.md](ENV_REFERENCE.md) for a full list with explanations.
