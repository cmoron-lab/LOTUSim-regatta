# Roadmap

**State as of 2026-07-30.** The full lap runs natively on Ubuntu 24.04 / WSL2 at
RTF ≈ 1.0: the reference pilot beats up to the windward mark, rounds it leaving it
to port, runs back down, rounds the leeward mark and starts another lap. Verified
headless (`SMOKE PASS`), in the LOTUSim web UI, and rendered in the Unity editor on
Linux — the last two **simultaneously from one stack**, since both are consumers of
the same ROS topics rather than competing publishers.

**Also verified on macOS / Apple Silicon (2026-07-30)**, through the container path:
same `SMOKE PASS`, marks left to port within a centimetre of the native run. Two
things were settled there and both are recorded in `measurements/2026-07-30-macOS.md`:
the simulation is already at real time and has no headroom left to win, while a
renderer attached at native Retina resolution takes 87 % of the clock. And the pilot
now ticks on the **simulated** clock, so a lap no longer depends on who is watching
it — the trajectory held to 1 cm across a 5.5× change in RTF.

The repository is a `uv` project whose core needs neither ROS nor gz, so a pilot can
be written and iterated without installing either.

## 1. Multi-competitor regatta

Racing one algorithm against another is the point of the project, and the plumbing
is further along than it looks.

**Already multi-vessel, established by inspection:**

- gz runs a `MultiAgentSystem` plugin;
- the ROS interfaces are **arrays** — `VesselCmdArray`, `VesselPositionArray`;
- each vessel is an `<include>` carrying its own `<lotus_param>` block with **its own
  xdyn URI**, so vessels are not forced to share a physics server;
- the co-simulation protocol's payload is `"states": [...]`, a list;
- Unity already ships a Photon session layer — `Assets/Scripts/MultiUser/`
  (`Launcher.cs`, `GameManager.cs`, `PlayerManager.cs`), `Scenes/Launcher.unity`, a
  player/spectator distinction and an offline fallback. It synchronises **presence**,
  not physics.

**The architecture that follows.** This repository is the *client*: one instance, one
pilot, and that is clean. LOTUSim/gz is the *server*: world, spawning, clock, topics.
**xdyn stays behind the server and stays authoritative** — client-side physics would
mean two competitors do not face identical conditions, which destroys the very
comparison the project exists for.

**Open, in order:**

1. **Measure**: does one `xdyn-for-cs` accept N concurrent websocket connections, or
   is it one process per vessel? It is stateless and its model yaml declares
   `bodies:` in the plural, so both are plausible. One process per vessel is the
   no-unknowns fallback: ≈ 2.4 ms per rk4 substep on 8-16 cores holds a small fleet.
2. **N pilots in the helmsman.** `Pilot` is already per-vessel and stateful, so this
   is N instances rather than a redesign.
3. **Give the state stream a transport fit for racing.** Established 2026-07-30 by
   reading the code, not by inference:
   - the core publishes vessel state `RELIABLE`, `TRANSIENT_LOCAL`, depth 10
     (`render_interface/src/ros_interface.cpp:36`). A reliable queue is the wrong
     shape for a state broadcast: one slow competitor makes the middleware
     retransmit and can hold the producer back, and the client renders stale states
     in order instead of the freshest one. A state feed wants `BEST_EFFORT`,
     `KEEP_LAST(1)`, `VOLATILE` — latest wins, never retransmit.
   - **a native ROS client can already choose that for itself** (DDS lets a
     `BEST_EFFORT` reader subscribe to a `RELIABLE` writer). **A Unity client cannot**:
     the real subscriber is `ros_tcp_endpoint`, which hardcodes
     `RELIABLE`+`TRANSIENT_LOCAL` (`subscriber.py:45`) and exposes only `ROS_IP` and
     `ROS_TCP_PORT`. That bridge belongs to Unity Robotics, not to LOTUSim.
   - **the state carries no velocity.** xdyn knows `u,v,w`; nothing publishes it, so
     Unity components each re-derived speed from frame-to-frame position deltas —
     the defect fixed on 2026-07-30. A client that must extrapolate between packets,
     which is what network play is, needs velocity in the state.
   - note ROS 2 is **already UDP** (FastDDS); the TCP is only the Unity leg, and
     only because Unity has no DDS stack. The gz↔xdyn websocket is correctly TCP —
     it is synchronous request/response where a lost message breaks the step.
4. **Guarantee the compute budget.** gz never drops a physics step; when it cannot
   keep up it slows the clock. A simulator should; a race cannot run in slow motion.
   So the server must hold RTF ≥ 1 **with N vessels** — one blocking websocket round
   trip per vessel per step — and it must not share a machine with a renderer
   (`measurements/2026-07-30-macOS.md`). This is sizing, not code.
5. Deserves its own design doc before any code.

## 2. Rendering: Unity and the web UI

**Unity on Linux/WSL2 — de-risked, 2026-07-26.** The editor Play mode was blocked
outright: `Assets/Editor/BuildRegatta.cs` referenced `UnityEditor.OSXStandalone` from
`Assets/Editor/`, i.e. from `Assembly-CSharp-Editor`, where a single compile error
stops the whole editor. Fixed with per-OS guards plus a Linux build target
(`bc7b63f` in `LOTUSim-Unity-modules`), verified by a cold batchmode import: 0
`error CS`. The Regatta scene then ran from the editor against a live stack.

`ros_tcp_endpoint` is now built by `install.sh` — it came from the Docker image
before, so the documented `UNITY=1` procedure would have failed on a fresh clone.

**Unity 6 production cutover completed, 2026-07-31.** The canonical renderer is
now `LOTUSim-Unity6-modules` on `main`, using Unity `6000.3.21f1` with HDRP
`17.3.0`. The Regatta scene, Addressables, foam wake, render-budget controls,
and native arm64 macOS player are ported and visually validated. The Unity 2023
project and its broader defense-demo content are retired from the Regatta
production path; their dated measurements remain as historical evidence.

**Web UI.** Works, and is not a priority. Five upstream defects met along the way:

- fallback paths contain a **literal `~`**, which Node never expands, so
  `GET /scenarios` answers 500 — and that 500 also empties the instance list,
  because the dashboard fetches both together;
- the models fallback spells the directory `src/lotusim` in lowercase;
- `lotusim ui` hardcodes `~/.nvm`, wrong when nvm honours `XDG_CONFIG_HOME`;
- instance auto-discovery never removes stale instances;
- **one spectator per instance** — clients are indexed by instance name and the
  second is silently ignored, so a second browser tab receives nothing.

The broadcast period is also hardcoded at 2000 ms, unusably coarse for anything that
manoeuvres (70 cm between frames at 0.35 m/s, and a tack is invisible); our fork
makes it `WS_BROADCAST_MS`. **Plan:** keep our own UI alive, merging our work with
upstream, and eventually build something modern rather than patching theirs. Not now.

## 3. Keyboard and gamepad helm in Unity

Sailing the boat by hand next to an algorithm sailing its own is the clearest way
to show what the simulator is.

**Keyboard path built, 2026-07-27** — differently from the sketch above's "a ROS
node": the input device lives where Unity lives (Windows), so `ManualHelm.cs`
captures it there and publishes on `/lotusim/manual_cmd_array`, and the
**helmsman arbitrates** — a fresh manual message overrides the Pilot, silence
hands the helm back (dead-man switch, no mode topic). The helmsman stays the
only publisher on `vessel_cmd_array`, so nothing downstream changes and the
before-gz launch-order constraint is untouched.

**Live-verified on the Windows editor, 2026-07-27** — sailed with Thrustmaster
T-Rudder pedals (helm, one toe brake per side) and a HOTAS Warthog stick
(sheet). "Gamepad" resolved by generalisation: `ManualHelm` binds any two
physical axes on any device (in-game `B` calibration, excursion-based), so a
gamepad stick is just another bind. The Windows→WSL2 endpoint path works over
plain `127.0.0.1` (WSL2 forwards localhost).

## Smaller, and worth doing

- **Select the pilot class by ROS parameter.** Today a user edits `helmsman.py` to
  run their own. This is the natural next step for the audience the guide addresses.
- **A real start/finish line**: a bounded segment between two marks. Today it is the
  leeward mark's infinite perpendicular, which is why tacks recross it during the
  beat.

## Standing notes

- `LOTUSim@regatta-base` = upstream `new_main` + the focus_v2 model + patched xdyn
  binaries (pending naval-group/LOTUSim-Xdyn#2) + composable `--assets-path`
  (pending naval-group/LOTUSim#47). Each temporary layer disappears when its upstream
  PR lands; the branch should melt back into upstream.
- **The boat cannot be brought to rest.** The sail polar has no stall regime
  (`Cl = 0.80` at 10° of incidence), so no trim stops her — measured, three
  candidates, in `measurements/2026-07-WSL.md` Q4. Stopping her is a change to the
  sail model, not to the pilot.
- Root blends (`~/src/lotusim-lab/*.blend`) are working copies; versioned sources
  live in `assets/blend/`.
