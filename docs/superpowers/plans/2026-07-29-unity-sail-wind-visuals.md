# Unity Sail Wind Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Focus V2 mainsail and jib visibly fill, flatten, and flutter from apparent wind in Unity.

**Architecture:** Blender shape keys provide deterministic sail geometry, while the existing `ActuatorAnimator` derives apparent wind from the constant scenario wind and bridged boat motion. Pure `SailVisualMath` owns the tested trim response; the actuator remains the ROS and Transform edge.

**Tech Stack:** Blender 4 Python API, FBX blend shapes, Unity `2023.1.20f1`, HDRP `15.0.7`, C#, NUnit EditMode tests.

## Global Constraints

- Rendering only: no xdyn, ROS message, render bridge, physics, water, or wake change.
- Both `Mainsail` and `Jib` receive `FilledPort`, `FilledStarboard`, `RipplePort`, and `RippleStarboard`.
- Preserve existing sail materials, object names, origins, and the current rigid boom/rudder fallback.
- True wind defaults to `3.0 m/s` from Unity world north (`windFromDeg = 0`).
- Reject pose steps greater than `0.25 m` when estimating boat velocity.
- No Unity Cloth, custom sail shader, dependency, or additional wind topic.
- The authored source is `assets/blend/focus_v2.blend`; the deployed FBX is in the Windows Unity worktree.
- Unity test success is read from the generated XML, not the process exit code alone.

---

### Task 1: Tested sail response math

**Files:**
- Create: `unity/WakeMath/SailVisualMath.cs`
- Modify: `unity/WakeMath/WakeMathTests.cs`
- Deploy: `/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeMath/SailVisualMath.cs`
- Deploy: `/mnt/c/Users/cyril/lotusim-unity/Assets/Tests/Editor/WakeMathTests.cs`

**Interfaces:**
- Consumes: Unity `Vector2`, `Vector3`, and `Mathf`.
- Produces: `SailVisualMath.ApparentWind`, `OptimalSheet`, `Response`, and `RippleWeights`.

- [ ] **Step 1: Add failing EditMode tests**

Append a `SailVisualMathTests` fixture to the existing source test file:

```csharp
[TestFixture]
public class SailVisualMathTests
{
    const float Eps = 1e-4f;

    [Test]
    public void ApparentWindSubtractsBoatVelocity()
    {
        Assert.AreEqual(
            new Vector3(-0.5f, 0f, -3f),
            SailVisualMath.ApparentWind(
                new Vector3(0f, 0f, -3f),
                new Vector3(0.5f, 0f, 0f)));
    }

    [Test]
    public void CorrectlyTrimmedSailFills()
    {
        Vector2 state = SailVisualMath.Response(
            3f, 60f, SailVisualMath.OptimalSheet(60f));
        Assert.Greater(state.x, 0.95f);
        Assert.Less(state.y, Eps);
    }

    [TestCase(5f, 4f)]
    [TestCase(60f, 70f)]
    public void HeadToWindOrOverEasedSailLuffs(float angle, float sheet)
    {
        Vector2 state = SailVisualMath.Response(3f, angle, sheet);
        Assert.Less(state.x, 0.05f);
        Assert.Greater(state.y, 0.95f);
    }

    [Test]
    public void NoWindProducesNoDeformation()
    {
        Assert.AreEqual(Vector2.zero,
            SailVisualMath.Response(0f, 60f, 11f));
    }

    [Test]
    public void DownwindTrimStaysFilled()
    {
        Vector2 state = SailVisualMath.Response(3f, 180f, 80f);
        Assert.Greater(state.x, 0.95f);
        Assert.Less(state.y, Eps);
    }

    [Test]
    public void RippleWeightsStayBoundedByLuff()
    {
        for (int i = 0; i < 100; ++i)
        {
            Vector2 weights = SailVisualMath.RippleWeights(0.6f, i * 0.2f);
            Assert.That(weights.x, Is.InRange(0f, 0.6f));
            Assert.That(weights.y, Is.InRange(0f, 0.6f));
        }
    }
}
```

- [ ] **Step 2: Deploy the failing test and prove RED**

Copy the source test into the Windows project, run the documented EditMode
command without `-quit`, and inspect
`C:\Users\cyril\lotusim-unity\Logs\editmode.xml`.

Expected: compilation failure because `SailVisualMath` does not exist.

- [ ] **Step 3: Implement the minimum pure math**

Create:

```csharp
using UnityEngine;

public static class SailVisualMath
{
    public static Vector3 ApparentWind(
        Vector3 trueAirVelocity, Vector3 boatVelocity)
    {
        trueAirVelocity.y = 0f;
        boatVelocity.y = 0f;
        return trueAirVelocity - boatVelocity;
    }

    public static float OptimalSheet(float windAngle)
    {
        return Mathf.Clamp(0.6f * (Mathf.Abs(windAngle) - 42f), 4f, 80f);
    }

    // x = filled camber, y = loose luff, both 0..1.
    public static Vector2 Response(
        float apparentSpeed, float windAngle, float sheetDeg)
    {
        if (apparentSpeed <= 0.05f) return Vector2.zero;

        float speed = Mathf.Clamp01(apparentSpeed);
        float drawingAngle = Mathf.InverseLerp(
            25f, 45f, Mathf.Abs(windAngle));
        float error = sheetDeg - OptimalSheet(windAngle);
        float overEased = Mathf.Clamp01(error / 25f);
        float overTrimmed = Mathf.Clamp01(-error / 35f);
        float fill = speed * drawingAngle * (1f - overEased)
            * (1f - 0.45f * overTrimmed);
        float luff = speed * Mathf.Max(1f - drawingAngle, overEased);
        return new Vector2(fill, luff);
    }

    public static Vector2 RippleWeights(float luff, float phase)
    {
        luff = Mathf.Clamp01(luff);
        float wave = Mathf.Clamp(
            0.72f * Mathf.Sin(phase)
                + 0.28f * Mathf.Sin(1.73f * phase + 0.7f),
            -1f, 1f);
        return new Vector2(
            luff * Mathf.Max(0f, -wave),
            luff * Mathf.Max(0f, wave));
    }
}
```

- [ ] **Step 4: Deploy and prove GREEN**

Copy `SailVisualMath.cs` into the existing `Regatta.WakeMath` assembly and run
the full EditMode suite.

Expected XML: `result="Passed"`, all previous tests plus the six new sail tests,
zero failed.

- [ ] **Step 5: Commit the tested source**

```bash
git add unity/WakeMath/SailVisualMath.cs unity/WakeMath/WakeMathTests.cs
git commit -m "feat(unity): derive sail pressure from apparent wind"
```

---

### Task 2: Deterministic Blender sail shapes

**Files:**
- Create: `assets/blend/author_sail_shapes.py`
- Modify: `assets/blend/focus_v2.blend`
- Modify: `assets/blend/README.md`
- Deploy: `/mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/mesh/focus_v2.fbx`

**Interfaces:**
- Consumes: Blender objects named `Mainsail` and `Jib`.
- Produces: the four exact shape-key names required by `ActuatorAnimator`.

- [ ] **Step 1: Prove the asset gate currently fails**

Run:

```bash
blender --background assets/blend/focus_v2.blend --python-expr \
  'import bpy; expected={"FilledPort","FilledStarboard","RipplePort","RippleStarboard"}; [(_ for _ in ()).throw(AssertionError(f"{o.name}: shape keys missing")) if not o.data.shape_keys or not expected.issubset(o.data.shape_keys.key_blocks.keys()) else None for o in (bpy.data.objects["Mainsail"], bpy.data.objects["Jib"])]'
```

Expected: non-zero exit with `Mainsail: shape keys missing`.

- [ ] **Step 2: Add an idempotent Blender author/export script**

The script must:

```python
SAILS = {
    "Mainsail": {"ripple": 0.018},
    "Jib": {"ripple": 0.015},
}
SHAPES = ("FilledPort", "FilledStarboard", "RipplePort", "RippleStarboard")
```

For each sail it records the original lateral `x`, clears old shape keys, adds a
flat `Basis`, mirrors the original camber for the two filled keys, and creates
opposing three-wave leech ripples. The displacement envelope is zero on the
luff and at the head and foot:

```python
height = clamp((co.z - z_min) / (z_max - z_min), 0.0, 1.0)
chord = chord_fraction(sail_name, co.y, height)
envelope = math.sin(math.pi * height) * chord * chord
ripple = amplitude * envelope * math.sin(3.0 * math.pi * height)
```

It validates the exact key set, saves the open `.blend`, and exports the given
FBX using:

```python
bpy.ops.export_scene.fbx(
    filepath=output_fbx,
    axis_forward="-Z",
    axis_up="Y",
    bake_space_transform=True,
    path_mode="COPY",
    add_leaf_bones=False,
)
```

- [ ] **Step 3: Author the source and deploy the FBX**

Run:

```bash
blender --background assets/blend/focus_v2.blend \
  --python assets/blend/author_sail_shapes.py -- \
  --output-fbx /mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/mesh/focus_v2.fbx
```

Expected: both sails report the five keys including `Basis`; the source `.blend`
and target FBX are updated.

- [ ] **Step 4: Verify shapes from a fresh FBX import**

The authoring script asserts unchanged origins/material slots and fixed anchor
vertices before exporting. Independently verify the exported payload:

```bash
blender --background --factory-startup --python-expr \
  'import bpy; bpy.ops.import_scene.fbx(filepath="/mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/mesh/focus_v2.fbx"); expected={"FilledPort","FilledStarboard","RipplePort","RippleStarboard"}; [(_ for _ in ()).throw(AssertionError(f"{name}: exported shapes missing")) if not bpy.data.objects[name].data.shape_keys or not expected.issubset(bpy.data.objects[name].data.shape_keys.key_blocks.keys()) else print(name, sorted(bpy.data.objects[name].data.shape_keys.key_blocks.keys())) for name in ("Mainsail","Jib")]'
```

Expected: both objects print `Basis` plus the four exact shape names.

- [ ] **Step 5: Document and commit the authored asset**

Add the one-command regeneration recipe to `assets/blend/README.md`, then:

```bash
git add assets/blend/author_sail_shapes.py assets/blend/focus_v2.blend \
  assets/blend/README.md
git commit -m "feat(assets): let both sails carry visible wind"
```

---

### Task 3: Drive both sails from the live apparent wind

**Files:**
- Modify: `unity/ActuatorAnimator.cs`
- Deploy: `/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/ActuatorAnimator.cs`
- Modify only if defaults must be serialized: `/mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/focus_v2.prefab`

**Interfaces:**
- Consumes: `SailVisualMath`, the four shape keys on each sail, `BowAxis`, the
  existing sheet command, and the bridged root Transform.
- Produces: filled/ripple blend-shape weights while retaining `BoomSide`,
  `RudderAngle`, local manual override, boom rotation, and rudder rotation.

- [ ] **Step 1: Add minimal calibration and runtime state**

Add Inspector defaults:

```csharp
public float windFromDeg = 0f;
public float windSpeed = 3f;
public float maxPoseStep = 0.25f;
public float velocitySmoothing = 0.15f;
public float tackLuffTime = 0.65f;
public float flutterHz = 4f;
```

Track the jib Transform, both `SkinnedMeshRenderer`s, shape indices, last
position, smoothed velocity, last stable side, tack-luff age, and flutter phase.

- [ ] **Step 2: Resolve shape keys with a rigid fallback**

At `Start`, find `Jib` along with the existing parts. Resolve each renderer and
the four indices by exact name. If a renderer or index is absent, log one warning
for that sail and leave its blend-shape drive disabled; do not disable the
component.

- [ ] **Step 3: Derive apparent wind without bridge spikes**

Before applying rotations:

```csharp
Vector3 delta = transform.position - _lastPosition;
_lastPosition = transform.position;
delta.y = 0f;
if (delta.magnitude > maxPoseStep)
    _boatVelocity = Vector3.zero;
else
    _boatVelocity = Vector3.Lerp(
        _boatVelocity,
        Time.deltaTime > 0f ? delta / Time.deltaTime : Vector3.zero,
        velocitySmoothing > 0f
            ? Mathf.Clamp01(Time.deltaTime / velocitySmoothing)
            : 1f);

Vector3 trueAir = Quaternion.Euler(0f, windFromDeg, 0f)
    * Vector3.back * windSpeed;
Vector3 apparent = SailVisualMath.ApparentWind(trueAir, _boatVelocity);
Vector3 windFrom = apparent.sqrMagnitude > 1e-6f
    ? -apparent.normalized
    : Vector3.zero;
```

Use the signed angle from `windFrom` to `BowAxis` to update the side outside a
small ambiguity threshold. A side change resets the `0.65 s` tack-luff envelope.

- [ ] **Step 4: Apply the tested response to both sails**

Compute apparent wind angle, call `Response`, suppress fill by the tack envelope,
and raise luff by the same envelope. Feed:

```csharp
Vector2 mainRipple = SailVisualMath.RippleWeights(
    luff, _flutterPhase);
Vector2 jibRipple = SailVisualMath.RippleWeights(
    Mathf.Clamp01(luff * 1.15f), _flutterPhase * 1.23f + 0.4f);
```

Set only the current side's filled key. Set both ripple keys from the two
weights. Keep the existing boom/mainsail and rudder rotations unchanged.

- [ ] **Step 5: Compile and run all EditMode tests**

Deploy `ActuatorAnimator.cs`, run the documented EditMode command, and inspect
the XML.

Expected: `result="Passed"`, zero compilation errors and zero failed tests.

- [ ] **Step 6: Commit the runtime**

```bash
git add unity/ActuatorAnimator.cs
git commit -m "feat(unity): make both sails fill and luff"
```

---

### Task 4: Integration, visual gate, documentation, and ship

**Files:**
- Modify: `docs/unity-scenario.md`
- Create: `docs/verification/2026-07-29-unity-sail-wind-visuals.md`
- Commit in Windows Unity repo: deployed scripts, tests, FBX, generated `.meta`
  files, and prefab only if intentionally changed.

**Interfaces:**
- Consumes: one simulator stack, the Regatta player, and the approved design
  acceptance list.
- Produces: reproducible test/build evidence and the production Unity commit.

- [ ] **Step 1: Run repository checks**

```bash
uv run pytest -q
uv run ruff check .
git diff --check
```

Expected: all Python tests pass, Ruff reports no errors, and the diff check is
empty.

- [ ] **Step 2: Run Unity EditMode verification**

With the editor closed, run the exact command in `docs/unity-scenario.md` and
inspect `Logs/editmode.xml`.

Expected: root test run `result="Passed"` and `failed="0"`.

- [ ] **Step 3: Build the Windows player**

Run `BuildRegatta.Build` using the documented Unity batch command.

Expected: log contains `[BuildRegatta] Succeeded`, `0 errors`, and the process
exits zero.

- [ ] **Step 4: Run and inspect the real scene**

Start exactly one stack:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

Launch `Builds/Regatta/Regatta.exe`, capture the close-hauled state and one tack,
and inspect the captures. Verify both sails fill on the same leeward side,
flatten/flutter through the tack, and refill opposite; the jib responds faster;
the wake, rudder, water, and boat pose remain stable.

- [ ] **Step 5: Record evidence**

Create the verification note with:

- Blender and Unity versions;
- exact shape-key names and calibration values;
- EditMode count/result;
- player build result;
- observed close-hauled, tack, luff, downwind, and reset behaviour;
- any acceptance item not observable in the automated run.

Update `docs/unity-scenario.md` with the two-sail behaviour and one-command asset
regeneration recipe.

- [ ] **Step 6: Review and spec-gate**

Review both repository diffs for unrelated changes, silent fallback, broken
manual override, missing deployed copies, or a changed FBX GUID. Compare every
acceptance item in the design to fresh evidence.

- [ ] **Step 7: Commit and publish**

Commit the source documentation:

```bash
git add docs/unity-scenario.md \
  docs/verification/2026-07-29-unity-sail-wind-visuals.md
git commit -m "docs(unity): make sail visual acceptance reproducible"
```

Commit the Windows Unity worktree with a conventional commit, push both
`autoship/sail-visuals` branches, and open ready PRs against
`feat/multiplatform-harness` and `feature/regatta-scenario`. Do not auto-merge:
the final gate is visual and the work spans two repositories.
