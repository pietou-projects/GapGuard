# AutoRecovery 4.2.0-rc1

Cette récupération est spécifique à l'intégration Elegoo auditée, pas une reprise universelle Klipper.

1. Après PD3_NO_MOTION avec PD4 présent, la PAUSE publique Elegoo existante est exécutée une seule fois. Le hook de fin arme AutoRecovery.
2. Attendre la fin physique de la pause puis 30 secondes. Si la pause n'est plus réelle ou PD4 absent, aucune purge automatique ne commence.
3. Réchauffer uniquement la buse à `RESUME.etemp`, la cible déjà sauvegardée. La disponibilité thermique native et la cohérence de cible sont contrôlées.
4. Sauvegarder temporairement l'état G-code, passer en extrusion relative et neutraliser les multiplicateurs M220/M221 pour la purge.
5. Soumettre 15 blocs `G1 E20 F200`, avec vérification de leur fin physique et comptage passif des vrais fronts reçus pendant chaque bloc. Total physique attendu : 300 mm. L'écart E toléré pour la vérification d'un bloc est 0,005 mm, justifié dans le code par la quantification de la référence extrudeur.
6. À la fin des 15 blocs, sommer leurs fronts : minimum 2 pour le profil publié. Un bloc à zéro, ou les six derniers blocs à zéro, n'est pas en soi un échec si le cumul complet atteint le seuil. Une obtention précoce de deux fronts ne raccourcit pas la purge.
7. Attendre le délai SETTLE existant de deux secondes puis envoyer l'essuyage ci-dessous en un script continu, avec une seule vérification de fin globale.
8. Restaurer E, les flags PAUSE/RESUME, les états sauvegardés timelapse B puis A (MOVE_SPEED=250 puis 50), et émettre un seul M24. Observer passivement `printing` + Virtual SD actif. Le mutex occupé juste après M24 n'est pas un échec automatique ; la confirmation conserve sa deadline de dix secondes.

```gcode
G1 X-20 F15000
G1 X20
G1 X-20
G1 X20
G1 X-20
G1 X20
```

G91 a été envoyé avant cette séquence. F15000 est hérité par les cinq dernières commandes. Les inversions et accélérations physiques restent gérées par Klipper ; « continu » signifie absence d'attente AutoRecovery insérée entre les six soumissions, pas vitesse constante aux changements de direction.

PD4 absent pendant la récupération provoque son échec. D'autres gardes concrets existent dans le code : changement de pause/mode/état sauvegardé, mouvement manuel, erreur native, chauffage ou fin de mouvement non confirmés. Un échec ne déclenche pas de M24 de remplacement. Le nettoyage remet la cible buse à zéro quand la pause appartient encore à cette opération ; une annulation ou reprise externe conserve la main.

AutoRecovery n'appelle pas RESUME ou BASE_RESUME. La purge manuelle Elegoo `G1 E100 F200` n'est donc pas ajoutée : total automatique 300 mm, pas 400 mm. Les reprises manuelles conservent la macro native. Il n'existe pas de plafond de tentatives par session.
