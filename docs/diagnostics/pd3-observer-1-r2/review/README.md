# GapGuard 4.2.1-rc1 — pd3-observer-1-r2

**Variante diagnostique préparée hors machine le 1er novembre 2026. Non installée. Aucun correctif fonctionnel.**

Révision r2 : correction limitée à l'identité des restitutions diagnostiques et à leur lecteur hors machine. Le paquet observer-1 d'origine est conservé intact. Lire le [rapport d'intégrité r2](READER-INTEGRITY.md) pour les défauts reproduits, le format corrigé et ses limites.

Le seul fichier destiné à une éventuelle exécution future est [src/gapguard.py](src/gapguard.py). Ce paquet ne comporte aucune procédure de déploiement et ne donne aucune instruction à la Giga. Les fichiers de configuration présents sous `tests/` sont exclusivement des fixtures historiques de tests, pas des fichiers à installer.

La base est le module exact récupéré pendant l'audit du 1er novembre, et non une ancienne candidate reconstruite :

```text
baseline/gapguard.py
bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a
```

`VERSION` reste `4.2.1-rc1`. L'identité diagnostique séparée `4.2.1-rc1+pd3-observer-1-r2` apparaît dans les restitutions du tampon. Elle ne constitue pas une nouvelle release et n'ajoute aucune commande publique.

## Livrables de revue

- [Rapport détaillé, limites et lecture des résultats](REVIEW.md).
- [Diff exact du module collecté vers la variante](gapguard-live-to-observer.diff).
- [Diff du module observer-1 vers r2 : métadonnées seulement](observer-1-to-r2.module.diff).
- [Diff du lecteur observer-1 vers r2](observer-1-to-r2.reader.diff).
- [Résultat complet des 311 tests](results/suite.txt).
- [Collision entre deux instances : exemple corrigé, simulé](results/integrity-examples/cross-instance-collision-SIMULATED.txt).
- [Validation et provenance](results/validation.json).
- [Mesures de coût sur le PC uniquement](results/cost-estimate-PC.json).
- [Exemple simulé : événements reçus puis rejetés ou hors VERIFY](results/example-received-rejected-SIMULATED.txt).
- [Exemple simulé : aucun nouveau callback entre le dernier front et le défaut](results/example-no-callback-SIMULATED.txt).
- [Exemple simulé : transitions réellement comptées dans VERIFY](results/example-VERIFY-counted-SIMULATED.txt).
- [Empreintes des fichiers](SHA256SUMS.txt).

## Rejouer les vérifications hors machine

Python et les dépendances indiquées dans [tests/requirements.txt](tests/requirements.txt) sont nécessaires. Dans le workspace de préparation, les dépendances déjà présentes ont été réutilisées ; aucun téléchargement ni changement de dépendances de la Giga n'a eu lieu.

```text
python -B tests/run_tests.py
```

La suite conserve les 287 cas du premier paquet (258 cas existants et 29 cas d'observation) et ajoute 24 tests d'intégrité/identité. Les six contrôles de périmètre déjà adaptés dans observer-1 restent actifs. [tests/observer_scope.py](tests/observer_scope.py) vérifie que retirer uniquement l'instrumentation et son import de métadonnées restitue exactement l'arbre syntaxique de la base. Un nouveau contrôle vérifie séparément le diff observer-1 → r2 : seules trois méthodes de `PD3Observer` changent, pour ajouter les identifiants. Les autres contrôles fonctionnels n'ont pas été assouplis.

Les exemples sont produits par [tools/produce_evidence.py](tools/produce_evidence.py), exclusivement avec des entrées simulées. Le lecteur de restitution fonctionne hors machine :

```text
python -B tools/read_diagnostic.py results/example-received-rejected-SIMULATED.log
```

Le lecteur émet un avertissement numéroté pour chaque lot orphelin et chaque ligne diagnostique illisible. Son code de sortie est `2` en présence d'avertissements, `0` sinon. Les anciennes traces sans identité de capture ne sont pas certifiées complètes ; aucun rattachement par le seul numéro `dump` n'est tenté.

Les tests et les exemples ne prouvent ni une cause matérielle ni une résolution du défaut runtime. Aucune connexion à la Giga, aucun transfert, aucune activation et aucune publication n'ont été effectués pour cette préparation.
