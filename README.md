# LOTUSim-regatta

A pedagogical windward-leeward regatta for a Focus V2 RC sailboat on
[LOTUSim](https://github.com/naval-group/LOTUSim) (Gazebo + xdyn co-simulation,
rendered in Unity). A reference helmsman sails a full W/L lap around two buoys;
the pipeline is the seed for a course where students later write their own
trajectory control in place of the reference pilot.

## Architecture

```
                        ┌────────────────────────┐
                        │  xdyn-for-cs (physics)  │   NED frame, ws :12345
                        │  focus_v2.yaml model    │   stateless: full state
                        └───────────▲────────────┘   round-trips every step
                                    │ websocket
                        ┌───────────┴────────────┐
                        │ gz physics_interface_   │   NED ↔ ENU conversion
                        │ plugin (physics OFF)    │
                        └───────────┬────────────┘
                                    │ renderer_poses (ROS2)
                                    ▼
                        ┌─────────────────────────┐
                        │ ros-tcp-endpoint :10000 │───► Unity (render, ENU→Z-Y)
                        └─────────────────────────┘
                                    ▲
                                    │ gz pose (ENU)
                        ┌───────────┴────────────┐
                        │ helmsman (ROS2 node)    │   ENU→NED, Pilot, →JSON cmd
                        │ gz pose → Pilot →       │
                        │ vessel_cmd_array        │
                        └─────────────────────────┘
```

- gz's own physics is **off** — it only orchestrates the clock, pose broadcast
  and the Unity render bridge. All forces are computed by **xdyn**, an external
  co-simulation process; gz's `physics_interface_plugin` is a websocket client
  to it.
- **xdyn is stateless**: the complete vessel state (position, quaternion,
  velocities) round-trips over the websocket on every communication step —
  xdyn does not remember anything between calls.
- Two independent step sizes: the co-sim **comm step** (gz ↔ xdyn round-trip,
  `0.01` s) and the internal xdyn **integration step** (`--dt 0.005`, solver
  `rk4`); xdyn substeps the comm step internally at `--dt`.

## Quickstart

### 1. Offline oracle (physics ground truth)

Fast, deterministic, no gz/ROS/Unity — direct websocket to `xdyn-for-cs`. This
is the reference the full stack is checked against.

```bash
cd offline && python3 oracle.py
# xdyn_dt 0.001 | comm_dt 0.005 | marks reached 2/2 | tacks 3 | dur 161s
# ORACLE PASS
```

Knobs: env `COMM_DT` / `XDYN_DT` to A/B the step sizes.

### 2. Headless smoke gate (full gz co-sim stack)

```bash
timeout 450 bash scripts/run_regatta.sh 300 smoke
# ... SMOKE PASS
```

Brings up xdyn → helmsman → gz headless in Docker and asserts the boat rounds
both marks (`scripts/smoke_rounds_marks.py`, a gz pose oracle).

### 3. Unity (rendered)

```bash
UNITY=1 timeout 1000 bash scripts/run_regatta.sh 900 hold
```

Then open `LOTUSim-Unity-modules/Builds/Regatta.app` (standalone player), or the
Regatta scene in the editor and press Play — see
`docs/unity-scenario.md` for how to (re)build that scene.

## Prerequisites

Runtime is **Docker only** (this project is developed on Apple Silicon;
`--platform linux/amd64` via Rosetta, RTF ≈ 1.0 with the current step config).
Everything runs inside `lotusim:focus-v2`, built from the post-#36 upstream
`main` (all three physics fixes below are merged) plus the lab branches
(`LOTUSim@integration/post36`: focus_v2 assets + control-surfaces seeding) and
`ros_tcp_endpoint` (for the Unity bridge). Rebuild recipe, run once inside a
throwaway container of the previous image:

```bash
# 1. replace the whole source tree (packages get renamed upstream; overlaying
#    would leave dead ones behind), from the integration branch
docker exec <container> rm -rf /lotusim_ws/src/LOTUSim
git -C LOTUSim archive integration/post36 | docker cp - <container>:/lotusim_ws/src/LOTUSim
# 2. build IN THE SAME container the image is committed from
#    (radar_sensor needs: apt-get install -y ros-jazzy-radar-msgs)
docker exec <container> bash -lc \
  'source /opt/ros/jazzy/setup.bash && cd /lotusim_ws && \
   colcon build --merge-install'
# 3. freeze the layer -- docker commit KEEPS the container entrypoint: create
#    the container without --entrypoint or restore ENTRYPOINT ["/ros_entrypoint.sh"]
docker commit <container> lotusim:focus-v2
```

## Performance

Wall-clock durations in the scripts above ARE the sim duration — Rosetta RTF
is well below hardware-native.

| Config | comm step | xdyn `--dt` | RTF (Rosetta) |
|---|---|---|---|
| baseline | 0.005 | 0.001 | ≈ 0.26 |
| current | 0.01 | 0.005 | ≈ 1.01 |

One rk4 substep costs ≈ 3.1 ms under Rosetta — it is what set the ceiling;
widening both steps to the values above removed it without touching
integration quality (oracle unchanged: 2/2 marks, 3 tacks).

## Debug tooling

- `WS_TAP=1 bash scripts/run_regatta.sh ...` — passive websocket tap between
  the gz plugin and xdyn (`_tap.jsonl`), for diffing what the plugin actually
  sends/receives against the offline reference.
- `WS_LOG=<path>` (offline side, in `offline/ws.py`) — same idea, logs the
  oracle's own websocket traffic.
- `offline/probe_helm.py` — constant-rudder probe (bypasses the Pilot) to
  characterize the boat's open-loop response in isolation.
- The debugging pattern that found the upstream bugs below: diff the round
  trip bit-for-bit between the offline oracle and the gz stack at each layer
  boundary; "verbatim" means that layer is clean, move to the next.

## Upstream fixes (naval-group/LOTUSim)

| Issue / PR | Fix | Status |
|---|---|---|
| [#27](https://github.com/naval-group/LOTUSim/issues/27) / [#28](https://github.com/naval-group/LOTUSim/pull/28) | xdyn quaternion `j`/`k` swapped on receive — pre-existing, invisible at identity attitude | merged upstream 2026-07-13 |
| [#32](https://github.com/naval-group/LOTUSim/issues/32) / [#33](https://github.com/naval-group/LOTUSim/pull/33) | NED↔ENU attitude conversion missing the FLU↔FRD body-frame swap — root cause of the boat not holding a beat | merged upstream 2026-07-13 |
| [#34](https://github.com/naval-group/LOTUSim/issues/34) / [#35](https://github.com/naval-group/LOTUSim/pull/35) | co-sim `t` carried the step duration in ms instead of absolute sim time — freezes any time-dependent forcing (waves); prerequisite for swell | merged upstream 2026-07-13 |

## Repo map

```
LOTUSim-regatta/
├── offline/                  # websocket physics oracle (ws.py, oracle.py, probe_helm.py)
├── src/regatta_agents/       # ROS2 package: pilot.py (brain) + helmsman.py (ROS node)
├── assets/{worlds,models}/   # regatta.world, regatta_buoy model
├── assets/blend/             # Blender sources (buoy, boat)
├── unity/                    # C# scripts deployed into LOTUSim-Unity-modules
├── scripts/                  # run_regatta.sh, smoke_rounds_marks.py, ws_tap.py
└── docs/                     # design, plans, HANDOFF, unity-scenario.md
```

- Design: `docs/design/2026-07-06-regatta-mvp-design.md`
- Plan: `docs/plans/2026-07-06-regatta-mvp-plan.md`
- Gz-beat investigation (resolved): `docs/HANDOFF-gz-beat.md`
- Unity scene recipe: `docs/unity-scenario.md`

License: EPL-2.0.
