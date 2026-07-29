# Unity native water-foam spike

**Date:** 2026-07-29
**Status:** approved direction, pending written-spec review

## Why

The particle, trail, and HDRP 14 decal implementations all failed the visual
acceptance test:

- particles look like sparse cards and can leave the rendered water;
- a trail follows one centreline instead of forming a divergent wake;
- ordinary decals do not provide HDRP's local foam accumulation and have not
  remained visually convincing on the rough rendered sea.

The Windows project currently uses Unity `2022.3.62f2` and HDRP `14.0.12`.
HDRP's local `WaterFoamGenerator`, intended among other uses for boat trails,
starts in HDRP 15 and therefore requires Unity 2023.1.

## Decision

Run a disposable migration spike with Unity `2023.1.20f1` and HDRP `15.0.7`.
This is the smallest editor and render-pipeline upgrade that contains the
native foam generator.

The spike answers one question: can HDRP's accumulated local foam produce a
dense, wave-integrated, divergent wake for the Focus V2 at the scenario's
roughly `0.5 m/s` speed?

It does not authorize migrating the main Unity project. A visually successful
spike is required before choosing whether to retain Unity 2023.1, migrate
further, or port the result elsewhere.

## Isolation

The source project remains:

`C:\Users\cyril\lotusim-unity`

Create a separate Windows project:

`C:\Users\cyril\lotusim-unity-2023.1-spike`

Copy project-controlled content and the current local work, but exclude
regenerable directories such as `Library`, `Temp`, `Logs`, `obj`, `.vs`, and
player builds. Opening and upgrading the spike must not modify the source
project or its Git worktree.

Install Unity `2023.1.20f1` alongside, not instead of, Unity `2022.3.62f2`.
Install only the Windows build support needed by the existing Regatta build.

## Migration gate

Open only the isolated copy in Unity 2023.1 and align the four coupled render
packages to `15.0.7`:

- High Definition RP;
- Render Pipelines Core;
- Shader Graph;
- Universal RP, because it is already a direct project dependency.

Keep all unrelated packages at their current versions unless Unity reports an
actual incompatibility. Use the HDRP Wizard only for required migration fixes.

Before wake work, require:

1. zero C# compilation errors;
2. the Regatta scene opens with the boat and ocean intact;
3. existing EditMode tests pass;
4. the Windows player still builds;
5. the Unity ROS bridge can connect without adding another pose publisher.

If satisfying this gate requires broad changes to ROS, XR, Ultraleap,
Addressables, or scene architecture, stop the spike and report the blockers.

## Native wake experiment

Disable the rejected `WakeEmitter` renderer in the spike so only one wake
implementation is visible.

Enable local foam in the HDRP asset and on the existing `WaterSurface`. Add two
small `WaterFoamGenerator` children at the rudder or stern anchor:

- rectangle generators;
- left and right arms rotated symmetrically around the boat's aft direction;
- surface foam enabled, deep foam initially disabled;
- dimensions calibrated to the one-metre Focus V2;
- intensity and foam persistence calibrated against the measured
  `0.5 m/s` reference speed.

This is the first visual gate. It uses no new runtime script, custom shader,
texture, particle system, or ordinary decal.

If two attached generators produce adequate density and divergence, stop there.
Do not add code.

If native accumulation follows the waves but remains too parallel, retain the
HDRP foam path and replace only the generator placement with the smallest
bounded runtime extension:

- reuse the existing tested distance sampling and `WakeMath` divergence;
- maintain a pool below HDRP's 64-generator limit;
- emit left/right native generator pairs in world space;
- move active generators laterally along their captured emission heading;
- disable generators after their short injection lifetime and let HDRP retain,
  reproject, and erode the injected foam.

The extension never writes the boat transform and clears its pool after a pose
discontinuity.

## Calibration

Keep the number of exposed controls small:

- minimum and reference boat speed;
- emission spacing, only if the pooled extension is needed;
- V half-angle;
- generator width and length;
- surface foam intensity;
- injection lifetime, only if the pooled extension is needed;
- WaterSurface foam persistence.

Start from the existing `19.5°` half-angle and `0.5 m/s` reference speed.
Rendering quality settings remain unchanged unless the native foam atlas shows
a measured resolution limitation.

## Verification

Run the scene against exactly one simulation stack:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

Accept the spike only if a Windows editor run and `Regatta.exe` both show:

1. a dense wake beginning at the stern without visible particle cards;
2. two readable arms that diverge on a straight leg;
3. foam integrated into the moving wave surface, without repeated
   under-wave cuts;
4. curved world-space history during turns;
5. no airborne foam when the boat heels or pitches;
6. natural fading after stopping;
7. no long wake segment after spawn, reconnect, or pose reset;
8. stable boat motion with no multi-publisher teleportation.

Record the editor version, HDRP version, relevant foam settings, test results,
and one representative capture. Visual acceptance is the final gate; a clean
compile alone is insufficient.

## Outcomes

- **Accepted:** preserve the isolated spike, document its exact migration and
  wake settings, then make a separate decision about the production Unity
  version.
- **Migration failure:** leave the Unity 2022 project untouched and report the
  first incompatible dependency.
- **Native foam failure:** do not backport HDRP internals and do not revive the
  rejected trail or decal implementations. Reassess particles using the visual
  evidence from the spike.
