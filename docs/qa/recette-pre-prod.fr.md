# Xpert-ERP — Cahier de recette pré-production

> **Objet :** scénarios de test manuel couvrant l'ensemble des flux métier, de toutes les perspectives (Admin, Secrétaire/Réceptionniste, Mécanicien, Gestionnaire de stock, Comptable, Lecture seule, Super-Admin).
> **Date :** 2026-06-27 · **Périmètre :** application complète (atelier, commercial, finance, achats, stock, GED/OCR, administration).
> **Mode d'emploi :** chaque cas de test est exécuté manuellement, puis marqué d'un **X** dans **une** des trois colonnes de statut. Les remarques (n° de bug, question, comportement observé) vont dans la dernière colonne.

## Légende des statuts

| Statut | Signification |
|---|---|
| **Bon** | Le cas fonctionne comme attendu. |
| **Bug** | Comportement incorrect / erreur / écart avec le résultat attendu. |
| **Clarification** | Comportement ambigu, règle métier à confirmer, ou besoin de précision avant de trancher. |

## Comptes de test recommandés

Créer (ou vérifier) un utilisateur par rôle pour tester les perspectives :

| Rôle (code) | Libellé | Usage de test |
|---|---|---|
| `admin` | Administrateur | Accès total (opérationnel + admin) |
| `secretary` / `receptionist` | Secrétaire / Réceptionniste | Front-office : CRM, devis, factures, caisse |
| `mechanic` | Mécanicien | Atelier uniquement (tablette) |
| `inventory_manager` | Gestionnaire de stock | Pièces, stock, achats |
| `accountant` | Comptable | Lecture finance + export comptable |
| `read_only` | Lecture seule | Consultation uniquement |
| `super_admin` | Super-administrateur | Multi-garage / plateforme |

> ⚠️ **À clarifier d'emblée :** le back-end définit les rôles `secretary`, `inventory_manager`, `read_only` ; l'écran *Utilisateurs* (front) affiche `receptionist`, `parts_manager`. Vérifier la cohérence des libellés/codes de rôles (cas **ADM-09**).

---

## 1. Authentification & sécurité d'accès

| # | Scénario (Préconditions → Action → Résultat attendu) | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| AUTH-01 | Connexion valide : saisir email + mot de passe corrects → redirection vers le tableau de bord, menu adapté au rôle. | | | | |
| AUTH-02 | Connexion invalide : mauvais mot de passe → message « Email ou mot de passe incorrect », pas d'accès. | | | | |
| AUTH-03 | Verrouillage : enchaîner les échecs jusqu'à la limite (`AUTH_MAX_FAILED_ATTEMPTS`, déf. 5) → compte verrouillé pendant `AUTH_LOCKOUT_MINUTES` (déf. 15). | | | | |
| AUTH-04 | Mot de passe oublié : `/forgot-password` → email reçu (vérifier Mailpit) avec lien valide. | | | | |
| AUTH-05 | Réinitialisation : ouvrir le lien `/reset-password`, définir un nouveau mot de passe (≥ `PASSWORD_MIN_LENGTH`=12) → connexion possible avec le nouveau. | | | | |
| AUTH-06 | Déconnexion → retour à `/login`, jeton invalidé (le retour arrière ne redonne pas l'accès). | | | | |
| AUTH-07 | Expiration de session : laisser expirer l'access token → rafraîchissement automatique transparent (l'utilisateur reste connecté). | | | | |
| AUTH-08 | Accès direct à une URL non autorisée (ex. mécanicien → `/users`) : saisir l'URL à la main → accès refusé / redirection, pas de fuite de données. | | | | |

---

## 2. Clients (CRM) & limite de crédit

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| CLI-01 | Créer un client (nom, téléphone, email, adresse) → apparaît dans la liste, fiche consultable. | | | | |
| CLI-02 | Modifier un client → changements persistés. | | | | |
| CLI-03 | Recherche/filtre clients (nom, téléphone, email) → résultats pertinents. | | | | |
| CLI-04 | Définir une **limite de crédit** sur un client (rôle admin) → valeur enregistrée et affichée. | | | | |
| CLI-05 | Un non-admin (secrétaire) tente de modifier la limite de crédit → action indisponible/refusée. | | | | |
| CLI-06 | Fiche client : l'**encours** (solde dû) et l'historique d'activité (devis, factures, BL) s'affichent correctement. | | | | |
| CLI-07 | Suppression client : tenter de supprimer un client avec documents liés → comportement attendu (blocage ou soft-delete cohérent). | | | | |
| CLI-08 | Fusion de clients (si exposée) → les documents/véhicules sont rattachés au client conservé. | | | | |

---

## 3. Véhicules & ré-immatriculation

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| VEH-01 | Créer un véhicule (marque, modèle, VIN, immatriculation, année, carburant, km) rattaché à un client. | | | | |
| VEH-02 | Modifier un véhicule (km, carburant, etc.) → enregistré. **Note :** le VIN n'est pas modifiable après création (identifiant immuable) — vérifier le comportement de l'écran. | | | | |
| VEH-03 | Fiche véhicule : historique des réparations et documents (carte grise) visibles. | | | | |
| VEH-04 | Ré-immatriculation : changer l'immatriculation via le dialogue dédié (avec contrôle de permission) → nouvelle plaque enregistrée, historique conservé. | | | | |
| VEH-05 | Unicité : tenter de réutiliser une immatriculation déjà attribuée à un autre véhicule → erreur 409 / message clair (pas de doublon). | | | | |

---

## 4. Catalogue pièces & gestion du stock

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| STK-01 | Créer une pièce (SKU, nom, catégorie, prix d'achat, prix de vente, seuil de réappro). | | | | |
| STK-02 | Le **nom de la pièce** s'affiche partout où la pièce est utilisée (devis, OR, BL, achats). | | | | |
| STK-03 | Enregistrer un mouvement d'**entrée** de stock → `on_hand` augmente. | | | | |
| STK-04 | Enregistrer un **ajustement** d'inventaire → `on_hand` corrigé, mouvement tracé. | | | | |
| STK-05 | **Réservation** : ajouter une pièce du catalogue à un OR → `reserved` augmente, `on_hand` inchangé. | | | | |
| STK-06 | **Validation** : passer l'OR en « En réparation » → la réservation devient une sortie (`on_hand` diminue, `reserved` revient). | | | | |
| STK-07 | **Stock négatif interdit** (`CFG_ALLOW_NEGATIVE_STOCK=false`) : sortir plus que le stock disponible → blocage avec message, opération annulée (rollback). | | | | |
| STK-08 | **Stock négatif autorisé** (`=true`) : la sortie passe et `on_hand` peut devenir négatif. | | | | |
| STK-09 | **Alerte stock bas** : faire passer `on_hand` sous le seuil de réappro → alerte créée (suggestion fournisseur/quantité). | | | | |
| STK-10 | Tableau de bord : le compteur « stock bas » reflète les alertes ouvertes. | | | | |

---

## 5. Fournisseurs & achats (BC → réception → facture → 3-way match)

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| ACH-01 | Créer un fournisseur (nom, conditions de paiement, délais) → enregistré. | | | | |
| ACH-02 | Créer un **bon de commande** (fournisseur, lignes pièces, quantités, PU HT) en brouillon → total HT calculé. | | | | |
| ACH-03 | **Envoyer** le BC → statut `envoyé`, numéro de document attribué. | | | | |
| ACH-04 | **Réception** partielle → statut `partiellement reçu`, quantités reçues mises à jour, stock entré. | | | | |
| ACH-05 | Réception complète → statut `terminé`. | | | | |
| ACH-06 | Enregistrer une **facture fournisseur** rattachée au BC → rapprochement 3 voies exécuté. | | | | |
| ACH-07 | **Écart quantité** : facture avec qté ≠ qté reçue → ligne marquée `qty_mismatch`, facture signalée pour revue. | | | | |
| ACH-08 | **Écart prix** : PU facturé hors tolérance vs PU du BC → ligne marquée `inv_mismatch`. Vérifier la **tolérance** appliquée (`CFG_PO_MATCH_TOLERANCE_PERCENT`, déf. 5 %). | | | | |
| ACH-09 | Facture fournisseur sans écart → rapprochement « ok », passage `posté` puis `approuvé`. | | | | |
| ACH-10 | Facture fournisseur **autonome** (sans BC) → création possible, pas de rapprochement. | | | | |
| ACH-11 | Unicité : même numéro de facture pour le même fournisseur → refusé. | | | | |

### 5.1 Bons de retour & avoirs fournisseurs

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| RET-01 | **Retour fournisseur** : créer un bon de retour (type fournisseur) sur pièces défectueuses → à la confirmation, sortie de stock + avoir fournisseur créé. | | | | |
| RET-02 | **Retour client** : bon de retour (type client) avec `restock=true` → réintégration en stock à la confirmation. | | | | |
| RET-03 | Retour client `restock=false` (pièce HS) → pas de réintégration vendable (mise au rebut). | | | | |
| RET-04 | Annuler un bon de retour en brouillon → aucun impact stock. | | | | |
| RET-05 | « Reverser » un bon de retour confirmé → mouvements de stock annulés. | | | | |

---

## 6. Ordres de réparation (cycle complet)

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| OR-01 | Créer un OR (client + véhicule + description, lignes main d'œuvre & pièces) → statut **Créé**. | | | | |
| OR-02 | Ajouter une ligne **main d'œuvre** (durée, taux) → montant calculé avec TVA. | | | | |
| OR-03 | Ajouter une ligne **pièce** du catalogue → réservation de stock (cf. STK-05) et coût recalculé. | | | | |
| OR-04 | Passer **Créé → Diagnostic**. | | | | |
| OR-05 | **Affecter un mécanicien** → notification in-app au mécanicien + email (best-effort), `accepté` remis à zéro. | | | | |
| OR-06 | Le mécanicien **accepte l'affectation** → date d'acceptation enregistrée. | | | | |
| OR-07 | Remplir le **diagnostic** (questions D1–D5 + notes) et le marquer terminé. | | | | |
| OR-08 | **Blocage de transition** : tenter **Diagnostic → En réparation** SANS mécanicien affecté/accepté ou diagnostic non terminé → bouton désactivé avec **motif affiché** (« Affectez un mécanicien », « L'affectation doit être acceptée », « Terminez le diagnostic »). *(point de vigilance — correctif récent)* | | | | |
| OR-09 | Préconditions remplies → **Diagnostic → En réparation** autorisé ; réservations validées en sorties de stock. | | | | |
| OR-10 | **En réparation → En attente de pièces** puis retour **→ En réparation**. | | | | |
| OR-11 | **En réparation → Terminé → Livré** (état final, plus de transition). | | | | |
| OR-12 | Transitions « retour arrière » autorisées (ex. En réparation → Diagnostic) cohérentes. | | | | |
| OR-13 | Modifier un OR existant (client/véhicule/lignes) → enregistré, totaux recalculés. | | | | |
| OR-14 | Joindre des **documents/photos** à l'OR. | | | | |
| OR-15 | Le statut **« paused_approval » n'existe plus** : vérifier qu'il n'apparaît nulle part (liste, filtres, tablette, détail). *(point de vigilance — statut supprimé)* | | | | |

---

## 7. Atelier — Tablette mécanicien (`/tablet`)

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| TAB-01 | Connexion en mécanicien → la tablette n'affiche **que les OR affectés** au mécanicien. | | | | |
| TAB-02 | **Pointage** : démarrer une session de travail → indicateur actif ; arrêter → temps cumulé mis à jour. | | | | |
| TAB-03 | **Photos** : prendre une photo via la caméra → vignette ajoutée, compteur incrémenté. | | | | |
| TAB-04 | **Commentaires** : ajouter un commentaire (Ctrl+Entrée) → visible avec auteur + horodatage. | | | | |
| TAB-05 | **Transitions de statut** depuis la tablette respectent la machine à états (boutons contextuels). | | | | |
| TAB-06 | Rafraîchissement auto (~15 s) → nouvelles données/affectations apparaissent. | | | | |
| TAB-07 | Suivi Atelier (Kanban `/workshop`) : déplacement des OR par statut cohérent avec la machine à états. | | | | |

---

## 8. Inspections

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| INS-01 | (Admin) Créer/éditer un **modèle d'inspection** (sections + points de contrôle). | | | | |
| INS-02 | Lancer une inspection à partir d'un modèle → statut `brouillon` puis `en cours`. | | | | |
| INS-03 | Renseigner chaque point (ok / attention / défectueux / non applicable) + notes + photos. | | | | |
| INS-04 | En-tête de section se colore (rouge si défauts, vert si tout ok). | | | | |
| INS-05 | Marquer l'inspection **terminée** → état final cohérent. | | | | |
| INS-06 | **Lien d'approbation externe** (`/approve/:token`) → accessible sans connexion, à usage unique, expire. | | | | |
| INS-07 | Recommandations véhicule générées depuis les points « attention/défectueux ». | | | | |

---

## 9. Devis

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| DEV-01 | Créer un devis (client, véhicule, lignes MO/pièces) → statut `brouillon`, **sans** numéro. | | | | |
| DEV-02 | **Remise par ligne** (%) + **TVA** : vérifier le calcul (TVA appliquée sur le montant **remisé**). | | | | |
| DEV-03 | **Envoyer** le devis → statut `envoyé`, numéro attribué, devis verrouillé. | | | | |
| DEV-04 | Devis accepté / rejeté → statut reflété. | | | | |
| DEV-05 | **Conversion en facture** d'un devis envoyé/accepté → facture créée avec lignes & totaux copiés, devis passé à `converti`. | | | | |
| DEV-06 | Générer le **PDF** du devis (mise en page, logo, mentions). | | | | |

---

## 10. Bons de livraison (BL)

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| BL-01 | Créer un BL (client, lignes pièce/service/autre) → brouillon. | | | | |
| BL-02 | **Émettre** le BL → numéro attribué ; réservations/sorties de stock selon les lignes pièces. | | | | |
| BL-03 | Émission avec **dépassement de limite de crédit** → blocage + dialogue de dérogation (cf. §15). | | | | |
| BL-04 | BL émis **sous dérogation** → marqué `issued_under_override` ; sa conversion ultérieure en facture **ne re-contrôle pas** le crédit. | | | | |
| BL-05 | Conversion BL → facture : lignes et totaux repris correctement. | | | | |
| BL-06 | Marquer **livré** → date de livraison enregistrée. | | | | |

---

## 11. Factures

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| FAC-01 | Créer une facture (depuis devis, depuis BL, ou manuelle) → brouillon, sans numéro. | | | | |
| FAC-02 | **Émettre** une facture (client rattaché) → numéro attribué, encours client mis à jour, statut `émise`. | | | | |
| FAC-03 | Émission **sans client** rattaché → bloquée avec message. | | | | |
| FAC-04 | **Auto-déduction des avances** : émettre une facture pour un client ayant un dépôt non appliqué → l'avance est imputée (FIFO), reste à payer réduit. | | | | |
| FAC-05 | **Contrôle de crédit** à l'émission : encours projeté > limite → blocage / dérogation (§15). | | | | |
| FAC-06 | **Notifications de seuil** : encours franchissant 80 % puis 90 % de la limite → notifications envoyées **une seule fois** par seuil. | | | | |
| FAC-07 | Sortie de **stock** pour les lignes pièces à l'émission (cf. STK). | | | | |
| FAC-08 | Annulation d'une facture émise → workflow d'avoir (pas de suppression directe). | | | | |
| FAC-09 | Générer le **PDF** facture (numéro, TVA, totaux, mentions légales). | | | | |

---

## 12. Paiements & sessions de caisse

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| PAY-01 | Enregistrer un **paiement** sur une facture (espèces/carte/virement/chèque/autre) → reste à payer mis à jour. | | | | |
| PAY-02 | Paiement partiel → facture passe `partiellement payée` ; paiement du solde → `payée`. | | | | |
| PAY-03 | **Ouvrir une session de caisse** avec **fond de caisse** initial. | | | | |
| PAY-04 | Empêcher l'ouverture d'une 2ᵉ session alors qu'une est déjà ouverte. | | | | |
| PAY-05 | Les paiements **espèces** s'attachent à la session ouverte. | | | | |
| PAY-06 | **Clôture (rapport Z)** : saisir le montant **compté** → écart calculé (compté − attendu). | | | | |
| PAY-07 | Écart non nul avec `CFG_CASH_DIFF_REQUIRE_REASON=true` → **motif obligatoire** pour clôturer. | | | | |
| PAY-08 | Un utilisateur ne peut pas clôturer une session qu'il n'a pas ouverte (sauf admin). | | | | |
| PAY-09 | Historique des sessions : heures d'ouverture/clôture + écart visibles. | | | | |

---

## 13. Avances / Dépôts

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| AVA-01 | Enregistrer une **avance** client (montant, mode de paiement), éventuellement liée à un OR. | | | | |
| AVA-02 | Avance non appliquée visible dans la liste « en attente ». | | | | |
| AVA-03 | Application automatique à l'émission de facture (cf. FAC-04), avec imputation partielle si l'avance > facture. | | | | |
| AVA-04 | Solde d'avance restant correctement reporté après imputation partielle. | | | | |

---

## 14. Avoirs (notes de crédit) & remboursements

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| AVO-01 | Créer un **avoir** rattaché à une facture émise → brouillon. | | | | |
| AVO-02 | **Émettre** l'avoir → numéro attribué. | | | | |
| AVO-03 | **Remboursement** : enregistrer un remboursement (lié à un paiement et à l'avoir) → reste à payer / encours ajustés. | | | | |
| AVO-04 | Avoir auto-créé lors de l'annulation d'une facture payée/partielle. | | | | |
| AVO-05 | Annuler (void) un avoir → état `annulé`, horodaté. | | | | |

---

## 15. Dérogations de limite de crédit (workflow override)

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| DER-01 | Client au crédit dépassé : à l'émission d'une facture/BL → **dialogue « Limite de crédit dépassée »** (encours actuel, limite, montant projeté). | | | | |
| DER-02 | Cliquer **« Demander une dérogation »** → demande créée (statut `en attente`), message « Demande envoyée à l'administrateur ». | | | | |
| DER-03 | **Notification admin** : les utilisateurs ayant `credit.override.manage` reçoivent une notification. | | | | |
| DER-04 | (Admin) Écran **Dérogations de crédit** : **approuver** → fenêtre de validité de **24 h** ouverte. | | | | |
| DER-05 | (Admin) **Rejeter** avec motif → demandeur notifié, émission toujours bloquée. | | | | |
| DER-06 | Après approbation, ré-émission du document **passe** (dérogation consommée), document marqué « sous dérogation ». | | | | |
| DER-07 | Dérogation **expirée** (> 24 h) → l'émission est de nouveau bloquée. | | | | |
| DER-08 | Dé-duplication : 2 demandes pour le même client/type → la demande existante est réutilisée. | | | | |
| DER-09 | Mode `warn` vs `block` (`credit_limit_mode`) : en `warn`, l'émission passe avec avertissement ; en `block`, elle est bloquée. | | | | |

---

## 16. Documents (GED) & OCR

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| DOC-01 | Téléverser un document (PDF/image) avec catégorie + type de propriétaire (client/véhicule/OR/facture…). | | | | |
| DOC-02 | Recherche/filtre par catégorie, type de propriétaire, identifiant. | | | | |
| DOC-03 | Télécharger / prévisualiser / supprimer (soft-delete) un document. | | | | |
| OCR-01 | **Carte grise** : téléverser → OCR extrait immatriculation, VIN, date 1ʳᵉ mise en circulation, marque, modèle, propriétaire. | | | | |
| OCR-02 | Écran de revue OCR (`/ocr/:id`) : aperçu image/PDF + champs **éditables** ; corriger un champ. | | | | |
| OCR-03 | **Écriture vers le véhicule** : « Mettre à jour le véhicule » → champs fusionnés dans la fiche véhicule. | | | | |
| OCR-04 | **CIN / pièce d'identité** : extraction (numéro CIN, nom, prénom, date de naissance) → « Mettre à jour le client ». | | | | |
| OCR-05 | **Facture fournisseur** par OCR : extraction (n°, dates, fournisseur, HT/TVA/TTC) → validation. | | | | |
| OCR-06 | Confiance faible → document marqué « à revoir » (`needs_review`), pas d'écriture automatique sans validation. | | | | |
| OCR-07 | Langue/accents français correctement reconnus (é, è, ç, à…). | | | | |

---

## 17. Notifications

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| NOT-01 | Affectation d'OR → notification in-app + email au mécanicien. | | | | |
| NOT-02 | Cloche de notifications in-app : marquer comme lu, lien ouvre la bonne page. | | | | |
| NOT-03 | **Heures silencieuses** (`CFG_QUIET_HOURS_*`) : email/SMS différés pendant la plage ; in-app toujours délivrée. | | | | |
| NOT-04 | Échec d'envoi → relances jusqu'à `CFG_NOTIFICATION_MAX_RETRIES`, statut `failed` après épuisement. | | | | |
| NOT-05 | (Admin) Modèles de notification : créer/éditer un modèle (sujet + corps Jinja2), activer/désactiver. | | | | |

---

## 18. KPI / Tableau de bord

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| KPI-01 | Tableau de bord : cartes (OR en cours, clients, facturation, CA, stock bas) affichent des valeurs cohérentes. | | | | |
| KPI-02 | Écran KPIs & rapports (`/kpi`) : CA, métriques atelier, rentabilité. | | | | |
| KPI-03 | Cohérence des chiffres KPI avec les données réelles (recouper un indicateur manuellement). | | | | |
| KPI-04 | Cache KPI (`CFG_KPI_REFRESH_INTERVAL_SECONDS`) : les chiffres se rafraîchissent après l'intervalle. | | | | |

---

## 19. Export comptable & numérotation

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| EXP-01 | Lancer un **export comptable** sur une période → fichier généré (format Sage/Cegid/EBP/CSV), comptage des écritures cohérent. | | | | |
| EXP-02 | Les pièces déjà exportées sont marquées (`is_exported`) pour éviter les doublons. | | | | |
| SEQ-01 | **Numérotation sans trou** : émettre plusieurs documents du même type à la suite → numéros consécutifs (ex. `FAC-2026-000123`, `…124`). | | | | |
| SEQ-02 | Numérotation **par type** indépendante (devis, facture, avoir, BL, BC, BR, facture fournisseur). | | | | |
| SEQ-03 | Réinitialisation annuelle de la séquence (changement d'année) — à confirmer le comportement attendu. | | | | |

---

## 20. Matrice d'accès par rôle (tests de permissions)

Pour chaque rôle, se connecter et vérifier la visibilité du menu + l'autorisation des actions. Marquer **Bon** si l'accès correspond à l'attendu ci-dessous.

| # | Rôle | Attendu | Bon | Bug | Clarification | Remarques |
|---|---|---|:--:|:--:|:--:|---|
| RBAC-01 | **Mécanicien** | Voit Atelier, Inspections, Documents, tablette. **Ne voit pas** Clients, Véhicules, Devis, Factures, Paiements, Stock, KPIs. Ne peut rien créer (sauf actions atelier). | | | | |
| RBAC-02 | **Secrétaire / Réceptionniste** | CRM, devis, factures, BL, caisse, paiements, achats (lecture), stock (lecture). **Pas** d'admin, **pas** d'override de crédit, **pas** d'annulation de facture, **pas** de modif. limite crédit. | | | | |
| RBAC-03 | **Gestionnaire de stock** | Pièces (créer/éditer), mouvements de stock, réservations, fournisseurs, BC (créer/approuver), réceptions, bons de retour. **Pas** de devis/factures/paiements. | | | | |
| RBAC-04 | **Comptable** | Lecture finance (factures, paiements, caisses, balance client), **export comptable**, journal d'audit. **Aucune écriture** métier. | | | | |
| RBAC-05 | **Lecture seule** | Consultation uniquement, aucun bouton de création/modification actif. | | | | |
| RBAC-06 | **Admin** | Accès total : opérationnel + utilisateurs, rôles, paramètres, audit, config, dérogations de crédit, modèles. | | | | |
| RBAC-07 | **Super-admin** | Comme admin + portée multi-garage (si applicable). | | | | |
| RBAC-08 | **Cumul de rôles** | Un utilisateur avec 2 rôles obtient l'**union** des permissions. | | | | |
| RBAC-09 | **Garde-fous** | Un utilisateur ne peut pas modifier ses propres rôles ni se désactiver lui-même. | | | | |

---

## 21. Administration & paramètres

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| ADM-01 | (Admin) Créer un utilisateur (nom, email, mot de passe), assigner des rôles. | | | | |
| ADM-02 | Éditer un utilisateur, désactiver, réinitialiser le mot de passe. | | | | |
| ADM-03 | (Admin) Écran Rôles : consulter/éditer les permissions d'un rôle. | | | | |
| ADM-04 | Paramètres : infos société, TVA, branding PDF (nom, adresse, logo) → répercutés sur les documents. | | | | |
| ADM-05 | Journal d'audit : les créations/modifications/suppressions sont tracées (date, utilisateur, entité). | | | | |
| ADM-06 | Paramètres de configuration `CFG_*` modifiables sans redéploiement (ex. capacité atelier, tolérance achats). | | | | |
| ADM-07 | Visualiseur de logs (si exposé) → lecture des journaux applicatifs. | | | | |
| ADM-08 | Multi-garage : isolation des données par garage (un utilisateur ne voit que son garage). | | | | |
| ADM-09 | **Cohérence des rôles** front/back : les rôles proposés à l'écran *Utilisateurs* correspondent aux rôles réels du back-end (cf. avertissement en tête). | | | | |

---

## 22. Cas transverses / limites

| # | Scénario | Bon | Bug | Clarification | Remarques |
|---|---|:--:|:--:|:--:|---|
| TRX-01 | **Édition concurrente** (verrou optimiste) : deux utilisateurs éditent le même document → le 2ᵉ enregistrement échoue proprement (« conflit de version, rechargez »). | | | | |
| TRX-02 | **Accents / encodage** : saisir des libellés avec accents (é, à, ç) dans clients/pièces/notes → affichage et PDF corrects (pas de mojibake). | | | | |
| TRX-03 | **Montants** : vérifier l'arrondi et l'affichage des montants (centimes) et de la TVA sur l'ensemble des documents. | | | | |
| TRX-04 | **Cohérence stock ↔ documents** : un cycle complet (BC → réception → OR/BL/facture) laisse le stock cohérent. | | | | |
| TRX-05 | **PWA / hors-ligne** : la tablette mécanicien continue d'afficher les dernières données en cas de coupure réseau, puis se resynchronise. | | | | |
| TRX-06 | **Performance** : listes volumineuses (factures, OR) paginées et réactives. | | | | |

---

*Document de recette généré le 2026-06-27 à partir d'une analyse du code (rôles, machines à états, écrans). À compléter au fil des tests ; reporter chaque anomalie avec son n° de cas.*
