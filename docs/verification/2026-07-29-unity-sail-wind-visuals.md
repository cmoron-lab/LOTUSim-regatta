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
- Sail markings retain their signed relief relative to the cloth:
  grand-voile `-2.151…+2.210 mm` (`4.361 mm` span), foc
  `-2.559…+5.500 mm` (`8.059 mm` span). This keeps lettering and stripes on
  the deformed surface instead of leaving them on the neutral plane.

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
| Unity EditMode XML | `54/54`, `result="Passed"`, `failed="0"` |
| Windows player build | `[BuildRegatta] Succeeded`, `370 MB`, `0 errors`, `3 warnings`, `00:00:16.522` |

## Standalone visual gate

The production player was run against
`UNITY=1 ./scripts/run_regatta.sh 900 hold`.

- Fresh corrected captures cover both wind sides: heading `297°`, TWA `63°`,
  wind over port; then heading `057°`, TWA `57°`, wind over starboard.
- Grand-voile stripes stayed coincident with the curved surface while its
  shape changed. The Blender/FBX relief gate checks the same attachment for
  every marking vertex on both the grand-voile and foc.
- Boat pose, rudder, water, and wake remained stable during the observed run.
- Spawn/reconnect produced no visible deformation spike.

Local evidence was captured in the Unity worktree under
`Logs/sail-relief-*-final.png`; build and test evidence is in
`Logs/regatta-build.log` and `Logs/editmode.xml`.

The opposite stable sides were captured, but the sub-second tack transition
was not archived frame by frame. Downwind fill and side stability across the
`+180°/-180°` seam are covered by EditMode tests; manual helm was not exercised
in this run. Those remain useful human review points before merging the
cross-repository PRs.
