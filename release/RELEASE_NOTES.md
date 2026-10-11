# GapGuard 4.2.0-rc1 — notes de prépublication

Tag proposé : `v4.2.0-rc1`. **PRE-RELEASE**, pas une version stable. Aucune publication effectuée.

- Module exact : `cf239a52f65f345092946f2289a473c590244ced22c5f31c27e88e26b20473f1`.
- Profil Giga : 9 / 20 / 20 / 2 (fin VERIFY à 40 mm). Les defaults Python historiques restent inchangés ; le profil fourni fixe explicitement les valeurs Giga.
- AutoRecovery : 300 mm, 15 × 20 mm à F200, minimum 2 vrais fronts cumulés sur les 300 mm ; aucune validation window6 actuelle.
- Essuyage continu à F15000 ; M24 unique suivi d'une confirmation passive.
- Pause GapGuard : buse à 0, quatre cibles bed maintenues. PAUSE/RESUME/CANCEL_PRINT Elegoo restent natives.
- FlowQ information-only : aucune pause, reprise, annulation ou décision PD3/PD4.
- Hardware complet SFS V2.1 : guide corrigé, six JPG et STL/3MF exacts renommés sans modification binaire. Les anciens libellés V2.0 de cette installation étaient erronés ; sources externes V2.0 inchangées.

Licences distinctes : GapGuard GPL-3.0-or-later ; watcher séparé MIT ; modèles du support CC0 1.0.

Le ZIP contient code, configuration extraite, tests, docs, matériel, provenance et checksums. Il exclut les configurations machine complètes, SAVE_CONFIG/mesh, credentials, journaux, exports privés et packs de travail. Les anciennes sources sous tests/ sont des fixtures de régression, jamais des modules à installer.

Validation hors machine : suite publique GapGuard et suite watcher relancées lors de la préparation finale ; résultats exacts dans le rapport de vérification livré avec la préparation. La suite interne précédente comptait 231 tests ; 8 contrôles de configurations privées ne sont pas distribués. Aucune validation runtime supplémentaire n'est revendiquée. La cause de tous les silences PD3 historiques n'est pas déclarée résolue.

Assets : `GapGuard-4.2.0-rc1.zip`, `SHA256SUMS.txt`.
