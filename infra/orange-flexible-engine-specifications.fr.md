# Spécifications d'hébergement — Xpert ERP

**Plateforme cible :** Orange Business — Flexible Engine (Cloud public, OpenStack)
**Région :** Paris (`eu-west-0`) — France
**Document destiné à :** Orange Business Services (pour devis et provisionnement)
**Modèle de facturation :** à l'usage (PAYG) ou Réservé 1–3 ans, au choix du client
**Date :** 16/06/2026 · **Version :** 1.0

---

## 1. Contexte

Xpert ERP est une application de gestion pour atelier de réparation automobile
(réception, devis, ordres de réparation, facturation, caisse, stock, OCR de
documents). L'architecture est conteneurisée (Docker) et regroupe :

| Composant | Technologie | Profil de charge |
|-----------|-------------|------------------|
| API applicative | FastAPI / Python 3.11 (Uvicorn + Gunicorn) | CPU + RAM |
| Moteur OCR | PaddleOCR 3.x / PaddlePaddle (CPU) | **RAM + CPU intensif** |
| Génération PDF | WeasyPrint | RAM ponctuelle |
| Base de données | PostgreSQL 15 (archivage WAL / PITR) | RAM + IOPS + disque |
| Cache / files | Redis 7 | RAM |
| Stockage objets | MinIO (dev) → **OBS** en production | disque, en croissance |
| Frontend | React 18 (SPA statique, servie par nginx) | négligeable |

**Élément dimensionnant :** le moteur OCR (PaddleOCR/PaddlePaddle en mode CPU)
charge ses modèles d'inférence en mémoire (pic ~2–3 Go par traitement) et requiert
un volume disque conséquent pour ses dépendances. C'est lui qui fixe le
dimensionnement minimal de la machine.

---

## 2. Phase 1 — Démarrage (un atelier, hôte unique)

Topologie « hôte unique » : l'ensemble des conteneurs s'exécute sur une seule
instance ECS. C'est la configuration de départ recommandée.

### 2.1 Instance de calcul (ECS)

| Caractéristique | Valeur demandée |
|-----------------|-----------------|
| Service | Elastic Cloud Server (ECS) |
| Gamme | S6 — usage général |
| **Flavor** | **`s6.xlarge.4` — 4 vCPU / 16 Go RAM** |
| Système d'exploitation | Ubuntu 22.04 LTS 64 bits (licence gratuite) |
| Région / zone | Paris `eu-west-0` |
| Quantité | 1 |

> Minimum acceptable : `s6.xlarge.2` (4 vCPU / 8 Go). Déconseillé : 8 Go laisse
> peu de marge lors d'un traitement OCR simultané à la charge base de données.
> **Recommandé : 16 Go (`s6.xlarge.4`).**

### 2.2 Stockage bloc (EVS)

| Volume | Type | Taille | Usage |
|--------|------|--------|-------|
| Disque système | Ultra-high I/O (SSD) | 50 Go | OS + images Docker (image OCR volumineuse ~5 Go) |
| Disque données | Ultra-high I/O (SSD) | 100 Go | PostgreSQL + archives WAL + fichiers applicatifs |

> Le disque données doit être **extensible** (la base et les documents croissent
> avec l'activité). Type SSD requis pour les IOPS de PostgreSQL.

### 2.3 Réseau

| Élément | Valeur demandée |
|---------|-----------------|
| VPC + sous-réseau privé | 1 |
| Adresse IP publique (EIP) | 1 |
| Bande passante Internet | 20 Mbps (ou facturation au trafic) |
| Groupe de sécurité (entrant) | 443/HTTPS, 80/HTTP (redirection), 22/SSH (restreint à IP d'admin) |

### 2.4 Sauvegarde et stockage objets

| Service | Spécification |
|---------|---------------|
| Sauvegarde (CBR / VBS) | Snapshot **quotidien** des volumes, rétention **30 jours**, réplication hors-site |
| Stockage objets (OBS) | 1 bucket — documents, photos, pièces OCR · versioning activé · chiffrement au repos (SSE) · ~100 Go initial, extensible |

### 2.5 Récapitulatif Phase 1 (à chiffrer par Orange)

| Poste | Spécification | Qté |
|-------|---------------|-----|
| ECS | `s6.xlarge.4` (4 vCPU / 16 Go), Ubuntu 22.04 LTS | 1 |
| EVS système | SSD Ultra-high I/O, 50 Go | 1 |
| EVS données | SSD Ultra-high I/O, 100 Go (extensible) | 1 |
| EIP | IP publique + 20 Mbps | 1 |
| CBR/VBS | Sauvegarde quotidienne, rétention 30 j | 1 |
| OBS | Bucket chiffré, ~100 Go | 1 |
| Support | Niveau à préciser avec le client | — |

---

## 3. Phase 2 — Montée en charge (multi-ateliers / haute disponibilité)

À activer lorsque l'activité croît ou qu'un second atelier est intégré. Aucune
réécriture applicative requise : ces services remplacent les conteneurs
correspondants.

| Service Flexible Engine | Remplace | Bénéfice |
|-------------------------|----------|----------|
| **RDS for PostgreSQL** (managé, HA) | conteneur PostgreSQL | sauvegardes, PITR, bascule automatique gérés par Orange |
| **DCS for Redis** (managé) | conteneur Redis | cache managé, haute disponibilité |
| **OBS** (déjà en place dès la Phase 1) | MinIO | stockage objets durable, règles de cycle de vie |
| **ELB** (Elastic Load Balancer) | nginx unique | répartition de charge, terminaison TLS |
| **Auto Scaling (AS)** | instance unique | montée/descente automatique de l'API et des workers OCR |

> Dimensionnement indicatif Phase 2 : ECS 4 vCPU / 8–16 Go (application + OCR
> uniquement, base déportée) + RDS PostgreSQL 2 vCPU / 8 Go + DCS Redis (petite
> instance). À chiffrer le moment venu.

---

## 4. Exigences transverses

- **Région** : France (Paris `eu-west-0`) — résidence des données.
- **Chiffrement** : au repos (volumes EVS + bucket OBS) et en transit (TLS).
- **Sauvegarde** : quotidienne minimum, rétention 30 jours, copie hors-site
  (objectif RPO 15 min / RTO 1 h pour la base de données).
- **OS** : distribution Linux gratuite (Ubuntu/Debian) — aucune licence Windows
  ni SQL Server nécessaire.
- **Pas de GPU requis** : l'OCR fonctionne en mode CPU ; ne pas provisionner
  d'instance GPU.

---

## 5. Questions à confirmer avec Orange

1. Tarif unitaire `s6.xlarge.4` en région Paris (à l'usage et en Réservé 1 an).
2. Tarif EVS SSD Ultra-high I/O (€/Go/mois) et OBS (€/Go/mois + trafic sortant).
3. Tarif sauvegarde CBR/VBS (€/Go protégé/mois) avec réplication hors-site.
4. Remise négociée applicable au compte du client.
5. Niveau de support inclus / proposé (Standard, Bronze, Silver, Gold).
6. Estimation de la trajectoire de coût Phase 2 (RDS + DCS + ELB).

---

*Toutes les ressources demandées sont localisées en région Paris (France),
conformément aux exigences de résidence des données du client final.*
