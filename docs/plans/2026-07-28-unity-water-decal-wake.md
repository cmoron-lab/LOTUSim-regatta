# Unity Water-Decal Wake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rejected trail with a curved-history, V-shaped wake made
of HDRP decals projected directly onto the animated water surface.

**Architecture:** Keep the serialized `WakeEmitter` component, but replace its
`TrailRenderer` with a fixed pool of paired `DecalProjector` foam stamps. Each
stamp stores its emission frame in world space, drifts laterally at a 19.5-degree
half-angle, and fades independently; one shared HDRP decal material supplies a
procedural foam texture.

**Tech Stack:** Unity 2022.3.62f2, C#, HDRP 14.0.12 `DecalProjector`,
`HDRP/Decal`, NUnit EditMode tests, LOTUSim ROS pose rendering.

## Global Constraints

- Source repository:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta`.
- Windows Unity worktree:
  `/mnt/c/Users/cyril/lotusim-unity`, branch `feat/regatta-particles`.
- `LOTUSim-regatta/unity/` remains the handwritten source of truth.
- Do not reset, checkout, clean, rebase, or stage unrelated dirty files.
- Preserve unrelated scene, camera, HUD, manual helm, build, Addressables, XR,
  and project-setting changes.
- Keep the `WakeEmitter` class and `.meta` GUID so the Focus V2 prefab reference
  remains valid.
- The wake must never write the boat transform.
- The decal history remains in world space after emission.
- Defaults: `refSpeed=0.5`, `minSpeed=0.03`, `maxStep=0.25`,
  `emissionSpacing=0.12`, `stampWidth=0.18`, `stampLength=0.30`,
  `lifetime=5`, `wakeAngle=19.5`, `projectorDepth=1`,
  `smoothing=0.15`.
- Allocate 48 pairs (96 projectors) once; no per-emission instantiate/destroy.
- Use one shared material and each projector's `fadeFactor`; do not clone a
  material per stamp.
- Remove the rejected `RegattaWake.shader`; do not retain trail or particle
  fallback code.
- The final acceptance gate is a visual run in both the Windows editor and
  `Regatta.exe`.

## File Structure

| File | Responsibility |
|---|---|
| `unity/WakeMath/WakeMath.cs` | pure emission, divergence, and fade arithmetic |
| `unity/WakeMath/WakeMathTests.cs` | source-of-truth NUnit tests |
| `unity/WakeEmitter.cs` | projector pool, distance emission, stamp lifecycle |
| `unity/RegattaWakeDecal.mat` | referenced HDRP decal material for player builds |
| `unity/RegattaWakeDecal.mat.meta` | stable Unity GUID for the material |
| `unity/RegattaWake.shader*` | rejected assets to delete |
| `Assets/Scripts/Regatta/...` | deployed runtime and math copies |
| `Assets/Tests/Editor/WakeMathTests.cs` | deployed Unity tests |
| `Assets/Resources/RegattaWakeDecal.mat*` | build-safe material resource |
| `Assets/Resources/RegattaWake.shader*` | rejected deployed assets to delete |
| `Assets/models/focus_v2/focus_v2.prefab` | serialized decal calibration |

---

### Task 1: Specify the world-space V arithmetic

**Files:**

- Modify: `unity/WakeMath/WakeMath.cs`
- Modify: `unity/WakeMath/WakeMathTests.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeMath/WakeMath.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Tests/Editor/WakeMathTests.cs`

**Interfaces:**

- Produces:
  `WakeMath.SpeedFactor(float speed, float refSpeed) -> float`.
- Produces:
  `WakeMath.ShouldEmit(float distance, float spacing, float speed,
  float minSpeed) -> bool`.
- Produces:
  `WakeMath.LateralOffset(float age, float speed, float angleDegrees) -> float`.
- Produces:
  `WakeMath.StampPosition(Vector3 origin, Vector3 right, int side, float age,
  float speed, float angleDegrees) -> Vector3`.
- Produces:
  `WakeMath.Fade(float age, float lifetime) -> float`.
- Produces:
  `WakeMath.NextPairIndex(int current, int capacity) -> int`.

- [ ] **Step 1: Write the failing decal-math tests**

Replace `unity/WakeMath/WakeMathTests.cs` with:

```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
using NUnit.Framework;
using UnityEngine;

public class WakeMathTests
{
    const float Eps = 1e-4f;

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.5f)]
    [TestCase(0.5f, 1f)]
    [TestCase(5f, 1f)]
    public void SpeedFactorIsClamped(float speed, float expected)
    {
        Assert.AreEqual(expected, WakeMath.SpeedFactor(speed, 0.5f), Eps);
    }

    [TestCase(0.11f, 0.5f, false)]
    [TestCase(0.12f, 0.5f, true)]
    [TestCase(0.20f, 0.02f, false)]
    public void EmissionRequiresDistanceAndSpeed(
        float distance, float speed, bool expected)
    {
        Assert.AreEqual(
            expected,
            WakeMath.ShouldEmit(distance, 0.12f, speed, 0.03f));
    }

    [Test]
    public void StampPositionDivergesFromCapturedRightAxis()
    {
        Vector3 origin = new Vector3(1f, 0f, 2f);
        Vector3 right = WakeMath.StampPosition(
            origin, Vector3.right, 1, 2f, 0.5f, 45f);
        Vector3 left = WakeMath.StampPosition(
            origin, Vector3.right, -1, 2f, 0.5f, 45f);
        Assert.AreEqual(2f, right.x, Eps);
        Assert.AreEqual(0f, left.x, Eps);
        Assert.AreEqual(origin.z, right.z, Eps);
        Assert.AreEqual(origin.z, left.z, Eps);
    }

    [TestCase(0f, 1f)]
    [TestCase(2.5f, 0.5f)]
    [TestCase(5f, 0f)]
    [TestCase(8f, 0f)]
    public void FadeIsClampedByLifetime(float age, float expected)
    {
        Assert.AreEqual(expected, WakeMath.Fade(age, 5f), Eps);
    }

    [Test]
    public void InvalidCalibrationProducesNoWake()
    {
        Assert.IsFalse(WakeMath.ShouldEmit(1f, 0f, 1f, 0.03f));
        Assert.AreEqual(0f, WakeMath.LateralOffset(1f, 1f, -1f), Eps);
        Assert.AreEqual(0f, WakeMath.Fade(1f, 0f), Eps);
    }

    [TestCase(0, 48, 1)]
    [TestCase(47, 48, 0)]
    [TestCase(3, 0, 0)]
    public void PairIndexWrapsInsideFixedPool(
        int current, int capacity, int expected)
    {
        Assert.AreEqual(
            expected, WakeMath.NextPairIndex(current, capacity));
    }
}
```

Deploy the test with a targeted file copy.

- [ ] **Step 2: Run the focused test and verify red**

First check whether the Windows editor owns the project:

```bash
powershell.exe -NoProfile -Command \
  'Get-Process Unity -ErrorAction SilentlyContinue | Select-Object Id,MainWindowTitle'
```

If it is open, close only that Unity process after warning Cyril. Then run:

```bash
'/mnt/c/Program Files/Unity/Hub/Editor/2022.3.62f2/Editor/Unity.exe' \
  -batchmode -nographics \
  -projectPath 'C:\Users\cyril\lotusim-unity' \
  -runTests -testPlatform EditMode -testFilter WakeMathTests \
  -testResults 'C:\Users\cyril\lotusim-unity\Logs\wake-decal-red.xml' \
  -logFile 'C:\Users\cyril\lotusim-unity\Logs\wake-decal-red.log'
```

Expected: compilation fails because `ShouldEmit`, `StampPosition`, and `Fade`
do not exist.

- [ ] **Step 3: Implement the minimal pure arithmetic**

Replace `unity/WakeMath/WakeMath.cs` with:

```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Pure motion arithmetic for the Unity water-decal wake.
using UnityEngine;

public static class WakeMath
{
    public static float SpeedFactor(float speed, float refSpeed)
    {
        if (refSpeed <= 0f) return 0f;
        return Mathf.Clamp01(speed / refSpeed);
    }

    public static bool ShouldEmit(
        float distance, float spacing, float speed, float minSpeed)
    {
        return spacing > 0f && distance >= spacing && speed >= minSpeed;
    }

    public static float LateralOffset(
        float age, float speed, float angleDegrees)
    {
        if (age <= 0f || speed <= 0f ||
            angleDegrees < 0f || angleDegrees >= 90f)
            return 0f;
        return age * speed * Mathf.Tan(angleDegrees * Mathf.Deg2Rad);
    }

    public static Vector3 StampPosition(
        Vector3 origin, Vector3 right, int side, float age,
        float speed, float angleDegrees)
    {
        return origin + Mathf.Sign(side) * right.normalized *
            LateralOffset(age, speed, angleDegrees);
    }

    public static float Fade(float age, float lifetime)
    {
        if (lifetime <= 0f) return 0f;
        return 1f - Mathf.Clamp01(age / lifetime);
    }

    public static int NextPairIndex(int current, int capacity)
    {
        if (capacity <= 0) return 0;
        return (current + 1) % capacity;
    }
}
```

Deploy the helper to the Windows worktree.

- [ ] **Step 4: Run the focused test and verify green**

Repeat Task 1 Step 2 with result paths `wake-decal-green.xml` and
`wake-decal-green.log`.

Expected: every `WakeMathTests` case passes, zero failures, and no `error CS`
or shader error in the log.

- [ ] **Step 5: Commit the pure contract**

Commit the three source files (`WakeMath.cs`, tests, existing asmdef) in the
source repository and the two deployed copies in the Windows worktree. Stage
only those paths.

Use:

```text
feat(wake): define the world-space decal motion
```

---

### Task 2: Create the build-safe HDRP decal material

**Files:**

- Temporarily create, then delete:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Editor/CreateWakeDecalMaterial.cs`
  and its generated `.meta`
- Create: `unity/RegattaWakeDecal.mat`
- Create: `unity/RegattaWakeDecal.mat.meta`
- Create:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Resources/RegattaWakeDecal.mat`
- Create:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Resources/RegattaWakeDecal.mat.meta`
- Delete: `unity/RegattaWake.shader`
- Delete: `unity/RegattaWake.shader.meta`
- Delete:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Resources/RegattaWake.shader`
- Delete:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Resources/RegattaWake.shader.meta`

**Interfaces:**

- Produces a `Resources.Load<Material>("RegattaWakeDecal")` asset.
- The material uses `HDRP/Decal`, affects albedo only, and is validated through
  `HDMaterial.ValidateMaterial`.

- [ ] **Step 1: Add the temporary deterministic material generator**

Create the editor-only script:

```csharp
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

public static class CreateWakeDecalMaterial
{
    const string Output =
        "Assets/Resources/RegattaWakeDecal.mat";

    public static void Create()
    {
        Shader shader = Shader.Find("HDRP/Decal");
        if (shader == null)
            throw new System.InvalidOperationException(
                "HDRP/Decal shader not found");

        AssetDatabase.DeleteAsset(Output);
        var material = new Material(shader) {
            name = "RegattaWakeDecal"
        };
        material.SetColor(
            "_BaseColor", new Color(1f, 1f, 1f, 0.65f));
        material.SetTexture("_BaseColorMap", Texture2D.whiteTexture);
        material.SetFloat("_AffectAlbedo", 1f);
        material.SetFloat("_AffectNormal", 0f);
        material.SetFloat("_AffectAO", 0f);
        material.SetFloat("_AffectMetal", 0f);
        material.SetFloat("_AffectSmoothness", 0f);
        material.SetFloat("_AffectEmission", 0f);
        if (!HDMaterial.ValidateMaterial(material))
            throw new System.InvalidOperationException(
                "HDRP decal validation failed");

        AssetDatabase.CreateAsset(material, Output);
        AssetDatabase.SaveAssets();
    }
}
```

- [ ] **Step 2: Generate and inspect the material**

Run Unity batchmode with:

```text
-executeMethod CreateWakeDecalMaterial.Create
```

Expected:

- material and `.meta` exist under `Assets/Resources`;
- shader GUID is HDRP's `1d64af84bdc970c4fae0c1e06dd95b73`;
- `_MATERIAL_AFFECTS_ALBEDO` and `_COLORMAP` are valid keywords;
- normal, mask-map, and emissive influence are disabled.

- [ ] **Step 3: Promote the generated asset and remove the rejected shader**

Add exact textual copies of the generated `.mat` and `.meta` under `unity/`.
Then delete the temporary editor script and its `.meta`, and delete both source
and deployed `RegattaWake.shader` assets.

Verify:

```bash
sha256sum \
  unity/RegattaWakeDecal.mat \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Resources/RegattaWakeDecal.mat \
  unity/RegattaWakeDecal.mat.meta \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Resources/RegattaWakeDecal.mat.meta
```

Expected: matching hashes for each source/deployed pair.

Do not commit this task alone; the material has no consumer until Task 3.

---

### Task 3: Replace the trail with a fixed decal-stamp pool

**Files:**

- Modify: `unity/WakeEmitter.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeEmitter.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/focus_v2.prefab`
- Include the material additions and shader deletions from Task 2.

**Interfaces:**

- Consumes all `WakeMath` methods from Task 1.
- Consumes `Resources.Load<Material>("RegattaWakeDecal")`.
- Produces exactly 96 disabled-at-start `DecalProjector` instances.
- Each active stamp owns origin, captured right axis, captured arm direction,
  side, emission speed, age, and projector.

- [ ] **Step 1: Define the serialized decal calibration and stamp state**

Replace trail-only fields and state in `WakeEmitter` with:

```csharp
public float refSpeed = 0.5f;
public float minSpeed = 0.03f;
public float maxStep = 0.25f;
public float emissionSpacing = 0.12f;
public float stampWidth = 0.18f;
public float stampLength = 0.30f;
public float lifetime = 5f;
public float wakeAngle = 19.5f;
public float projectorDepth = 1f;
public float smoothing = 0.15f;

const int PairCapacity = 48;
const string MaterialResource = "RegattaWakeDecal";
const string FoamTextureProperty = "_BaseColorMap";
const int FoamTextureWidth = 64;
const int FoamTextureHeight = 128;

sealed class Stamp
{
    public DecalProjector projector;
    public Vector3 origin;
    public Vector3 right;
    public float speed;
    public float age;
    public int side;
    public bool active;
}
```

Validation must reject non-positive spacing, sizes, lifetime, depth, reference
speed, or maximum step, and angles outside `[0, 90)`.

- [ ] **Step 2: Create one shared material and the fixed projector pool**

Load and clone the resource material, assign the procedural texture, and call:

```csharp
if (!HDMaterial.ValidateMaterial(_mat))
{
    Debug.LogError(
        "WakeEmitter: invalid HDRP decal material — disabling.");
    enabled = false;
    return;
}
```

Create a world-root object and 96 projectors:

```csharp
_wakeRoot = new GameObject("WakeDecals");
_stamps = new Stamp[PairCapacity * 2];
for (int i = 0; i < _stamps.Length; i++)
{
    var go = new GameObject($"WakeStamp-{i:00}");
    go.transform.SetParent(_wakeRoot.transform, false);
    var projector = go.AddComponent<DecalProjector>();
    projector.material = _mat;
    projector.size =
        new Vector3(stampWidth, stampLength, projectorDepth);
    projector.drawDistance = 100f;
    projector.fadeFactor = 0f;
    projector.enabled = false;
    _stamps[i] = new Stamp { projector = projector };
}
```

The root must not be parented to the boat. `OnDestroy` destroys the root,
runtime material, and procedural texture.

- [ ] **Step 3: Emit paired world-space stamps by travelled distance**

For every accepted horizontal movement:

```csharp
_distanceSinceEmission += delta.magnitude;
if (WakeMath.ShouldEmit(
        _distanceSinceEmission, emissionSpacing, _speed, minSpeed))
{
    EmitPair(delta.normalized);
    _distanceSinceEmission = 0f;
}
```

`EmitPair` reuses one ring-buffer pair. For `side=-1` and `side=1`, capture:

```csharp
Vector3 forward = movementForward;
Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;
float tangent = Mathf.Tan(wakeAngle * Mathf.Deg2Rad);
Vector3 arm = (forward - side * right * tangent).normalized;

stamp.origin = new Vector3(
    _rudder.position.x, _water.transform.position.y, _rudder.position.z);
stamp.right = right;
stamp.speed = _speed;
stamp.age = 0f;
stamp.side = side;
stamp.active = true;
stamp.projector.transform.SetPositionAndRotation(
    stamp.origin,
    Quaternion.LookRotation(Vector3.down, arm));
stamp.projector.fadeFactor =
    WakeMath.SpeedFactor(_speed, refSpeed);
stamp.projector.enabled = true;
```

Increment and wrap the pair index after both sides are configured.

Use pair slots `_nextPair * 2` and `_nextPair * 2 + 1`, then advance with:

```csharp
_nextPair = WakeMath.NextPairIndex(_nextPair, PairCapacity);
```

- [ ] **Step 4: Update, fade, and recycle stamps**

Each frame, for every active stamp:

```csharp
stamp.age += Time.deltaTime;
float fade = WakeMath.Fade(stamp.age, lifetime);
if (fade <= 0f)
{
    stamp.active = false;
    stamp.projector.enabled = false;
    continue;
}

stamp.projector.transform.position = WakeMath.StampPosition(
    stamp.origin, stamp.right, stamp.side, stamp.age,
    stamp.speed, wakeAngle);
stamp.projector.fadeFactor =
    fade * WakeMath.SpeedFactor(stamp.speed, refSpeed);
```

On a movement step above `maxStep`, reset smoothed speed and emission distance,
disable every active projector, and do not emit.

- [ ] **Step 5: Generate one soft irregular foam-streak texture**

For `u/v` in a `64x128` RGBA texture, use:

```csharp
float x = 2f * u - 1f;
float y = 2f * v - 1f;
float ellipse = Mathf.Clamp01(1f - x * x - y * y);
float breakup = Mathf.Clamp01(
    0.72f +
    0.18f * Mathf.Sin(2f * Mathf.PI * (2f * v + u)) +
    0.10f * Mathf.Sin(2f * Mathf.PI * (5f * v - 3f * u)));
float alpha = ellipse * ellipse * breakup;
tex.SetPixel(px, py, new Color(1f, 1f, 1f, alpha));
```

Use bilinear filtering and `TextureWrapMode.Clamp`.

- [ ] **Step 6: Deploy and update only prefab wake fields**

Deploy `WakeEmitter.cs` byte-identically. In
`Assets/models/focus_v2/focus_v2.prefab`, replace only the serialized
`WakeEmitter` calibration with the exact defaults in Global Constraints.

Do not save or stage `Assets/Scenes/Regatta/Regatta.unity`.

- [ ] **Step 7: Run focused and full EditMode tests**

Run the focused `WakeMathTests`, then the entire EditMode suite. Expected:

- focused report: all decal-math cases pass;
- full report: zero failures;
- no `error CS`, shader compilation error, or missing resource error.

- [ ] **Step 8: Commit source and Windows wake assets separately**

Source commit stages only:

```text
unity/WakeEmitter.cs
unity/WakeMath/WakeMath.cs
unity/WakeMath/WakeMathTests.cs
unity/RegattaWakeDecal.mat
unity/RegattaWakeDecal.mat.meta
unity/RegattaWake.shader
unity/RegattaWake.shader.meta
```

Windows commit stages only the deployed equivalents, the exact Focus V2 prefab,
and the material/shader rename set.

Use:

```text
feat(wake): project curved foam history onto the water
```

---

### Task 4: Validate the rendered behavior and player build

**Files:**

- Modify only calibration values in:
  `Assets/models/focus_v2/focus_v2.prefab`, if the visual gate requires it.
- Do not modify or save the Regatta scene.

**Interfaces:**

- Consumes the runtime wake from Task 3.
- Produces visual evidence from editor and Windows player runs.

- [ ] **Step 1: Prove the editor behavior with the real stack**

Run:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

Open the existing Regatta scene in the Windows editor, press Play, resume only
the known `tf2_msgs/TFMessage` Error Pause, and inspect Orbit view.

Acceptance:

- straight motion produces two widening, irregular foam arms;
- a turn preserves old curved history;
- stamps remain projected on wave crests and troughs with no cuts;
- no stamp appears above the water;
- no teleportation or second transform writer.

- [ ] **Step 2: Tune only the approved calibration knobs**

If needed, adjust only spacing, stamp width/length, lifetime, angle, or material
base alpha. Do not add another renderer, particle system, shader, or quality
abstraction.

After each calibration change, copy any source-owned file back to `unity/` and
rerun the focused tests.

- [ ] **Step 3: Build and launch `Regatta.exe`**

Use the existing `LOTUSim/Build Regatta (Windows)` menu or:

```text
Unity.exe -batchmode -quit
  -projectPath C:\Users\cyril\lotusim-unity
  -executeMethod BuildRegatta.Build
```

Start the real stack, launch `Builds/Regatta/Regatta.exe`, and repeat the
straight/turn/rough-water acceptance checks. Inspect `Player.log` for missing
material, decal, or shader errors.

- [ ] **Step 4: Run final verification**

Run:

- full Unity EditMode suite;
- `uv run pytest -q` in `LOTUSim-regatta`;
- SHA-256 equality checks for each source/deployed wake-owned file;
- `git diff --check` for all wake-owned paths;
- process check confirming no leftover Unity test process, `run_regatta.sh`,
  `lotusim`, `xdyn-for-cs`, or temporary UI automation script.

- [ ] **Step 5: Commit visual calibration if it changed**

If Task 4 changed only the Windows prefab calibration, stage that one path and
commit:

```text
fix(wake): calibrate the water-projected foam
```

If no file changed, create no empty commit.
