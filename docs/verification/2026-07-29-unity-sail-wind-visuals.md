# Unity sail wind visuals — verification

**Date:** 2026-07-29  
**Source branch:** `autoship/sail-visuals`  
**Unity branch:** `autoship/sail-visuals`

## Scope

Rendering only. Grand-voile and foc react to apparent wind in Unity; xdyn,
ROS messages, the render bridge, wake, water, and vessel physics are unchanged.

## Authored asset

- Blender `4.5.11 LTS`.
- Both sails export exactly `Basis`, `FilledPort`, `FilledStarboard`,
  `RipplePort`, and `RippleStarboard`.
- Two consecutive author/export runs produced the same inventory.
- A factory-startup FBX import passed exact key-set equality for both sails.
- Sail markings retain a signed surface separation of at most `0.2 mm`; this
  prevents the lettering and stripes from collapsing into the neutral or
  rippling cloth.

Calibration defaults:

- true wind: `3.0 m/s` from world north (`windFromDeg = 0`);
- bridge pose-step rejection: `0.25 m`;
- velocity smoothing: `0.15 s`;
- tack luff: `0.65 s`;
- flutter: `4 Hz`, with a slightly faster and stronger foc response.

## Automated gates

| Gate | Result |
| --- | --- |
| `uv run pytest -q` | `8 passed` |
| `uv run ruff check .` | passed |
| Blender authoring twice + inventory diff | passed, no diff |
| Fresh FBX exact shape-key import | passed for both sails |
| Unity EditMode XML | `48/48`, `result="Passed"`, `failed="0"` |
| Windows player build | `[BuildRegatta] Succeeded`, `370 MB`, `0 errors`, `3 warnings` |

## Standalone visual gate

The production player was run against
`UNITY=1 ./scripts/run_regatta.sh 900 hold`.

- Corrected captures show stable markings and camber on both wind sides:
  heading `051°`, TWA `51°`, wind over starboard; then heading `297°`,
  TWA `63°`, wind over port.
- Grand-voile stripes and lettering stayed attached while the sail shape
  changed. The foc used the same fill state with its faster ripple phase.
- Boat pose, rudder, water, and wake remained stable during the observed run.
- Spawn/reconnect produced no visible deformation spike.

Local evidence was captured in the Unity worktree under
`Logs/sail-markings-fixed-*.png`; build and test evidence is in
`Logs/regatta-build.log` and `Logs/editmode.xml`.

The opposite stable sides were captured, but the sub-second tack transition
was not archived frame by frame. Downwind fill is covered by the EditMode
response test; manual helm was not exercised in this run. Those remain useful
human review points before merging the cross-repository PRs.
