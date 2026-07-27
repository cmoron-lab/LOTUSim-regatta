# Unity Regatta scenario — build recipe

The Regatta scene and everything it depends on (boat/buoy assets, Addressable
entry, deployed scripts) are committed on `feature/regatta-scenario` — the
Unity repo **must be on that branch**: on `main` the scene may still open from
a stray working-tree copy, but the `focus_v2` Addressable key does not exist
and the bridge fails at spawn with `InvalidKeyException`. This doc remains the
recipe to rebuild the scene from scratch if needed.

- Project: `LOTUSim-Unity-modules` (fork `cmoron-lab`), Unity `2022.3.62f2`, HDRP.
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
- **Buoys**: two static instances of `regatta_buoy.fbx` placed directly in the
  scene (not bridged, not an Addressable — see the design doc's C2) at Unity
  `(0, 0, 0)` and `(0, 0, 15)`. Conversion from gz coordinates: `unity = (gz.x,
  gz.z, gz.y)` (see `common.cs` in the Unity modules for the canonical formula).
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

## Standalone player (no editor)

`Assets/Editor/BuildRegatta.cs` builds a native arm64 `Builds/Regatta.app`
(menu `LOTUSim > Build Regatta (macOS)`, or headless — editor must be closed):

```bash
/Applications/Unity/Hub/Editor/2022.3.62f2/Unity.app/Contents/MacOS/Unity \
  -batchmode -quit -projectPath LOTUSim-Unity-modules \
  -executeMethod BuildRegatta.Build -logFile /tmp/unity_build.log
```

First build ≈ 11 min (HDRP shader variants), then cached. Run flow is the same
as the editor: start the stack (`UNITY=1 ./scripts/run_regatta.sh 900 hold`), then open
`Regatta.app` instead of pressing Play. Trap: editor-only code outside an
`Editor/` folder compiles in the editor but breaks player builds (CS0246) —
`LotusimConnectorEditor.cs` carries the `#if UNITY_EDITOR` guard for this.

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
