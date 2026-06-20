# Rapport — Optimisation des coûts du serveur (Xpert ERP)

**À l'attention du client** — pour la négociation de l'hébergement avec Orange
**Hébergeur visé :** Orange Business — Flexible Engine (région Paris, France)
**Date :** 20/06/2026 · **Version :** 1.0

> Ce document explique, en langage simple, le travail réalisé pour réduire la
> taille (et donc le coût) du serveur, et indique précisément la machine à
> demander à Orange. Aucune connaissance technique n'est nécessaire pour le lire.

---

## 1. En une phrase

Nous avons retravaillé la partie la plus « gourmande » du logiciel — la lecture
automatique des documents (cartes grises, pièces d'identité, factures) — pour
qu'elle consomme **environ deux fois moins de mémoire**. Résultat : le serveur à
louer chez Orange peut passer de **16 Go à 8 Go de mémoire**, ce qui **réduit la
facture mensuelle**, sans rien perdre des fonctionnalités.

---

## 2. Pourquoi le serveur était « gros » au départ

Un serveur se dimensionne surtout sur deux ressources :

- la **mémoire de travail** (la « RAM ») — comme le plan de travail d'un
  établi : plus il est grand, plus on peut traiter de choses en même temps ;
- l'**espace de stockage** (le « disque ») — comme une armoire de rangement.

Dans Xpert ERP, presque tout est léger **sauf une fonction** : la **lecture
automatique des documents** (la « reconnaissance de texte », ou OCR). Pour
reconnaître le texte d'une carte grise, le logiciel charge un « modèle »
d'intelligence artificielle qui occupe beaucoup de mémoire. C'est cette seule
fonction qui obligeait à prendre un serveur de 16 Go.

---

## 3. Les optimisations réalisées (en langage simple)

Chacune a été développée, testée, puis enregistrée séparément.

| # | Ce qui a été fait | Image simple | Bénéfice |
|---|-------------------|--------------|----------|
| 1 | **Une seule copie du modèle de lecture** | Avant, le logiciel chargeait le modèle **deux fois** en parallèle. On n'en garde qu'**une seule copie**. | ~2× moins de mémoire pour l'OCR |
| 2 | **Retrait d'options inutiles** | Le modèle activait des traitements pour photos « tordues » ou en biais. Nos documents sont des scans bien à plat : on les a **désactivés**. | −70 Mo de mémoire, scans plus rapides |
| 3 | **Libération de la mémoire au repos** | Quand personne ne scanne de document, la mémoire utilisée par l'OCR est **rendue au serveur** automatiquement, puis reprise au scan suivant. | Le serveur respire le reste du temps |
| 4 | **Nouveau moteur de lecture, plus léger** | Un moteur alternatif (technologie « ONNX ») fait le même travail en occupant **moitié moins de mémoire** et **15 fois moins d'espace disque**. | Prêt à activer (voir §6) |
| 5 | **Image d'installation allégée** | On a retiré de l'installation tous les outils qui ne servent qu'à la fabrication, et on peut produire une version **beaucoup plus petite**. | Disque réduit, déploiement plus sûr |

---

## 4. Résultat chiffré : avant / après

Mesures réelles effectuées pendant le développement.

| Indicateur | **Avant** | **Après** (config par défaut) | **Après** (option ONNX, §6) |
|------------|-----------|-------------------------------|------------------------------|
| Mémoire utilisée par l'OCR pendant un scan | ~1 100–1 200 Mo | ~525 Mo | **~233 Mo** |
| Mémoire utilisée par l'OCR au repos | élevée en permanence | quasi nulle (rendue au serveur) | quasi nulle |
| Espace disque de la partie lecture | ~780 Mo | ~780 Mo | **~52 Mo** |
| **Mémoire serveur recommandée** | **16 Go** | **8 Go** | **8 Go (large marge)** |

**Conclusion :** la lecture de documents n'est plus le facteur qui impose la
taille du serveur. Un serveur de **8 Go** suffit désormais confortablement.

---

## 5. Serveur recommandé à demander à Orange

> Ceci **remplace** la taille indiquée précédemment (16 Go) dans la fiche
> technique [orange-flexible-engine-specifications.fr.md](orange-flexible-engine-specifications.fr.md).
> Tous les autres éléments de cette fiche (stockage, sauvegarde, réseau, région)
> restent valables.

| Élément | Valeur à demander |
|---------|-------------------|
| Type de machine | Serveur cloud **Flexible Engine ECS**, gamme S6 (usage général) |
| **Taille** | **`s6.xlarge.2` — 4 processeurs (vCPU) / 8 Go de mémoire** |
| Système | Ubuntu 22.04 (Linux, gratuit) |
| Région | **Paris (France)** — données hébergées en France |
| Disque | 50 Go (système) + 100 Go (données, extensible), type SSD |
| Sauvegarde | quotidienne, conservée 30 jours, copie hors-site |
| Adresse Internet | 1 adresse IP publique |

**Pourquoi cette taille :** 4 processeurs gardent le logiciel réactif (y compris
pendant un scan), et 8 Go de mémoire offrent une marge confortable maintenant
que l'OCR a été allégé. La machine reste **agrandissable à tout moment** si
l'activité augmente (passage à 16 Go ou ajout d'une base de données gérée), sans
réinstallation.

---

## 6. Option pour aller encore plus loin (gratuite)

Le **nouveau moteur de lecture « ONNX »** (optimisation n°4) est intégré et
**désormais compatible avec le français**. Il divise encore la mémoire par deux
et réduit fortement l'espace disque.

**Vérification des accents : faite.** Le moteur ONNX a d'abord été testé avec un
modèle anglais/chinois, qui déformait les accents (« Jérôme » devenait
« JBrBme »). Nous avons donc intégré le **modèle français dédié** (« latin »), le
même que celui utilisé aujourd'hui. Après ce correctif, les accents (é, è, ô, ç)
sont lus correctement — au niveau du moteur actuel, parfois mieux.

**Pour l'activer en production**, deux conditions techniques (à la charge de
l'équipe, sans impact pour vous) : utiliser la version allégée du logiciel et
activer un réglage. **Le serveur de 8 Go convient dans les deux cas** — ONNX
n'est qu'un gain supplémentaire, pas une nécessité.

---

## 7. Autres leviers d'économie côté Orange

À aborder lors de la négociation (indépendants du logiciel) :

- **Engagement 1 à 3 ans** plutôt qu'au mois : remise importante, car le serveur
  tourne en continu.
- **Tarif négocié** : faire appliquer la remise liée à votre relation
  commerciale avec Orange.
- **Démarrer simple** : un seul serveur aujourd'hui ; les services « gérés »
  (base de données, etc.) ne deviennent utiles qu'avec un second garage.

---

## 8. Ce qu'il reste à faire

1. **Côté client :** transmettre à Orange la fiche technique mise à jour (machine
   `s6.xlarge.2`, 4 vCPU / 8 Go, Paris) et demander un devis ferme avec la remise
   négociée.
2. **Côté équipe (optionnel) :** valider le moteur ONNX sur de vrais documents
   pour, si concluant, réduire encore la consommation.

---

*Toutes les mesures de ce rapport ont été réalisées et vérifiées pendant le
développement. Le détail technique est consigné dans
[cost-optimization-log.md](cost-optimization-log.md).*
