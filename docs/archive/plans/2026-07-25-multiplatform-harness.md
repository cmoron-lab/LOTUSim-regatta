# Multi-platform regatta harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the regatta run natively on Ubuntu 24.04 (including WSL2), with macOS kept working through Docker as the special case.

**Architecture:** The harness splits into a platform-agnostic sequence (`regatta_stack.sh`, assumes it runs inside a LOTUSim environment) and a thin entry point (`run_regatta.sh`, execs it directly on Linux or wraps it in `docker run` on macOS). The hand-rolled environment block disappears because `lotusim run --assets-path` now does it. Three open questions are measured on the target machine before the tasks that depend on them.

**Tech Stack:** Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic, bash, Python 3 (rclpy), xdyn co-simulation over websocket, Docker (macOS path only).

**Spec:** `docs/design/2026-07-25-multiplatform-design.md`

## Global Constraints

- Reference platform: **Ubuntu 24.04 → ROS 2 Jazzy + Gazebo Harmonic**. Never `ign`/Fortress.
- Core comes from `LOTUSim@regatta-base` (fork `cmoron-lab/LOTUSim`). It carries the focus_v2 model, the patched xdyn binaries and the composable `--assets-path`.
- **`xdyn --dt 0.005` and the 0.01 comm step are numerical requirements, not tuning.** 0.02 diverges. Do not change them while porting.
- ROS setup scripts are **bash only**. Under zsh they break silently.
- `pkill -f "gz sim"` kills the calling shell too — always capture PIDs and `kill "$pid"`.
- gz ignores SIGTERM: cleanup must use `kill -9`.
- Scenario assets stay in this repo and reach gz via `--assets-path`. Never copy them into the core tree.
- Commit after every task. Conventional Commits, message says *why*.

## File Structure

| File | Responsibility |
|---|---|
| `install.sh` (create) | Bring a clean Ubuntu 24.04 to a working core + overlay |
| `scripts/regatta_stack.sh` (create) | The run sequence. Platform-agnostic, assumes a LOTUSim env |
| `scripts/run_regatta.sh` (rewrite) | Entry point: direct on Linux, `docker run` on macOS |
| `assets/conditions/regatta_conditions.yaml` (create) | Scenario wind, layered onto the core model by xdyn |
| `offline/ws.py` (modify) | Launch xdyn natively instead of through Docker |
| `scripts/smoke_rounds_marks.py` (modify) | Gate on simulated time instead of wall clock |
| `docs/measurements/2026-07-WSL.md` (create) | Recorded answers to the three open questions |

---

### Task 1: Bring up the machine, captured as `install.sh`

**Files:**
- Create: `install.sh`
- Test: manual gate — `lotusim run` starts gz on a core world

**Interfaces:**
- Produces: a working `$HOME/lotusim_ws` (core at `regatta-base`) and this repo built as a colcon overlay. Every later task assumes `lotusim` is on `PATH` and `$LOTUSIM_PATH` / `$LOTUSIM_WS` are set.

- [ ] **Step 1: Check the platform is what we think it is**

```bash
lsb_release -rs        # expect: 24.04
uname -m               # expect: x86_64
```

If `uname -m` is not `x86_64`, stop: the committed `physics/xdyn-for-cs` is an x86-64 ELF and the whole native premise fails.

- [ ] **Step 2: Clone the core at `regatta-base`**

```bash
mkdir -p "$HOME/lotusim_ws/src"
git clone -b regatta-base git@github.com:cmoron-lab/LOTUSim.git "$HOME/lotusim_ws/src/LOTUSim"
```

- [ ] **Step 3: Export the LOTUSim variables and install**

```bash
export LOTUSIM_WS="$HOME/lotusim_ws"
export LOTUSIM_PATH="$LOTUSIM_WS/src/LOTUSim"
export PATH="$LOTUSIM_PATH/launch:$PATH"
sudo -E lotusim install     # ROS 2 Jazzy + gz Harmonic + colcon build; long
```

- [ ] **Step 4: Verify the core runs before touching anything else**

```bash
timeout -s KILL 30 lotusim run lotusim.world 2>&1 | tail -20
```

Expected: the `GZ_SIM_RESOURCE_PATH` banner, then `Running the simulation world: .../assets/worlds/lotusim.world`, and no `Unable to find uri`. gz stays silent at `-v0`; add `--debug` if you need to see it work.

- [ ] **Step 5: Verify the `--assets-path` fix is present on this branch**

```bash
bash "$LOTUSIM_PATH/launch/tests/test_assets_path.sh"
```

Expected: `===== 9 passed / 0 failed =====`. If this fails, the core is not on `regatta-base`.

- [ ] **Step 6: Build this repo as a colcon overlay**

```bash
cd ~/src/LOTUSim-regatta          # wherever it is cloned
source "$LOTUSIM_WS/install/setup.bash"
colcon build --symlink-install
source install/setup.bash
python3 -c "import regatta_agents.pilot; print('overlay OK')"
```

Expected: `overlay OK`.

- [ ] **Step 7: Write `install.sh` capturing exactly what you just did**

Write the steps above into `install.sh`, guarded and idempotent. Model it on
`LOTUSim-generic-scenario/install_core_and_generic_scenario.sh`: detect the release, fail
loudly on anything but 24.04, and append the exports to `~/.bashrc`.

```bash
#!/usr/bin/env bash
# Brings a clean Ubuntu 24.04 to a runnable regatta: LOTUSim core at regatta-base
# plus this repository built as a colcon overlay.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
die() { echo -e "${RED}$*${NC}" >&2; exit 1; }
ok()  { echo -e "${GREEN}$*${NC}"; }

[[ "$(lsb_release -rs)" == "24.04" ]] || die "Ubuntu 24.04 required (ROS 2 Jazzy); found $(lsb_release -rs)"
[[ "$(uname -m)" == "x86_64" ]]       || die "x86_64 required: physics/xdyn-for-cs is an x86-64 binary"

REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOTUSIM_WS="${LOTUSIM_WS:-$HOME/lotusim_ws}"
export LOTUSIM_PATH="$LOTUSIM_WS/src/LOTUSim"

if [[ ! -d "$LOTUSIM_PATH" ]]; then
  mkdir -p "$LOTUSIM_WS/src"
  git clone -b regatta-base https://github.com/cmoron-lab/LOTUSim.git "$LOTUSIM_PATH"
fi

export PATH="$LOTUSIM_PATH/launch:$PATH"
sudo -E lotusim install
ok "core installed"

# ROS setup files read unset variables; -u must be off while sourcing them.
set +u
source "$LOTUSIM_WS/install/setup.bash"
cd "$REGATTA_ROOT" && colcon build --symlink-install
source "$REGATTA_ROOT/install/setup.bash"
set -u
ok "overlay built"

grep -q 'LOTUSIM_WS' ~/.bashrc || cat >> ~/.bashrc <<EOF

# LOTUSim regatta
export LOTUSIM_WS="$LOTUSIM_WS"
export LOTUSIM_PATH="\$LOTUSIM_WS/src/LOTUSim"
export PATH="\$LOTUSIM_PATH/launch:\$PATH"
source "\$LOTUSIM_WS/install/setup.bash"
source "$REGATTA_ROOT/install/setup.bash"
source "\$LOTUSIM_PATH/launch/bash_completion.sh"
EOF
ok "environment written to ~/.bashrc — open a new shell"
```

- [ ] **Step 8: Commit**

```bash
git add install.sh
git commit -m "feat(install): bring-up script for Ubuntu 24.04

Captures the manual bring-up so a second machine costs one command instead of
a runbook read. Follows the two-workspace overlay pattern of
LOTUSim-generic-scenario."
```

---

### Task 2: Run xdyn natively in the offline harness

`offline/ws.py` launches xdyn through `docker run --platform linux/amd64`. On x86-64 Linux
the binary runs directly, and the offline oracle is the cheapest physics gate we have —
it must work before anything else is trusted.

**Files:**
- Modify: `offline/ws.py:12-16` (the `LAB`-derived constants, including the container mesh
  path), `offline/ws.py:98-114` (`launch_xdyn` / `stop_xdyn`)
- Test: `offline/oracle.py` — an existing assertion-based gate

**Interfaces:**
- Consumes: `$LOTUSIM_PATH` from Task 1.
- Produces: module-level `ws.launch_xdyn(port=12345, solver="rk4", dt=0.005)` and
  `ws.stop_xdyn()`. These are plain module functions, not methods. The current signatures
  carry a `name="regatta_cosim"` argument — the Docker container name — which becomes
  meaningless here; it can be dropped because the only callers, `offline/oracle.py:23,38`
  and `offline/probe_helm.py:23,47`, never pass it.

- [ ] **Step 1: Run the oracle unchanged, to see it fail**

```bash
cd offline && python3 oracle.py
```

Expected: failure — it tries `docker run --platform linux/amd64` and either Docker is
absent or the container path `/lab/...` does not exist.

- [ ] **Step 2: Replace the hard-coded lab paths**

`offline/ws.py:12-16` currently reads:

```python
LAB = os.path.expanduser("~/src/lotusim-lab")
IMAGE = "lotusim:focus-v2"
MODEL_SRC = f"{LAB}/LOTUSim/assets/models/focus_v2/focus_v2.yaml"
OFF = f"{LAB}/LOTUSim-regatta/offline"
C_MESH = "/lab/LOTUSim/assets/models/focus_v2/meshes/focus_v2.stl"
```

Note `C_MESH`: `write_model()` rewrites the model's `mesh:` line to that **container**
path. It is invisible for as long as everything runs in Docker and wrong the moment it
does not. Replace the whole block with:

```python
# Core assets and the xdyn binaries come from the installed LOTUSim; repo-local
# paths come from this file's location. Neither depends on a checkout layout.
LOTUSIM_PATH = os.environ.get("LOTUSIM_PATH")
if not LOTUSIM_PATH:
    raise RuntimeError("LOTUSIM_PATH is unset -- source the LOTUSim environment first")
REGATTA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_SRC = f"{LOTUSIM_PATH}/assets/models/focus_v2/focus_v2.yaml"
OFF = f"{REGATTA_ROOT}/offline"
# Absolute mesh path for the temp model: xdyn resolves it relative to its cwd
# otherwise, and the cwd differs between the offline and gz paths.
C_MESH = f"{LOTUSIM_PATH}/assets/models/focus_v2/meshes/focus_v2.stl"
```

`IMAGE` becomes dead once Step 3 lands — delete it rather than leave it.

- [ ] **Step 3: Launch xdyn as a local process**

Replace `launch_xdyn` / `stop_xdyn` (`offline/ws.py:98-114`) — they are module-level
functions, and the `name` argument was only the container's name:

```python
_XDYN_PROC = None


def launch_xdyn(port=12345, solver="rk4", dt=0.005):
    """Start xdyn-for-cs locally. The binary is x86-64: this needs an x86-64 host."""
    global _XDYN_PROC
    physics = os.path.join(LOTUSIM_PATH, "physics")
    _XDYN_PROC = subprocess.Popen(
        [os.path.join(physics, "xdyn-for-cs"), f"{OFF}/_cosim_model.yaml",
         "-s", solver, "--dt", str(dt), "-a", "127.0.0.1", "-p", str(port)],
        cwd=os.path.join(LOTUSIM_PATH, "assets", "models"),
        env=dict(os.environ, LD_LIBRARY_PATH=physics),
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    time.sleep(4)   # the websocket server needs to be listening before we connect


def stop_xdyn():
    global _XDYN_PROC
    if _XDYN_PROC is not None:
        _XDYN_PROC.kill()      # xdyn, like gz, is not reliable on SIGTERM
        _XDYN_PROC.wait()
        _XDYN_PROC = None
```

Add `import subprocess` and `import time` at the top if they are not already there. The
model file name is `_cosim_model.yaml` — the one `write_model()` produces, not the gz
harness's `_regatta_model.yaml`.

- [ ] **Step 4: Run the oracle to verify it passes**

```bash
cd offline && python3 oracle.py
```

Expected: `xdyn_dt 0.001 | comm_dt 0.005 | marks reached 2/2 ...` and no assertion error.
This is the moment the physics is proven sound on the new platform.

- [ ] **Step 5: Note the wall time**

Record how long the oracle took. Compare it with the Mac figure in `README.md`. This is
the first real measurement of the native speed-up and it feeds Task 8's expectations.

- [ ] **Step 6: Commit**

```bash
git add offline/ws.py
git commit -m "fix(offline): launch xdyn natively instead of through Docker

The oracle is the cheapest physics gate; making it the first thing that runs on
a new machine means any later failure is plumbing, not physics."
```

---

### Task 3: Measure — does xdyn merge two `environment models:` sections?

Open question 1 of the spec. It decides whether the wind can leave the core model.

**Files:**
- Create: `docs/measurements/2026-07-WSL.md`
- Create (throwaway): `/tmp/wind_only.yaml`

- [ ] **Step 1: Write a second YAML carrying only the wind**

```yaml
# /tmp/wind_only.yaml
environment models:
  - model: uniform wind
    velocity:  {unit: m/s, value: 3.0}
    direction: {unit: deg, value: 180.0}
```

- [ ] **Step 2: Feed xdyn both files and observe**

```bash
cd "$LOTUSIM_PATH/assets/models"
LD_LIBRARY_PATH="$LOTUSIM_PATH/physics" "$LOTUSIM_PATH/physics/xdyn-for-cs" \
  focus_v2/focus_v2.yaml /tmp/wind_only.yaml \
  -s rk4 --dt 0.005 -a 127.0.0.1 -p 12399 2>&1 | head -20
```

Three possible outcomes, all informative:

| Observed | Meaning | Consequence |
|---|---|---|
| starts, wind is 180 | later file overrides | wind moves out of the core cleanly |
| starts, two wind models listed | sections concatenate | the core model must drop its wind |
| refuses with a duplicate/parse error | no merge | wind stays in the core; scenario needs a full model |

- [ ] **Step 3: Record the answer**

Create `docs/measurements/2026-07-WSL.md` with the exact command, the exact output, and
the conclusion in one sentence. Measurements that are not written down get re-litigated.

- [ ] **Step 4: Commit**

```bash
git add docs/measurements/2026-07-WSL.md
git commit -m "docs(measurements): record how xdyn handles layered environment models"
```

---

### Task 4: Split the harness

The core of the work. `run_regatta.sh` currently holds a `docker run` wrapping a large
single-quoted inline script; the inline part becomes a real file, and the platform choice
becomes "how do I invoke that file".

**Files:**
- Create: `scripts/regatta_stack.sh`
- Rewrite: `scripts/run_regatta.sh`

**Interfaces:**
- Consumes: the environment from Task 1 (`lotusim` on PATH, `$LOTUSIM_PATH` set).
- Produces: `regatta_stack.sh [duration_s] [hold|smoke]`, honouring `UNITY`, `WS_TAP`,
  `HELM_TEST` from the environment exactly as the current inline script does.

- [ ] **Step 1: Create `scripts/regatta_stack.sh`**

```bash
#!/bin/bash
# The regatta stack: xdyn co-sim, helmsman, then gz -- in that order.
#
# Assumes it runs INSIDE a LOTUSim environment: `lotusim` on PATH, LOTUSIM_PATH
# set, this repo's overlay sourced. It knows nothing about the platform;
# run_regatta.sh decides whether that environment is local or a container.
#
# Usage: regatta_stack.sh [duration_s] [hold|smoke]
#   hold  = keep the stack up for the duration (interactive / Unity)  [default]
#   smoke = run the gz pose oracle as a pass/fail gate
# UNITY=1  also publish the ROS-TCP endpoint (:10000) and wait for Unity first.
# WS_TAP=1 insert a logging websocket tap between the gz plugin and xdyn.

DUR=${1:-120}
MODE=${2:-hold}
REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${LOTUSIM_PATH:?source the LOTUSim environment first}"

XPID= GPID= HPID= WPID= EPID=
cleanup(){ kill -9 $XPID $GPID $HPID $WPID $EPID 2>/dev/null; }  # gz ignores SIGTERM
trap cleanup EXIT

if [ -n "${UNITY:-}" ]; then
  # Endpoint first: Unity should be attached before the sim starts, so the
  # opening moments of the lap are rendered rather than missed.
  echo "[*] ros_tcp_endpoint on 0.0.0.0:10000"
  ros2 run ros_tcp_endpoint default_server_endpoint \
    --ros-args -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000 > /tmp/endpoint.log 2>&1 & EPID=$!
  for _ in $(seq 1 24); do
    grep -q "Connection from" /tmp/endpoint.log 2>/dev/null && { echo "[*] Unity connected"; break; }
    echo "[*] waiting for Unity (open the Regatta scene, press Play)..."
    sleep 5
  done
  grep -q "Connection from" /tmp/endpoint.log 2>/dev/null || \
    echo "[!] WARNING: no Unity connection after 120s -- continuing headless."
fi

# xdyn co-sim. --dt 0.005 is the physics-proven step (0.02 diverges): do not tune it.
MODEL="$LOTUSIM_PATH/assets/models/focus_v2/focus_v2.yaml"
( cd "$LOTUSIM_PATH/assets/models" && LD_LIBRARY_PATH="$LOTUSIM_PATH/physics" \
  "$LOTUSIM_PATH/physics/xdyn-for-cs" "$MODEL" \
  -s rk4 --dt 0.005 -a 127.0.0.1 -p 12345 ) > /tmp/xdyn.log 2>&1 & XPID=$!
sleep 4

WORLD_ARG="regatta.world"
if [ -n "${WS_TAP:-}" ]; then
  python3 "$REGATTA_ROOT/scripts/ws_tap.py" --log "$REGATTA_ROOT/_tap.jsonl" \
    > /tmp/ws_tap.log 2>&1 & WPID=$!
  sleep 1
  sed "s|ws://127.0.0.1:12345|ws://127.0.0.1:9999|" \
    "$REGATTA_ROOT/assets/worlds/regatta.world" > /tmp/regatta_tap.world
  TAP_ASSETS=/tmp/regatta_tap_assets
  mkdir -p "$TAP_ASSETS/worlds" && cp /tmp/regatta_tap.world "$TAP_ASSETS/worlds/regatta.world"
  ASSETS_ARG="$TAP_ASSETS:$REGATTA_ROOT/assets"
else
  ASSETS_ARG="$REGATTA_ROOT/assets"
fi

# Helmsman BEFORE gz: it publishes vessel_cmd_array continuously, so xdyn has
# sheet and helm at the first physics step. Without it xdyn answers "Unable to
# find signal" and the plugin crashes parsing the reply.
python3 -u -m regatta_agents.helmsman > /tmp/helm.log 2>&1 & HPID=$!
sleep 3

lotusim --assets-path "$ASSETS_ARG" run "$WORLD_ARG" > /tmp/gz.log 2>&1 & GPID=$!
sleep 8

RC=0
if [ "$MODE" = "smoke" ]; then
  python3 -u "$REGATTA_ROOT/scripts/smoke_rounds_marks.py" "$DUR"; RC=$?
else
  sleep "$DUR"
fi

echo "=== XDYN (tail) ===";  tail -6  /tmp/xdyn.log
echo "=== GZ (tail) ===";    tail -12 /tmp/gz.log
echo "=== HELM (tail) ===";  tail -12 /tmp/helm.log
exit $RC
```

Note what disappeared: the ROS/workspace sourcing, `GZ_SIM_SYSTEM_PLUGIN_PATH`,
`GZ_SIM_RESOURCE_PATH`, `FASTDDS_BUILTIN_TRANSPORTS`, the `_patched_lib` copy, and every
`/lab/` path. `lotusim run` covers the first three; the rest had no purpose left.

- [ ] **Step 2: Rewrite `scripts/run_regatta.sh` as the entry point**

```bash
#!/bin/bash
# Entry point for the regatta stack.
#   Linux : the stack runs directly, in the LOTUSim environment of this machine.
#   macOS : ROS and gz cannot run natively, so the same stack runs in a container.
# Override with RUNNER=native|docker.
# Usage: run_regatta.sh [duration_s] [hold|smoke]
set -u
DUR=${1:-120}
MODE=${2:-hold}
REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER=${RUNNER:-$([ "$(uname -s)" = "Linux" ] && echo native || echo docker)}

if [ "$RUNNER" = "native" ]; then
  exec "$REGATTA_ROOT/scripts/regatta_stack.sh" "$DUR" "$MODE"
fi

# --- Docker path (macOS) ---------------------------------------------------
IMAGE=${IMAGE:-lotusim:focus-v2}
LAB=${LAB:-$(cd "$REGATTA_ROOT/.." && pwd)}
UNITY_PORT=; [ -n "${UNITY:-}" ] && UNITY_PORT="-p 10000:10000"
# In-container bash is PID1 and ignores SIGINT, so the EXIT trap never fires
# without this host-side backstop.
trap 'docker rm -f regatta >/dev/null 2>&1' INT TERM
exec docker run --rm --platform linux/amd64 --name regatta -v "$LAB":/lab \
  $UNITY_PORT \
  -e DUR="$DUR" -e MODE="$MODE" -e UNITY="${UNITY:-}" -e WS_TAP="${WS_TAP:-}" \
  -e HELM_TEST="${HELM_TEST:-}" \
  "$IMAGE" bash -lc \
  "/lab/$(basename "$REGATTA_ROOT")/scripts/regatta_stack.sh \"\$DUR\" \"\$MODE\""
```

- [ ] **Step 3: Make both executable and run the plumbing pre-flight**

```bash
chmod +x scripts/regatta_stack.sh scripts/run_regatta.sh
timeout -s KILL 30 lotusim --debug --assets-path "$PWD/assets" run regatta.world 2>&1 \
  | grep -Ei "Running the simulation|unable to find|error" | head
```

Expected: `Running the simulation world: .../assets/worlds/regatta.world` and **no**
`Unable to find uri[model://regatta_buoy]`. If the buoy is missing, the assets root is
wrong — fix that before running the full stack.

- [ ] **Step 4: Run the stack in hold mode**

```bash
./scripts/run_regatta.sh 60 hold
```

Expected: xdyn, helmsman and gz all start; the tails at the end show no
`Unable to find signal` in `/tmp/xdyn.log` and no plugin crash in `/tmp/gz.log`.

- [ ] **Step 5: Commit**

```bash
git add scripts/regatta_stack.sh scripts/run_regatta.sh
git commit -m "refactor(harness): split the stack from its platform wrapper

The sequence no longer knows where it runs, and stops re-implementing what
lotusim run already does. macOS keeps its container path; Linux runs native."
```

---

### Task 5: Move the wind into a scenario conditions file

**Gated by Task 3.** Apply the branch its measurement selected.

**Files:**
- Create: `assets/conditions/regatta_conditions.yaml`
- Modify: `scripts/regatta_stack.sh` (the xdyn invocation)

- [ ] **Step 1: Write the conditions file**

```yaml
# Scenario conditions for the windward-leeward lap: a steady breeze from the
# north. Layered onto the core focus_v2 model, which keeps its own demo breeze
# for the core demo world.
environment models:
  - model: uniform wind
    velocity:  {unit: m/s, value: 3.0}
    direction: {unit: deg, value: 180.0}   # compass bearing the wind blows TOWARD
```

- [ ] **Step 2: Pass both files to xdyn**

In `scripts/regatta_stack.sh`, change the xdyn line to:

```bash
  "$LOTUSIM_PATH/physics/xdyn-for-cs" "$MODEL" "$REGATTA_ROOT/assets/conditions/regatta_conditions.yaml" \
```

If Task 3 found that sections concatenate rather than override, first remove the
`uniform wind` block from the core model on `regatta-base` and push that change, so only
one wind model is ever defined.

- [ ] **Step 3: Verify the wind actually took**

```bash
./scripts/run_regatta.sh 60 hold 2>&1 | tee /tmp/wind_check.log
grep -i "wind" /tmp/xdyn.log | head
```

Expected: one wind model, direction 180. Two wind entries means the layering concatenated
and step 2's fallback was needed.

- [ ] **Step 4: Commit**

```bash
git add assets/conditions/regatta_conditions.yaml scripts/regatta_stack.sh
git commit -m "feat(scenario): carry the wind as scenario conditions

The harness used to rewrite the core model with a regex at every run. xdyn
layers YAML files natively, so the scenario states its own conditions and the
core keeps its demo breeze."
```

---

### Task 6: Measure — is the patched initial state needed on the gz path?

Open question 2. The spec's hypothesis: in co-simulation xdyn is stateless, the pose
round-trips every step, and `regatta.world` places the boat — so `psi`/`u` in the model
YAML only ever mattered to the offline oracle.

**Files:**
- Modify: `docs/measurements/2026-07-WSL.md`
- Possibly modify: `scripts/regatta_stack.sh`

- [ ] **Step 1: Capture the first exchanged state with a tap**

```bash
WS_TAP=1 ./scripts/run_regatta.sh 40 hold
head -3 _tap.jsonl
```

Read the first frame the gz plugin sends: it contains the pose and velocities gz believes
the boat has at t=0.

- [ ] **Step 2: Compare against the world**

```bash
grep -A6 "focus_v2" assets/worlds/regatta.world | grep -i pose
```

If the first tapped frame matches `regatta.world`'s pose rather than the model YAML's
`psi: 0`, the world governs and the YAML values are dead on this path.

- [ ] **Step 3: Confirm by running without any patched state**

The stack as rewritten in Task 4 already passes the unpatched core model. So:

```bash
./scripts/run_regatta.sh 300 smoke
```

Expected if the hypothesis holds: the lap completes, exactly as it did with the patch.
If instead the boat sits head-to-wind and never bears away, the initial state does matter
on the gz path — in which case add `initial position` / `initial velocity` to
`regatta_conditions.yaml` if Task 3 showed layering works, or keep a scenario-owned copy
of the body block.

- [ ] **Step 4: Record the answer and commit**

```bash
git add docs/measurements/2026-07-WSL.md scripts/regatta_stack.sh
git commit -m "docs(measurements): settle whether the gz path needs a seeded initial state"
```

---

### Task 7: Gate the smoke on simulated time

The gate currently measures wall clock, which only matched simulated time because Rosetta
gave RTF ≈ 1.0. Native x86-64 breaks that coincidence and the gate silently loses its
discriminating power.

**Files:**
- Modify: `scripts/smoke_rounds_marks.py:25-30`

- [ ] **Step 1: Write the failing check first**

Add to the top of `scripts/smoke_rounds_marks.py` a self-check that fails today:

```python
def _selftest():
    """The gate must bound the lap in simulated seconds, never in wall seconds."""
    import inspect
    src = inspect.getsource(main)
    assert "time.time()" not in src, "smoke gate still bounded by wall clock"
    print("selftest OK")
```

- [ ] **Step 2: Run it and watch it fail**

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import smoke_rounds_marks as s; s._selftest()"
```

Expected: `AssertionError: smoke gate still bounded by wall clock`.

- [ ] **Step 3: Bound the loop with simulated time**

The pose callback already receives gz messages; take the simulation clock from them and
use it as the deadline. Replace the wall-clock loop:

```python
    timeout_sim = float(sys.argv[1]) if len(sys.argv) > 1 else 130.0
    # Simulated seconds, not wall seconds: RTF must change how long we wait,
    # never whether the lap counts as complete.
    while state["sim_t"] < timeout_sim and state["idx"] < len(MARKS):
        time.sleep(0.5)
```

and set `state["sim_t"]` in the pose callback from the message header stamp
(`msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9`), initialising `state["sim_t"] = 0.0`.

- [ ] **Step 4: Run the self-check to verify it passes**

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import smoke_rounds_marks as s; s._selftest()"
```

Expected: `selftest OK`.

- [ ] **Step 5: Run the real gate**

```bash
./scripts/run_regatta.sh 300 smoke; echo "exit=$?"
```

Expected: `exit=0`, and a wall duration noticeably shorter than 300 s if the native RTF is
above 1 — which is the whole point: the verdict no longer depends on the machine.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke_rounds_marks.py
git commit -m "fix(smoke): bound the lap in simulated time, not wall time

The gate matched its documentation only because Rosetta happened to give
RTF 1.0. Native hardware is 3-4x faster, which silently gave a slowed-down
boat three times more simulated time to pass anyway."
```

---

### Task 8: The WSL exit criterion

**Files:** none — this is the acceptance run.

- [ ] **Step 1: Full smoke from a clean shell**

```bash
exec bash -l                       # prove the ~/.bashrc exports are enough
cd ~/src/LOTUSim-regatta
./scripts/run_regatta.sh 600 smoke; echo "exit=$?"
```

Expected: `exit=0`. A fresh login shell is part of the test: it proves Task 1's
environment survives without anything typed by hand.

- [ ] **Step 2: Record the RTF**

Note wall time against the 600 simulated seconds and write the ratio into
`docs/measurements/2026-07-WSL.md`. This is the number that justifies the whole port.

- [ ] **Step 3: Update the README performance table**

Replace the Rosetta-only table with both platforms, and drop "Runtime is **Docker only**"
from the Prerequisites section — it is no longer true.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/measurements/2026-07-WSL.md
git commit -m "docs: record native performance and drop the Docker-only claim"
```

---

### Task 9: macOS non-regression

The Docker path must still work. Run once, at the end — not per commit; it costs about
900 s of wall time under Rosetta.

**Files:** none, unless it fails.

- [ ] **Step 1: On the Mac, pull the branch and run the same gate**

```bash
cd ~/src/lotusim-lab/LOTUSim-regatta && git pull
./scripts/run_regatta.sh 600 smoke; echo "exit=$?"
```

Expected: `exit=0`, with `RUNNER` auto-detecting `docker` because `uname -s` is `Darwin`.

- [ ] **Step 2: If it fails, fix in `run_regatta.sh` only**

The container path is the only thing that may differ. `regatta_stack.sh` must stay
platform-agnostic — if a fix needs to go inside it, that is a design smell worth raising
before committing it.

- [ ] **Step 3: Commit any fix**

Only if Step 1 failed. Describe in the commit message what the container path needed and
why the native path did not — that difference is the useful record.

---

### Task 10 (optional): Measure the Unity link under Windows

Open question 3. Only worth doing when Unity rendering is actually wanted; the sim does
not depend on it.

- [ ] **Step 1: Run with Unity attached**

```bash
UNITY=1 ./scripts/run_regatta.sh 600 hold
```

Open the Regatta scene from `LOTUSim-Unity-modules` on the **`feature/regatta-scenario`**
branch — mandatory, other branches raise `InvalidKeyException` on the `focus_v2`
addressable — and press Play. Expect the first Play to be slow while shaders compile.

- [ ] **Step 2: Judge before optimising**

If motion looks stuttery, measure before touching anything: `SleepTimeSeconds` on the
`ROSConnection` component is a serialized field (default 0.01), and `Task.Delay` may round
up to the Windows timer resolution. Record the observation in
`docs/measurements/2026-07-WSL.md` rather than tuning blind.

---

## Notes for whoever executes this

- **Tasks 3 and 6 are measurements, not implementations.** Their deliverable is a written
  answer. Do not skip the writing: the value is in not having to re-derive it.
- **The wind is patched in two places, and this plan only moves one.** `offline/ws.py`'s
  `write_model()` rewrites the wind direction for the offline path, on purpose: the oracle
  sweeps wind as a parameter (`run_lap(wind_dir_deg=...)`). That parameterisation is a
  feature — leave it. Task 5 concerns the gz path, where the wind is fixed scenario
  configuration rather than a swept variable.
- **Proposing `focus_v2` upstream is deliberately not in this plan.** The spec lists it as
  a follow-up; it is an upstream contribution with its own workflow (issue, then PR, per
  CONTRIBUTING) and it does not gate anything here.
- **Task 5 is gated by Task 3, Task 6 gates its own outcome.** Running them out of order
  produces a plausible harness that nobody can justify.
- `lotusim run` calls `clear`, so `/tmp/gz.log` will contain terminal escape codes. Cosmetic;
  do not chase it.
- If gz appears to hang at startup with no output, remember it is silent at `-v0` — add
  `--debug` before concluding anything is wrong.
