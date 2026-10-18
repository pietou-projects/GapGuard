# Future hardware investigation

## Objective

Investigate whether filament-path geometry contributes to the PD3 motion-signal gaps observed during testing. The underlying cause of every historical absence of PD3 transitions remains unknown. There is currently no proof that the long PTFE section causes these gaps.

This is a planned, controlled hardware experiment, not a validated solution or a requirement for using GapGuard. GapGuard 4.2.0 remains stable, and the published hardware installation remains the tested reference. No software, thresholds, AutoRecovery behavior or live-printer settings are changed by this plan.

## Current reference layout

The validated reference installation has approximately 1.2 m of PTFE between the BTT SFS V2.1 and the OrangeStorm Giga extruder:

```text
CURRENT TESTED LAYOUT

Infinity Flow S1+
        |
    BTT SFS V2.1
        |
        | ~1.2 m PTFE
        |
     Extruder
```

The current stable release is based on this tested arrangement. See the [reference hardware guide](hardware/BTT-SFS-V2.1-ORANGESTORM-GIGA.md) for the existing installation. The diagram describes the filament path; it is not a scale drawing.

## Moving the SFS closer to the extruder

The planned change is to mount the same BTT SFS V2.1 directly on the print head, with a rigid attachment to suitable metal parts. The sensor would sit as close as reasonably practical to the extruder inlet.

The **current mechanical design target** is approximately **20–30 mm of PTFE** between the SFS outlet and the extruder inlet. This is not a proven optimum or a universal installation dimension. The attachment, alignment and final spacing have not yet been physically validated.

```text
PLANNED HARDWARE TEST — NOT YET VALIDATED

Infinity Flow S1+
        |
        | long low-friction PTFE
        |
 upper-frame PTFE guide
        |
    BTT SFS V2.1
 mounted on print head
        |
        | ~20–30 mm PTFE
        | supported by a rigid PETG guide
        |
     Extruder
```

## Short rigidly supported PTFE section

The short SFS-to-extruder section would still use normal PTFE tubing. A printed PETG part would supply the rigidity, supporting the tube along almost its entire length to limit bending and keep the sensor outlet aligned with the extruder inlet. It must support the PTFE without crushing or clamping it.

The current concept is a PETG channel or tube into which the PTFE is inserted. For PTFE with approximately 4 mm outside diameter, the guide may have a slightly larger internal passage. The clearance and final geometry are design questions to test physically, not manufacturing dimensions specified by this document.

## Upper-frame PTFE guide

A long tube would still be needed between the S1+ and the moving print head. A separate guide near the top of the Giga is planned to keep this tube away from the S1+ body, maintain a clean path with a large, smooth bend radius, and let it move freely with the head. It should avoid transmitting unnecessary pulling forces to either the S1+ or the SFS.

This upper guide must **guide the PTFE, not rigidly clamp it**. Possible concepts include a large-radius curved guide, a pivoting arm or a freely articulated guide. Routing approaches used on Voron or other CoreXY printers may provide design inspiration, but no specific design has been selected or validated for this installation.

## Why this may help the PD3 investigation

The current approximately 1.2 m section separates the location where PD3 measures motion from the filament drive point at the extruder. Moving the SFS closer would place the measurement nearer that drive point and greatly reduce the filament and tubing between them that can accommodate slack, compression, bending or other mechanical effects.

Whether those effects explain the observed PD3 behavior is a **hypothesis**. The experiment is intended to determine whether the long mechanical path is a contributing factor. It does not start from the assumption that this path causes the gaps, nor that every historical gap has the same cause.

## Controlled comparison plan

As far as possible, keep the same Giga, Infinity Flow S1+, BTT SFS V2.1, GapGuard code, GapGuard thresholds, Klipper/firmware environment and PD3/PD4 logic. Do not tune the thresholds while assessing the mechanical change.

The main variables would be the physical SFS position, SFS-to-extruder PTFE length and filament-path guidance. Compare PD3 behavior before and after the change under comparable conditions. Record the tested layout and routing so differences can be interpreted later.

The tubing comparison below is a separate part of the investigation. Where practical, compare tube materials while holding geometry constant rather than changing material and sensor position together. Otherwise, an observed difference could not readily be attributed to either change.

## PTFE visibility problem

In the maintainer's current installation, the Bambu Lab PTFE has shown very good mechanical behavior and low feeding resistance. However, it is not transparent enough to make the A/B filament junction easy to observe. These are observations from this installation, not a ranking of all tubing products.

During S1+ tests, it is useful to see where filament A ends, where filament B begins and where their B|A junction is along the path. Observing when that junction passes through the SFS and reaches the print head or extruder would help correlate physical events with PD3 transitions and GapGuard logs.

## Candidate tubing

The planned comparison includes:

- The current Bambu Lab PTFE as the mechanical reference.
- Transparent or highly translucent PTFE with similar dimensions.
- Creality low-resistance star-shaped PTFE as a candidate to measure, without assuming lower friction than the reference tube.
- Potentially transparent FEP, if its friction and feeding behavior prove acceptable in the tested path.

No winner has been selected. Visibility, movement consistency and feeding resistance must be compared in the actual test conditions; a product description alone does not establish better mechanical performance.

## Planned friction comparison

Use identical tube lengths, the same filament, bend radius, routing, fittings and environment. Compare or measure:

- The force required to pull filament through the tube.
- The force required to push filament through the tube.
- Consistency of movement and any tendency to catch or bind in curves.
- Visibility of the A/B junction.
- Ease of insertion through the S1+, SFS and extruder path.

A small mechanical or digital force gauge may be used if force measurements are made. No acceptable force threshold has been established. Record the method and conditions alongside any measurements so results can be compared meaningfully.

## What would constitute useful evidence

If large PD3 gaps disappear, become significantly shorter or change significantly in frequency after relocating the SFS under comparable conditions, that would suggest filament-path geometry is a contributing factor. Visual observations of the junction, aligned with PD3 transitions and GapGuard logs, would help interpret those changes.

If gaps remain similar in nature, frequency and duration despite moving the SFS close to the extruder, that would weaken the hypothesis that the approximately 1.2 m section is the primary contributing factor. Neither outcome would be absolute proof.

## What this experiment will NOT prove by itself

Moving the sensor closer does not automatically identify an electrical or firmware cause of a PD3 gap. Changed behavior would show a correlation with the altered mechanical path, not necessarily establish the exact mechanism. Unchanged behavior would not prove that mechanical effects never matter. Additional controlled testing may still be required.

## Current status

As of 18 October 2026, this document describes a future investigation. The new SFS position, PETG support, upper-frame guide and tubing choice have not been validated. The root cause of every historical absence of PD3 transitions remains unresolved.

GapGuard 4.2.0 remains stable. This experiment is optional and is not part of the current installation procedure. The published reference hardware configuration, stable release, production module, thresholds, AutoRecovery and separate watcher remain unchanged. This documentation update does not perform any modification or test on the live Giga.

[Back to the README](../README.md)
