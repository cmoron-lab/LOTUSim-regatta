# LOTUSim-regatta

[![License: EPL-2.0](https://img.shields.io/badge/license-EPL--2.0-blue)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Ubuntu_24.04_x86--64-orange)](#not-on-ubuntu-2404-x86-64)

A windward-leeward regatta for a 1 m RC sailboat, simulated for real: the boat
cannot sail into the wind, has to tack, and loses speed when it does.

<!-- Hero: drop a Unity capture at docs/media/regatta-unity.png (the boat on port
     tack, windward buoy ahead), then uncomment:
<p align="center"><img src="docs/media/regatta-unity.png" width="720"
   alt="The Focus V2 beating toward the windward buoy, rendered in Unity"></p>
-->

Built on [LOTUSim](https://github.com/naval-group/LOTUSim): Gazebo orchestrates, an
external **xdyn** process computes every force over a websocket, ROS carries the
commands, Unity renders. A reference pilot sails the full lap around two buoys —
**replacing it with your own navigation algorithm is the point.**

## Which door is yours

| you want to | read |
|---|---|
| **test a navigation algorithm** — install, run, plug your pilot in | [`docs/guide.md`](docs/guide.md) |
| **work on the simulator** — architecture, procedures, platforms, pitfalls | [`docs/reference.md`](docs/reference.md) |
| **work on this as an agent** — what to run as proof, what not to touch | [`CLAUDE.md`](CLAUDE.md) |
| know **where it is going** | [`docs/ROADMAP.md`](docs/ROADMAP.md) |

## Quickstart

Once:

```bash
./install.sh          # ROS 2 Jazzy + Gazebo + the LOTUSim core + this overlay
. ./env.sh            # puts that environment in YOUR shell, and says what it found
```

Both are safe to re-run, and neither touches your `~/.bashrc` or `~/.zshrc` —
which is why `env.sh` is sourced per shell rather than once and forgotten.

Then, in increasing order of ceremony:

```bash
uv run regatta-oracle                   # the physics alone, no gz, no ROS -> ORACLE PASS
./scripts/run_regatta.sh 400 smoke      # the whole thing, asserted        -> SMOKE PASS
./scripts/run_regatta.sh 900 hold       # the same run, left up to watch
UNITY=1 ./scripts/run_regatta.sh 900 hold                    # rendered in Unity
```

`smoke` counts in **simulated** seconds — a faster machine shortens the wait, never
changes the verdict. `hold` counts in wall seconds, because it only sleeps.
Everything else — the modes, the switches, the logs — is in
`./scripts/run_regatta.sh -h`.

## Architecture

```
                        ┌─────────────────────────┐
                        │  xdyn-for-cs (physics)  │   NED frame, ws :12345
                        │  focus_v2.yaml model    │   stateless: full state
                        └───────────▲─────────────┘   round-trips every step
                                    │ websocket  (gz is the CLIENT)
                        ┌───────────┴─────────────┐
                        │ gz physics_interface_   │   NED ↔ ENU conversion
                        │ plugin (gz physics OFF) │
                        └───────────┬─────────────┘
                                    │ poses
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
      ros-tcp-endpoint      /lotusim/poses           gz pose topic
        :10000 → Unity      → web UI                 → helmsman → Pilot
                                                     → vessel_cmd_array
```

- **gz orchestrates; it does not simulate** — its own physics is off, every force comes from xdyn.
- **xdyn is stateless** — the complete vessel state round-trips on every step.
- **Two step sizes, neither tunable** — communication at `0.01` s, integration at `--dt 0.005`; `0.02` diverges.

Three frames, three unsynchronised clocks, and why each matters:
[`docs/reference.md`](docs/reference.md).

## Repo map

```
install.sh  env.sh            bring-up, and the environment it brings up
src/regatta/                  PURE python, stdlib only: pilot.py (the brain),
                                xdyn.py (co-sim client), oracle.py, probes/
src/regatta_agents/           the ROS2 edge: helmsman.py, the node around the brain
scripts/                      run_regatta.sh (entry point, see -h) + the gz gate
tests/                        pytest for the pure core
assets/                       world, buoy model, scenario wind, Blender sources
../LOTUSim-Unity6-modules/    Unity 6 renderer: scene, scripts, shaders, tests
docs/                         guide, reference, roadmap, design notes, measurements
```

The split that matters: `src/regatta` needs **nothing but the standard library**,
which is what lets the ROS node import it from the system interpreter — `rclpy` and
`gz-transport` come from apt, not PyPI.

## Upstream fixes (naval-group/LOTUSim)

Found by diffing the round trip bit-for-bit between the offline oracle and the gz
stack at each layer boundary — all three merged upstream 2026-07-13.

| Issue / PR | Fix |
|---|---|
| [#27](https://github.com/naval-group/LOTUSim/issues/27) / [#28](https://github.com/naval-group/LOTUSim/pull/28) | xdyn quaternion `j`/`k` swapped on receive — pre-existing, invisible at identity attitude |
| [#32](https://github.com/naval-group/LOTUSim/issues/32) / [#33](https://github.com/naval-group/LOTUSim/pull/33) | NED↔ENU attitude conversion missing the FLU↔FRD body-frame swap — root cause of the boat not holding a beat |
| [#34](https://github.com/naval-group/LOTUSim/issues/34) / [#35](https://github.com/naval-group/LOTUSim/pull/35) | co-sim `t` carried the step duration in ms instead of absolute sim time — freezes any time-dependent forcing; prerequisite for swell |

## Not on Ubuntu 24.04 x86-64?

Anywhere docker runs, the same stack runs in an Ubuntu 24.04 container —
`run_regatta.sh` wraps itself whenever this machine is not what `install.sh`
targets. Another x86-64 Linux runs it natively; Apple Silicon and arm64 run it
emulated (Rosetta/qemu), because `xdyn-for-cs` ships as an x86-64 binary. Verified
on Apple Silicon: the same `SMOKE PASS`, rounding the same two marks within
centimetres of the native run. Image recipe and the two traps that path has in
[`docs/reference.md`](docs/reference.md).

License: EPL-2.0.
