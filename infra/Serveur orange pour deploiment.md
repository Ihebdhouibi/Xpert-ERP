# Spécifications — Serveur Xpert ERP (Orange Flexible Engine)

**Région :** Paris (`eu-west-0`, France) · **Engagement :** 1 an réservé · **Système :** Ubuntu 22.04 LTS (gratuit)

Serveur unique tout-en-un (application + OCR, base PostgreSQL, cache Redis,
stockage de fichiers — en conteneurs Docker).

## 1. Calcul (ECS)
| Élément | Valeur |
|---|---|
| Service | Elastic Cloud Server (ECS), gamme **S6** (usage général) |
| Flavor / Taille | **`s6.xlarge.2` — 4 vCPU / 8 Go RAM** |
| Quantité | 1 |

## 2. Stockage bloc (EVS — disques de la machine)
| Disque | Type | Taille | Usage |
|---|---|---|---|
| Disque **système** | SSD (Ultra-high I/O) | **40 Go** | OS + conteneurs Docker + journaux |
| Disque **données** | SSD (Ultra-high I/O) | **100 Go** (extensible) | PostgreSQL, archives WAL, fichiers/photos, MinIO |

- **Chiffrement au repos** activé sur les deux disques.
- Le disque données doit être **extensible** (la base et les documents grossissent).

## 3. Stockage objets (OBS) — *recommandé*
| Élément | Valeur |
|---|---|
| Service | Object Storage Service (OBS), 1 bucket |
| Capacité initiale | **~100 Go**, extensible |
| Options | **Chiffrement (SSE)**, **versioning**, règles de cycle de vie (archivage des vieilles photos) |
| Usage | Stockage durable des documents scannés / photos (hors du disque de la machine) |

## 4. Réseau
| Élément | Valeur |
|---|---|
| VPC + sous-réseau privé | 1 |
| Adresse IP publique (EIP) | 1 |
| Bande passante Internet | **20 Mbps** (ou facturation au trafic) |
| Groupe de sécurité (entrant) | **443/HTTPS**, **80/HTTP** (redirection), **22/SSH** restreint à l'IP d'admin |

## 5. Sauvegarde (CBR / VBS)
| Élément | Valeur |
|---|---|
| Fréquence | **Quotidienne** |
| Rétention | **30 jours** |
| Copie | **Hors-site** (autre zone) |
| Objectifs | Perte max. 15 min (RPO) · Remise en service ~1 h (RTO) |

## 6. Support
| Élément | Valeur |
|---|---|
| Niveau | **Standard** (inclus) — ou Bronze/Silver/Gold en option, à arbitrer |

## 7. À NE PAS provisionner
- **Pas de GPU** (l'OCR tourne en CPU).
- **Pas de licence Windows / SQL Server** (tout est Linux/Open-Source).

---

## Points à demander explicitement à Orange
1. Devis en **engagement 1 an (réservé)**, pas au paiement à l'usage.
2. **Remise négociée** appliquée à votre compte.
3. Tarifs unitaires : ECS `s6.xlarge.2` réservé 1 an · EVS SSD (€/Go/mois) · OBS (€/Go/mois + trafic sortant) · sauvegarde CBR (€/Go protégé/mois).
