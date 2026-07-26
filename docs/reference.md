# Developer reference

For whoever works **on** the simulator. If you came to plug in a navigation
algorithm, `guide.md` is your door; if you are an agent, start from `CLAUDE.md`.

Everything here is something you cannot deduce by reading the code, or something
that cost someone an hour. Numbers live in `measurements/2026-07-WSL.md`; the
reasoning behind decisions lives in `design/`.

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
        :10000 → Unity      → web UI backend         → helmsman → Pilot
                                                     → vessel_cmd_array
```

**gz orchestrates; it does not simulate.** `regatta.world` sets
`<gravity>0 0 0</gravity>` and gz's own physics is off. gz owns the clock, the
scene, the pose broadcast and the render bridge. Every force in the simulation
comes from xdyn.

**xdyn is an external server, and gz is its client.** `xdyn-for-cs` listens on
`ws://127.0.0.1:12345`; the vessel declares that URI in its `<lotus_param>` block
in the world file. Consequence: **xdyn must be listening before gz starts**, which
is why `regatta_stack.sh` launches it first and waits.

**xdyn is stateless.** The complete vessel state — position, attitude quaternion,
both velocity triples — round-trips over the websocket on every communication step.
xdyn remembers nothing between calls. Consequence: there is no physics state to
save, restore or diverge; whoever holds the state owns the truth, and that is the
caller.

**The offline oracle is a second client of the same API**, not a bypass. It speaks
the identical co-simulation protocol with no gz and no ROS, which is what makes it
usable as ground truth: when the two disagree, the difference is in the layers gz
adds, and you can bisect them.

## Frames, and the conversions that bit us

| where | frame |
|---|---|
| xdyn | **NED** — x North, y East, z **Down**; body x forward, y starboard, z down (FRD) |
| gz | **ENU** — x East, y North, z **Up**; body x forward, y **port**, z up (FLU) |
| Unity | y up, z forward |

Two of the three upstream bugs this project found were conversion bugs, and both
were **invisible at identity attitude** — they only appear once the boat heels and
turns:

- the quaternion's `j`/`k` swapped on receive
  ([#27](https://github.com/naval-group/LOTUSim/issues/27));
- the NED↔ENU attitude conversion missing the **FLU↔FRD body-frame swap**, which is
  what stopped the boat holding a beat
  ([#32](https://github.com/naval-group/LOTUSim/issues/32)).

Practical consequence when reading code: a position conversion is a coordinate
swap (`NED.x = ENU.y`, `NED.y = ENU.x`), but an **attitude** conversion is that
*plus* the body-frame handedness change. Getting only the first right produces a
boat that looks fine until it turns.

## Clocks and step sizes

Three clocks run, and **no two of them lock**:

| clock | who | note |
|---|---|---|
| simulated time | gz, stamped on every pose | the only one a verdict may depend on |
| wall time | the machine | RTF ≈ 1.0 native, ≈ 1.01 under Rosetta |
| the helmsman's timer | a 30 Hz ROS wall-clock timer | **not** driven by the pose stream |

The last one is why **a trajectory is not bit-reproducible between two runs of the
same commit**: the control ticks on wall time while the physics advances on the sim
clock, and the phase between them drifts. Two runs of the same code gave rounding
margins 11 cm apart. Any gate written against a tight threshold is one bad run from
a false failure — which is why the smoke gate now asks "was the mark passed and
left to port", a question that does not care about centimetres.

Two **independent** step sizes:

- **communication step** `0.01 s` — one gz↔xdyn round trip, set in the world's
  `max_step_size`;
- **integration step** `--dt 0.005` (solver `rk4`) — xdyn substeps the
  communication step internally.

`--dt 0.02` **diverges** (NaN, then gz aborts). This is a numerical requirement,
not a tuning preference: do not raise it to buy speed. `rkck` is also forbidden —
it needs a monotonic clock the co-simulation does not provide.

Cost model, measured: `ms/trip ≈ 1.3 + 2.4 × substeps`. The fixed 1.3 ms is the
websocket round trip; the rest is integration. **The cost is in the substep, not
the transport**, so batching communication buys nothing.

## The command path

The helmsman publishes `lotusim_msgs/msg/VesselCmdArray` on
`/lotusim/vessel_cmd_array`, each entry carrying a JSON `cmd_string`:

```json
{"mainsail(sheet)": 0.19, "rudder(helm)": -0.31}
```

The keys are xdyn command signals, declared per vessel in the world's
`<control_surfaces>` block. Both are angles in radians.

**Helm sign** (measured, not assumed): **negative turns to starboard**, positive to
port, clamped to ±35°. **Sheet**: 0 is hauled flat amidships, larger is eased out,
with a floor of 4° — which is *not* "sails luffing", see the finish-behaviour note
below.

The publisher uses `TRANSIENT_LOCAL` durability. This is not a style choice: it is
compatible with every subscriber, and a volatile publisher is **silently rejected**
by `ros_tcp_endpoint` with an incompatible-QoS warning you will not see unless you
look. It also means Unity pressing Play mid-run gets the last command immediately.

The helmsman must be up **before** gz: without a command, xdyn answers "Unable to
find signal" and the gz plugin crashes parsing the reply.

## A physics limit worth knowing

**The boat cannot be stopped.** `focus_v2.yaml`'s sail polar gives `Cl = 0.80` at
10° of incidence and never stalls, so no combination of sheet and helm brings her
to rest: head to wind with the sheet hauled flat she still settles at 9.8° off the
wind making 0.28 m/s. Heaving to is not available in this model.

Consequence for the reference pilot: at the last mark it starts a new lap rather
than stopping, because sailing on is the only behaviour that keeps her on the
course area. Stopping her would need a stall branch in the sail model, not a change
to the pilot. Three trims were measured; see `measurements/2026-07-WSL.md`, Q4.

## Procedures

All of them assume the environment. `. ./env.sh` works in bash and zsh, writes
nothing to your rc files, and the harness sources it by itself.

### The offline oracle — physics ground truth

```bash
. ./env.sh && uv run regatta-oracle
# xdyn_dt 0.001 | comm_dt 0.005 | marks reached 2/2 | tacks 3 | dur 189s
# ORACLE PASS
```

~10 min of wall time: the oracle runs at RTF 0.39 because of the fine `--dt 0.001`
it uses on purpose. Knobs: `COMM_DT` and `XDYN_DT` to A/B the step sizes.

### The smoke gate — the full gz stack, headless

```bash
./scripts/run_regatta.sh 400 smoke
# windward: rounded, left to port by 1.70 m
# leeward: rounded, left to port by 1.79 m
# SMOKE PASS
```

The argument is a budget in **simulated** seconds. A full lap is ≈ 243 of them, so
~4 min of wall time at RTF ≈ 1. It refuses to start if anything already publishes
on the world's topics.

### A run to watch

```bash
./scripts/run_regatta.sh 900 hold          # ~5 laps
UNITY=1 timeout 1000 bash scripts/run_regatta.sh 900 hold
```

### The web UI

Two services, each in its own shell, both needing **Node 18** — `rclnodejs` is a
native addon that does not build against Node 24's C++20 headers.

```bash
# backend, port 5000
export NVM_DIR="$HOME/.config/nvm"; . "$NVM_DIR/nvm.sh"; nvm use 18
. /path/to/LOTUSim-regatta/env.sh
export LOTUSIM_MODELS_PATH="$LOTUSIM_PATH/assets/models"
export LOTUSIM_SCENARIOS_PATH="$LOTUSIM_PATH/assets/scenarios"
export WS_BROADCAST_MS=100
cd LOTUSim-UI-backend && npm run dev

# frontend, port 5173
cd LOTUSim-UI-frontend && npm run dev
```

Then open `http://localhost:5173` and pick the `lotusim` instance.

Five things to know, all upstream defects rather than configuration mistakes:

- the backend's fallback paths contain a **literal `~`**, which Node never expands,
  so `GET /scenarios` answers 500 — and because the dashboard fetches scenarios and
  instances together, that 500 also empties the instance list. Exporting the two
  `LOTUSIM_*_PATH` variables above is the workaround.
- the models fallback also spells the directory `src/lotusim` in lowercase.
- `lotusim ui` hardcodes `~/.nvm`, which is wrong when nvm honours
  `XDG_CONFIG_HOME`.
- instance auto-discovery never removes stale instances.
- **one spectator per instance**: the backend indexes clients by instance name and
  silently ignores the second (`if (!this.clientNameWsMapping.get(...))`), so a
  second browser tab receives nothing.

The broadcast period is hardcoded at 2000 ms upstream — unusably coarse, since a
vessel at 0.35 m/s moves 70 cm between frames and a tack is invisible. Our fork
makes it `WS_BROADCAST_MS`.

Protocol note if you write your own client: the websocket sends nothing until the
client announces itself with `{"instance": "lotusim"}`.

## Platforms

### Ubuntu 24.04, including WSL2 — the reference platform

Native. `./install.sh` clones `LOTUSim@regatta-base` into `~/lotusim_ws`, installs
ROS 2 Jazzy and Gazebo Harmonic, builds the core, builds this repository as a colcon
overlay, and syncs the `uv` environment. Requirements: Ubuntu 24.04 (Jazzy) and
**x86-64** — the shipped `physics/xdyn-for-cs` is an x86-64 binary.

Scenario assets never get copied into the core: they reach gz through
`lotusim --assets-path`.

### Everything else — Docker

ROS and gz do not run natively on Apple Silicon, so the same stack runs in a
container (`--platform linux/amd64`, under Rosetta). Any other Linux lands here too:
`scripts/run_regatta.sh` routes on `install.sh`'s own rule — Ubuntu 24.04 **and**
x86-64 — rather than on `uname -s`, because a Fedora host or an arm64 Ubuntu cannot
run the native path either. Force either side with `RUNNER=native|docker`.

**Status: unverified since the harness was split.** The container gets by
environment (`LOTUSIM_WS`, `LOTUSIM_PATH`, `PYTHONPATH`) what a native machine gets
from `install.sh`, and that branch has not been run on a Mac since it was written.

Everything runs inside `lotusim:focus-v2`, built from `LOTUSim@regatta-base`
(upstream `new_main` with the physics fixes merged, plus the focus_v2 model, the
patched xdyn binaries and the composable `--assets-path`) and `ros_tcp_endpoint`.
The image carries two git-invisible `docker commit` layers, so it can only be
rebuilt, never derived from a Dockerfile. Run this inside a throwaway container of
the previous image:

```bash
# 1. replace the whole source tree (packages get renamed upstream; overlaying
#    would leave dead ones behind), from the regatta base branch
docker exec <container> rm -rf /lotusim_ws/src/LOTUSim
git -C LOTUSim archive regatta-base | docker cp - <container>:/lotusim_ws/src/LOTUSim
# 2. build IN THE SAME container the image is committed from
#    (radar_sensor needs: apt-get install -y ros-jazzy-radar-msgs)
docker exec <container> bash -lc \
  'source /opt/ros/jazzy/setup.bash && cd /lotusim_ws && \
   colcon build --merge-install'
# 3. freeze the layer -- docker commit KEEPS the container entrypoint: create the
#    container without --entrypoint, or restore ENTRYPOINT ["/ros_entrypoint.sh"]
docker commit <container> lotusim:focus-v2
```

Backup tag before the quaternion fix: `focus-v2-pre-quatfix`.

### Performance

| config | comm step | xdyn `--dt` | RTF (Rosetta) | RTF (native x86-64) |
|---|---|---|---|---|
| baseline | 0.005 | 0.001 | ≈ 0.26 | ≈ 0.39 |
| current | 0.01 | 0.005 | ≈ 1.01 | ≈ 1.0 |

Native is **not** the 3-4× the port assumed: one rk4 substep costs ≈ 2.4 ms on a
Ryzen 7 5800X against ≈ 3.1 ms under Rosetta, a 1.3× gain. This is why the smoke
gate's budget is in simulated seconds — RTF is a property of the machine, and it
must change how long you wait, never the verdict.

## Pitfalls

Listed by **symptom**, because that is what you arrive with.

| symptom | cause | fix |
|---|---|---|
| the gate passes in 17 simulated seconds for a 240 s lap | an orphaned gz from an earlier run still publishes on the same topics; the pose stream carries two boats and the gate counts both marks at once | kill the process **tree** (`lotusim run` spawns gz as a child), and refuse to start when the world's topics already have a publisher — both are in `regatta_stack.sh` |
| your own shell dies when you kill the simulation | `pkill -f`/`pgrep -f` matches any process whose command line contains the pattern, starting with the shell that ran the command | ask gz instead: `gz topic -l \| grep -q "^/world/lotusim/"` |
| `frame: connection closed` right after a clean start | a previous xdyn still holds port 12345; the new one died of "address already in use" while the client happily connected to the **old** server, silently using the wrong model | `xdyn.launch_xdyn` pre-binds the port and refuses; note it sets `SO_REUSEADDR`, or sockets in `TIME_WAIT` read as busy for a minute |
| `no such file or directory: <cwd>/local_setup.sh` | a ROS `setup.bash` sourced under zsh: `${BASH_SOURCE}` is empty there, so the prefix resolves to `$PWD` | source the `.zsh` flavour — `env.sh` picks it for you |
| the boat starts in irons, or the wind is not what you set | a second YAML **replaces** the whole `environment models:` section rather than merging into it | restate the complete section, `no waves` included, in the conditions file |
| `ImportError: regatta.pilot` in `/tmp/helm.log` | the ROS node runs on the system interpreter and needs `src/` on `PYTHONPATH` | `. ./env.sh` — and if you changed it, check the `PYTHONPATH` block |
| tooling reports a process is gone when it is running | the `rtk` hook summarises `ps`/`grep` output | re-run through `rtk proxy ps ...` before concluding |

## Where the rest lives

- **Numbers and how they were measured**: `measurements/2026-07-WSL.md` — the
  environment-section semantics, whether the gz path needs a seeded initial state,
  native performance, why the boat cannot be stopped.
- **Decisions and their reasoning**: `design/`.
- **Executed plans and closed investigations**: `archive/`.
- **Unity scene recipe**: `unity-scenario.md`.
