# Unity water-decal wake

**Date:** 2026-07-28
**Status:** approved direction, pending written-spec review

## Why

The `TrailRenderer` wake is rejected after testing in `Regatta.exe`.

It has two structural defects:

- it records one ribbon along the boat path, not the characteristic divergent
  V of a displacement hull;
- each old vertex keeps the water height sampled when it was emitted, while the
  rendered HDRP waves continue moving, so the ribbon is intermittently hidden.

Tuning width, density, texture, or height offset cannot fix either defect.

## Decision

Replace the trail with a bounded pool of small HDRP `DecalProjector` foam
stamps. Decals are rendered directly onto the `WaterSurface`, so they follow the
current rendered wave shape without CPU height sampling or vertical particles.

The wake emits one left/right pair at regular travelled-distance intervals. Each
stamp stores its world position, emission heading, side, speed, and age. It
remains in world space after emission, drifts laterally along the perpendicular
captured at emission, and fades out. The two stamp streams form a V on straight
legs and retain the actual curved history during turns.

The initial divergence uses a wake half-angle close to 20 degrees. Its lateral
drift is derived from the speed captured at emission, so a stamp does not rotate
or change course when the boat subsequently turns.

## Rendering

All stamps share one HDRP decal material:

- white monochrome base color, which is supported on HDRP water;
- a soft irregular alpha texture, with no circular particle card;
- base-color influence only; no emission, metal, normal, or ambient-occlusion
  modification;
- one per-projector `fadeFactor`, avoiding a material instance per stamp.

Each projector is a shallow downward-facing volume tall enough to intersect the
full rendered wave range. Its transform height does not define the visible foam
height: HDRP projects the decal into the water rendering itself.

The material is a referenced asset under `Resources`, not a shader found only by
name, so the Windows player build cannot strip it.

## Lifetime and pooling

The implementation allocates a fixed pool at startup and reuses it. There is no
runtime instantiate/destroy loop and no unbounded wake history.

Emission is driven by horizontal distance, not frame count. Speed controls stamp
opacity and size. Below the existing minimum speed, no new pair is emitted and
existing stamps finish fading naturally.

A ROS spawn, reset, or pose jump above the existing maximum-step threshold clears
the pool. The wake code never writes the boat transform.

The first visual calibration keeps only these physical-art knobs:

| Parameter | Initial value |
|---|---:|
| minimum speed | `0.03 m/s` |
| emission spacing | `0.12 m` |
| lifetime | `5 s` |
| stamp width | `0.18 m` |
| stamp length | `0.30 m` |
| divergence half-angle | `19.5 deg` |
| projector depth | `1 m` |
| reference speed | `0.5 m/s` |
| speed smoothing | `0.15 s` |

The pool contains 48 left/right pairs (96 projectors). This covers a five-second
wake at more than `1 m/s` with `0.12 m` spacing and remains an implementation
constant, not a user-facing quality system.

## Ownership and cleanup

`LOTUSim-regatta/unity/` remains the source of truth and is copied to:

`/mnt/c/Users/cyril/lotusim-unity/`

The implementation replaces the current trail inside `WakeEmitter`; it does not
add a second wake component. The rejected `RegattaWake.shader` and trail-only
math/tests are removed when they are no longer used.

Unrelated scene, camera, manual helm, build, Addressables, XR, and project-setting
changes in the Windows worktree remain untouched.

## Errors

- Missing rudder anchor, water surface, decal material, or texture property:
  log an error and disable the wake.
- Invalid calibration: disable the wake rather than emitting invalid projectors.
- Pose discontinuity: clear all active stamps and resume from the new pose.

There is no silent fallback to the rejected trail or to the old particles.

## Verification

Pure EditMode tests cover:

- distance-based emission decisions;
- left/right divergence from the captured heading;
- age-to-position and age-to-fade mapping;
- pool wrap/reuse and discontinuity reset where practical outside Unity objects.

Runtime acceptance is performed in both the Windows editor and `Regatta.exe`:

1. a straight leg forms a stable, widening V;
2. a turn leaves curved world-space history instead of rotating the old wake;
3. rough waves do not cut or hide foam stamps;
4. heel and pitch cannot launch foam into the air;
5. stopping lets the wake fade without new stamps;
6. spawn/reconnect draws no long segment;
7. the boat remains stable with one ROS pose publisher and no wake transform
   writer.

The visual pass is the acceptance gate.
