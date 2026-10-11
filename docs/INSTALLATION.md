# Installation — configuration de référence uniquement

Ce dossier est une préparation de release candidate. Le module exact, le guide SFS V2.1, les six photos et les modèles de montage sont inclus. Voir le [guide hardware](hardware/BTT-SFS-V2.1-ORANGESTORM-GIGA.md) pour le montage réellement documenté.

## Préconditions réelles

Le module se charge comme extra Klipper `[gapguard]`. Il dépend des objets `buttons`, `mcu`, `toolhead`, `gcode_move`, `print_stats`, `virtual_sdcard`, `pause_resume`, de l'extrudeur et de `output_pin fan1` de la référence. Il utilise des API internes du Klipper Elegoo audité ; il ne s'agit pas d'une extension portable garantie sur toute version Klipper.

Les macros PAUSE, RESUME et CANCEL_PRINT doivent être celles de la référence Elegoo déjà présentes, avec leurs dépendances PLR et leurs variables intactes. AutoRecovery lit dans RESUME `saved_x`, `saved_y`, `saved_z`, `saved_e`, `etemp` et utilise `timelapse_state_a` / `timelapse_state_b` sauvegardés par PAUSE. Il manipule `flag_print_status` de PAUSE et RESUME. Une simple macro générique portant ces noms n'est pas suffisante. Le dossier `tests/` contient des extraits à usage de simulation, **pas des macros d'installation**.

## Procédure d'intégration proposée

1. Hors impression, conserver une sauvegarde exacte du module existant et de la configuration active, y compris SAVE_CONFIG, mesh et includes. Relever les hashes.
2. Vérifier la version et le SHA-256 du fichier `src/gapguard.py`. Aucun patch du fichier n'est prévu.
3. Examiner les sections de `config/gapguard-example.cfg` avec sa documentation. Retirer les anciens propriétaires de PD3/PD4, en particulier `fila` et `sfs_motion`. Ne pas utiliser `duplicate_pin_override` pour partager ces broches.
4. Installer le module dans le dossier `klippy/extras/` de **l'installation réellement utilisée**, puis intégrer uniquement les sections nécessaires. Les chemins ne sont pas supposés universels. Ne pas remplacer le printer.cfg complet, le mesh ou les réglages de l'extrudeur par un fichier d'exemple.
5. Conserver PAUSE/RESUME/CANCEL_PRINT Elegoo. Ajouter les six macros publiques de délégation. Fusionner le bloc idle_timeout : il ne doit exister qu'une seule section.
6. Vérifier les hashes et l'absence de doubles propriétaires avant le chargement.
7. Pour la référence Giga, le protocole retenu après changement Python est un OFF physique complet, environ 30 secondes d'attente puis ON par l'opérateur, pas RESTART/FIRMWARE_RESTART. Aucun flash ou changement de firmware n'est nécessaire.
8. Premier niveau sans impression/chauffe/mouvement : Ready, absence d'exception, six macros présentes, STATUS et DEBUG, acquisition PD3/PD4 cohérente. Les essais d'impression et d'AutoRecovery sont une validation physique distincte, supervisée et autorisée séparément.

Le retour arrière utilise la paire sauvegardée propre à cette installation. Aucun script public ne remplace une configuration ou ne redémarre automatiquement la machine.
