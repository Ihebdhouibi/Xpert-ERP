# Flux — Bon de livraison fournisseur (OCR → liaison BC → réception)

> **Objet :** documenter le flux complet de traitement d'un **bon de livraison (BL) fournisseur**, de son téléversement jusqu'à la **réception** (entrée en stock et mise à jour du bon de commande), puis fournir un **scénario de test** pour valider l'ensemble.
> **Périmètre :** côté achats (Fournisseur → Garage). Le module `delivery_note` (BL client) n'est pas concerné.

---

## 1. Vue d'ensemble

Un BL fournisseur arrive avec la marchandise. Dans Xpert-ERP, on le téléverse, on le **rattache à un bon de commande (BC)**, l'**OCR** extrait ses champs, l'opérateur **vérifie**, puis **valide la réception** : le stock entre et le BC est mis à jour. Le **numéro de BL** sert de clé de corrélation avec la future **facture fournisseur** (rapprochement 3 voies).

```
Téléversement BL ─► Catégorie « Bon de livraison »
                    Type propriétaire « Bon de commande » ─► choisir le BC (ou le créer)
        ─► OCR automatique ─► Vérification (champs détectés)
        ─► « Valider » ouvre la RÉCEPTION ─► mapping lignes BL ↔ lignes BC
        ─► Confirmer ─► entrée en stock + quantité reçue (BC) + statut + enregistrement du BL
```

## 2. Étapes & écrans

| Étape | Où | Ce qui se passe |
|---|---|---|
| **Téléversement** | Documents → « Télécharger un document » | Catégorie = **Bon de livraison** ; Type propriétaire = **Bon de commande** → un **sélecteur de BC** (recherche) remplace l'ancien champ « ID propriétaire ». Le téléversement est **bloqué tant qu'aucun BC n'est choisi**. |
| **Créer un BC à la volée** | même dialogue → « Créer un nouveau bon de commande » | Saisie manuelle du BC. Le fournisseur peut être **créé à la volée** (« Ajouter un nouveau fournisseur », nom provisoire accepté). Les pièces inconnues sont saisies en ligne **« Autre »** (proposée **en premier** dans la liste). |
| **OCR** | automatique au téléversement d'un BL | Extraction des champs (voir §3). |
| **Vérification** | Extraction automatique (page OCR) | Les **« Champs détectés — Bon de livraison »** s'affichent et sont éditables : N° de BL, date, fournisseur, référence commande, immatriculation, totaux, lignes (brut). |
| **Réception** | bouton **« Réceptionner »** (sur un BL) → dialogue de réception | Affiche le **BC lié** + son **fournisseur** (lecture seule). Si des lignes ont été capturées dans la grille, **une ligne de mapping par ligne de BL** : choisir la **ligne de BC** correspondante + la **quantité reçue** (pour une ligne **« Autre »**, **affecter la pièce réelle**). Sinon, repli sur la saisie **par ligne de BC**. |
| **Confirmation** | « Confirmer la réception » | Entrée en stock, mise à jour de `quantité reçue` et du **statut du BC**, enregistrement du **BL** (n°, date, lignes). |

## 3. Champs extraits du BL (OCR)

- **En-tête** : `numero_bl` (clé de corrélation), `date_bl`, `fournisseur` (en-tête/letterhead — confiance abaissée, à confirmer), `reference_commande`, `immatriculation`, `total_ht` / `tva` / `total_ttc`.
- **Lignes** : une **grille éditable** par ligne — colonnes **Code / Désignation / Qté / PU Brut / PU Net / Montant**. Pré-remplie au mieux depuis l'extraction (`lignes`), puis **corrigée par l'opérateur**. **Chaque cellule est remplissable au recadrage (crop)** : on dessine la zone sur le document et l'OCR remplit la cellule — **sur n'importe quelle page** (utile pour les BL multi-pages). Le champ brut « Lignes détectées (brut) » reste disponible en secondaire.
- **Client** : toujours notre garage (`GARAGE MOTORS UTILITAIRE`) ; **« AL DELIVERY » = société de livraison, pas le client** → non extrait comme client.

## 4. Règles métier

- **BL → BC : N:1 obligatoire.** Un BL appartient à **un seul** BC ; un BC peut recevoir **plusieurs** BL (ex. 50 articles livrés en 5×10).
- **Cumul des réceptions.** `purchase_order_line.quantity_received` est la **somme** des quantités reçues sur tous les BL d'une ligne.
- **Lignes « Autre ».** Une ligne de BC peut viser une pièce hors catalogue (`part_id` nul + `label`). À la réception, l'opérateur **affecte une pièce réelle** → la ligne de BC est **réaffectée** (swap) à cette pièce, ce qui débloque l'entrée en stock. (Tant qu'une ligne « Autre » n'a pas de pièce, sa réception est refusée.)
- **Sur-livraison / article en trop : accepté + signalé.** La réception passe, la ligne du BL est marquée `over` et le BL porte `has_discrepancy = true`.
- **N° de BL unique** par (garage, fournisseur). En cas de doublon, un **avertissement** est affiché avec possibilité de **« Confirmer quand même »**.
- **Fournisseur (HITL).** Le fournisseur de la réception provient du **BC** (déterminé à la création du BC, où la création de fournisseur à la volée est disponible). Aucune ressaisie : il est affiché en lecture seule.

## 5. Modèle de données (rappel)

- `supplier_delivery_note` : `purchase_order_id` (non nul), `supplier_id`, **`bl_number`** (unique par garage+fournisseur), `bl_date`, `document_id`, `status`, `has_discrepancy`.
- `supplier_delivery_note_line` : `po_line_id`, `part_id`, `description`, `quantity` (Numeric — décimales conservées), `unit_price_ht`, `match_flag`.
- `purchase_order_line` : `part_id` **nullable** + `label` (lignes « Autre »), `quantity_received` (cumul).

## 6. Limites connues (assumées)

- **Quantités décimales** : conservées sur la ligne de BL, mais la **réception vers le BC utilise des entiers** (le BC est en entier). Cas décimal pur à traiter ultérieurement.
- **Lignes BL** : capturées dans une **grille éditable** (cellule par cellule, recadrage OCR sur toutes les pages) ; le **mapping** ligne BL ↔ ligne BC reste **manuel** dans la réception. Auto-matching par code (mémorisation `code → pièce`) = amélioration **future**.
- **Création de pièce catalogue à la volée** depuis la réception : non incluse — affecter une **pièce existante** (créer la pièce via le catalogue si besoin).
- **Rapprochement 3 voies avec la facture** (BL ↔ facture via `bl_number`) : étape **suivante**, non incluse ici.

---

## 7. Scénario de test (recette)

> Pré-requis : être connecté (admin/secrétaire), avoir au moins un fournisseur et quelques pièces au catalogue. Disposer d'un BL d'exemple (ex. `tests/factures/1.jpeg`).

| # | Action | Résultat attendu | Bon | Bug |
|---|---|:--:|:--:|:--:|
| BL-01 | Documents → Télécharger → choisir le fichier BL → Catégorie **Bon de livraison** → Type propriétaire **Bon de commande**. | Le champ « ID propriétaire » est remplacé par un **sélecteur de BC** ; « Télécharger » reste **désactivé**. | | |
| BL-02 | Sélectionner un **BC existant** du bon fournisseur → Télécharger. | Le document est filé sous ce BC ; l'OCR démarre automatiquement. | | |
| BL-03 | (Variante) Cliquer **« Créer un nouveau bon de commande »** → si le fournisseur n'existe pas, **« Ajouter un nouveau fournisseur »** → créer ; ajouter des lignes (dont une **« Autre »** avec désignation) → Créer. | Le BC est créé et **auto-sélectionné** ; le fournisseur créé est sélectionnable. | | |
| BL-04 | Ouvrir la page **Extraction automatique** du BL (ou « Ré-analyser » si OCR fait avant la fonctionnalité). | En-tête + la **grille de lignes** (Code/Désignation/Qté/PU Brut/PU Net/Montant) s'affichent, éditables et pré-remplies au mieux. | | |
| BL-04b | Dans la grille, cliquer l'icône **recadrage** d'une cellule → dessiner la zone sur le document → relâcher. | La cellule se remplit avec le texte OCR de la zone. | | |
| BL-04c | (BL multi-pages) Aller à **page 2** → recadrer une cellule sur cette page. | Le recadrage fonctionne **aussi sur la page 2** (la cellule se remplit). | | |
| BL-05 | Corriger la grille au besoin ; cliquer **« Réceptionner »**. | Le dialogue s'ouvre : BC + fournisseur (lecture seule) + **une ligne de mapping par ligne capturée**. | | |
| BL-06 | Pour chaque ligne capturée : choisir la **ligne de BC** + la **quantité reçue** ; pour une ligne **« Autre »**, **affecter une pièce** existante. | La ligne « Autre » exige une pièce ; chaque ligne exige une ligne de BC + qté > 0. | | |
| BL-07 | « Confirmer la réception ». | Succès ; **stock entré**, **quantité reçue** du BC mise à jour, **statut** mis à jour, la ligne « Autre » porte la **pièce affectée**, et les **champs capturés** (code/PU brut/PU net/montant) sont enregistrés sur la ligne du BL. | | |
| BL-08 | Refaire un BL avec le **même n° de BL** pour le même fournisseur. | **Avertissement** « N° de BL déjà existant » + bouton **« Confirmer quand même »**. | | |
| BL-09 | Réceptionner une **quantité supérieure** à la quantité commandée restante. | Réception acceptée + **signalement** (écart / `has_discrepancy`). | | |
| BL-10 | Livraison partielle : recevoir 10 sur une ligne commandée à 50, puis un 2ᵉ BL de 10. | `quantité reçue` **cumulée** (20/50) ; statut `partiellement reçu`. | | |

*Document généré le 2026-06-30. À mettre à jour si le flux évolue (notamment lors de l'ajout du rapprochement facture).*
