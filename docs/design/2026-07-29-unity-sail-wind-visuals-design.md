# Unity sail wind visuals

**Date:** 2026-07-29
**Status:** approved

## Goal

Make the Focus V2 mainsail and jib visibly react to the wind in Unity without
changing xdyn physics. A drawing sail must look pressurised and cambered; a sail
that is under-trimmed, head-to-wind, or crossing during a tack must lose its
shape and flutter before filling on the other side.

This is a rendering feature. The existing xdyn aerodynamic polar remains the
authority for forces, even though it has no realistic stall regime yet.

## Current state

`ActuatorAnimator` subscribes to `/lotusim/vessel_cmd_array`, rotates the boom
and mainsail as one rigid object from `mainsail(sheet)`, and rotates the rudder.
It chooses the leeward side geometrically from the boat heading and the
scenario's constant north wind. The jib is static.

The Blender source already contains separate, dense `Mainsail` and `Jib`
meshes. Both have enough geometry for FBX blend shapes; neither currently has
shape keys, an armature, or a cloth simulation.

The scenario wind is uniform: `3.0 m/s`, blowing south from north. Unity already
receives the boat pose, so it can infer horizontal boat velocity and apparent
wind without another ROS topic.

## Decision

Use authored Blender shape keys driven procedurally by the existing Unity
actuator component.

Do not use Unity Cloth. Its constraints, collision setup, solver tuning, and
non-determinism are disproportionate to this one-metre visual model.

Do not add a custom sail shader. Geometry deformation gives the silhouette,
lighting, and shadows needed here while preserving the current sail materials.

Do not change xdyn, the ROS messages, or the render bridge.

## Blender asset

Add the same four shape keys to `Mainsail` and `Jib`:

- `FilledPort`
- `FilledStarboard`
- `RipplePort`
- `RippleStarboard`

`Basis` is the neutral, unpressurised sail. The two filled shapes preserve the
existing authored camber and mirror it across the boat centre plane. The two
ripple shapes bend in opposite directions and concentrate displacement toward
the leech, while the luff and corners remain anchored.

The mainsail keeps its mast and boom edges fixed. The jib keeps its forestay
edge and three corners fixed. Deformation changes only the lateral coordinate;
it does not move either sail's object origin or change the existing materials.

The authored `.blend` remains the source of truth. A small deterministic Blender
script creates or refreshes the shape keys, validates their names and anchor
positions, saves the source, and exports the FBX with the project's existing
axis conversion.

## Unity behaviour

### Apparent wind

`ActuatorAnimator` retains the existing ROS subscription and command parsing.
Each frame it derives:

1. smoothed horizontal boat velocity from pose displacement;
2. true air velocity from `windFromDeg = 0` and `windSpeed = 3`;
3. apparent air velocity as true air velocity minus boat velocity;
4. apparent wind angle and side relative to `BowAxis`.

A pose step greater than `0.25 m` is a bridge discontinuity. It resets the
velocity estimate instead of creating a false wind impulse. Near exactly
downwind, where the side is ambiguous, the last stable side is retained.

`windFromDeg` and `windSpeed` remain Inspector calibration fields because they
must match the scenario conditions.

### Fill and luff

Pure `SailVisualMath` functions convert apparent wind, apparent wind angle, and
sheet command into two normalised values:

- `fill`: pressure/camber;
- `luff`: loose flutter.

The calibrated trim reference follows the existing pilot curve:

`sheet degrees = clamp(0.6 * (wind angle degrees - 42), 4, 80)`.

A drawing sail close to that trim receives high fill. A sail near head-to-wind
loses fill. Easing substantially beyond the reference produces luff; over-
trimming flattens the sail without the same loose flutter. No apparent wind
means neither fill nor flutter.

When the apparent-wind side changes, both sails receive a short tack luff
envelope before filling on the new side. This keeps the existing visible boom
sweep and adds the missing loss and recovery of sail pressure.

### Applying shape keys

The mainsail and jib use the same fill/luff state:

- only the filled shape on the current leeward side receives fill weight;
- the two ripple weights alternate during luff;
- the jib uses a slightly faster phase and stronger ripple than the mainsail.

The mainsail continues rotating with the boom. The jib stays attached to its
forestay and changes shape instead of rotating as a rigid triangle.

If either mesh or its expected shape keys are missing, log one explicit warning
and preserve the existing rigid boom/rudder animation. A missing visual
enhancement must not break steering or ROS command handling.

## Files

LOTUSim-regatta:

- `assets/blend/focus_v2.blend` — authored shape keys;
- `assets/blend/author_sail_shapes.py` — deterministic author/export script;
- `unity/WakeMath/SailVisualMath.cs` — pure apparent-wind and trim response;
- `unity/WakeMath/WakeMathTests.cs` — EditMode coverage for sail visual math;
- `unity/ActuatorAnimator.cs` — pose sampling and blend-shape drive;
- `docs/unity-scenario.md` — operator-facing behaviour and calibration.

LOTUSim-Unity-modules production worktree:

- `Assets/models/focus_v2/mesh/focus_v2.fbx`;
- deployed copies under `Assets/Scripts/Regatta/`;
- `Assets/models/focus_v2/focus_v2.prefab` only if serialized calibration differs
  from script defaults.

## Verification

Automated gates:

1. The Blender authoring command completes and a fresh FBX import contains all
   four shapes on both sails.
2. Sail visual math tests first fail without the implementation, then pass.
3. The complete Unity EditMode result XML reports `result="Passed"` and zero
   failed tests.
4. The Windows Regatta player builds with zero errors.
5. Existing repository Python tests and lint remain green.

Visual acceptance in the Regatta scene:

1. Close-hauled, both sails show stable camber on the leeward side.
2. During a tack, both sails visibly flatten and flutter before refilling on the
   opposite side; the jib reacts a little faster than the mainsail.
3. Head-to-wind or substantially over-eased, both sails luff instead of staying
   rigid.
4. Downwind with the sheet eased, both sails remain filled and do not alternate
   sides rapidly.
5. No sail deformation spike follows spawn, reconnect, or a pose reset.
6. Manual helm, rudder animation, wake, water, and boat pose remain unchanged.

The visual run is the final acceptance gate. Compilation alone cannot establish
that the camber direction, anchor constraints, or flutter amplitude look right.
