# Correction d'intégrité — pd3-observer-1-r2

Préparation entièrement hors machine. Aucun transfert, aucune installation, aucune activation, aucune connexion Giga et aucune modification GitHub. Cette correction ne résout pas et ne prétend pas résoudre le défaut PD3.

## Défaut reproduit

Le paquet original est conservé intact : `GapGuard-4.2.1-rc1-pd3-observer-1-OFFLINE-REVIEW.zip`, SHA-256 `3c30db8267830031d5abde4b1118c3edf469a5f4868b03e04d4e6f22a3103814`.

Le lecteur précédent ignorait silencieusement le JSON illisible et les lots sans en-tête. Il choisissait ensuite le dernier en-tête possédant le même numéro `dump`. Ce numéro repartant à 1 par instance, un en-tête A pouvait être associé aux événements B si les événements A et l'en-tête B manquaient. Un compteur de lignes cohérent suffisait alors à afficher à tort `COMPLETE=True`.

Le test `test_review_collision_reproduces_old_bug_but_not_new_reader` reproduit ce faux positif avec le lecteur exact du paquet précédent. Sur la même entrée, le lecteur r2 signale les événements B comme orphelins et la capture A comme incomplète.

## Identité émise par le module

Une instance de `PD3Observer` crée un UUID v4, une seule fois, via la bibliothèque standard Python. Chaque restitution possède le couple instance/numéro et sa représentation explicite :

```json
{
  "schema": 2,
  "instance_id": "<32 caractères hexadécimaux>",
  "dump": 1,
  "capture_id": "<même UUID>:1"
}
```

Ces métadonnées sont présentes dans `FAULT_CONTEXT` et dans **chaque** lot `EVENTS`. Un redémarrage ou une nouvelle instance produit un nouvel UUID, même si le compteur, l'heure monotone et le PID recommencent aux mêmes valeurs. Les lots reprennent les identifiants de l'en-tête figé, pas un identifiant recomputé au moment de l'écriture.

L'UUID ne dépend d'aucune lecture E, du fichier d'impression, du GPIO ou d'un fichier persistant. Un second défaut de la même instance utilise le même UUID mais un numéro de capture différent. La source aléatoire est appelée une fois par observateur ; aucun nouveau G-code, timer ou réglage n'est ajouté.

L'unicité est celle d'un UUID v4 aléatoire (122 bits aléatoires), avec un risque de collision extrêmement faible, et non une garantie mathématique absolue. Ces identifiants ne sont pas une signature cryptographique : le lecteur ne peut pas authentifier des lignes volontairement falsifiées avec des identifiants copiés. Il n'invente pas un identifiant moins fiable si la génération échoue.

## Règles de lecture

Le lecteur s'appuie uniquement sur `capture_id`, avec validation de `schema`, `instance_id`, `dump` et `build`. Il n'effectue aucun repli vers le seul compteur `dump`.

- Un lot sans en-tête lisible **de la même capture** produit `ORPHAN_EVENTS`, avec son numéro de ligne et son identité. Il n'est pas ajouté à une autre capture.
- Une ligne reconnue par le marqueur `[GAPGUARD_PD3_DIAG]` mais illisible ou invalide produit `UNREADABLE_DIAGNOSTIC`, avec son numéro de ligne. JSON tronqué, clés JSON dupliquées, types invalides et identité incohérente sont signalés.
- Si une ligne endommagée ne peut être attribuée, les captures encore ouvertes sont marquées non certifiables par prudence. Une capture déjà terminée avant cette ligne n'est pas assimilée à une nouvelle capture endommagée.
- Les offsets doivent être consécutifs ; le nombre total doit correspondre à l'en-tête ; le dernier lot doit annoncer la fin. Les trous, duplications, inversions, en-têtes répétés et lots après fin empêchent `COMPLETE=True`.
- Deux captures identifiées peuvent être entrelacées sans mélanger leurs événements.
- À la fin du fichier, chaque capture non terminée reçoit `INCOMPLETE_CAPTURE`, référencé à la ligne où elle a commencé.
- Une trace ancienne sans `schema=2` et sans identité est signalée et n'est pas certifiée complète. Les vieux octets sont conservés dans le paquet original ; le lecteur ne devine pas leurs frontières.

Le rapport commence par `INTEGRITY: OK` ou `INTEGRITY: WARNINGS`. Le code de sortie est **0** sans avertissement et **2** s'il existe des anomalies, des données incomplètes ou aucune donnée diagnostique. Les événements orphelins ne disparaissent plus sans signalement. `read()` retourne maintenant deux collections explicites : `captures` et `issues`.

`COMPLETE=True` signifie uniquement que les lots de cette capture identifiée ont été reçus sans anomalie détectée. Cela ne prouve ni l'exhaustivité électrique des fronts PD3 ni l'absence d'écrasement antérieur du tampon. Si le marqueur diagnostique lui-même a disparu, la ligne ne peut pas être distinguée d'une ligne ordinaire ; les offsets ou les lots orphelins permettent de signaler la perte lorsqu'elle rend la restitution incomplète.

## Périmètre embarqué contrôlé

Par rapport à observer-1 :

- ajout de l'import standard `uuid` ;
- mise à jour du libellé diagnostique `BUILD` et de sa docstring ;
- `PD3Observer.__init__` : création de l'identité de l'instance ;
- `PD3Observer.fault` : identité de la capture dans l'en-tête ;
- `PD3Observer.flush` : mêmes métadonnées dans chaque lot.

**Toutes les méthodes de `GapGuard` sont inchangées octet pour octet par rapport à observer-1.** Les autres méthodes de `PD3Observer`, le traitement des événements, les buffers et les limites restent également inchangés. Les classes Settings, Native, Motion, Machine et AutoRecovery restent identiques à la base live. Les fixtures de configuration sont vérifiées octet pour octet contre le ZIP original.

Le test de périmètre compare les blocs exacts et confirme l'identité de l'arbre syntaxique après retrait des seules métadonnées ajoutées. Les tests différentiels existants (10 000 étapes et trois AutoRecovery complètes simulées) sont rejoués. Aucune lecture E ou native supplémentaire, aucun G-code, aucun réarmement et aucune nouvelle minuterie n'ont été ajoutés.

## Résultats

**311/311 tests PASS** : les 287 précédents et 24 nouveaux tests. Les cas ajoutés couvrent : capture intacte ; en-tête absent ; JSON d'en-tête corrompu ; champs d'en-tête invalides ; lot central ou final absent ; marqueur final absent ; lot illisible ; collision exacte de la revue ; deux instances complètes avec `dump=1` ; entrelacement ; doublons d'en-tête et de lots ; lots désordonnés ; événements après fin ; divergence de métadonnées ; identité incohérente ; ancien format ; JSON ambigu ; capture vide ; sortie CLI ; génération unique de l'UUID ; erreur de génération sans changement des décisions ; périmètre strictement limité aux métadonnées ; syntaxe Python 3.7.

Six exemples, tous **simulés**, sont fournis dans [results/integrity-examples/summary.json](results/integrity-examples/summary.json), avec leurs journaux bruts et rapports. L'[exemple de collision](results/integrity-examples/cross-instance-collision-SIMULATED.txt) affiche des lots orphelins aux lignes 2, 3 et 4 ; la capture dont l'en-tête est ligne 1 reste `COMPLETE=False`.

Les coûts PC actualisés sont uniquement indicatifs. **Le coût réel sur la Giga reste non mesuré.** La source aléatoire et l'instrumentation ajoutent du travail dont la latence matérielle n'a pas été validée. Aucun nouveau test physique n'a été effectué.

Arrêt à la revue du paquet r2. Aucun déploiement et aucune revendication de résolution du défaut PD3.
