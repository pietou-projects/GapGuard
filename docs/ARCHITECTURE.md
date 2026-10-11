# Architecture

`Settings` valide les paramètres. `Motion` suit acquisition, référence E, SUSPECT/VERIFY et transitions. `Machine` porte modes, lifecycle, défauts et demande de pause. `GapGuard` adapte ces objets au Reactor, à buttons et aux commandes natives. `AutoRecovery` est un composant séparé exécuté après la pause.

PD3 et PD4 appartiennent au même groupe buttons dans ce build, sans interception pulse_counter ni réémission diagnostique buttons_add. PD3 mesure le mouvement, PD4 la présence. UNKNOWN est distinct de LOW. L'acquisition utilise le snapshot réel, ou le baseline non inversé après la borne dépendant de l'OID : ready + 1,5 s + 0,01×OID + init_guard. Elle ne compte aucun front.

Les vrais fronts HIGH↔LOW rejoignent Motion avec la position issue de `find_past_position()` au timestamp du signal. La RC supprime le rejet interne qui pouvait exclure ces fronts pendant un vrai cycle printing. Les protections contre les événements obsolètes restent distinctes de ce traitement. Les niveaux dupliqués ne sont pas des transitions.

Avec le profil 9/20/20/2 : une absence de front place en SUSPECT à 9 mm. VERIFY s'ouvre à référence+20 et se termine à référence+40, sans fenêtre glissante. Deux fronts qualifient la fenêtre. Les bornes inclusives et les fronts reçus avant l'exécution effective d'une PAUSE gardent leur priorité. L'ordonnancement réel peut amener l'observation au-delà de la borne ; ce n'est pas une pause physique instantanée à exactement 40,000 mm.

Un cycle réel requiert print_stats et Virtual SD. Une pause suspend la surveillance ; l'envoi de RESUME seul ne la réarme pas. Le vrai retour printing actif crée une nouvelle référence E et ARMING, puis le premier vrai front établit NORMAL. `active_fault` est effacé à la reprise, `last_fault` reste diagnostic. Complete, cancel et nouveau fichier nettoient la session.

Les modes PARTIAL/FULL rebasent la logique de surveillance ; ils ne reconfigurent pas les GPIO ou le MCU. BYPASS désactive les protections. FlowQ n'est pas une entrée du détecteur. Les essais diagnostiques RC11/12/13 ne sont pas la base de cette RC.

Le mutex protège les envois courts. Le worker de récupération avance par étapes et observe les fins physiques. Après M24, la confirmation passive ne doit pas dépendre de la disponibilité immédiate du mutex.
