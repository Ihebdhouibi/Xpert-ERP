# DNS Setup Guide — Xpert-ERP

## What DNS is

Your server has a numeric IP address (`51.210.2.5`).
DNS (Domain Name System) is the internet's "phone book" — it translates a
human-readable domain name like `motors-utilitaires.fr` into that IP address.

Without DNS:
- Users must type `http://51.210.2.5:5173` to reach the app
- HTTPS/SSL is impossible (Let's Encrypt requires a domain name)
- The app looks unprofessional

With DNS + SSL:
- Users type `https://motors-utilitaires.fr`
- The browser gets a green padlock (HTTPS)
- All traffic is encrypted

---

## Domains needed

| Domain / Subdomain | Points to | Purpose |
|---|---|---|
| `motors-utilitaires.fr` | `51.210.2.5` | Main app (production frontend) |
| `staging.motors-utilitaires.fr` | `51.210.2.5` | Staging environment |
| `deploy.motors-utilitaires.fr` | `51.210.2.5` | Dokploy admin dashboard |
| `api.motors-utilitaires.fr` *(optional)* | `51.210.2.5` | Direct API access |

All subdomains point to the **same IP**. Traefik (the reverse proxy inside Dokploy)
routes traffic to the correct container based on the domain name in the HTTP request.

---

## Step 1 — Buy a domain

### Option A: OVH (recommended — same account)
1. Go to https://www.ovhcloud.com/fr/domains/
2. Search for `motors-utilitaires.fr`
3. Purchase (typically 7–15 €/year)
4. The domain automatically appears in your OVH Manager

### Option B: Cloudflare Registrar (cheapest long-term)
1. Go to https://www.cloudflare.com/products/registrar/
2. Create a free Cloudflare account
3. Search and purchase the domain (at-cost, ~8 €/year, no markup)
4. You get Cloudflare's DNS management + DDoS protection for free

---

## Step 2 — Create DNS records

Once you own the domain, go to the DNS management panel (OVH Manager or Cloudflare).

Add these **A records** (A = maps domain → IPv4 address):

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` (root domain) | `51.210.2.5` | 300 |
| A | `staging` | `51.210.2.5` | 300 |
| A | `deploy` | `51.210.2.5` | 300 |

### In OVH Manager (if you bought through OVH):
1. OVH Manager → **Web Cloud** → **Domain names** → select your domain
2. Tab **DNS Zone**
3. Click **Add an entry** for each row in the table above
4. Type = `A`, subdomain = as shown, target = `51.210.2.5`

### In Cloudflare:
1. Cloudflare dashboard → select domain → **DNS** tab
2. Click **Add record** for each row
3. **Proxy status**: set to **DNS only** (grey cloud) for now
   (Proxied mode can interfere with Let's Encrypt certificate issuance)

---

## Step 3 — Wait for propagation

DNS changes take 5 minutes to 48 hours to propagate worldwide (usually < 30 min).

Check propagation:
```bash
# From your local machine
nslookup motors-utilitaires.fr
# Expected: Address: 51.210.2.5

# Or use https://www.whatsmydns.net/ and check your domain
```

---

## Step 4 — Configure Dokploy with the domain

Once DNS resolves to your server IP:

1. Dokploy dashboard → **Settings → Web Server**
2. **Domain** field: `deploy.motors-utilitaires.fr`
3. **Let's Encrypt Email**: your real email
4. **HTTPS toggle**: ON
5. Click **Save**, then **Traefik → Reload**

Dokploy will automatically obtain an SSL certificate from Let's Encrypt.
The dashboard will then be accessible at `https://deploy.motors-utilitaires.fr`
and port 3000 can be closed in the OVH firewall.

---

## Step 5 — Close port 3000 in OVH firewall (after DNS + SSL work)

1. OVH Manager → **Public Cloud** → **Motors utilitaires** project
2. **Network → Security Groups**
3. Remove or restrict the inbound rule for port `3000`

After this, the Dokploy dashboard is only accessible via `https://deploy.motors-utilitaires.fr`
(protected by HTTPS + your Dokploy login), not via the raw IP + port.

---

## DNS record summary (copy-paste ready)

```
Type  Name                              Value         TTL
A     @                                 51.210.2.5    300
A     staging                           51.210.2.5    300
A     deploy                            51.210.2.5    300
```

Replace `@` with the full domain if your registrar requires it
(e.g. `motors-utilitaires.fr` instead of `@`).

---

## Ports used (reference for firewall rules)

| Port | Service | Open to |
|---|---|---|
| 80 | HTTP (redirects to HTTPS) | Public |
| 443 | HTTPS (frontend + API) | Public |
| 3000 | Dokploy dashboard | Close after DNS setup |
| 22 | SSH | Your IP only |
| 5432 | PostgreSQL | Never — internal only |
| 6379 | Redis | Never — internal only |
| 9000/9001 | MinIO | Internal only (or restrict) |
