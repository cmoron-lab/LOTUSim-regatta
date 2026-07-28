# Unity Wake Trail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sparse airborne particle discs with one continuous,
water-bound wake ribbon scaled to the Focus V2's measured speed.

**Architecture:** Keep the serialized `WakeEmitter` component and replace its
runtime `ParticleSystem` children with one world-space `TrailRenderer`. Keep
speed-to-width arithmetic in the existing pure `WakeMath` assembly, generate a
repeatable two-band foam texture at runtime, and deploy the reviewed C# sources
from `LOTUSim-regatta/unity/` into the linked Windows Unity worktree.

**Tech Stack:** Unity 2022.3.62f2, C#, HDRP 14.0.12, `TrailRenderer`, NUnit
EditMode tests, LOTUSim ROS pose rendering.

## Global Constraints

- Source repository:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta`.
- Unity worktree:
  `/mnt/c/Users/cyril/lotusim-unity`, branch `feat/regatta-particles`.
- `LOTUSim-regatta/unity/` is the source of truth for handwritten C#.
- Do not checkout, reset, rebase, clean, or move either dirty worktree.
- Stage only the exact files listed in each task.
- Preserve deleted `Assets/AddressableAssetsData/link.xml*`, scene edits,
  `ManualHelm`, camera, HUD, build, XR, and project-setting changes.
- Reuse `Assets/Resources/RegattaSpray.mat`; add no package, shader graph,
  material, prefab, or VFX Graph.
- Keep the `WakeEmitter` class and its existing `.meta` GUID so the prefab
  reference remains valid.
- Exact defaults: `seaLevel=0`, `surfaceOffset=0.005`,
  `refSpeed=0.5`, `minSpeed=0.03`, `maxStep=0.25`,
  `minVertexDistance=0.03`, `wakeWidth=0.30`, `lifetime=6`,
  `smoothing=0.15`.
- The trail must have no particle velocity and no boat-relative rotation.
- Unity batchmode proves compilation and arithmetic; the Windows editor visual
  pass is the acceptance gate.

## File Structure

| File | Responsibility |
|---|---|
| `unity/WakeMath/WakeMath.cs` | pure speed normalisation and trail-width mapping |
| `unity/WakeMath/WakeMath.asmdef` | exposes the pure helper to Unity EditMode tests |
| `unity/WakeMath/WakeMathTests.cs` | source-of-truth NUnit tests copied into Unity |
| `unity/WakeEmitter.cs` | creates, positions, textures, and updates the trail |
| `docs/unity-scenario.md` | operator-facing description and Windows deployment rule |
| `Assets/Scripts/Regatta/WakeMath/WakeMath.cs` | deployed Unity helper |
| `Assets/Tests/Editor/WakeMathTests.cs` | executable Unity copy of the tests |
| `Assets/Scripts/Regatta/WakeEmitter.cs` | deployed Unity component |
| `Assets/models/focus_v2/focus_v2.prefab` | serialized wake calibration |

---

### Task 1: Scale wake width from measured boat speed

**Files:**

- Modify:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta/unity/WakeMath/WakeMath.cs`
- Add:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta/unity/WakeMath/WakeMath.asmdef`
  to the source-repository commit (the file already exists locally but is
  untracked)
- Create:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta/unity/WakeMath/WakeMathTests.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeMath/WakeMath.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Tests/Editor/WakeMathTests.cs`

**Interfaces:**

- Produces:
  `WakeMath.SpeedFactor(float speed, float refSpeed) -> float` in `[0,1]`.
- Produces:
  `WakeMath.WakeWidth(float speed, float refSpeed, float maxWidth) -> float`
  in `[0,maxWidth]`.
- `refSpeed <= 0` or `maxWidth <= 0` returns `0`; no division by zero and no
  negative geometry.

- [ ] **Step 1: Replace the source-of-truth tests with the trail contract**

Create `unity/WakeMath/WakeMathTests.cs`:

```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
using NUnit.Framework;

public class WakeMathTests
{
    const float RefSpeed = 0.5f;
    const float MaxWidth = 0.3f;
    const float Eps = 1e-4f;

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.5f)]
    [TestCase(0.5f, 1f)]
    [TestCase(5f, 1f)]
    public void SpeedFactorIsClamped(float speed, float expected)
    {
        Assert.AreEqual(expected, WakeMath.SpeedFactor(speed, RefSpeed), Eps);
    }

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.15f)]
    [TestCase(0.5f, 0.3f)]
    [TestCase(5f, 0.3f)]
    public void WakeWidthTracksMeasuredSpeed(float speed, float expected)
    {
        Assert.AreEqual(expected,
                        WakeMath.WakeWidth(speed, RefSpeed, MaxWidth), Eps);
    }

    [Test]
    public void InvalidCalibrationDisablesWidth()
    {
        Assert.AreEqual(0f, WakeMath.SpeedFactor(1f, 0f), Eps);
        Assert.AreEqual(0f, WakeMath.WakeWidth(1f, RefSpeed, 0f), Eps);
    }
}
```

Copy it over the tracked Unity test:

```bash
cp unity/WakeMath/WakeMathTests.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Tests/Editor/WakeMathTests.cs
```

- [ ] **Step 2: Run the focused EditMode test and prove it fails**

First verify that no Windows editor process owns the project. Do not kill it:

```bash
tasklist.exe /FI "IMAGENAME eq Unity.exe"
```

If Unity is open, ask Cyril to close it before batchmode. Then run:

```bash
UNITY_EXE='/mnt/c/Program Files/Unity/Hub/Editor/2022.3.62f2/Editor/Unity.exe'
UNITY_PROJECT='C:\Users\cyril\lotusim-unity'
"$UNITY_EXE" -batchmode -quit \
  -projectPath "$UNITY_PROJECT" \
  -runTests -testPlatform EditMode -testFilter WakeMathTests \
  -testResults 'C:\Users\cyril\lotusim-unity\Logs\wake-tests.xml' \
  -logFile 'C:\Users\cyril\lotusim-unity\Logs\wake-tests.log'
```

Expected: non-zero exit and `CS0117` or an NUnit compile failure saying
`WakeMath` has no `WakeWidth`.

- [ ] **Step 3: Replace particle-rate arithmetic with width arithmetic**

Replace `unity/WakeMath/WakeMath.cs` with:

```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Pure speed-to-width mapping for the Unity wake trail.
using UnityEngine;

public static class WakeMath
{
    public static float SpeedFactor(float speed, float refSpeed)
    {
        if (refSpeed <= 0f) return 0f;
        return Mathf.Clamp01(speed / refSpeed);
    }

    public static float WakeWidth(float speed, float refSpeed, float maxWidth)
    {
        if (maxWidth <= 0f) return 0f;
        return maxWidth * SpeedFactor(speed, refSpeed);
    }
}
```

Deploy only the helper:

```bash
cp unity/WakeMath/WakeMath.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeMath/WakeMath.cs
```

- [ ] **Step 4: Run the focused test and prove it passes**

Repeat the Task 1 Step 2 Unity command.

Expected: exit `0`; every `WakeMathTests` case passes and the report has zero
failures. Confirm the log has no C# error:

```bash
rg -n 'error CS|test-run failed|FAIL' \
  /mnt/c/Users/cyril/lotusim-unity/Logs/wake-tests.log
```

Expected: no match.

- [ ] **Step 5: Commit the source and deployed copies separately**

In `LOTUSim-regatta`:

```bash
git add -- \
  unity/WakeMath/WakeMath.cs \
  unity/WakeMath/WakeMath.asmdef \
  unity/WakeMath/WakeMathTests.cs
git diff --cached --name-only
git commit -m "feat(wake): scale the trail from measured boat speed"
```

Expected staged names: exactly the three paths above.

In the Windows Unity worktree:

```bash
git -C /mnt/c/Users/cyril/lotusim-unity add -- \
  Assets/Scripts/Regatta/WakeMath/WakeMath.cs \
  Assets/Tests/Editor/WakeMathTests.cs
git -C /mnt/c/Users/cyril/lotusim-unity diff --cached --name-only
git -C /mnt/c/Users/cyril/lotusim-unity commit \
  -m "feat(wake): scale the trail from measured boat speed"
```

Expected staged names: exactly the two paths above.

---

### Task 2: Replace the three particle clouds with one water-bound trail

**Files:**

- Modify:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta/unity/WakeEmitter.cs`
- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeEmitter.cs`

**Interfaces:**

- Consumes:
  `WakeMath.WakeWidth(float speed, float refSpeed, float maxWidth)`.
- Consumes:
  `Resources.Load<Material>("RegattaSpray")`.
- Consumes:
  child transform named `Rudder`.
- Produces:
  one runtime child named `WakeTrail`; no `ParticleSystem`.
- Serialized fields are exactly:
  `seaLevel`, `surfaceOffset`, `refSpeed`, `minSpeed`, `maxStep`,
  `minVertexDistance`, `wakeWidth`, `lifetime`, `smoothing`.

- [ ] **Step 1: Replace the component implementation**

Replace `unity/WakeEmitter.cs` with:

```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Continuous water-bound wake driven by the boat's own horizontal motion.
using UnityEngine;

public class WakeEmitter : MonoBehaviour
{
    public float seaLevel = 0f;
    public float surfaceOffset = 0.005f;
    public float refSpeed = 0.5f;
    public float minSpeed = 0.03f;
    public float maxStep = 0.25f;
    public float minVertexDistance = 0.03f;
    public float wakeWidth = 0.30f;
    public float lifetime = 6f;
    public float smoothing = 0.15f;

    const string MaterialName = "RegattaSpray";
    const string FoamTextureProperty = "Texture2D_23DD87FD";
    const int FoamTextureWidth = 128;
    const int FoamTextureHeight = 64;

    static readonly Quaternion FlatRotation =
        Quaternion.LookRotation(Vector3.up, Vector3.forward);

    TrailRenderer _trail;
    Transform _rudder;
    Material _mat;
    Texture2D _foam;
    Vector3 _lastPos;
    float _speed;

    void Start()
    {
        if (refSpeed <= 0f || minSpeed < 0f || maxStep <= 0f ||
            minVertexDistance <= 0f || wakeWidth <= 0f || lifetime <= 0f)
        {
            Debug.LogError("WakeEmitter: invalid calibration — disabling.");
            enabled = false;
            return;
        }

        var src = Resources.Load<Material>(MaterialName);
        if (src == null)
        {
            Debug.LogError($"WakeEmitter: material '{MaterialName}' not found — disabling.");
            enabled = false;
            return;
        }

        _rudder = FindPart("Rudder");
        if (_rudder == null)
        {
            Debug.LogError("WakeEmitter: 'Rudder' not found — disabling.");
            enabled = false;
            return;
        }

        _mat = new Material(src) { name = MaterialName + " (runtime)" };
        _foam = BuildFoamTexture(FoamTextureWidth, FoamTextureHeight);
        if (!_mat.HasProperty(FoamTextureProperty))
        {
            Debug.LogError($"WakeEmitter: material property '{FoamTextureProperty}' " +
                           "not found — disabling.");
            enabled = false;
            return;
        }
        _mat.SetTexture(FoamTextureProperty, _foam);

        _trail = MakeTrail();
        _lastPos = transform.position;
        PlaceTrail();
        _trail.Clear();
    }

    void Update()
    {
        Vector3 delta = transform.position - _lastPos;
        _lastPos = transform.position;
        delta.y = 0f;
        PlaceTrail();

        if (delta.magnitude > maxStep)
        {
            _speed = 0f;
            _trail.emitting = false;
            _trail.Clear();
            return;
        }

        float instant = Time.deltaTime > 0f
            ? delta.magnitude / Time.deltaTime
            : 0f;
        float blend = smoothing > 0f
            ? Mathf.Clamp01(Time.deltaTime / smoothing)
            : 1f;
        _speed = Mathf.Lerp(_speed, instant, blend);

        _trail.widthMultiplier = WakeMath.WakeWidth(_speed, refSpeed, wakeWidth);
        _trail.emitting = _speed >= minSpeed && _trail.widthMultiplier > 0f;
    }

    TrailRenderer MakeTrail()
    {
        var go = new GameObject("WakeTrail");
        go.transform.SetParent(transform, worldPositionStays: false);
        var trail = go.AddComponent<TrailRenderer>();
        trail.material = _mat;
        trail.alignment = LineAlignment.TransformZ;
        trail.textureMode = LineTextureMode.Tile;
        trail.generateLightingData = true;
        trail.receiveShadows = false;
        trail.time = lifetime;
        trail.minVertexDistance = minVertexDistance;
        trail.widthMultiplier = 0f;
        trail.widthCurve = new AnimationCurve(
            new Keyframe(0f, 1f),
            new Keyframe(0.75f, 0.65f),
            new Keyframe(1f, 0.2f));
        trail.numCornerVertices = 2;
        trail.numCapVertices = 2;
        trail.emitting = false;

        var gradient = new Gradient();
        gradient.SetKeys(
            new[] {
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 1f)
            },
            new[] {
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.55f, 0.15f),
                new GradientAlphaKey(0.8f, 1f)
            });
        trail.colorGradient = gradient;
        return trail;
    }

    void PlaceTrail()
    {
        Vector3 p = _rudder.position;
        p.y = seaLevel + surfaceOffset;
        _trail.transform.SetPositionAndRotation(p, FlatRotation);
    }

    static Texture2D BuildFoamTexture(int width, int height)
    {
        var tex = new Texture2D(width, height, TextureFormat.RGBA32, mipChain: true);
        for (int y = 0; y < height; y++)
            for (int x = 0; x < width; x++)
            {
                float u = (x + 0.5f) / width;
                float v = (y + 0.5f) / height;
                float left = Band(v, 0.22f, 0.16f);
                float right = Band(v, 0.78f, 0.16f);
                float breakup = Mathf.Clamp01(
                    0.55f +
                    0.25f * Mathf.Sin(2f * Mathf.PI * (3f * u + v)) +
                    0.20f * Mathf.Sin(2f * Mathf.PI * (7f * u - 2f * v)));
                float edges = Mathf.Max(left, right) *
                    Mathf.SmoothStep(0.15f, 0.85f, breakup);
                float centre = 0.10f * Band(v, 0.5f, 0.30f) *
                    (0.5f + 0.5f * Mathf.Sin(2f * Mathf.PI * 5f * u));
                float a = Mathf.Clamp01(edges + centre);
                a = a * a * (3f - 2f * a);
                tex.SetPixel(x, y, new Color(a, a, a, a));
            }
        tex.Apply(updateMipmaps: true, makeNoLongerReadable: false);
        tex.wrapMode = TextureWrapMode.Repeat;
        tex.filterMode = FilterMode.Bilinear;
        return tex;
    }

    static float Band(float value, float centre, float halfWidth)
    {
        return Mathf.Clamp01(1f - Mathf.Abs(value - centre) / halfWidth);
    }

    void OnDestroy()
    {
        if (_mat != null) Destroy(_mat);
        if (_foam != null) Destroy(_foam);
    }

    Transform FindPart(string name)
    {
        foreach (var t in GetComponentsInChildren<Transform>(true))
            if (t.name == name) return t;
        return null;
    }
}
```

- [ ] **Step 2: Deploy only the component source**

```bash
cp unity/WakeEmitter.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeEmitter.cs
cmp -s unity/WakeEmitter.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeEmitter.cs
```

Expected: `cmp` exits `0`.

- [ ] **Step 3: Compile and run the full EditMode suite**

Run the Task 1 Step 2 Unity command without `-testFilter WakeMathTests`.

Expected: exit `0`, zero failed tests, and no `error CS` in
`Logs/wake-tests.log`.

- [ ] **Step 4: Inspect the generated component contract**

```bash
rg -n 'ParticleSystem|wakeRate|bowRate|rudderRate|maxRudderDeg|particleSize' \
  unity/WakeEmitter.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeEmitter.cs
rg -n 'TrailRenderer|LineAlignment.TransformZ|TextureWrapMode.Repeat|maxStep' \
  unity/WakeEmitter.cs
```

Expected: the first command has no matches; the second finds the trail,
horizontal alignment, repeating texture, and discontinuity guard.

- [ ] **Step 5: Commit the source and deployed copies separately**

In `LOTUSim-regatta`:

```bash
git add -- unity/WakeEmitter.cs
git diff --cached --name-only
git commit -m "feat(wake): keep the wake continuous and water-bound"
```

Expected staged name: only `unity/WakeEmitter.cs`.

In the Windows Unity worktree:

```bash
git -C /mnt/c/Users/cyril/lotusim-unity add -- \
  Assets/Scripts/Regatta/WakeEmitter.cs
git -C /mnt/c/Users/cyril/lotusim-unity diff --cached --name-only
git -C /mnt/c/Users/cyril/lotusim-unity commit \
  -m "feat(wake): keep the wake continuous and water-bound"
```

Expected staged name: only `Assets/Scripts/Regatta/WakeEmitter.cs`.

---

### Task 3: Serialize, document, and visually accept the wake

**Files:**

- Modify:
  `/mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/focus_v2.prefab`
- Modify:
  `/home/cyril/src/lotusim-lab/LOTUSim-regatta/docs/unity-scenario.md`

**Interfaces:**

- Consumes the nine serialized fields defined by Task 2.
- Produces a prefab that loads the approved defaults rather than the old
  `3 m/s` particle calibration.
- Produces the operator-facing statement that the wake is one continuous,
  water-bound trail.

- [ ] **Step 1: Replace only the serialized `WakeEmitter` calibration**

In `Assets/models/focus_v2/focus_v2.prefab`, keep the existing component and
script GUID, and replace:

```yaml
  seaLevel: 0
  refSpeed: 3
  wakeRate: 60
  bowRate: 40
  rudderRate: 25
  maxRudderDeg: 35
  particleSize: 0.12
  lifetime: 4
  smoothing: 0.15
```

with:

```yaml
  seaLevel: 0
  surfaceOffset: 0.005
  refSpeed: 0.5
  minSpeed: 0.03
  maxStep: 0.25
  minVertexDistance: 0.03
  wakeWidth: 0.3
  lifetime: 6
  smoothing: 0.15
```

Do not open or reserialize the scene.

- [ ] **Step 2: Update the operator documentation**

Replace the two wake lines in `docs/unity-scenario.md` with:

```markdown
- `WakeEmitter` + `WakeMath/` — one continuous world-space wake trail,
  distance-sampled from the rudder anchor and clamped to the visual water
  level. Width reaches its configured maximum around the measured
  `0.5 m/s`; pose jumps clear the trail instead of drawing across the scene.
```

- [ ] **Step 3: Verify source deployment and serialized defaults**

```bash
cmp -s unity/WakeEmitter.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeEmitter.cs
cmp -s unity/WakeMath/WakeMath.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/WakeMath/WakeMath.cs
cmp -s unity/WakeMath/WakeMathTests.cs \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Tests/Editor/WakeMathTests.cs
rg -n 'surfaceOffset: 0.005|refSpeed: 0.5|minVertexDistance: 0.03|lifetime: 6' \
  /mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/focus_v2.prefab
git diff --check -- docs/unity-scenario.md
git -C /mnt/c/Users/cyril/lotusim-unity diff --check -- \
  Assets/models/focus_v2/focus_v2.prefab
```

Expected: all `cmp` commands exit `0`, all four prefab values match, and both
diff checks are clean.

- [ ] **Step 4: Run the Unity suite once more**

Run the full EditMode command from Task 2 Step 3.

Expected: exit `0`, zero failed tests, and zero C# errors.

- [ ] **Step 5: Run the live visual acceptance pass**

With the Windows Unity editor open on the Regatta scene, start the interactive
stack from WSL:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

Press Play when the terminal prints `[*] waiting for Unity ...`. Check:

1. no circular cards or isolated discs;
2. one continuous trail on straight legs and through turns;
3. no trail geometry rises with heel;
4. the wake remains dense at the normal `0.28-0.52 m/s` boat speed;
5. the wake fades naturally after emission stops;
6. reconnecting or resetting does not draw a long segment.

Tune width, lifetime, offset, or density through the nine serialized prefab
values. If the ribbon is wider at the stern than at its oldest end, reverse
the three `widthCurve` values in `WakeEmitter.MakeTrail`; if the foam bands run
across the ribbon, swap `u` and `v` only in the `left`, `right`, and `centre`
band calculations. Redeploy `WakeEmitter.cs`, rerun the suite, and repeat the
six checks. Do not add another renderer or particle system.

- [ ] **Step 6: Commit only the calibrated prefab**

In the Windows Unity worktree:

```bash
git -C /mnt/c/Users/cyril/lotusim-unity add -- \
  Assets/models/focus_v2/focus_v2.prefab
git -C /mnt/c/Users/cyril/lotusim-unity diff --cached --name-only
git -C /mnt/c/Users/cyril/lotusim-unity commit \
  -m "fix(wake): calibrate the ribbon for the Focus V2"
```

Expected staged name: only the prefab.

Do not stage `docs/unity-scenario.md`: it already contains adjacent,
pre-existing manual-helm and Windows workflow edits. Leave the targeted wake
description in that working-tree change for its owner to commit with the rest
of that document.

- [ ] **Step 7: Final preservation audit**

```bash
git status --short --branch --untracked-files=all
git -C /mnt/c/Users/cyril/lotusim-unity \
  status --short --branch --untracked-files=all
git log --oneline -4
git -C /mnt/c/Users/cyril/lotusim-unity log --oneline -4
```

Expected: the pre-existing unrelated changes remain present and unstaged,
including `docs/unity-scenario.md`. There is no merge commit, no reset, and no
push.
