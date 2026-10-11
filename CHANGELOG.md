# Changelog

## 4.2.0-rc1 — Release Candidate

Préparation finale archivée le 9 octobre 2026 ; aucune promotion stable.

### Fixed

- Vrais fronts PD3 reçus mais exclus de Motion par la logique interne pendant un cycle réellement printing.
- Origine de pause GapGuard et maintien des quatre cibles bed, y compris après l'expiration d'idle_timeout, sans modifier la pause manuelle Elegoo.
- Faux échec AutoRecovery après M24 lorsque le mutex est occupé : confirmation passive sur l'état réel.
- Essuyage : six mouvements transmis dans une séquence continue, sans pas de worker entre chaque mouvement.

### Changed

- Critère AutoRecovery fondé sur le cumul de transitions sur l'ensemble des 300 mm ; abandon de la fenêtre glissante window6.
- Minimum configurable de transitions, deux dans la configuration de référence.
- Identification et sorties humaines 4.2.0-rc1.

### Known limitations

- La cause racine de toutes les pertes PD3 n'est pas définitivement expliquée. Le correctif des fronts n'est pas une preuve de causalité unique.
- RC non promue stable ; compatibilité principalement étudiée sur la référence Elegoo.
- Tests automatisés simulés, distincts des tests physiques.
- Guide, six photos finales et modèles STL/3MF retrouvés dans la Library. Le mainteneur confirme un SFS V2.1 depuis le début des essais ; les anciens libellés V2.0 de cette installation sont corrigés.
