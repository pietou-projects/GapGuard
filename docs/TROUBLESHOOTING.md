# Dépannage et limites

## Silences PD3

La cause de tous les silences/pertes de signal PD3 historiques n'est pas définitivement identifiée. Des absences anormales ont été observées. La RC corrige un chemin interne qui pouvait exclure des fronts réellement reçus ; cela ne démontre ni une cause unique ni la résolution de chaque incident matériel.

Commencer par STATUS puis DEBUG et les traces `[GAPGUARD_TRACE]` de toute la fenêtre de test. Distinguer : absence de callback, niveau dupliqué, vraie transition, surveillance suspendue, événement obsolète et défaut confirmé. Une LED bleue visible ne prouve pas à elle seule le niveau au MCU. Ne pas qualifier d'emblée le capteur, le câble ou Klipper de cause.

## UNKNOWN au démarrage

L'entrée n'est pas encore acquise. Ne pas la renommer LOW. Attendre la borne calculée selon l'OID, puis examiner Ready/shutdown et l'acquisition. Le vieux délai fixe de 0,5 seconde n'est pas une preuve suffisante.

## Macros absentes / erreur de chargement

Les six macros publiques doivent être présentes une fois chacune et déléguer au backend Python. Les commandes de reprise GapGuard historiques ne sont pas disponibles dans ce build. Les macros Elegoo et leurs états sauvegardés sont des prérequis. Aucun attribut `stats` ne doit être ajouté au module : une ancienne candidate avait heurté la découverte automatique des callbacks Klipper.

## Plateaux coupés pendant une pause

Le maintien ne repose pas seulement sur gapguard.py. Vérifier la branche idle_timeout fondée sur pause_origin. La macro Elegoo peut fixer le délai à 1800 s ; sans cette branche, TURN_OFF_HEATERS coupait aussi les beds. Ne pas masquer le problème en modifiant les cibles ou en réinstallant une ancienne configuration complète.

## Échec AutoRecovery

Lire la phase et la raison exactes. Aucun succès ne doit être déduit de l'envoi seul de M24. Une purge de 300 mm insuffisamment qualifiée ne doit pas reprendre. Un déplacement manuel ou une intervention externe peut invalider l'opération. Les gardes physiques ne sont pas à supprimer pour obtenir un PASS.

## FlowQ et deux voyants rouges S1+

Une erreur générale S1+ peut laisser un état FlowQ ancien apparemment normal. Le watcher ne peut pas détecter une panne que les données reçues ne représentent pas. REST/WS sont des interfaces non documentées et la fraîcheur n'est pas une garantie. Le watcher actuel est informatif, pas une sécurité de remplacement pour PD3/PD4.
