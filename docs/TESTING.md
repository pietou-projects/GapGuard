# Tests et portée

Le 11 octobre 2026, la suite de la préparation finale exacte a été relancée hors machine : **231 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, Python 3.14.7. Compilation et analyse syntaxique Python 3.7 : PASS. Ce n'est pas une exécution sous Python 3.7 sur l'imprimante.

## Suite publique

Utiliser Python 3.10 ou ultérieur pour cet environnement de test public (exécuté ici sous 3.14.7). Les dépendances de test ne sont pas à installer sur la Giga.

```sh
python -m venv .venv
# activer cet environnement selon le système
python -m pip install -r tests/requirements.txt
python -B tests/run_tests.py
```

La suite publique contient **223 tests**, tous repassés. Les assertions comportementales sont reprises des tests existants : acquisition, Motion, lifecycle, modes, pause, fan, thermique, AutoRecovery, M24, cumul de fronts et essuyage. Les chemins de fixtures ont été relocalisés ; les configurations de simulation sont des extraits sans mesh ni calibration.

Huit tests de préservation de configurations complètes privées et de leurs hashes ne sont pas distribués. Leur liste exacte figure dans `tests/EXCLUDED_MACHINE_PRESERVATION_TESTS.json`. Ils restent présents et passent dans les 231 tests internes. Aucune assertion de sécurité comportementale n'est retirée pour obtenir ce résultat.

Les sources historiques Python dans `tests/reference/` et `tests/fixtures/` servent uniquement aux régressions de non-modification et tests négatifs. Elles ne doivent pas être installées. Seul `src/gapguard.py` est le module de production. Le parseur G-code de la fixture provient des sources Klipper auditées ; mouvements, GPIO, horloges, mutex et chauffage sont simulés. Les erreurs volontairement injectées peuvent produire des traces ERROR de logging alors que unittest réussit.

Les 9/50/12/6 historiques présents dans certains tests vérifient la paramétrabilité ; le profil public explicite reste 9/20/20/2. Les noms historiques de tests ne changent pas le critère AutoRecovery actuel, cumulatif sur 300 mm.

Les essais physiques précédents concernent leurs candidates respectives. Une suite hors machine, même complète, ne prouve pas une garantie de détection ni la correction définitive des silences PD3. Aucun test physique n'est effectué pendant cette préparation GitHub.
