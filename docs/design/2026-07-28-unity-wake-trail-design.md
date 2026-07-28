# Unity wake trail

**Date:** 2026-07-28  
**Status:** approved

## Why

The current Unity wake is made of three independent particle clouds: hull wake,
bow foam, and rudder wash. Even after adding a soft procedural texture, random
rotation, and horizontal billboards, it still reads as sparse floating discs.
Some particles also leave the water plane because their initial velocity inherits
the boat's orientation.

The configured reference speed is another mismatch: `3 m/s` is the scenario wind
speed, while the measured boat speed is roughly `0.28-0.52 m/s`. At the nominal
`0.35 m/s`, the current quadratic bow emitter produces less than one particle per
second.

The target is a continuous, dense wake that stays on the rendered water and makes
the boat's trajectory legible without pretending to simulate fluid dynamics.

## Decision

Keep the existing `WakeEmitter` component and prefab attachment, but replace its
three `ParticleSystem` children with one world-space `TrailRenderer`.

The trail starts at the existing `Rudder` anchor, follows the boat by distance
rather than by elapsed time, widens behind the stern, and fades after a short
distance. It uses the existing `RegattaSpray` material with a new deterministic
procedural texture containing two broken foam bands and a mostly transparent
centre.

No bow or rudder particle emitter remains. They can be reconsidered only after the
single trail has been judged insufficient in the Windows editor.

## Rendering

`WakeEmitter` creates one `WakeTrail` child at runtime:

- `TrailRenderer.alignment = TransformZ`, with its normal fixed to world up;
- emitter position = `Rudder` world `x/z`, clamped to `seaLevel` plus a `5 mm`
  rendering offset;
- `minVertexDistance = 0.03 m`, so spatial density is independent of frame rate;
- `time = 6 s`, giving a wake around `2.1 m` long at `0.35 m/s`;
- width grows from about `0.06 m` at the stern to at most `0.30 m` at the tail;
- width is scaled against `refSpeed = 0.5 m/s`;
- the oldest end fades to zero alpha;
- the generated texture tiles along the trail instead of stretching once over its
  full length.

The renderer begins emitting above `0.03 m/s`. Below that threshold, it stops
adding vertices but lets the existing wake expire naturally.

The trail has no particle velocity and no boat-relative rotation. It therefore
cannot be thrown upward by heel, pitch, or rudder angle.

## Motion discontinuities

The speed estimate remains the smoothed horizontal displacement already used by
the current component. Vertical motion never contributes.

If the boat moves more than `0.25 m` in one Unity update, the movement is treated
as a spawn, reset, or ROS pose discontinuity. The trail is cleared instead of
drawing a line across the scene.

## Parameters

Only parameters useful for the visual calibration remain serialized:

| Parameter | Default | Purpose |
|---|---:|---|
| `seaLevel` | `0 m` | visual water reference |
| `surfaceOffset` | `0.005 m` | avoid depth fighting without visible hovering |
| `refSpeed` | `0.5 m/s` | full wake width |
| `minSpeed` | `0.03 m/s` | stop emitting at rest |
| `maxStep` | `0.25 m` | reject pose discontinuities |
| `minVertexDistance` | `0.03 m` | spatial trail density |
| `wakeWidth` | `0.30 m` | maximum tail width |
| `lifetime` | `6 s` | wake persistence |
| `smoothing` | `0.15 s` | speed smoothing |

Emission rates, particle size, bow rate, rudder rate, and maximum rudder angle are
removed because the new renderer does not use them.

## Code and ownership

`LOTUSim-regatta/unity/` remains the source of truth. Implementation changes are
limited to:

- `unity/WakeEmitter.cs`;
- `unity/WakeMath/WakeMath.cs`;
- `unity/WakeMath/WakeMathTests.cs`, copied to the existing Unity EditMode test
  assembly;
- the wake description in `docs/unity-scenario.md`.

`WakeMath` keeps only the pure speed normalisation and width mapping used by the
trail; the obsolete particle-rate functions and tests are removed.

The two C# source files are then copied to the linked Windows Unity worktree:

`/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/`

The existing `feat/regatta-particles` worktree contains unrelated local edits.
Only wake-owned files and the `focus_v2` prefab's serialized `WakeEmitter` fields
may change. Deleted `link.xml` files, scene edits, manual helm work, camera work,
and project settings are left untouched.

No new package, shader graph, material, prefab, or VFX Graph is introduced.

## Errors

- Missing `RegattaSpray` material: log an error and disable the component.
- Missing `Rudder` anchor: log an error and disable the component.
- Non-positive `refSpeed`, `minVertexDistance`, `wakeWidth`, `lifetime`, or
  `maxStep`: stop emission rather than producing invalid geometry.
- Pose discontinuity: clear the trail and continue from the new position.

There is no silent fallback to particles.

## Verification

1. Unity EditMode tests cover speed clamping and width mapping.
2. Unity batchmode compiles the Windows worktree with zero C# errors and passes
   the EditMode suite.
3. The WSL and Windows copies of `WakeEmitter.cs` and `WakeMath.cs` have identical
   checksums.
4. Visual pass in the Windows editor:
   - no circular cards or isolated discs;
   - continuous wake on straight legs and through turns;
   - no geometry leaves the water when the boat heels;
   - wake density does not change with frame rate;
   - wake fades after the boat stops;
   - no long segment appears after a reset or reconnect.

The visual pass is the acceptance gate. Batchmode proves compilation and logic,
not whether the wake looks convincing.
