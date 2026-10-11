# Histoire technique retrouvée

Cet historique est documentaire ; il ne fabrique aucun ancien commit Git.

- Le dépôt watcher public possède 21 commits du 29 août au 3 septembre 2026. Sa release v1.0.0 est autonome et utilise INFINITY_EMERGENCY_PAUSE/RESUME. Le dernier commit documente l'erreur générale S1+ non exposée par FlowQ.
- Le watcher archivé du 14 septembre ajoute `SOURCE=FLOWQ` à son appel de pause, encore actif à cette étape. Le bundle public local du 14 septembre contient un guide étiqueté à tort SFS V2.0 pour cette installation, le mapping DET0/PD4 et DET1/PD3, ainsi que l'ancien filament_motion_sensor natif. Cette configuration et son detection_length sont historiques, pas l'installation GapGuard actuelle.
- Une archive du 28 septembre conserve le vrai watcher devenu informatif : les alertes A/B ne déclenchent plus de pause. L'ID personnel est remplacé par un placeholder dans sa proposition publique.
- Les archives 4.1 conservent les audits d'acquisition initiale, transactions et lifecycle. Les premières candidates géraient une recovery propre plus large. La candidate.7 revient à la détection SFS avec les macros Elegoo natives.
- Les candidates suivantes ajoutent sorties humaines, seuils configurables, traces de fronts et gestion fan1 des pauses GapGuard. Candidate.10 est la base de la branche actuelle.
- Des pistes diagnostiques RC11/12/13 ont été investiguées ; elles ne sont pas des instructions d'installation de 4.2.
- Candidate.14 ajoute AutoRecovery isolée, 300 mm par blocs de 20 mm après la pause. La variante window6 utilisait les six derniers blocs ; cette règle est abandonnée dans 4.2.0-rc1 au profit du cumul complet.
- La préparation finale du 9 octobre fixe le traitement des vrais fronts, l'origine de pause/idle_timeout, la confirmation M24 et la continuité d'essuyage. Le module final est identifié par son hash exact, pas seulement par le nom RC1 partagé avec une préparation antérieure.

Les chronologies physiques et l'identification électrique brute PD3 ne sont pas reconstituées à partir de souvenirs. Le guide complet, les six photos finales, les modèles et les relevés GPIO documentés ont été retrouvés dans la Library et les archives.

Certaines anciennes notes et premiers drafts identifiaient par erreur le capteur comme V2.0, alors que le matériel réellement utilisé depuis le début était V2.1 (confirmation explicite du mainteneur le 11 octobre 2026). Les références externes V2.0 conservent leur version ; aucune équivalence universelle V2.0/V2.1 n’est déduite.
