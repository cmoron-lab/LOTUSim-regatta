# LOTUSim-regatta — MVP Design (Phase 1)

**Goal:** A dedicated, out-of-tree LOTUSim project in which a single Focus V2
sailboat, driven by a reference helmsman, sails a full windward-leeward lap
around two buoys — physics by xdyn co-simulation, rendered in Unity — as the
seed of a pedagogical regatta where students later write the trajectory control.

**Architecture:** A standalone colcon workspace that *consumes* the LOTUSim core
(engine + `focus_v2` model + patched xdyn) exactly as `LOTUSim-generic-scenario`
does, but reduced to the regatta. It owns its world, its buoy model, its
pilot(s), its offline physics oracle, and its Unity integration. No change to
the core is required for the MVP.

**Tech Stack:** ROS 2 Jazzy · Gazebo Harmonic (`gz`) · xdyn (co-sim, patched
`libx-dyn.so`) · Python (rclpy + gz-transport) · Unity HDRP (Addressables,
Input System) · Blender (buoy mesh, via MCP or headless CLI).

## Global Constraints

- **License EPL-2.0** (whole ecosystem). Never vendor GPL / non-redistributable
  assets; the buoy is re-authored from Cyril's own Blender source.
- **Runtime is Docker only on this Mac** — no native ROS2/gz/xdyn. Images:
  `lotusim:focus-v2` (amd64 / Rosetta). Unity runs natively (Cyril launches it).
- **xdyn conventions** (verified, non-negotiable): NED frame; body X-fwd,
  Y-stbd, Z-down; rotation `Z/Y/X` `[psi, theta', phi'']`; quaternion order
  `qr, qi, qj, qk`. gz↔Unity is `Z→-Y`.
- **xdyn ignores the yaml `commands:` block.** Actuator setpoints are *published*
  on `/<world>/vessel_cmd_array` (`lotusim_msgs/msg/VesselCmdArray`); each
  `VesselCmd.cmd_string` is JSON forwarded verbatim to xdyn.
- **Angle-commanded actuators have no default command** → their full signals
  (`mainsail(sheet)`, `rudder(helm)`) must be seeded via the world's
  `<control_surfaces>` block, or xdyn throws before the first ROS setpoint.
- **`HELM_SIGN = -1`** and the tuned `focus_v2.yaml` yaw damping (lin 0.3 /
  quad 0.4) are prerequisites carried by the core branch `feature/focus-v2-model`.
- **Commit only when Cyril asks.** Scaffolding may be created uncommitted.

## Context — what already exists (do not rebuild)

| Piece | Where | State |
|---|---|---|
| `focus_v2` xdyn model | core `assets/models/focus_v2/focus_v2.yaml` | tuned (yaw damping → tacking works) |
| Patched xdyn (`libx-dyn.so`) | core `physics/` + submodule | foil heading bug fixed, ABI-compatible |
| `focus_v2_demo.world` | core `assets/worlds/` | 1-buoy demo; template for our world |
| Unity `focus_v2` prefab | `LOTUSim-Unity-modules/Assets/models/focus_v2/` | boat mesh ready (branches `demo/focus-v2`, `feature/focus-v2-mesh`) |
| Reference helmsman (skeleton) | generic-scenario `src/agents/focus_v2/focus_v2/helmsman.py` | proven ROS2↔gz↔xdyn plumbing; **single-mark** tactics |
| W/L racing brain | `_offline/cosim.py` (`sail_course`) | proven **W/L + engaged tack** (2/2 marks, 3-4 tacks), websocket-direct |
| Buoy mesh source | `regatta_buoy.blend` | authored; **not yet exported / imported** |

**Key synthesis:** the regatta helmsman is *neither* a move *nor* a wholesale
copy of the generic-scenario agent. It **grafts** the generic-scenario ROS2
skeleton (pose-in / cmd-out / params — the proven plumbing) onto the
`_offline/cosim.py` W/L brain (the proven tactics). The generic-scenario agent
stays untouched.

## Scope

**Phase 1 (this spec — MVP):** one boat, reference helmsman, full W/L lap, flat
sea + uniform wind + two buoys, rendered in Unity. Plus two Unity visual layers
Cyril asked for: a **wind indicator** (force + direction) and **animated sail +
rudder** driven by the live commands. Validated offline (physics) + headless
Docker (integration) + Unity (render). The sail/rudder animation is the final,
rig-gated step (see C7/R5) — it enriches the demo but must not block the core
pipeline proof.

**Phase 2 (documented, NOT built now):** start/finish line (committee boat +
pin), shifting/gusting wind. Config-driven multi-boat via
`scenario_launch.sh --config regatta.json` (requires patching
`generate_lotus_param()` to emit `<control_surfaces>`). Scoring.

**Phase 3+ (vision):** student-authored pilots (one ROS2 pkg per student),
Unity keyboard-control mode (Input System → `vessel_cmd_array`, physics still by
xdyn), race sequencing.

## Project structure

```
LOTUSim-regatta/
├── README.md, LICENSE (EPL-2.0)
├── docs/design/2026-07-06-regatta-mvp-design.md   # this spec
├── assets/
│   ├── worlds/regatta.world                        # sea + uniform wind + 2 buoys + include focus_v2
│   └── models/regatta_buoy/
│       ├── model.config, model.sdf                 # gz model with <visual>
│       └── meshes/regatta_buoy.dae                 # exported from regatta_buoy.blend
├── src/
│   └── regatta_agents/                             # ROS2 ament_python package
│       ├── package.xml, setup.py, setup.cfg, resource/
│       └── regatta_agents/helmsman.py              # skeleton (generic-scenario) + brain (_offline)
├── unity/
│   ├── README.md                                   # import + rig + scene-wiring steps
│   ├── WindIndicator.cs                            # C6 — wind arrow/force widget
│   └── ActuatorAnimator.cs                         # C7 — sail+rudder from vessel_cmd_array
├── offline/
│   └── cosim.py                                    # physics oracle (migrated from _offline)
└── scripts/
    └── run_regatta.sh                              # xdyn-for-cs + gz(regatta.world) + helmsman
```

## Components

### C1 — `assets/worlds/regatta.world`
**Responsibility:** define the race arena and wire the boat.
**Content:** adapted from `focus_v2_demo.world` — scene, ODE physics stub,
`gravity 0 0 0` (xdyn owns forces), the four LOTUSim plugins
(`physics_interface_plugin`, `entity_manager_plugin`, `lotusim_sensor_plugin`,
`render_plugin` with `<connection_protocol>ROS2</connection_protocol>`) +
`SceneBroadcaster` for self-contained gz runs. Flat `sea` visual plane. **Two**
buoy models: `mark_windward` and `mark_leeward` (`include model://regatta_buoy`),
positioned to define the W/L axis aligned with the wind. `include model://focus_v2`
with `<lotus_param>`: `<physics_engine_interface>` (uri `ws://127.0.0.1:12345`,
`<control_surfaces><sail>mainsail(sheet)</sail><rudder>rudder(helm)</rudder>`),
`<render_interface><renderer_type_name>focus_v2</renderer_type_name>`.
**Uniform wind** stays in `focus_v2.yaml` (the xdyn environment model), not the
world — the world only positions the marks. World name = the Unity namespace.
**Depends on:** core `model://focus_v2`, this project's `model://regatta_buoy`.

### C2 — `assets/models/regatta_buoy/`
**Responsibility:** the buoy, visible in gz and resolvable in Unity.
**Content:** `regatta_buoy.blend` → `regatta_buoy.dae` (or `.glb`) via Blender
(MCP if the editor is live, else `blender --background --python` headless).
`model.config` + `model.sdf` (SDF 1.10) with a `<static>true` link and a
`<visual>` referencing the mesh; no `<collision>` (buoys are not physically hit
in the MVP). **Unity side (unambiguous for MVP):** the buoy is a **static scene
object** placed directly in the Unity regatta scene from the imported mesh — it
does not move, so it is **not** bridged and **not** an Addressable. Only the boat
goes through the render bridge (`renderer_cmd` CREATE + per-tick `renderer_poses`).
Making the buoy a bridged Addressable is a Phase 2 concern (moving/instanced marks).
**Depends on:** `regatta_buoy.blend`.

### C3 — `src/regatta_agents/regatta_agents/helmsman.py`
**Responsibility:** the reference pilot — sail a full W/L lap.
**Content:** ROS2 `Node` (ament_python), skeleton from generic-scenario:
subscribe gz-transport `/world/<world>/dynamic_pose/info` (`Pose_V`), publish
`/<world>/vessel_cmd_array` (`mainsail(sheet)`, `rudder(helm)` in radians),
ROS2 params for marks/gains/wind. Control **brain ported from `_offline`**:
`desired_heading` (NO_GO zone → beat on current tack, else bearing),
`run_leg` PD (kp 2.2 / kd 0.9, `HELM_SIGN=-1`), `opt_sheet` calibrated curve,
`sail_course` state machine (leg → corridor tacking with the **engaged-tack**
routine → mark rounding → next leg). Marks list = `[windward, leeward]` (a lap);
finishing rounds both and stops.
**Interface:** in = gz pose (x, y, yaw, roll, r); out = JSON cmd string.
**Depends on:** `lotusim_msgs`, `gz.transport13`, the world's control_surfaces seeding.
**Risk (see R1):** offline runs control+physics in lockstep at dt=0.005; here the
helmsman is an async ~10-50 Hz timer against xdyn at its own `--dt`.

### C4 — `offline/cosim.py`
**Responsibility:** fast, deterministic **physics oracle** — the maneuver proof.
**Content:** migrated from `_offline/cosim.py` (websocket-direct to `xdyn-for-cs`
in Docker). Extended so the offline `sail_course` replays the *same* W/L lap the
ROS2 helmsman will fly, asserting 2/2 marks + tacks. This is the reference the
helmsman's control logic is validated against before touching gz.
**Depends on:** Docker `xdyn-for-cs`, patched lib, `focus_v2.yaml`.

### C5 — `scripts/run_regatta.sh`
**Responsibility:** one-command headless run of the full stack.
**Content:** like `run_demo.sh` — start `xdyn-for-cs focus_v2.yaml --port 12345
-s rk4 --dt 0.005` from the models dir; `gz sim -s -r regatta.world` with
`GZ_SIM_RESOURCE_PATH` including both the core models and this project's models;
`ros2 run regatta_agents helmsman`. `trap cleanup EXIT` (never `pkill -f` — it
self-kills, pitfall #5). Parameterized duration + mark positions.

### C6 — `unity/` regatta scene
**Responsibility:** render the lap.
**Content:** a regatta scene in `LOTUSim-Unity-modules` (HDRP water for the sea,
two static buoy instances from the imported mesh, the existing `focus_v2`
prefab as the bridged renderer). `LotusimInterface.m_namespace` **must equal the
world name**. The boat is created via the latched `renderer_cmd` CREATE and moved
each tick by `renderer_poses`. Buoys are static scene objects (no bridge).
A **wind indicator** — a world-space arrow/windsock (or HUD compass) showing wind
direction + a force readout — reads the wind from a scene config matching
`focus_v2.yaml` (static for the uniform-wind MVP; the same widget goes dynamic in
Phase 2 shifting wind). Built/inspected via **Unity MCP** when the editor is live;
Cyril drives the GUI.
**Depends on:** the boat Addressable already existing; the imported buoy mesh.

### C7 — Unity actuator animation (sail + rudder)
**Responsibility:** make the sail trim and the rudder steer on screen, driven by
the live commands — the "magical" layer.
**Content:** a Unity C# component subscribes to `/<world>/vessel_cmd_array` via the
**ROS-TCP-Endpoint** (present in `LOTUSim-Unity-modules/Submodules/`), parses the
JSON `mainsail(sheet)` and `rudder(helm)` (radians), and rotates two rigged
pivots: **Boom + Mainsail** about the mast axis at the gooseneck, and **Rudder**
about its stock. The mesh already ships these as separate objects (`Mainsail`,
`Jib`, `Boom`, `Mast`, `Gooseneck`, `Rudder`), so no re-modelling — only a pivot
rig (parent Boom+Mainsail to a mast-base empty; Rudder to a stock empty) in
Blender or the Unity editor. `sheet` maps directly to the sail's boat-relative
angle; the boom must sit to **leeward**, so the sign follows the current tack
(the sail flips sides through a tack). Jib animation is optional (mainsail is the
big visual). No core change; no new data on the render bridge.
**Interface:** in = `vessel_cmd_array` (already published by the helmsman);
out = local rotations on the sail/rudder pivots.
**Depends on:** the pivot rig (R5); ROS-TCP-Endpoint built for the Unity project.
**Sequencing:** LAST in the MVP — after the boat renders and moves. Rig-gated;
slips to Phase 1.5 if the rig proves fiddly, without blocking C1–C6.

## Data flow (standard LOTUSim)

```
helmsman ─► /<world>/vessel_cmd_array ─► gz physics_interface ─► xdyn (patched)
   (sail/rudder JSON)                        (websocket 12345)        │
                                                                      ▼
Unity ◄── render_plugin ◄── gz entity pose ◄──────────────────── xdyn state
 (Z→-Y)     (ROS2, /<world>/renderer_poses)     (NED→ENU)
```

## Error handling

- **No xdyn server on the port** → `XdynWebsocket::onFail`; `run_regatta.sh`
  starts xdyn first with a `sleep`, and the smoke test asserts `onOpen` in the log.
- **Actuator seeding** → `<control_surfaces>` in the world prevents the pre-first-
  setpoint throw. The helmsman also publishes an initial neutral setpoint on start.
- **gz-transport python absent** (import-time) → the node logs an error and exits
  cleanly (no silent catch); the skeleton already guards `_HAVE_GZ`.
- **Tack stalls "in irons"** → the engaged-tack routine (firm rudder + high gain
  through the eye); if the async cadence breaks it (R1), the fallback is to raise
  the helmsman timer rate before re-tuning gains.

## Verification (proof of execution — 3 levels)

1. **Physics / maneuvers** → `offline/cosim.py` replays the W/L lap; assert
   `marks_reached == 2` and `tacks >= 1`. Fast, deterministic, the primary gate.
2. **ROS2 / gz / xdyn integration** → `run_regatta.sh` headless in Docker; a
   **gz pose oracle** (subscribe `dynamic_pose/info`) asserts the boat passes
   within `wp_radius` of both marks. Confirms the async control cadence holds.
3. **Unity render** → Unity MCP scene inspection (boat + 2 buoys present, boat
   pose updating) + Cyril's visual confirmation in the editor.

## Risks

- **R1 (highest) — async control cadence vs the engaged tack.** Offline is
  lockstep dt=0.005; ROS2 is async ~10-50 Hz vs xdyn `--dt`. The tack may not
  complete. *Mitigation:* validate in level-2 smoke first; raise helmsman rate;
  re-tune only if needed. This is the one thing that can invalidate the port.
- **R2 — buoy mesh export.** Blender MCP needs a live Blender with the file open;
  headless CLI is the fallback. Scale/orientation must match gz (Z-up) and Unity
  (`Z→-Y`).
- **R3 — Unity Addressable / namespace mismatch** → "connected, nothing renders".
  Namespace == world name; boat Addressable address == `renderer_type_name`.
- **R4 — Rosetta slowness** makes Docker smoke iterations slow; keep the offline
  oracle as the fast inner loop, hit Docker only at integration checkpoints.
- **R5 — sail/rudder rig (C7).** The mesh has the parts but not the pivots;
  Boom+Mainsail must rotate about the mast at the gooseneck (not the mesh origin),
  and the boom side must follow the tack. Getting the pivot placement and the
  sign/side right is the fiddly bit. *Mitigation:* it is sequenced last and can
  slip to Phase 1.5 without touching the validated pipeline.

## Out of scope (explicit)

Start line, shifting wind, multi-boat, config-driven `scenario_launch.sh`,
`generate_lotus_param()` control-surfaces patch, scoring, keyboard mode. All are
Phase 2/3 and must not creep into the MVP.
