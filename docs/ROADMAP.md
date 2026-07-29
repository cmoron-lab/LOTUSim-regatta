# Roadmap

**State as of 2026-07-26.** The full lap runs natively on Ubuntu 24.04 / WSL2 at
RTF ≈ 1.0: the reference pilot beats up to the windward mark, rounds it leaving it
to port, runs back down, rounds the leeward mark and starts another lap. Verified
headless (`SMOKE PASS`), in the LOTUSim web UI, and rendered in the Unity editor on
Linux — the last two **simultaneously from one stack**, since both are consumers of
the same ROS topics rather than competing publishers.

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
3. Deserves its own design doc before any code.

## 2. Rendering: Unity and the web UI

**Unity on Linux/WSL2 — de-risked, 2026-07-26.** The editor Play mode was blocked
outright: `Assets/Editor/BuildRegatta.cs` referenced `UnityEditor.OSXStandalone` from
`Assets/Editor/`, i.e. from `Assembly-CSharp-Editor`, where a single compile error
stops the whole editor. Fixed with per-OS guards plus a Linux build target
(`bc7b63f` in `LOTUSim-Unity-modules`), verified by a cold batchmode import: 0
`error CS`. The Regatta scene then ran from the editor against a live stack.

`ros_tcp_endpoint` is now built by `install.sh` — it came from the Docker image
before, so the documented `UNITY=1` procedure would have failed on a fresh clone.

**Windows/HDRP production cutover completed, 2026-07-29.** The canonical Windows
project now runs Unity `2023.1.20f1` with HDRP `15.0.7` and the native foam wake.
The recorded evidence is EditMode `41/41`, a successful Windows player build
with 9 warnings, and accepted mono-boat visual validation. A separate Windows
player containing the existing `Launcher` and `defenseScenario` scenes also
builds successfully; their visual non-regression and multi-boat foam remain
unqualified.

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
- **Drive the helmsman off the pose stream** instead of a 30 Hz wall-clock timer.
  The two clocks do not lock, so the trajectory is not reproducible between two runs
  of the same commit — margins moved 11 cm between runs. This is the root cause, and
  fixing it beats widening any threshold.
- **A real start/finish line**: a bounded segment between two marks. Today it is the
  leeward mark's infinite perpendicular, which is why tacks recross it during the
  beat.
- **macOS non-regression.** The Docker wrapper feeds the container by environment
  what a native machine gets from `install.sh`, and has not been run on a Mac since
  the harness was split. Needs the Mac.

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
