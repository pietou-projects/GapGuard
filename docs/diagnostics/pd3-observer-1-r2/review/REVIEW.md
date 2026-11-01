# Revue — observation de la chaîne PD3 à l'intérieur de GapGuard

Révision `pd3-observer-1-r2` : l'observation et les décisions restent celles du premier paquet. La correction d'identité et de lecture est détaillée dans [READER-INTEGRITY.md](READER-INTEGRITY.md). Le présent rapport est actualisé pour décrire le paquet r2, sans nouvelle preuve matérielle.

## Objet et source exacte

Cette variante répond à une seule question : les événements manquants avant un défaut entrent-ils dans le callback de GapGuard, et, s'ils entrent, qu'en fait le code existant ? Elle n'essaie pas de corriger le réarmement ni de résoudre le défaut.

La capture source est `GapGuard_PD3_Live_20261101/gapguard.py`, récupérée le 1er novembre 2026 entre 20:16:59.967400 et 20:17:00.164872 UTC depuis `/home/mks/klipper/klippy/extras/gapguard.py`. Le manifeste de l'audit rapporte 80 557 octets, une taille et un mtime inchangés pendant la lecture, et SHA-256 `bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a`. Cette empreinte a été revérifiée pendant la préparation. La copie est conservée dans `baseline/`.

Aucune nouvelle connexion à la Giga n'a été utilisée. Les conclusions de l'audit précédent ne sont pas remplacées par ces simulations : les neuf AutoRecovery complètes de cette capture avaient bien réarmé la surveillance, et de vrais fronts étaient déjà traités avant MANUAL_FULL.

## Périmètre exact du diff

Le module ajoute une classe `PD3Observer` et une méthode d'isolation des erreurs `GapGuard._pd3_diag`. Huit méthodes existantes reçoivent uniquement des appels d'observation :

| Méthode | Observation ajoutée |
| --- | --- |
| `_gpio` | Entrée avant le premier retour ; raison des trois retours anticipés ; association à la file |
| `_drain_edges` | Acquisition préalable ; sortie de file ; résultat du filtre epoch/génération/temps |
| `_gpio_observed` | État avant traitement ; résultat de `Machine.gpio` ; éventuel changement ultérieur par l'observateur AutoRecovery |
| `_observe` | Dernier état natif déjà lu et points de repère aux changements d'état |
| `_trace_pd3_fault` | Gel d'une copie bornée du tampon au défaut PD3 confirmé |
| `_monitor` | Restitution différée d'un petit lot, après son travail existant |
| `_reset_file` | Étiquetage des événements abandonnés par le `clear()` déjà existant |
| `_shutdown` | Même étiquetage pour le `clear()` de shutdown déjà existant |

L'affectation du résultat de `popleft()` est décomposée en deux lignes pour retrouver l'objet tuple exact ; l'appel reste à la même place. Les tuples de `_edges` conservent leurs cinq éléments et leur ordre. Aucun événement ne leur est ajouté par l'observateur. Le `else` ajouté au filtre ne contient qu'un enregistrement du rejet.

Les classes **Settings, Native, Motion, Machine et AutoRecovery sont inchangées octet pour octet**. Toutes les autres méthodes existantes, dont `_worker`, `_execute_pause`, les commandes publiques, fan1, thermique, `position()` et les méthodes de reprise, sont inchangées. Le test structurel confirme également l'identité de tout le code fonctionnel après retrait des seuls ajouts d'observation. Les fins de ligne historiques de toutes les lignes conservées sont préservées.

Aucun changement de paramètre ni de fichier de configuration n'est proposé. Les décisions 9/20/20/2 utilisées sur la machine, les modes, les pauses, le lifecycle et AutoRecovery ne sont pas modifiés. Les traces `PD3_REARM_BEGIN`, `PD3_RECOVERY_VALIDATED`, `PD3_RESUME_GENERATION`, `PD3_RESUME_ACTIVE` et `PD3_FIRST_POST_RESUME_EDGE` sont conservées.

## Ce qui est enregistré

### Entrée du callback et retours anticipés

Chaque entrée de `_gpio` reçoit un numéro diagnostique local. Sont mémorisés le masque du groupe, `eventtime`, l'heure monotone de traitement, ready, initialized, session, epoch, génération, serial, mode, phase, running et les barrières temporelles courantes.

Les retours sont distincts :

- `dead` : arrêt du traitement parce que `_dead` est vrai ;
- `not_ready_boot_snapshot_saved` : le masque a réellement été conservé dans `_boot_snapshot` par le code existant ; ce n'est pas un événement simplement perdu ;
- `eventtime_below_floor` : l'événement précède `max(min_eventtime, generation_time)`. Les valeurs comparées sont présentes.

**Les tags epoch/génération sont des données hôte.** Le callback MCU ne fournit pas une identité de session. À l'entrée, le diagnostic décrit donc la session courante ; les comparaisons de session et génération deviennent réellement possibles sur les tuples déjà mis en file. Il ne prétend pas découvrir la session d'origine d'un message MCU.

### File et filtres

Le même identifiant relie réception, mise en file, sortie de file et effet. L'association est latérale, par identité du tuple, sans changer la file fonctionnelle. Le tuple reste conservé dans l'association afin d'éviter une réutilisation ambiguë de son identifiant Python.

Au rejet de file, le diagnostic donne toutes les comparaisons suivantes, même celles que le `and` natif aurait court-circuitées : ready ; epoch reçu/courant ; génération reçue/courante ; `eventtime`, `min_eventtime`, `generation_time`. Leur résultat décrit le filtre existant et ne pilote pas son résultat.

Une acquisition préalable à `_drain_edges` est identifiée séparément. Elle peut avoir établi le niveau avant le passage dans `Machine.gpio` : l'absence de transition à ce second passage n'est alors pas un front perdu.

Lors d'un reset/shutdown, les événements encore corrélés reçoivent la raison d'abandon avant le `clear()` existant. Quand une association a été écrasée par la capacité du tampon, un dequeue peut être enregistré avec `missing_callback_record=true` : cela signifie **réception non conservée dans le tampon**, pas absence de callback.

### Effet sur le détecteur

Les instantanés encadrent l'appel existant à `Machine.gpio`. Ils contiennent PD3/PD4, état, E déjà mémorisé dans Motion, référence E, bornes VERIFY, compteur VERIFY, compteur de fronts de génération et dernier E de front. L'E du tuple, déjà calculé par le chemin normal, est conservé séparément comme `processing.E`.

Le diagnostic distingue :

1. **Réception** : entrée dans `_gpio`, y compris si le masque sera rejeté.
2. **Acquisition** : UNKNOWN devient un niveau connu ; aucun front artificiel.
3. **Transition reconnue** : PD3 change entre deux niveaux connus après validation de l'événement.
4. **Acceptation par Machine** : valeur de retour du véritable `Machine.gpio`. Elle ne signifie pas nécessairement qu'un front a compté dans VERIFY.
5. **Transition comptée dans VERIFY** : constat des compteurs et des bornes du chemin existant. Un nouveau VERIFY peut repartir de zéro après un ancien compteur à 2 ; ce cas est testé.

Un front après la borne finale peut donc avoir `electrical_transition=true`, `machine_accepted=true`, mais `verify_counted=false`. Les valeurs E et les bornes permettent de comprendre ce résultat. L'étiquette VERIFY est strictement diagnostique ; elle ne remplace pas le détecteur.

Les raisons de non-acceptation incluent acquisition, absence de changement PD3, fichier non actif, mode différent de FULL, E indisponible et filtre de génération. Si le callback AutoRecovery existant modifie ensuite le détecteur, un champ `after_recovery_observer` conserve cet état distinct de l'effet immédiat de `Machine.gpio`.

## Collecte et sortie bornées

Ces constantes concernent uniquement la télémétrie ; elles ne deviennent pas des réglages de la surveillance :

- 128 derniers enregistrements d'événements ;
- 32 derniers changements de contexte/état avec compteur cumulatif d'entrées callback ;
- au maximum 2 restitutions de défaut en attente ;
- 1 écriture de journal par passage du moniteur existant, contenant au maximum 4 événements, après un en-tête ;
- aucune nouvelle minuterie, aucun nouveau worker, aucun G-code et aucune commande de dump.

Les compteurs indiquent les événements/associations écrasés et les restitutions refusées quand les deux places sont occupées. Le tampon ne bloque jamais la file fonctionnelle.

Lors d'un `PD3_NO_MOTION` confirmé dans le chemin normal, une copie du tampon est figée. Cette étape n'écrit pas les événements dans le journal avant l'appel à la PAUSE. Le moniteur ne restitue rien tant que le worker GapGuard est `_busy`, notamment pendant l'attente de la PAUSE native. Il émet ensuite `[GAPGUARD_PD3_DIAG]` par lots. Avec 128 événements et un moniteur à 0,250 s, une restitution complète demande nominalement 33 passages, environ 8,25 s après qu'elle peut commencer. Il n'y a pas de garantie temporelle si le Reactor est retardé.

Les nouvelles traces ne sont pas écrites pour chaque étape de chaque front. Les traces PD3 déjà activées auparavant restent telles quelles. L'instrumentation capture aussi lorsque `motion_trace` vaut faux, sans changer ce réglage ni la surveillance.

Un dump comprend désormais `schema=2`, un UUID d'instance et `capture_id=<UUID>:<numéro>`, répétés dans chaque lot. Les compteurs et les offsets ne sont plus utilisés seuls pour identifier une capture. Les lots orphelins et les lignes diagnostiques illisibles produisent des avertissements avec numéros de ligne. Les anciens dumps sans identité ne peuvent pas être certifiés complets. Le détail figure dans le rapport d'intégrité r2. Il ne faut pas confondre `COMPLETE=True` pour la **transmission du tampon identifié** avec une conservation de toute l'histoire depuis le démarrage.

## Coût et risque de perturbation

Mesure indicative r2 sur le PC, Python 3.14.7, avec des doubles de test et sans mesure d'écriture disque : médiane de 6,74 µs par callback pour la base et 19,03 µs pour la variante, sur cinq séries de 10 000 callbacks chacune. La copie au défaut a pris environ 91 µs. Le graphe de données conservées mesuré avec deux dumps pleins occupait environ 683 Ko ; les deux restitutions totalisaient environ 612 Ko de texte. Le plus gros en-tête mesuré faisait environ 20,8 Ko. La plus longue sérialisation d'un lot mesurée était d'environ 0,51 ms. Les différences avec les mesures PC précédentes ne démontrent pas un gain de performances.

La génération d'UUID ajoute un appel à la source aléatoire du système à la création de l'observateur, pas à chaque front ni à chaque défaut. Sa disponibilité et sa latence sur la Giga ne sont pas mesurées. Une exception est isolée par le mécanisme diagnostique existant ; aucun fallback à un identifiant temporel ou à un PID réutilisable n'est introduit.

Ces valeurs ne sont **ni une borne sur la Giga, ni une mesure de son processeur, ni une garantie de charge acceptable en impression**. Le détail et la dispersion figurent dans [cost-estimate-PC.json](results/cost-estimate-PC.json). Les structures sont bornées en nombre ; les nombres Python peuvent évidemment grossir avec la durée du processus. Les chemins conservés sont tronqués à 256 caractères et ne servent jamais à une décision.

Le risque d'observation existe : allocations Python, lectures d'horloge, sérialisation, collecte mémoire et sortie du journal peuvent retarder le Reactor et les lectures E normales qui viennent ensuite. Aucun E supplémentaire n'est lu, mais leur instant réel d'exécution peut être décalé. L'identité des décisions avec des entrées simulées identiques ne démontre donc pas une neutralité temporelle sur le matériel. Une saturation disque ou une exception grave ne peut pas être exclue par un test PC.

Les exceptions ordinaires du diagnostic sont isolées ; un compteur d'erreurs les signale dans le dump suivant. Un échec du logger ne provoque pas de boucle de réessai. En cas d'erreur de diagnostic, de lots manquants ou de capture écrasée, il faut limiter la conclusion à la portion effectivement conservée. Si Klipper s'arrête avant la restitution, celle-ci peut être perdue : aucun mécanisme de persistance indépendant n'est ajouté.

## Limites de causalité

- Le champ `eventtime` est celui remis par `buttons` au callback. Dans le `buttons.py` exact collecté, `handle_buttons_state()` programme `handle_button()` via `register_async_callback`, puis `handle_button()` appelle GapGuard si le masque changé le concerne. Ce n'est pas un horodatage matériel du front PD3. `processed_at - eventtime` ne mesure donc pas la latence complète capteur → MCU → hôte.
- Un callback de groupe peut provenir de PD4 seul. `callback_entries` ne compte pas nécessairement des fronts PD3.
- Si les compteurs et les points de repère montrent qu'aucun nouveau callback n'est entré pendant un intervalle couvert, avec diagnostic sans erreur et restitution intacte, on peut conclure à une absence de livraison **à `_gpio`** pendant cet intervalle.
- Cela ne prouve pas une absence électrique de signal. Le capteur, le GPIO, le MCU, le transport, `buttons.py` et son filtrage sont en amont. Aucun de ces étages n'est instrumenté ou modifié ici.
- Un callback reçu mais trop ancien, d'une génération périmée, ou reconnu hors VERIFY peut être identifié sans conclure que le rejet est erroné. Il faut comparer les valeurs à la logique déjà validée.
- L'absence de nouveau défaut n'entraîne pas de nouvelle restitution. Les événements ultérieurs restent dans le tampon et peuvent être écrasés. Les traces habituelles de reprise restent disponibles, mais ce diagnostic ne promet pas un enregistrement continu de toute l'impression.

## Vérifications effectuées

La variante r2 passe **311/311 tests** : les 258 cas existants, les 29 cas d'observation/équivalence du premier paquet, et 24 nouveaux cas d'intégrité/identité. Six tests structurels historiques conservent leur adaptation explicite aux seuls appels d'observation. Aucun test fonctionnel n'est supprimé ou désactivé. Le contrôle r2 supplémentaire compare le module au précédent observer-1 et limite le diff embarqué aux métadonnées.

Les ajouts vérifient notamment : entrée avant les retours ; valeurs de comparaison des rejets séparés/cumulés ; acquisition UNKNOWN ; PD4 seul ; transitions en PARTIAL et en pause ; fronts aux deux bornes ; front après VERIFY ; nouveau compteur VERIFY après une fenêtre réussie ; abandon au reset/shutdown ; tampon et sorties bornés ; erreurs du diagnostic/logger ; maintien des traces de réarmement ; 10 000 étapes différentielles déterministes ; trois cycles AutoRecovery complets avec mêmes commandes, mêmes lectures E, trois M24 et 45 blocs de 20 mm.

La comparaison différentielle contrôle les états de Machine et Motion, les références, compteurs, flags, files et l'ordre des appels observables. Les tests structurels confirment que la syntaxe Python 3.7 reste acceptée. La compilation est vérifiée sans installation.

Les messages ERROR présents dans `results/suite.txt` proviennent de cas existants qui injectent volontairement des erreurs, par exemple une purge sans assez de transitions. Leur résultat de test est `ok` et le récapitulatif final est 311 tests, OK.

## Exemple de lecture — simulation uniquement

L'exemple [received/rejected](results/example-received-rejected-SIMULATED.txt), produit par le vrai code diagnostique avec un harness local, contient :

| Événement | Résultat observable |
| --- | --- |
| 1 | Masque reçu, transition PD3 reconnue, E=2, ARMING → NORMAL |
| 2 | Callback reçu avec eventtime=99, rejeté car generation_time=100 |
| 3 | Événement reçu et mis en file en génération 1, rejeté après passage à 2 |
| 4 | Événement reçu et mis en file en epoch 0, rejeté après passage à 1 |
| 5 | Transition reconnue à E=43,01 ; VERIFY=[23;43] ; compteur 0 → 0 ; aucun front crédité dans VERIFY |

Le deuxième exemple conserve un vrai callback simulé à 100,1 s puis les observations SUSPECT/VERIFY/défaut sans nouvelle entrée. Le dernier callback et les compteurs attestent cette absence **dans la simulation**, sans attribution à un composant physique.

Le troisième exemple montre deux transitions effectivement comptées, avec le second front exactement à la borne finale. Les trois fichiers `.log` sont les restitutions brutes ; les `.txt` sont leur lecture hors machine. Les identités epoch/génération artificiellement manipulées dans le harness ne sont jamais créées par le module diagnostique sur une imprimante.

## Arrêt

Variante prête à examiner. **Aucun transfert ni installation. Aucune intervention sur l'impression. Aucun changement Giga, watcher ou GitHub.** La prochaine conclusion causale dépend d'une future observation réelle autorisée, pas des simulations de ce paquet.
