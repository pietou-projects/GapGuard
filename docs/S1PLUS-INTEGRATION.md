# Infinity Flow S1+ et GapGuard

Deux circuits distincts composent l'installation. Le filament passe physiquement par le SFS vers l'extrudeur. Les informations FlowQ voyagent par REST/WebSocket vers le watcher. **FlowQ ne pilote pas GapGuard.**

Le [dépôt watcher existant](https://github.com/pietou-projects/infinity-flow-s1plus-klipper-watcher) doit accueillir la mise à jour informative retrouvée dans l'archive du 28 septembre. Son ancien tag [v1.0.0](https://github.com/pietou-projects/infinity-flow-s1plus-klipper-watcher/releases/tag/v1.0.0) documente une architecture autonome avec pause après unloaded/unloaded. Ce comportement historique n'est pas celui retenu avec GapGuard.

Version informative : authentification FlowQ, REST + WS, resynchronisation, A/B et délai de confirmation de dix secondes sont conservés. `emergency_pause()` conserve son ancien nom interne mais ne fait plus que journaliser et envoyer un RESPOND informatif. Aucun appel GAPGUARD_PAUSE, RESUME, CANCEL ni changement de mode n'est ajouté.

La reprise et la sécurité ne dépendent ni de la connexion cloud ni d'une validation FlowQ. Un état distant ancien et rassurant ne valide pas le filament réel. L'erreur générale S1+ à deux voyants rouges reste une limitation connue.
