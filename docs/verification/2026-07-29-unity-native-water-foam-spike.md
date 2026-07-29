# Unity native water-foam spike — verification

**Date:** 2026-07-29  
**Decision:** accepted spike; production migration still pending

## Result

The isolated Unity 2023.1 spike produces a dense, speed-dependent V wake with
HDRP's native local foam. The foam is rendered on the displaced water surface,
does not become airborne with the hull, and fades after the vessel stops.

![Native HDRP foam wake](../media/unity-native-water-foam-spike.png)

The Unity 2022 source project at
`C:\Users\cyril\lotusim-unity` was not modified by this spike.

## Versions

- Unity `2023.1.20f1` (`35a524b12060`)
- HDRP, Core, URP, and Shader Graph `15.0.7`
- isolated project:
  `C:\Users\cyril\lotusim-unity-2023.1-spike`
- player:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Builds\Regatta\Regatta.exe`

## Migration correction

HDRP 15 inserted `InstancedQuads` into `WaterGeometryType`. The migrated scene
retained serialized value `2`, which changed the ocean from `Infinite` to
`InstancedQuads` and made it effectively disappear at the existing transform
scale. Setting the Ocean `WaterSurface.geometryType` to `3` restored the
infinite sea.

The active Regatta camera was also verified to receive:

- an HDRP asset with water and water foam enabled;
- the global `WaterRendering` volume override;
- the camera `FrameSettingsField.Water` flag.

## Wake configuration

Water surface:

- foam atlas: `1024`, area `32 m × 32 m`, offset `(0, 7.5)`;
- persistence multiplier: `0.15`;
- texture tiling: `2`;
- smoothness: `0.3`;
- simulation foam amount: `0.2`.

Focus V2 prefab:

- rejected `WakeEmitter` disabled;
- two rectangular `WaterFoamGenerator` children;
- half-angle: `19.5°`;
- each arm: `0.09 m × 1.8 m`;
- stern anchor: local `x = -0.425 m`;
- arm centres: local `x = -0.8483 m`, `z = ±0.3005 m`;
- arm rotations: local yaw `∓70.5°`;
- maximum surface-foam dimmer: `0.6`.

`NativeFoamWakeController` scales both generators from zero at rest to full
intensity at `0.8 m/s`. A pose step above `0.25 m` is treated as a discontinuity
and injects no foam. Intensity smoothing is `0.15 s`.

## Verification evidence

EditMode tests:

```text
testcasecount=21 result=Passed passed=21 failed=0
```

Windows player build:

```text
[BuildRegatta] Succeeded — 369 MB, 0 errors, 2 warnings
```

Live command, with exactly one simulator stack and one Unity player:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

Observed:

- the ocean remains visible and animated;
- two foam arms start at the stern and diverge symmetrically;
- rough waves deform the foam without under-wave cuts;
- no particle cards or airborne markers are present;
- the vessel remains stable with no multi-publisher teleportation;
- after stopping the stack, the HUD reaches `0.00 m/s` and the foam disappears
  naturally within a few seconds.

The temporary runtime diagnostic used to inspect HDRP's camera volume stack and
prefab axes was removed before the final tests and build.

## Next gate

Keep the source Unity 2022 project unchanged until choosing the production
cutover. Retaining this implementation means migrating the canonical Windows
project to Unity `2023.1.20f1`/HDRP `15.0.7` and replaying the same tests before
replacing its build.
