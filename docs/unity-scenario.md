# Unity Regatta scenario — build recipe

The Regatta production scene is on Unity branch
`feature/regatta-scenario`. It provides the boat assets, Addressable entry, and
bridge integration; `main` may still open from a stray working-tree copy, but
lacks the `focus_v2` Addressable key and fails at spawn with
`InvalidKeyException`. This doc remains the recipe to rebuild the scene from
scratch if needed.

- Project: `LOTUSim-Unity-modules` (fork `cmoron-lab`), Unity `2023.1.20f1`,
  HDRP `15.0.7`.
- Branch: `feature/regatta-scenario`.

## Scene contents

Start from a duplicate of `defenseScenario` (it already has the LOTUSim bridge
wired) and strip it down:

- **World Script** → `LotusimInterface` component: set `m_namespace = "lotusim"`.
  This **must equal the gz world name** (`regatta.world`'s `<world name="lotusim">`)
  — the single most critical setting; everything else fails silently if it's wrong.
- **Game Manager** (multi-user login flow, inherited from defenseScenario) —
  delete, not needed for a single-boat headless-driven demo.
- Defense decor, the Leap Motion rig, the old camera rig — disable, not needed.
- **Marks and buoys** come from the simulation stack through the bridge. Do not
  add static scene copies: they duplicate the bridged objects and drift from
  the authoritative scenario.
- **Ocean**: HDRP `WaterSurface` component, `Ripples Wind Speed ≈ 2` — this is
  a rendering-only knob; the physics wind/sea is flat (uniform wind lives in
  `focus_v2.yaml`, not the visual ocean).

## The boat

**Never place the boat by hand** — it is spawned at runtime by the bridge
(`renderer_type_name = focus_v2` resolves to the Addressable) the moment gz
issues the `renderer_cmd` CREATE. A hand-placed boat becomes a second, inert
"ghost" boat sitting next to the real one — the most common setup mistake here.

Prefab structure: a root object + a child FBX (`Rotation Y = 270`, the
connector's heading convention) with `ActuatorAnimator` attached to the root.

## Scripts

Source of truth is `unity/*.cs` in **this** repo; deployed copies live at
`Assets/Scripts/Regatta/` in the Unity project.

- `ActuatorAnimator` — subscribes to `/lotusim/vessel_cmd_array`, parses
  `mainsail(sheet)` / `rudder(helm)` from the JSON `cmd_string`, and swings the
  boom to leeward based on the geometric bearing of `BowNose` vs `Hull`
  against the wind (no frame-convention assumption baked in). Inspector knobs
  `sailSign` / `rudderSign` flip a convention live without recompiling.
- `RegattaCameraRig` — chase / orbit / onboard / free-FPS modes, cycled with
  `C`; RMB-drag to look around, wheel to zoom/adjust speed.
- `ManualHelm` — `M` (or gamepad Start) toggles manual helm, publishing on
  `/lotusim/manual_cmd_array`. The helmsman treats a fresh manual message as an
  override and silence as "the algo sails" — no mode topic, so a dead Unity
  hands the helm back by itself. Inputs: arrow keys always; any two physical
  axes via the new Input System — defaults are baked in (helm = T-Rudder toe
  brakes, one per side; sheet = Warthog stick X, right hauls in), `B` runs a
  3-phase excursion-based rebind (push right / push left / push toward haul).
  A phantom axis parked at an extreme can never win a bind — it does not move.
  Float PlayerPrefs proved unreliable (read back as zeroes), so a persisted
  bind with `sign`/`span` 0 is treated as corrupt and the baked defaults win.
  Caveat: the FREE camera also reads the arrows; sail from the other modes.
- `NativeFoamWakeController` — the active native HDRP wake: four dynamic,
  periodically driven `WaterFoamGenerator`s per boat (stern arms plus bow and
  stern injection) and a `BowWave` `WaterDeformer`. The legacy `WakeEmitter`
  trail is disabled, so the scene renders one wake implementation only.

HDRP permits 64 foam generators. This milestone is qualified for one boat;
16 boats saturate that global limit and a 17th loses generators. Introduce a
shared generator pool before qualifying a fleet of that size.

### Unity on Windows

The project files must live on the **Windows** filesystem (here
`C:\Users\cyril\lotusim-unity`) — the editor is not usable against `\\wsl$`.
That working tree is the production Unity `2023.1.20f1` / HDRP `15.0.7`
checkout on `feature/regatta-scenario`.
The ROS IP stays `127.0.0.1`: WSL2 forwards localhost from Windows into Linux,
so the endpoint on `:10000` is reachable as-is. Deploy scripts from WSL via
`/mnt/c/Users/cyril/lotusim-unity/Assets/Scripts/Regatta/`.

## EditMode verification

With the editor closed:

```bash
'/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe' \
  -batchmode -projectPath 'C:\Users\cyril\lotusim-unity' \
  -runTests -testPlatform EditMode \
  -testResults 'C:\Users\cyril\lotusim-unity\Logs\editmode.xml' \
  -logFile 'C:\Users\cyril\lotusim-unity\Logs\editmode.log'
```

Do not add `-quit`: the Test Runner exits Unity itself, while `-quit` can stop
before the tests and still return 0. Verify the generated XML has
`result="Passed"`; the process exit code alone is insufficient.

## Standalone player (no editor)

`Assets/Editor/BuildRegatta.cs` selects the host platform. On the production
Windows worktree it creates `Builds/Regatta/Regatta.exe` (editor must be
closed):

```bash
'/mnt/c/Program Files/Unity/Hub/Editor/2023.1.20f1/Editor/Unity.exe' \
  -batchmode -quit -projectPath 'C:\Users\cyril\lotusim-unity' \
  -executeMethod BuildRegatta.Build \
  -logFile 'C:\Users\cyril\lotusim-unity\Logs\regatta-build.log'
```

On macOS the same method creates a native arm64 `Builds/Regatta.app`; on Linux
it creates `Builds/Regatta/Regatta.x86_64`, provided the matching Unity build
module is installed. First build ≈ 11 min (HDRP shader variants), then cached.
Run flow is the same as the editor: start the stack
(`UNITY=1 ./scripts/run_regatta.sh 900 hold`), then open the player instead of
pressing Play. Trap: editor-only code outside an `Editor/` folder compiles in
the editor but breaks player builds (CS0246) — `LotusimConnectorEditor.cs`
carries the `#if UNITY_EDITOR` guard for this.

## Launch order

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

`run_regatta.sh` starts the ROS-TCP endpoint **first**, before xdyn/helmsman/gz
— under Rosetta it doubles as the DDS participant that unblocks gz's own ROS2
plugins (see the DDS-deadlock note in `HANDOFF-gz-beat.md`). The script then
waits (polling `/tmp/endpoint.log` for `"Connection from"`) for Unity to
connect — open the Regatta scene and press Play once you see
`[*] waiting for Unity ...` in the terminal.

## Troubleshooting (pitfalls actually hit)

- **QoS DURABILITY mismatch**: a `volatile` publisher is silently rejected by
  a `TRANSIENT_LOCAL` subscriber (or vice versa) — nothing moves, no error in
  Unity. Proof is in `/tmp/endpoint.log` *inside the container*, not the Unity
  console.
- **`smoke` mode kills the stack mid-session** — it's a pass/fail gate with a
  hard timeout; use `hold` for anything interactive.
- **Bee/Mono crash, FD 1028**, after a long editor session — restart the
  Unity editor, not a code fix.
- **Serialized fields mask script defaults** — once a component's field has
  been touched in the Inspector, the serialized value wins over the script's
  default on every reload; check the Inspector, not just the source, when a
  "default" doesn't seem to apply.
- **OBJ importer merges materials** that the FBX export kept separate — import
  the `.fbx`, not the `.obj`, and bake the axis conversion into the export
  (`bake_space_transform`) rather than relying on the importer.
- **Pivots = Blender origins** — a part's rotation pivot in Unity is exactly
  its mesh origin in Blender; get the origin right at export time, there is no
  cheap fix in Unity afterward.
- **Game view vs. Display 1** — the Game view can be pointed at a display
  other than the one actually rendering; if the view looks frozen/black,
  check which Display tab is selected before debugging further.
- **Gizmos** — mark/wind-indicator debug gizmos are easy to mistake for real
  geometry; toggle the Gizmos button off when checking what a student would
  actually see.
