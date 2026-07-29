# Unity Native Water Foam Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove or reject HDRP 15's native `WaterFoamGenerator` as a dense,
wave-integrated V wake for the Focus V2 without modifying the Unity 2022
project.

**Architecture:** Install Unity 2023.1 beside the current editor, copy the
Windows Unity worktree into a disposable non-Git project, and migrate only that
copy to HDRP 15. Configure two native rectangular foam generators in the Unity
editor and accept the spike only after batch tests, a Windows build, and a live
ROS visual run.

**Tech Stack:** Unity `2023.1.20f1`, HDRP/Core/Shader Graph/URP `15.0.7`,
Windows Unity Hub CLI, Unity Test Framework, ROS 2 LOTUSim stack.

## Global Constraints

- The source project remains `C:\Users\cyril\lotusim-unity`.
- The spike project is `C:\Users\cyril\lotusim-unity-2023.1-spike`.
- Install Unity `2023.1.20f1` alongside Unity `2022.3.62f2`; never replace it.
- Exclude `.git`: the source project is a Git worktree whose `.git` file points
  into `/home/cyril/src/lotusim-lab/LOTUSim-Unity-modules`.
- Exclude `Library`, `Temp`, `Logs`, `Obj`, `obj`, `.vs`, `Build`, and `Builds`
  from the copy.
- Preserve every unrelated local change in both existing worktrees.
- Keep unrelated Unity packages at their current versions unless package
  resolution reports an actual incompatibility.
- Use exactly one ROS/simulation stack; never add a second pose publisher.
- Warn Cyril immediately before opening or focusing the Windows Unity editor.
- The first native experiment adds no runtime script, shader, texture,
  ParticleSystem, ordinary decal, or package.
- Do not implement the pooled-generator fallback unless the attached native
  baseline has first been visually rejected.
- Visual acceptance is required; compilation alone cannot accept the spike.

## File Map

Files changed only in the disposable Windows spike:

- `Packages/manifest.json` — direct render-pipeline versions.
- `Packages/packages-lock.json` — regenerated dependency lock.
- `ProjectSettings/ProjectVersion.txt` — updated editor version.
- `Assets/Settings/HDRP High Fidelity.asset` — native local-foam support.
- `Assets/Scenes/Regatta/Regatta.unity` — foam simulation area and persistence.
- `Assets/models/focus_v2/focus_v2.prefab` — rejected wake disabled and two
  native generators attached.

Evidence committed in `LOTUSim-regatta` after the experiment:

- `docs/verification/2026-07-29-unity-native-water-foam-spike.md` — commands,
  versions, results, settings, and decision.
- `docs/media/unity-native-water-foam-spike.png` — representative capture, only
  if the wake is visible.

The conditional pooled fallback is deliberately outside this plan. A failed
baseline still completes this spike and supplies the evidence required to plan
that code without guessing.

---

### Task 1: Install the Exact Unity Editor

**Files:**

- Read: `C:\Program Files\Unity\Hub\Editor\`
- Create: `C:\Program Files\Unity\Hub\Editor\2023.1.20f1\`

**Interfaces:**

- Consumes: installed Windows Unity Hub and the existing Unity license.
- Produces: `C:\Program Files\Unity\Hub\Editor\2023.1.20f1\Editor\Unity.exe`.

- [ ] **Step 1: Verify the source editor is closed and the target is absent**

Run:

```bash
powershell.exe -NoProfile -Command \
  "Get-Process Unity -ErrorAction SilentlyContinue | Select-Object Id,MainWindowTitle"
test ! -e '/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe'
```

Expected: no Unity process with the source project open, and `test` exits `0`.
If the editor is open, stop and ask Cyril to close it. If the target already
exists, skip installation and verify its version in Step 3.

- [ ] **Step 2: Install the archived editor through the official Hub CLI**

Run:

```bash
'/mnt/c/Program Files/Unity Hub/Unity Hub.exe' -- --headless install \
  --version 2023.1.20f1 \
  --changeset 35a524b12060
```

Expected: exit `0` and the target `Unity.exe` exists. No optional platform
module is required to build a Windows player from the Windows editor.

- [ ] **Step 3: Verify the installed editor**

Run:

```bash
test -x '/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe'
'/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe' \
  -batchmode -quit -version
```

Expected: output contains `2023.1.20f1`.

---

### Task 2: Create the Isolated Windows Project

**Files:**

- Read: `C:\Users\cyril\lotusim-unity\`
- Create: `C:\Users\cyril\lotusim-unity-2023.1-spike\`

**Interfaces:**

- Consumes: all current project-controlled and uncommitted source-project
  content.
- Produces: an independent, non-Git Unity project without generated caches.

- [ ] **Step 1: Assert the exact destination does not exist**

Run:

```bash
test ! -e /mnt/c/Users/cyril/lotusim-unity-2023.1-spike
```

Expected: exit `0`. If it exists, inspect it and stop; never overwrite or
recursively delete it automatically.

- [ ] **Step 2: Record the source worktree state**

Run:

```bash
git -C /mnt/c/Users/cyril/lotusim-unity status --short
git -C /home/cyril/src/lotusim-lab/LOTUSim-regatta status --short
```

Expected: the known unrelated local changes remain visible. Keep this output as
the before-state for Step 5.

- [ ] **Step 3: Copy only durable project content**

Run:

```bash
mkdir -p /mnt/c/Users/cyril/lotusim-unity-2023.1-spike
rsync -a --info=progress2 \
  --exclude='.git' \
  --exclude='Library/' \
  --exclude='Temp/' \
  --exclude='Logs/' \
  --exclude='Obj/' \
  --exclude='obj/' \
  --exclude='.vs/' \
  --exclude='Build/' \
  --exclude='Builds/' \
  /mnt/c/Users/cyril/lotusim-unity/ \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/
```

Expected: about 800 MB copied rather than the source project's roughly 5.9 GB.

- [ ] **Step 4: Verify isolation and representative content**

Run:

```bash
test ! -e /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/.git
test -f /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/Scenes/Regatta/Regatta.unity
test -f /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/models/focus_v2/focus_v2.prefab
sha256sum \
  /mnt/c/Users/cyril/lotusim-unity/Assets/Scenes/Regatta/Regatta.unity \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/Scenes/Regatta/Regatta.unity \
  /mnt/c/Users/cyril/lotusim-unity/Assets/models/focus_v2/focus_v2.prefab \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/models/focus_v2/focus_v2.prefab
```

Expected: no `.git`, both assets exist, and each source/spike checksum pair
matches.

- [ ] **Step 5: Prove the copy did not mutate either existing worktree**

Run the two `git status --short` commands from Step 2 again.

Expected: byte-for-byte the same status entries as the before-state.

---

### Task 3: Migrate the Disposable Copy to HDRP 15

**Files:**

- Modify: `C:\Users\cyril\lotusim-unity-2023.1-spike\Packages\manifest.json`
- Modify automatically:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Packages\packages-lock.json`
- Modify automatically:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\ProjectSettings\ProjectVersion.txt`
- Create:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\migration.log`

**Interfaces:**

- Consumes: the isolated Unity 2022 project and Unity 2023.1 editor.
- Produces: a compiling Unity 2023.1 project with all four coupled render
  packages at `15.0.7`.

- [ ] **Step 1: Change only the four direct render dependencies**

Apply this exact diff to the spike's `Packages/manifest.json`:

```diff
-    "com.unity.render-pipelines.core": "14.0.12",
-    "com.unity.render-pipelines.high-definition": "14.0.12",
-    "com.unity.render-pipelines.universal": "14.0.12",
+    "com.unity.render-pipelines.core": "15.0.7",
+    "com.unity.render-pipelines.high-definition": "15.0.7",
+    "com.unity.render-pipelines.universal": "15.0.7",
@@
-    "com.unity.shadergraph": "14.0.12",
+    "com.unity.shadergraph": "15.0.7",
```

Do not update any unrelated dependency proactively.

- [ ] **Step 2: Run the first migration import without opening the GUI**

Run:

```bash
mkdir -p /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Logs
'/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe' \
  -batchmode -quit -accept-apiupdate \
  -projectPath 'C:\Users\cyril\lotusim-unity-2023.1-spike' \
  -logFile 'C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\migration.log'
```

Expected: exit `0`. The first import can take several minutes because `Library`
was intentionally omitted.

- [ ] **Step 3: Reject compiler or package-resolution failures**

Run:

```bash
rg -n \
  'error CS|Compilation failed|Scripts have compiler errors|Package resolution failed|Failed to resolve packages' \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Logs/migration.log
```

Expected: no matches. If failures require broad ROS, XR, Ultraleap,
Addressables, or scene changes, stop and record a migration failure rather than
repairing around the gate.

- [ ] **Step 4: Verify exact resolved versions**

Run:

```bash
rg -n \
  'm_EditorVersion: 2023.1.20f1|com.unity.render-pipelines.(core|high-definition|universal)|com.unity.shadergraph' \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/ProjectSettings/ProjectVersion.txt \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Packages/manifest.json \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Packages/packages-lock.json
```

Expected: editor `2023.1.20f1` and each coupled render package `15.0.7`.

- [ ] **Step 5: Run the complete EditMode suite**

Run:

```bash
'/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe' \
  -batchmode -quit \
  -projectPath 'C:\Users\cyril\lotusim-unity-2023.1-spike' \
  -runTests -testPlatform editmode \
  -testResults 'C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\editmode-before-foam.xml' \
  -logFile 'C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\editmode-before-foam.log'
```

Expected: exit `0`, no failed test case, and the existing full suite passes.

- [ ] **Step 6: Build the unchanged Regatta player**

Run:

```bash
'/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe' \
  -batchmode -quit \
  -projectPath 'C:\Users\cyril\lotusim-unity-2023.1-spike' \
  -executeMethod BuildRegatta.Build \
  -logFile 'C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\build-before-foam.log'
```

Expected: exit `0`, log contains `[BuildRegatta] Succeeded`, and
`Builds/Regatta/Regatta.exe` exists.

---

### Task 4: Configure the Native Foam Baseline in Unity

**Files:**

- Modify:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Assets\Settings\HDRP High Fidelity.asset`
- Modify:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Assets\Scenes\Regatta\Regatta.unity`
- Modify:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Assets\models\focus_v2\focus_v2.prefab`

**Interfaces:**

- Consumes: a cleanly migrated HDRP 15 project.
- Produces: two attached native generators and no active legacy wake renderer.

- [ ] **Step 1: Warn Cyril and open only the spike project**

Send a commentary warning before taking Windows focus. Then launch:

```bash
powershell.exe -NoProfile -Command \
  "Start-Process -FilePath 'C:\Program Files\Unity\Hub\Editor\2023.1.20f1\Editor\Unity.exe' -ArgumentList '-projectPath','C:\Users\cyril\lotusim-unity-2023.1-spike','-logFile','C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\editor.log'"
```

Expected: the title bar identifies `lotusim-unity-2023.1-spike` and Unity
2023.1.20f1. Never proceed in a window showing `lotusim-unity`.

- [ ] **Step 2: Enable local water foam in the active HDRP asset**

In `Project Settings > Quality > HDRP > Rendering > Water` for **High
Fidelity**:

- keep Water enabled;
- enable Foam;
- keep the foam atlas at `512`, because rectangle generators do not consume
  texture-atlas detail.

Save the project.

- [ ] **Step 3: Calibrate the Ocean's local foam buffer**

Open `Assets/Scenes/Regatta/Regatta.unity`, select `Ocean`, and set:

- Foam Enable: on;
- Foam Resolution: `High 1024`;
- Foam Area Size: `(32, 32)` metres;
- Foam Area Offset: `(0, 7.5)` metres;
- Foam Persistence Multiplier: `0.9`;
- Foam Smoothness: `0.3`;
- Foam Texture Tiling: `2`;
- Simulation Foam: keep enabled;
- Simulation Foam Amount: keep the migrated value unless it hides the local
  wake.

The `32 m` region covers the `z=0` to `z=15 m` course while giving approximately
`3.1 cm` per foam texel at resolution `1024`.

- [ ] **Step 4: Disable the rejected renderer**

Open `Assets/models/focus_v2/focus_v2.prefab` in Prefab Mode. Disable the
existing `WakeEmitter` component; do not delete the component or its source.

- [ ] **Step 5: Add the left native generator**

Under the prefab root, create an empty `NativeFoamWake` at the stern, using the
`Rudder` transform only as the positional reference. Do not parent it to the
moving rudder.

Create child `FoamLeft`, add `Water Foam Generator`, and set:

- Type: `Rectangle`;
- Scale Mode: `Scale Invariant`;
- Region Size: `(0.12, 0.55)` metres;
- Surface Foam Dimmer: `0.8`;
- Deep Foam Dimmer: `0`;
- local yaw relative to the boat's aft axis: `-19.5°`.

Place the rectangle so its near end begins at the stern rather than straddling
the hull.

- [ ] **Step 6: Add the symmetric right generator**

Duplicate `FoamLeft` as `FoamRight` and change only the local yaw to `+19.5°`.
Confirm both generators share the same origin and dimensions. Save the prefab
and scene.

- [ ] **Step 7: Verify serialized configuration without relying on the open UI**

Close Unity cleanly, then run:

```bash
foam_meta=$(find \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Library/PackageCache \
  -path '*/Runtime/Water/FoamGenerator/WaterFoamGenerator.cs.meta' \
  -print -quit)
foam_guid=$(sed -n 's/^guid: //p' "$foam_meta")
test -n "$foam_guid"
test "$(rg -c "$foam_guid" \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/models/focus_v2/focus_v2.prefab)" -eq 2
rg -n \
  'supportWaterFoam: 1|foamResolution: 1024|foamAreaSize: \\{x: 32, y: 32\\}|foamPersistenceMultiplier: 0.9|m_Name: FoamLeft|m_Name: FoamRight' \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/Settings/HDRP\\ High\\ Fidelity.asset \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/Scenes/Regatta/Regatta.unity \
  /mnt/c/Users/cyril/lotusim-unity-2023.1-spike/Assets/models/focus_v2/focus_v2.prefab
```

Expected: exactly two generator components and every configured value is
serialized.

---

### Task 5: Re-run Automated Gates After Foam Configuration

**Files:**

- Create:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\editmode-native-foam.xml`
- Create:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\build-native-foam.log`
- Create:
  `C:\Users\cyril\lotusim-unity-2023.1-spike\Builds\Regatta\Regatta.exe`

**Interfaces:**

- Consumes: the serialized native-foam baseline.
- Produces: compile, test, and player-build evidence.

- [ ] **Step 1: Run the full EditMode suite**

Run the Task 3 test command with:

- results file `Logs\editmode-native-foam.xml`;
- log file `Logs\editmode-native-foam.log`.

Expected: exit `0` and no failed test case.

- [ ] **Step 2: Build the configured Windows player**

Run the Task 3 build command with log file
`Logs\build-native-foam.log`.

Expected: exit `0`, `[BuildRegatta] Succeeded`, and a fresh
`Builds/Regatta/Regatta.exe`.

- [ ] **Step 3: Confirm the source project is still untouched**

Run:

```bash
git -C /mnt/c/Users/cyril/lotusim-unity status --short
git -C /home/cyril/src/lotusim-lab/LOTUSim-regatta status --short
```

Expected: only the known source changes plus this plan commit; no migrated
package, scene, prefab, or project-setting change appears in either existing
worktree.

---

### Task 6: Run the Live Visual Acceptance Gate

**Files:**

- Read: `C:\Users\cyril\lotusim-unity-2023.1-spike\Builds\Regatta\Regatta.exe`
- Create on success:
  `docs/media/unity-native-water-foam-spike.png`

**Interfaces:**

- Consumes: one ROS simulation stack and the configured editor/player.
- Produces: a visual accept/reject decision with a representative capture.

- [ ] **Step 1: Load the LOTUSim operating instructions**

Before any LOTUSim or simulator command, invoke and follow the
`lotusim-developer` skill. Confirm that no existing regatta stack is publishing
the boat pose.

- [ ] **Step 2: Start exactly one simulation stack**

From `/home/cyril/src/lotusim-lab/LOTUSim-regatta`, run:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

Expected: the script waits for one Unity connection. If the boat later
teleports, stop and audit ROS publishers before assessing the wake.

- [ ] **Step 3: Warn Cyril, open the spike editor, and enter Play mode**

Use the Task 4 launch command. Confirm the spike project in the title bar before
focusing it or sending `Ctrl+P`. Open the Regatta scene if it is not already
open, then enter Play mode.

Expected: one Focus V2 spawns and moves normally.

- [ ] **Step 4: Evaluate the native baseline**

Observe a straight leg, a turn, and a stop. Accept only if all are true:

- dense foam begins at the stern with no cards or airborne particles;
- two arms are readable and diverge from the stern;
- rendered waves do not repeatedly cut the foam;
- the wake retains world-space history through a turn;
- heel and pitch do not detach foam from the rendered surface;
- stopping allows natural erosion;
- spawn or reconnect creates no long segment;
- the boat does not teleport.

If density alone is wrong, tune only rectangle dimensions, surface dimmer,
foam persistence, smoothness, and tiling, one value at a time. Do not create a
new wake implementation during this task.

- [ ] **Step 5: Cross-check the Windows player**

Exit Play mode and close the editor. Keep the same single stack alive and launch:

```bash
powershell.exe -NoProfile -Command \
  "Start-Process -FilePath 'C:\Users\cyril\lotusim-unity-2023.1-spike\Builds\Regatta\Regatta.exe'"
```

Expected: the player reproduces the editor result without missing shaders or
serialized fields.

- [ ] **Step 6: Capture accepted output**

With the player window unobstructed, capture its window to:

`C:\Users\cyril\lotusim-unity-2023.1-spike\Logs\unity-native-water-foam-spike.png`

Copy the capture into:

`/home/cyril/src/lotusim-lab/LOTUSim-regatta/docs/media/unity-native-water-foam-spike.png`

Inspect the copied file with the image viewer before using it as evidence.
Skip the committed capture if native foam is not visible enough to assess.

- [ ] **Step 7: Stop the player and the single simulation stack**

Close `Regatta.exe`, then terminate the held `run_regatta.sh` session cleanly.
Confirm no regatta-owned ROS, Gazebo, or xdyn process remains before concluding.

---

### Task 7: Record and Commit the Spike Decision

**Files:**

- Create:
  `docs/verification/2026-07-29-unity-native-water-foam-spike.md`
- Create conditionally:
  `docs/media/unity-native-water-foam-spike.png`

**Interfaces:**

- Consumes: exact versions, logs, test results, build result, settings, and
  visual observations from Tasks 1–6.
- Produces: the evidence needed to choose migration, a pooled native extension,
  or particle fallback.

- [ ] **Step 1: Write the verification record**

Record only observed facts:

- source and spike paths;
- editor `2023.1.20f1` and render packages `15.0.7`;
- migration warnings or incompatibilities;
- EditMode test counts before and after foam configuration;
- player build result;
- final generator and WaterSurface settings;
- editor and player observations for all eight acceptance criteria;
- accepted or rejected decision;
- if rejected, whether the blocker is migration, density, divergence, wave
  integration, turns, or player parity.

- [ ] **Step 2: Check the evidence diff**

Run:

```bash
git diff --check
git diff --stat
git status --short
```

Expected: only the verification record and an accepted representative capture
are new for this task; all earlier unrelated changes remain unstaged.

- [ ] **Step 3: Commit only the spike evidence**

For an accepted baseline:

```bash
git add \
  docs/verification/2026-07-29-unity-native-water-foam-spike.md \
  docs/media/unity-native-water-foam-spike.png
git commit -m "docs(verification): validate native HDRP wake"
```

For a rejected baseline without a useful capture:

```bash
git add docs/verification/2026-07-29-unity-native-water-foam-spike.md
git commit -m "docs(verification): bound native HDRP wake failure"
```

- [ ] **Step 4: Choose the next bounded action**

- Accepted attached generators: stop; do not write pooled runtime code.
- Foam follows waves but the arms do not diverge: write a separate
  test-driven plan for the bounded native-generator pool described in the
  approved design.
- Migration or native foam fails structurally: leave the Unity 2022 project
  untouched and reconsider particle v2 from the recorded evidence.
