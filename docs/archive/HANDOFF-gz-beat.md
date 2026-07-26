# LOTUSim-regatta — Gz co-sim "close-hauled beat": problem statement & handoff

> ## ✅ RESOLVED (2026-07-06)
> Root cause: two quaternion bugs in the LOTUSim `physics_engine_interface` plugin
> (separate repo, not this one) — (1) a qj/qk swap on receive, fixed upstream
> 2026-07-02 but absent from the 2026-06-27 docker image (needs a plugin rebuild),
> (2) an attitude conversion missing the FLU↔FRD body-frame offset
> (`ψ_ned = π/2 − ψ_enu`, not `−ψ_enu`). Verdict: **SMOKE PASS 2/2 marks**
> (windward 1.30 m, leeward 0.08 m, 4 tacks, ~163 s sim), trajectory matches the
> offline oracle to ±1.5 s. Ops notes: the rebuilt plugin `.so` is deployed via
> `_patched_lib/` (copied into the container by `run_regatta.sh`, gitignored);
> smoke duration is **wall-clock**, and Rosetta RTF ≈ 0.26 → ~900 s wall for one
> full lap (~230 s sim).

> **For the next agent (Fable 5):** the physics is proven; the boat will not yet
> sail a close-hauled **beat** through the **full gz co-sim stack**. Everything you
> need is below. **Do not re-guess rudder signs or re-discover the infra fixes** —
> Section 4 lists what is already solved; Section 7 is the investigation to run.

---

## TL;DR

- **Physics = locked & proven.** The offline oracle (`offline/oracle.py`, direct
  websocket to xdyn, pure NED) sails a full windward-leeward lap: **2/2 marks,
  3 tacks**. This uses the current tuned `focus_v2.yaml`.
- **Gz stack = runs end-to-end but does not beat.** `scripts/run_regatta.sh`
  brings up xdyn + gz + helmsman headless; the boat moves, pose flows, but it
  **drifts off to ~90–110° instead of holding a ~60° close-hauled beat** toward
  the windward mark. It reaches/runs but will not point.
- **Why:** locking the physics model proves xdyn's *forces*. The full stack adds
  an **integration layer** (gz `physics_interface_plugin` ↔ xdyn with NED↔ENU
  conversions + its step protocol, the ROS `vessel_cmd_array` bridge, the
  helmsman's ENU→NED). That layer never existed in the offline validation, and
  the conf-prep de-risking **never beat upwind in gz** (only reaching/downwind,
  which tolerates integration-layer sloppiness the beat does not).
- **Next step:** an **offline-vs-gz round-trip diff** (Section 7), not sign
  guessing. The remaining problem is integration plumbing, not physics.

---

## 1. Mission & architecture

**Mission:** a pedagogical windward-leeward regatta where students write the
trajectory control for a Focus V2 RC sailboat; one boat must sail a full W/L lap
(beat up to the windward mark, run down to the leeward mark), rendered in Unity.

**Stack (LOTUSim):**
- **gz (Gazebo Harmonic)** = orchestration + clock + pose broadcast + render
  bridge to Unity. **Its own physics is OFF** (`<gravity>0 0 0</gravity>`; gz does
  not integrate forces on the vessel).
- **xdyn** (external, co-simulation) = computes ALL forces and returns the state.
  gz's `physics_interface_plugin` is a **websocket client** to an `xdyn-for-cs`
  server (one per vessel, port 12345). Commands are **published** on ROS2
  `/<world>/vessel_cmd_array` (`lotusim_msgs/msg/VesselCmdArray`), `cmd_string` =
  JSON `{"mainsail(sheet)": <rad>, "rudder(helm)": <rad>}`, forwarded to xdyn.
- **Frames:** xdyn = **NED** (x=North, y=East, z=Down); gz world = **ENU**
  (x=East, y=North, z=Up); the plugin converts NED→ENU for gz poses; Unity is
  `Z→-Y` off gz.

## 2. The core distinction — physics-locked ≠ stack-works

```
OFFLINE (PROVEN):  pilot ──websocket──► xdyn          NED pure, one loop I own
                                                        (I send {state,cmds,Dt}, read state)

GZ STACK (unproven for the beat):
   pilot ──ROS vessel_cmd_array──► gz physics_plugin ──ws──► xdyn ──► gz pose ──► pilot
                                    NED↔ENU + step proto              NED↔ENU (helmsman)
```

The offline oracle bypasses the whole gz/ROS/frame layer. That layer has its own
conventions (NED↔ENU signs, the plugin's `Dt`/state protocol, async ROS/gz
timing). **A perfect force model says nothing about the correctness of that
layer.** The beat is the first maneuver that demands *precise* heading control
(hold ~60°, tack through the eye), so it is the first thing to expose an
integration-layer bug that reaching/downwind tolerated.

## 3. Current state (committed)

Repo: `~/src/lotusim-lab/LOTUSim-regatta` (its own git repo, branch `main`).

| Item | State | Commit |
|---|---|---|
| Design spec | done | `c1845ad` `docs/design/2026-07-06-regatta-mvp-design.md` |
| Implementation plan (9 tasks) | done | `ddc69f6` `docs/plans/2026-07-06-regatta-mvp-plan.md` |
| T1 workspace scaffold | done | `4f61cd3` |
| T2 `Pilot` pure brain + 6 unit tests | done, 6/6 pass | `6a3bcd1` |
| **T3 offline oracle (physics GATE)** | **PASS: 2/2 marks, 3 tacks** | `55438cd` |
| T4 `regatta.world` + buoy model | done | `01a849d` |
| T5 helmsman + `run_regatta.sh` (runs) | **WIP** — stack runs, beat unresolved | `cd823c5` |
| T6 gz smoke (beat) | **BLOCKED** | — |

The **offline oracle is the reference truth**: same xdyn, same model, and it beats.

## 4. Infrastructure ALREADY SOLVED (do not re-discover)

Runtime is **Docker only** on this Apple-Silicon Mac (`lotusim:focus-v2`,
`--platform linux/amd64`, Rosetta). LOTUSim is **prebuilt in the image at
`/lotusim_ws`**; the patched `focus_v2` model + xdyn lib come from the mounted
host `/lab` (= `~/src/lotusim-lab`). See memory `lotusim-gz-rosetta-runtime`.

1. **DDS deadlock (Rosetta).** The LOTUSim gz plugins (rclcpp) hang gz at init
   creating the *first* DDS participant under Rosetta → gz freezes after "Serving
   entity system service", `gz model --list` times out. **Fix: a ROS2 node must
   already exist in the domain before gz starts** — `run_regatta.sh` launches the
   helmsman BEFORE `gz sim`. (In conf-prep, Unity's ROS-TCP endpoint was that
   pre-existing node, so the deadlock was never seen.) `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`
   alone was NOT reliable.
2. **Plugin path:** sourcing does NOT set it → `export GZ_SIM_SYSTEM_PLUGIN_PATH=/lotusim_ws/install/lib`
   (else "Could not find shared library" ×4).
3. **Cleanup:** `gz sim` ignores SIGTERM → use `kill -9` / `timeout -s KILL`, and
   purge zombies: `docker ps -q --filter ancestor=lotusim:focus-v2 | xargs -r docker rm -f`.
4. **Numerical yaw oscillation:** at `max_step_size 0.05` a *constant* rudder made
   yaw oscillate ±1.3 rad/s (old "numerical spin" regime). **`max_step_size 0.005`
   fixes it** (already set in `regatta.world`).
5. **Frame conversion (helmsman):** gz pose is ENU; the Pilot is NED. Conversion
   (verified geometrically): `NED.x=ENU.y`, `NED.y=ENU.x`, `yaw_ned = π/2 − yaw_enu`.
   Buoys/spawn are placed in ENU: windward NED(15N,0E) → gz pose `(0,15,0)`; boat
   spawns at gz yaw `0.5236` (= NED 60°, close-hauled) because the plugin seeds
   xdyn's initial orientation from the gz spawn pose.
6. **Env recap** (all in `run_regatta.sh`): source `/opt/ros/jazzy/setup.bash` +
   `/lotusim_ws/install/setup.bash`; `GZ_SIM_SYSTEM_PLUGIN_PATH`, `GZ_SIM_RESOURCE_PATH`,
   `PYTHONPATH=.../src/regatta_agents`; xdyn `-s rk4 --dt 0.001`; order xdyn → helmsman → gz.

## 5. The blocker (precise, with data)

The boat sails but **weathervanes to a ~90–110° equilibrium and will not point up
to the ~60° close-hauled beat**. Debug data (`HELM_TEST` = constant rudder, Pilot
bypassed — see Section 6):

- **Constant +25° helm, coarse comm (0.05):** NED yaw oscillates ±1.3 rad/s around
  90° — numerical, fixed by (4).
- **Constant +25° helm, fine comm (0.005):** NED yaw settles at ~104° with `r≈0`
  and *stays* — a constant rudder produces an **equilibrium heading**, not a
  continuous turn. So sail/hull yaw moment balances the rudder at ~104°.
- **Under the Pilot (either helm sign):** the boat runs off to ~89–111° and sails
  away from the windward mark (drifts East, or South with large leeway).

**Ruled out:** frame geometry (verified), control logic (proven offline), DDS /
pipeline (working). **Ambiguous / unresolved:** the effective rudder sign in the
gz path appeared *opposite* to the offline `HELM_SIGN=-1`, but flipping it did not
produce a beat either — which is why sign-guessing must stop and the round-trip
diff (Section 7) must start.

## 6. How to run everything

```bash
# --- OFFLINE ORACLE (the proven reference; ~3 min, Docker) ---
cd ~/src/lotusim-lab/LOTUSim-regatta/offline && python3 oracle.py
#   expect: "marks reached 2/2 | tacks 3 ... ORACLE PASS"

# --- UNIT TESTS (Pilot brain; host) ---
cd ~/src/lotusim-lab/LOTUSim-regatta/src/regatta_agents \
  && rtk proxy uv run --no-project --with pytest python -m pytest test/test_pilot.py -q

# --- GZ STACK, headless smoke (rounds both marks?) ---
cd ~/src/lotusim-lab/LOTUSim-regatta
timeout 240 bash scripts/run_regatta.sh 120 smoke > /tmp/run.log 2>&1; docker rm -f regatta 2>/dev/null
head -4 /tmp/run.log                              # oracle verdict + closest approaches
sed -n '/HELM (tail)/,$p' /tmp/run.log | tail -12 # helmsman debug (enu/ned pose, cmds, pilot state)

# --- GZ STACK, hold mode + CONSTANT-RUDDER probe (diagnose the rudder) ---
HELM_TEST=25 timeout 140 bash scripts/run_regatta.sh 30 hold > /tmp/run.log 2>&1; docker rm -f regatta 2>/dev/null
sed -n '/HELM (tail)/,$p' /tmp/run.log | tail -12
```

Debug tooling currently in `helmsman.py`: `HELM_TEST` env (constant helm in deg,
bypasses the Pilot) and a throttled debug print in `_control` (enu pose, ned pose,
r, pilot wp/tack/tacking, sheet, helm). Remove both once the beat works.

## 7. Investigation plan — Option A (bounded)

**Goal: find where the gz round-trip diverges from the offline one.** Both drive
the *same* `xdyn-for-cs` + `focus_v2.yaml`; the offline one beats. So the delta is
in the gz integration layer. Instrument and diff — do **not** guess.

1. **Command path — does xdyn receive the same commands?** Log, per step, the
   exact `{sheet, helm, Dt}` the gz plugin sends to xdyn, and compare to what
   `offline/ws.py::step()` sends for the same NED state. Check: is `Dt` really
   0.005 (min(--dt, comm))? Is the command JSON identical (`mainsail(sheet)` /
   `rudder(helm)`)? Is the helm *sign* preserved end-to-end?
   - Tap xdyn's side: the plugin talks to `ws://127.0.0.1:12345`; you can proxy /
     log the frames, or add prints in a throwaway xdyn wrapper.
2. **State path — is the state round-trip loss-free?** The plugin converts NED→ENU
   for gz, then the helmsman converts ENU→NED back. Feed a *known* xdyn NED state,
   read the helmsman's reconstructed NED, and confirm they match bit-for-bit
   (position, heading, and especially **yaw-rate sign** — the Pilot's `-KD·r` term
   inverts control if r's sign is wrong).
3. **Force sanity — is the sail actually driving in gz?** In the failing runs the
   boat showed large leeway / low speed. Confirm the aerodynamic (sail) force is
   applied in the gz co-sim as it is offline (same apparent wind, same sheet). If
   the sail barely drives, the boat can't build the speed the rudder needs → it
   weathervanes. Compare boat speed offline vs gz on the same heading/sheet.
4. **Initial condition — where does xdyn's start state come from in gz?** The
   plugin seeds it from the gz spawn pose (confirmed: spawn yaw drives initial
   heading). Verify initial velocity: offline starts at u=0.8; does gz start at
   rest? A rest start bow-to-a-bad-angle can stall before way builds.
5. **Control cadence (R1).** Offline = 200 Hz lockstep; gz = ROS ~30 Hz + gz comm
   ~ (real_time_update_rate). Once 1–4 are clean, tune the helmsman rate / PD gains
   for the async regime if the beat is marginal.

**Rule:** reproduce each finding against the offline oracle (the known-good). The
moment gz and offline send xdyn the same state+command+Dt and read back the same
state, the boat will beat — because the physics already does.

## 8. Strategic fork (if A proves a deep hole)

| | **A. Fix gz integration** | **B. Offline xdyn core + light Unity bridge** |
|---|---|---|
| Physics | xdyn via gz plugin (to fix) | xdyn direct (**already proven**) |
| Student API | ROS `vessel_cmd_array` (LOTUSim-native) | the oracle's Python API |
| Unity render | gz→render_plugin (native) | custom pose bridge from the oracle |
| Fidelity to LOTUSim | ✅ the real stack | ⚠️ diverges from LOTUSim |

Recommendation: **A, bounded** (Section 7). Keep **B** as the fallback — it reuses
the proven xdyn path and only needs a custom Unity pose feed.

## 9. File map

```
LOTUSim-regatta/
├── offline/
│   ├── ws.py                 # websocket + docker + step() helpers (proven, from _offline/cosim.py)
│   └── oracle.py             # run_lap(): the PROVEN W/L beat (2/2 marks, 3 tacks)
├── src/regatta_agents/regatta_agents/
│   ├── pilot.py              # pure NED control brain (shared offline+ROS); unit-tested
│   └── helmsman.py           # ROS node: gz pose (ENU→NED) -> Pilot -> vessel_cmd_array  [has HELM_TEST/debug]
├── assets/
│   ├── worlds/regatta.world  # gz world: gravity 0, 4 LOTUSim plugins, 2 buoys, focus_v2; max_step_size 0.005
│   └── models/regatta_buoy/  # cylinder placeholder (Blender mesh export = T7, not started)
├── scripts/
│   ├── run_regatta.sh        # xdyn → helmsman → gz, headless; modes: hold|smoke; env HELM_TEST
│   └── smoke_rounds_marks.py # gz pose oracle: rounds both marks?
└── docs/{design,plans}/…, HANDOFF-gz-beat.md (this file)
```

Related host files: `~/src/lotusim-lab/LOTUSim/assets/models/focus_v2/focus_v2.yaml`
(the tuned model), `~/src/lotusim-lab/LOTUSim/physics/` (patched `libx-dyn.so`,
`xdyn-for-cs`), `~/src/lotusim-lab/_offline/cosim.py` (the original proven harness).
