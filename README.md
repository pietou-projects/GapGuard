# GapGuard 4.2.0-rc1

**PRE-RELEASE / RELEASE CANDIDATE — pas une version stable.**

GapGuard surveille la présence et le mouvement du filament dans Klipper. Il a été développé sur une Elegoo OrangeStorm Giga après des silences intermittents du signal de mouvement d'un BTT Smart Filament Sensor. Un défaut confirmé appelle la PAUSE Elegoo existante. Une récupération automatique séparée peut tenter de rétablir le mouvement après un défaut PD3.

**La cause de tous les silences PD3 historiques n'est pas définitivement comprise.** Cette RC corrige notamment l'exclusion interne de vrais fronts reçus. Cela ne démontre pas que cette erreur expliquait chaque longue absence de signal. GapGuard détecte et traite des situations ; il ne répare pas un capteur, un câble ou un étage électrique défectueux.

## Périmètre testé

La référence est la configuration Klipper Elegoo de l'OrangeStorm Giga conservée dans les archives d'essai, avec quatre plateaux et `fan1` en `output_pin`. Le mainteneur confirme que le capteur utilisé depuis le début de tous les essais est un BTT SFS V2.1. Les mentions V2.0 décrivant cette installation dans les anciennes notes sont des erreurs de libellé. Une photo de marquage n’est pas nécessaire pour trancher cette identité. Aucune compatibilité générale V2.0/V2.1 n'est revendiquée.

Ce dépôt n'est pas une configuration universelle de machine. L'AutoRecovery dépend des variables et états sauvegardés des macros Elegoo auditées. Les autres imprimantes nécessitent une adaptation distincte.

## Fonctionnement

| Élément | Rôle |
|---|---|
| PD4 / DET0 dans la référence | Présence : 1 présent, 0 absent |
| PD3 / DET1 dans la référence | Mouvement : HIGH→LOW et LOW→HIGH sont chacun un vrai front |
| FULL | Surveillance PD3 et PD4 |
| PARTIAL | Surveillance PD4 seulement |
| BYPASS | Protections filament désactivées |

L'acquisition initiale `UNKNOWN → niveau connu` n'est jamais un front. Les distances utilisent la position d'extrusion native au temps du signal. L'exemple machine conserve `9 / 20 / 20 / 2` : SUSPECT à 9 mm, VERIFY à 20 mm, fin à 40 mm, deux transitions nécessaires dans la fenêtre. Voir [architecture](docs/ARCHITECTURE.md).

Une pause GapGuard, volontaire ou déclenchée par PD3/PD4, coupe la consigne buse et `fan1` après confirmation de la pause native. Les quatre cibles de plateau sont conservées, y compris lors de l'expiration de l'idle timeout grâce au bloc de configuration fourni. Une PAUSE Elegoo manuelle conserve son comportement natif. Le CANCEL reste natif.

Après `PD3_NO_MOTION` avec PD4 présent, [AutoRecovery](docs/AUTORECOVERY.md) attend la fin physique de la pause puis 30 secondes, réchauffe la buse à la cible mémorisée et purge 300 mm en 15 blocs de 20 mm à F200. Au moins deux vrais fronts cumulés sur toute la purge sont requis. L'essuyage est une séquence continue de six mouvements. Un seul M24 est envoyé puis la reprise réelle est observée passivement.

## Commandes réellement disponibles

| Commande publique | Effet |
|---|---|
| `GAPGUARD_PAUSE` | Pause Elegoo prise en charge par GapGuard |
| `GAPGUARD_STATUS` | État et protections lisibles |
| `GAPGUARD_STATUS_DEBUG` | Diagnostic détaillé ; `RAW=1` ajoute le JSON |
| `GAPGUARD_ENABLE_FULL` | Mode FULL |
| `GAPGUARD_ENABLE_PARTIAL` | Mode PARTIAL |
| `GAPGUARD_DISABLE_ALL` | Mode BYPASS |

Il n'existe pas de `GAPGUARD_RESUME_FULL`, `GAPGUARD_RESUME_PARTIAL`, `GAPGUARD_RESUME_BYPASS` ni `GAPGUARD_CANCEL` dans ce build. Les reprises manuelles et annulations utilisent `RESUME` et `CANCEL_PRINT` Elegoo. Les noms `GAPGUARD_INTERNAL_*` sont les délégués Python des macros, pas l'interface utilisateur.

## Installation et matériel

- [Installation](docs/INSTALLATION.md) : prérequis et limites de l'exemple.
- [Configuration](docs/CONFIGURATION.md) et [extraits validés](config/gapguard-example.cfg).
- [Guide matériel et câblage](docs/hardware/BTT-SFS-V2.1-ORANGESTORM-GIGA.md).
- [Support imprimé](hardware/README.md) : STL/3MF exacts, six photos originales du pack final et licence CC0 1.0 pour les modèles.
- [Dépannage](docs/TROUBLESHOOTING.md), [historique](docs/HISTORY.md), [changements](CHANGELOG.md).

## Infinity Flow S1+

Le [watcher existant](https://github.com/pietou-projects/infinity-flow-s1plus-klipper-watcher) est un composant séparé. L'architecture actuelle avec GapGuard utilise FlowQ **uniquement comme télémétrie**. FlowQ ne déclenche ni pause, ni reprise, ni annulation, ni validation de fronts ou changement de mode. Le comportement autonome historique v1.0.0 déclenchait une pause : ne pas confondre les versions. Voir [intégration](docs/S1PLUS-INTEGRATION.md).

## Vérification et licence

La préparation interne exacte a repassé 231 tests hors machine, sans échec ni erreur. Le paquet public conserve 223 tests exécutables ; huit contrôles d'identité de configurations complètes privées restent dans l'archive interne. Les deux périmètres sont explicités dans [TESTING](docs/TESTING.md). Ce résultat simulé n'est pas une garantie physique et aucune validation machine nouvelle n'est revendiquée par cette publication.

Le module distribué est inchangé : SHA-256 `cf239a52f65f345092946f2289a473c590244ced22c5f31c27e88e26b20473f1`.

GapGuard est sous **GPL-3.0-or-later** : voir [LICENSE](LICENSE) et [licences et crédits](docs/LICENSES-AND-CREDITS.md). Le watcher conserve MIT. Les modèles STL/3MF sont sous **CC0 1.0**, voir [hardware/LICENSE](hardware/LICENSE). Ces trois composants ne sont pas présentés sous une licence unique.
