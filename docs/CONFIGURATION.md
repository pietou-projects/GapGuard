# Configuration extraite, sans calibration privée

Source : configuration validée SHA-256 `a018667f0ae1a7e20a19accbbd65bce103d8f83b4c323679e5f275aae5768bbc`. Le fichier complet n'est pas publié. Les corps de sections fournis sont extraits de cette source ; seuls l'en-tête et les séparateurs de l'exemple sont documentaires.

| Bloc | Statut | Adaptation |
|---|---|---|
| `[gapguard]` | Obligatoire | Pins, nom extrudeur et seuils de la référence Giga ; aucun doublon |
| Six `[gcode_macro GAPGUARD_*]` | Interface publique Fluidd | Délégation uniquement ; pas de logique de sécurité dans les macros |
| `[idle_timeout]` | Nécessaire au maintien des beds lors des pauses GapGuard | Fusionner dans l'existant, ne pas juxtaposer deux sections ; branche manuelle conservée dans la référence |
| PAUSE/RESUME/CANCEL_PRINT | Préexistants, spécifiques Elegoo | Non remplacés par l'exemple ; variables et états natifs exigés par AutoRecovery |
| `fan1` et quatre chauffages | Préexistants, spécifiques Giga | `fan1` est output_pin, scale 255 ; état runtime normalisé 0..1 |

## Seuils

L'exemple validé indique `suspect_distance=9`, `verify_trigger=20`, `verify_distance=20`, `verify_transitions=2`, `check_interval=0.250`, `init_guard=0.250`, `motion_trace=1`, `default_mode=FULL`. Les distances sont en mm d'extrusion native, pas en secondes ni en distance XY.

**Différence à connaître :** les défauts Python historiques de `Settings` sont 9/50/12/6 ; le profil validé 9/20/20/2 provient des valeurs explicites de l'exemple. Ne pas omettre ces paramètres en supposant que le code a les mêmes défauts. La fin de fenêtre est trigger + distance, soit 40 mm pour l'exemple.

## Paramètres AutoRecovery

Le code accepte enabled 0/1 et un minimum de transitions entier positif (2 dans l'exemple). Il vérifie les valeurs fixes de la candidate : délai 30 s, distance 300 mm, blocs 20 mm, avance F200. Ces paramètres ne sont pas librement réglables dans cette RC malgré leur présence en configuration. F200 est en mm/min, soit 3,333… mm/s. Il n'y a pas de maximum par session ni de validation window6.

## Thermique

Le statut `pause_origin == "gapguard"` signifie une pause réellement récupérable prise en charge par GapGuard. Dans cette branche, idle_timeout émet seulement `SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0`, sans TURN_OFF_HEATERS : les quatre cibles existantes sont conservées. Hors cette branche, le comportement Elegoo de référence reste en place. Ce mécanisme ne force aucune température de plateau et ne modifie pas CANCEL.

Les paramètres machine tels que rotation_distance, samples, fade_end, mesh, PID, limites et courants ne sont pas des réglages GapGuard et ne figurent pas dans l'exemple public.
