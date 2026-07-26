# LOTUSim-regatta

A windward-leeward regatta for a Focus V2 RC sailboat on
[LOTUSim](https://github.com/naval-group/LOTUSim) — Gazebo orchestrating, an
external **xdyn** process computing every force over a websocket, ROS carrying the
commands, and Unity or a web map rendering it.

A reference pilot sails the full lap around two buoys. **Replacing it with your own
navigation algorithm is the point**: the physics is real enough that a boat cannot
sail into the wind, has to tack, and loses speed when it does.

## Which door is yours

| you want to | read |
|---|---|
| **test a navigation algorithm** — install, run, plug your pilot in | [`docs/guide.md`](docs/guide.md) |
| **work on the simulator** — architecture, procedures, platforms, pitfalls | [`docs/reference.md`](docs/reference.md) |
| **work on this as an agent** — what to run as proof, what not to touch | [`CLAUDE.md`](CLAUDE.md) |
| know **where it is going** | [`docs/ROADMAP.md`](docs/ROADMAP.md) |

## Quickstart

Ubuntu 24.04 including WSL2, x86-64. Once:

```bash
./install.sh          # writes nothing to your ~/.bashrc or ~/.zshrc
. ./env.sh            # bash or zsh; the harness sources it by itself
```

Then, in increasing order of ceremony:

```bash
uv run regatta-oracle                   # physics bench, no gz, no ROS  -> ORACLE PASS
./scripts/run_regatta.sh 400 smoke      # full stack, headless, asserted -> SMOKE PASS
./scripts/run_regatta.sh 900 hold       # a run to watch (~5 laps)
UNITY=1 timeout 1000 bash scripts/run_regatta.sh 900 hold    # rendered in Unity
```

The numeric argument is a budget in **simulated** seconds, never wall seconds: a
faster machine changes how long you wait, never the verdict.

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

- **gz orchestrates; it does not simulate.** Its own physics is off. Every force
  comes from xdyn, an external process; the gz plugin is xdyn's websocket *client*.
- **xdyn is stateless**: the complete vessel state round-trips on every
  communication step. Nothing is remembered between calls.
- **Two independent step sizes**: the communication step (`0.01` s) and xdyn's
  internal integration step (`--dt 0.005`, `rk4`). `0.02` diverges — a numerical
  requirement, not a preference.

The rest — three frames, three unsynchronised clocks, and why each matters — is in
[`docs/reference.md`](docs/reference.md).

## Repo map

```
LOTUSim-regatta/
├── install.sh                # Ubuntu 24.04 bring-up: core + overlay + uv + Unity bridge
├── env.sh                    # the environment, sourceable from bash or zsh
├── pyproject.toml            # the uv project: src/regatta, zero runtime deps
├── src/regatta/              # PURE python, no ROS: pilot.py (the brain), xdyn.py
│                             #   (co-sim client), oracle.py, probes/{helm,tap}.py
├── src/regatta_agents/       # ROS2 package: helmsman.py, the node around the brain
├── tests/                    # pytest for the pure core
├── assets/{worlds,models}/   # regatta.world, regatta_buoy model
├── assets/conditions/        # scenario wind, layered onto the core model by xdyn
├── assets/blend/             # Blender sources (buoy, boat)
├── unity/                    # C# scripts deployed into LOTUSim-Unity-modules
├── scripts/                  # run_regatta.sh (entry point) + regatta_stack.sh (the
│                             #   sequence), smoke_rounds_marks.py
└── docs/                     # guide, reference, roadmap, design, measurements, archive
```

The split that matters: `src/regatta` needs **nothing but the Python standard
library**, which is what lets it run without ROS installed — and lets the ROS node
import it from the system interpreter. `rclpy` and `gz-transport` come from apt, not
PyPI.

## Upstream fixes (naval-group/LOTUSim)

Found by diffing the round trip bit-for-bit between the offline oracle and the gz
stack at each layer boundary.

| Issue / PR | Fix | Status |
|---|---|---|
| [#27](https://github.com/naval-group/LOTUSim/issues/27) / [#28](https://github.com/naval-group/LOTUSim/pull/28) | xdyn quaternion `j`/`k` swapped on receive — pre-existing, invisible at identity attitude | merged upstream 2026-07-13 |
| [#32](https://github.com/naval-group/LOTUSim/issues/32) / [#33](https://github.com/naval-group/LOTUSim/pull/33) | NED↔ENU attitude conversion missing the FLU↔FRD body-frame swap — root cause of the boat not holding a beat | merged upstream 2026-07-13 |
| [#34](https://github.com/naval-group/LOTUSim/issues/34) / [#35](https://github.com/naval-group/LOTUSim/pull/35) | co-sim `t` carried the step duration in ms instead of absolute sim time — freezes any time-dependent forcing (waves); prerequisite for swell | merged upstream 2026-07-13 |

## macOS

ROS and gz do not run natively on Apple Silicon, so the same stack runs in a
container under Rosetta; `scripts/run_regatta.sh` detects the platform and wraps
itself. **Currently unverified since the harness was split** — see
[`docs/reference.md`](docs/reference.md) for the status and the image rebuild recipe.

License: EPL-2.0.
