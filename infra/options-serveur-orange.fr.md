# Options de serveur Orange — Xpert ERP (moteur OCR ONNX)

**Hébergeur :** Orange Business — Flexible Engine · **Région :** Paris (France)
**Engagement :** abonnement **1 an** (réservé) pour les deux options — *pas* de
paiement à l'usage.
**Date :** 24/06/2026 · **Version :** 1.0

> Depuis l'optimisation de l'OCR (passage au moteur léger **ONNX**), la
> consommation mémoire de la lecture de documents est tombée à **~233 Mo** au
> pic (contre ~1,1 Go avant). Un serveur de **8 Go** est désormais largement
> suffisant — ce document propose deux dimensionnements, tous deux en
> **engagement 1 an**.

---

## 1. En bref

| | **Option 1 — Recommandée** | **Option 2 — Économique** |
|---|---|---|
| Machine | `s6.xlarge.2` | `s6.large.2` |
| Processeurs / Mémoire | **4 vCPU / 8 Go** | **2 vCPU / 4 Go** |
| Profil | Confortable, marge pour pics et croissance | Minimal viable, plus serré |
| Coût estimé (1 an, tout compris) | **~80–115 €/mois** | **~55–85 €/mois** |
| Idéal pour | Usage quotidien d'un garage, sérénité | Démarrage à coût réduit |

*Les coûts sont des estimations à confirmer par devis Orange — voir §5.*

---

## 2. Option 1 — Recommandée (`s6.xlarge.2`)

Serveur unique « tout-en-un » : l'ensemble des composants (application + OCR,
base de données PostgreSQL, cache Redis, stockage de fichiers) tourne sur une
seule machine, en conteneurs Docker.

| Élément | Valeur à demander |
|---------|-------------------|
| Type de machine | Flexible Engine **ECS**, gamme **S6** (usage général) |
| **Taille** | **`s6.xlarge.2` — 4 vCPU / 8 Go de mémoire** |
| Système | Ubuntu 22.04 LTS (Linux, gratuit) |
| Région | **Paris (France)** — données hébergées en France |
| Disque système | 40 Go SSD (Ultra-high I/O) |
| Disque données | 100 Go SSD (Ultra-high I/O), **extensible** |
| Adresse IP publique | 1 |
| Sauvegarde | quotidienne, rétention 30 jours, copie hors-site |
| Stockage objets (OBS) | 1 bucket chiffré (documents, photos), ~100 Go |
| Engagement | **1 an (réservé)** |

**Pourquoi la recommander :** 8 Go laissent une marge confortable même si
plusieurs scans, l'édition de PDF et la base de données s'exécutent en même
temps. 4 processeurs gardent l'application réactive. La machine reste
**agrandissable à tout moment** (passage à 16 Go, ou bascule de la base vers un
service managé) sans réinstallation, le jour où l'activité grandit.

---

## 3. Option 2 — Économique (`s6.large.2`)

Même architecture « tout-en-un », sur une machine plus petite. Viable
aujourd'hui **uniquement grâce au moteur OCR léger** (qui ne réserve plus
beaucoup de mémoire).

| Élément | Valeur à demander |
|---------|-------------------|
| Type de machine | Flexible Engine **ECS**, gamme **S6** |
| **Taille** | **`s6.large.2` — 2 vCPU / 4 Go de mémoire** |
| Système | Ubuntu 22.04 LTS |
| Région | **Paris (France)** |
| Disque système | 40 Go SSD |
| Disque données | 80 Go SSD, extensible |
| Adresse IP publique | 1 |
| Sauvegarde | quotidienne, rétention 30 jours, copie hors-site |
| Stockage objets (OBS) | 1 bucket chiffré, ~100 Go |
| Engagement | **1 an (réservé)** |

**À savoir :** 4 Go suffisent pour un garage à faible charge, mais la marge est
réduite — lors d'un pic (scan + génération de documents + requêtes base
simultanés), le serveur travaillera « au plus juste ». C'est le bon choix pour
**démarrer au coût le plus bas** ; un passage ultérieur à l'Option 1 se fait sans
réinstallation.

---

## 4. Éléments communs aux deux options

- **Région Paris (France)** — résidence des données en France.
- **Engagement 1 an (réservé)** — tarif plus avantageux que le paiement à
  l'usage, car le serveur fonctionne en continu.
- **Système Linux gratuit** (Ubuntu) — aucune licence Windows / SQL Server.
- **Sauvegarde quotidienne** + copie hors-site (objectif : perte de données
  max. 15 min, remise en service ~1 h).
- **Chiffrement** des disques et du stockage objets, et **TLS** pour les accès.
- **Pas de GPU** — le moteur OCR fonctionne en mode CPU ; ne rien provisionner de
  ce type.

---

## 5. Coûts (estimations, engagement 1 an)

| Poste | Option 1 (8 Go) | Option 2 (4 Go) |
|-------|-----------------|-----------------|
| Machine ECS (réservé 1 an) | ~45–70 €/mois | ~22–38 €/mois |
| Disques SSD (~140 / 120 Go) | ~12–22 €/mois | ~10–18 €/mois |
| IP publique + bande passante | ~3–6 €/mois | ~3–6 €/mois |
| Sauvegarde + stockage objets (OBS) | ~12–18 €/mois | ~12–18 €/mois |
| **Total estimé** | **~80–115 €/mois** | **~55–85 €/mois** |

> ⚠️ **Estimations indicatives.** Le tarif exact dépend du devis Orange et
> **surtout de la remise négociée** liée à votre relation commerciale. Faire
> chiffrer les deux options en **engagement 1 an**, région Paris.

---

## 6. Recommandation

**Option 1 (`s6.xlarge.2`, 4 vCPU / 8 Go)** : le meilleur compromis
confort/coût pour l'usage quotidien d'un garage, avec une vraie marge de
sécurité, pour un surcoût modéré (~25–30 €/mois) par rapport à l'option
économique. L'Option 2 reste un choix valable si l'objectif est le coût minimal
au démarrage.

> Cette note **remplace** le dimensionnement précédent (16 Go) : grâce au moteur
> OCR ONNX désormais en production, 8 Go suffisent largement.

---

## 7. À demander à Orange

1. Devis ferme pour **l'Option 1** et **l'Option 2**, en **engagement 1 an
   (réservé)**, région **Paris**.
2. Appliquer la **remise négociée** de votre compte.
3. Confirmer les tarifs : ECS S6 réservé 1 an, disque SSD (€/Go/mois), OBS
   (€/Go/mois), sauvegarde (€/Go protégé/mois).
4. Niveau de support souhaité (Standard inclus ; Bronze/Silver/Gold en option).
