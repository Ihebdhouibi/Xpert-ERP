# Dokploy Setup Guide

## 1. Install Dokploy on OVH server

```bash
ssh ubuntu@<SERVER_IP>

# One-line install (installs Docker if not present)
curl -sSL https://dokploy.com/install.sh | sh
```

Dokploy dashboard will be available at: `http://<SERVER_IP>:3000`

> **Secure it immediately**: set up a password on first login, then enable Traefik + HTTPS so the dashboard itself is served over TLS.

---

## 2. Connect GitHub repository

1. Dokploy dashboard → **Git** → **GitHub** → **Connect**
2. Authorize the Dokploy GitHub App on the `Ihebdhouibi/Xpert-ERP` repository
3. This enables Dokploy to read the repo and receive webhook events

---

## 3. Create Production application

### 3.1 New Application
- Dashboard → **Projects** → **New Project** → Name: `xpert-erp-production`
- **Add Service** → **Docker Compose**
- Source: **GitHub** → repo `Ihebdhouibi/Xpert-ERP` → branch `deployment`
- Compose file path: `infra/docker-compose.yml`

### 3.2 Environment variables
- In the service settings → **Environment** tab
- Paste contents of `.env.production.template` with real values filled in
- Key overrides for Dokploy (compose service names are resolved on the network):
  ```
  DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
  REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
  S3_ENDPOINT_URL=http://minio:9000
  ```

### 3.3 Domain + SSL
- **Domains** tab → Add domain: `motors-utilitaires.fr`
- Port: `5173` (frontend Nginx container)
- Enable **Let's Encrypt** → Dokploy handles cert renewal automatically
- Add second domain for API if needed: `api.motors-utilitaires.fr` → port `8000`

### 3.4 Get the redeploy webhook URL
- Service settings → **Deployments** tab → **Webhook URL**
- Copy and save to GitHub Secret `DOKPLOY_PRODUCTION_WEBHOOK`

---

## 4. Create Staging application

Repeat section 3 with:
- Project name: `xpert-erp-staging`
- Branch: `staging`
- Domain: `staging.motors-utilitaires.fr`
- Save webhook URL to GitHub Secret `DOKPLOY_STAGING_WEBHOOK`

> Staging uses its **own database volume** — never shared with production.

---

## 5. Update docker-compose.yml to use ghcr.io images

Once GitHub Actions is building and pushing images, update the compose file so Dokploy pulls pre-built images instead of building on the server:

```yaml
# infra/docker-compose.yml — production/staging override
services:
  api:
    image: ghcr.io/ihebdhouibi/xpert-erp-backend:latest   # or :staging
    # remove the build: block

  frontend:
    image: ghcr.io/ihebdhouibi/xpert-erp-frontend:latest  # or :staging
    # remove the build: block
```

> Until GitHub Actions is set up, leave the `build:` blocks — Dokploy will build locally.

---

## 6. Install monitoring stack (same server)

### Uptime Kuma
- Dokploy → **New Service** → **Docker** → Image: `louislam/uptime-kuma:1`
- Port: `3001:3001`
- Access: `http://<SERVER_IP>:3001`
- Add monitor: URL `https://motors-utilitaires.fr/api/v1/health` → every 1 min
- Configure alerts: email or Telegram

### Portainer (optional — Docker management UI)
```bash
docker volume create portainer_data
docker run -d -p 9443:9443 --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

---

## 7. Verify deployment

```bash
# SSH into server
ssh ubuntu@<SERVER_IP>

# Check all containers are running
docker ps

# Check API health
curl http://localhost:8000/api/v1/health

# Check frontend
curl -I http://localhost:5173

# View live logs
docker compose -f /path/to/infra/docker-compose.yml logs -f api
```

---

## 8. First-time admin setup

```bash
# Only run ONCE — creates the super_admin user
docker exec -it xpert_erp_api python seed_admin.py

# Follow the prompts to set email + password for the client
```

---

## Dokploy quick reference

| Action | Where |
|---|---|
| Manual redeploy | Service → Deployments → Deploy now |
| Rollback to previous | Service → Deployments → click old deploy → Rollback |
| View container logs | Service → Logs |
| Edit env vars | Service → Environment |
| SSL certificate status | Server → Traefik → Certificates |
| Webhook URL | Service → Deployments → Webhook |
