# Repository layout and three-audience documentation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a directory of loose scripts into a `uv`-managed pure-Python package
that runs without ROS, and replace one README that serves nobody with three
documents that each serve one reader.

**Architecture:** The frontier is the one the code already has — what needs the
system's ROS/gz Python, and what does not. `src/regatta/` becomes a `uv` project
with zero runtime dependencies (stdlib only), so the ROS node and the gz gate can
import it from the system Python through `PYTHONPATH` with no venv for `rclpy` to
see. Two files stay outside it, where they already are.

**Tech Stack:** Python 3.12 (ROS Jazzy's interpreter), `uv` + `hatchling`, `pytest`,
colcon/`ament_python` for the ROS edge, bash/zsh for the harness.

**Source spec:** `docs/design/2026-07-26-layout-and-docs-design.md`

## Global Constraints

- **`src/regatta/` has zero runtime dependencies.** Not an accident — it is what
  lets the system Python import it via `PYTHONPATH`. Adding one breaks the ROS edge.
- **`requires-python = ">=3.12"`** — the system interpreter is 3.12.3 and ROS Jazzy
  is built against it.
- **All documentation in English**, matching every existing document, the code
  comments and the commit messages.
- **`--dt 0.005` for xdyn is not a tuning knob.** 0.02 diverges.
- **The smoke gate's budget is in simulated seconds**, never wall seconds.
- **`env.sh` writes nothing to `~/.bashrc` or `~/.zshrc`.**
- **The smoke gate duplicates the pilot's rounding rule on purpose.** Do not
  refactor it to import `regatta.pilot`: it would then be unable to detect a bug in
  that logic.
- **Do not add a `[tool.ruff]` section.** The repository has never been formatted
  wholesale; configuring a line length would make the edit hook reflow every file
  it touches. A one-time `ruff format` is a separate, still-undecided commit.
- Platform: Ubuntu 24.04, x86-64 (`physics/xdyn-for-cs` is an x86-64 binary).
- Every task ends with a commit. Conventional Commits, subject says **why**.

---

# Phase 1 — Layout

### Task 1: The `uv` project and the pure core

Moves the brain and the transport into a real package, and fixes the failure that
started all this.

**Files:**
- Create: `pyproject.toml`
- Create: `src/regatta/__init__.py`
- Create: `src/regatta/pilot.py` (git mv from `src/regatta_agents/regatta_agents/pilot.py`)
- Create: `src/regatta/xdyn.py` (git mv from `offline/ws.py`)
- Create: `tests/test_pilot.py` (git mv from `src/regatta_agents/test/test_pilot.py`)
- Modify: `.gitignore`

- [ ] **Step 1: Move the three files with git, so history follows**

```bash
cd ~/src/lotusim-lab/LOTUSim-regatta
mkdir -p src/regatta tests
git mv src/regatta_agents/regatta_agents/pilot.py src/regatta/pilot.py
git mv offline/ws.py src/regatta/xdyn.py
git mv src/regatta_agents/test/test_pilot.py tests/test_pilot.py
touch src/regatta/__init__.py
git add src/regatta/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "regatta"
version = "0.1.0"
description = "Windward-leeward sailing brain and offline physics oracle for LOTUSim"
requires-python = ">=3.12"
license = { text = "EPL-2.0" }
authors = [{ name = "Cyril Moron", email = "cyril.moron@gmail.com" }]
# Deliberately empty, and it must stay empty. The ROS node and the gz smoke gate
# import this package from the SYSTEM Python (rclpy and gz-transport come from apt,
# not PyPI) through PYTHONPATH -- which only works while there is nothing to
# install. See docs/design/2026-07-26-layout-and-docs-design.md, D1.
dependencies = []

[project.scripts]
regatta-oracle = "regatta.oracle:main"

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/regatta"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Point the test at the new module path**

In `tests/test_pilot.py`, the import block becomes:

```python
from regatta.pilot import (
    CLOSE_HAULED,
    ROUND_OFFSET,
    Pilot,
    desired_heading,
    has_rounded,
    opt_sheet,
    rounding_target,
    wrap,
)
```

- [ ] **Step 4: Run the tests and watch them fail for the right reason**

Run: `uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'regatta.pilot'` is wrong;
you should instead see 8 tests collected and passing once `uv` has built the
editable install. If it reports `No module named 'regatta'`, the
`[tool.hatch.build.targets.wheel]` packages path is wrong.

- [ ] **Step 5: Fix `xdyn.py`'s two path assumptions**

Two module-scope facts break on the move. Replace the header block (the current
lines 25-37 of the file, from the `# Core assets` comment through `XDYN_LOG`) with:

```python
# The temp model and the launch log both live in /tmp. The previous version derived
# a repo path by counting parent directories, which silently depended on this file
# sitting exactly two levels below the root -- it now sits three.
XDYN_LOG = "/tmp/xdyn_offline.log"  # where a failed launch explains itself
MODEL_TMP = "/tmp/regatta_cosim_model.yaml"


def _lotusim_path():
    """Root of the installed LOTUSim tree.

    Checked here rather than at import time. Raising at module scope made the
    traceback end on `import ws`, so a missing environment variable was reported as
    a missing module -- which is exactly how this failure reached us."""
    path = os.environ.get("LOTUSIM_PATH", "")
    if not path:
        raise RuntimeError(
            "LOTUSIM_PATH is unset -- source the environment first: . ./env.sh"
        )
    return path
```

Then in `write_model`, build the paths from it and write to `MODEL_TMP`:

```python
def write_model(wind_dir_deg, wind_speed=None):
    """Write a temp model yaml with the requested wind direction and an absolute mesh path."""
    lotusim = _lotusim_path()
    # Absolute mesh path: xdyn resolves a relative one against its cwd, and the cwd
    # differs between the offline and the gz paths.
    mesh = f"{lotusim}/assets/models/focus_v2/meshes/focus_v2.stl"
    src = open(f"{lotusim}/assets/models/focus_v2/focus_v2.yaml").read()
```

...leaving the three `re.subn`/`re.sub` calls unchanged except that the mesh
substitution now uses the local `mesh`, and the final write becomes:

```python
    src = re.sub(r"^(\s*mesh:\s*)\S+\.stl", rf"\g<1>{mesh}", src, count=1, flags=re.M)
    open(MODEL_TMP, "w").write(src)
```

And in `launch_xdyn`, replace the `physics = os.path.join(LOTUSIM_PATH, "physics")`
line and the two references that follow it:

```python
    lotusim = _lotusim_path()
    physics = os.path.join(lotusim, "physics")
    _XDYN_PROC = subprocess.Popen(
        [
            os.path.join(physics, "xdyn-for-cs"),
            MODEL_TMP,
```

...and its `cwd=os.path.join(lotusim, "assets", "models"),`.

Finally delete the now-unused `LOTUSIM_PATH`, `REGATTA_ROOT`, `MODEL_SRC`, `OFF` and
`MESH` module-level names.

- [ ] **Step 6: Prove the guard now explains itself**

Run: `env -u LOTUSIM_PATH uv run python -c "from regatta import xdyn; xdyn.write_model(180)"`
Expected: `RuntimeError: LOTUSIM_PATH is unset -- source the environment first: . ./env.sh`
and the last traceback frame is inside `xdyn.py`, **not** on an `import` line.

- [ ] **Step 7: Drop the stale gitignore entry**

`offline/_*.yaml` no longer matches anything — the temp model is in `/tmp` now.
Remove that single line from `.gitignore`, leave the rest.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest -q`
Expected: `8 passed`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(core): make the sailing brain a uv package that needs no ROS

The pilot lived inside the colcon package, so writing one meant installing ROS --
backwards for a repository whose readers come to test navigation algorithms. It
now sits in src/regatta with the xdyn transport, as a uv project with zero runtime
dependencies, which is what lets the ROS node and the gz gate keep importing it
from the system Python.

ws.py becomes xdyn.py: the old name said which protocol, not which service, and it
is the name that made an unset LOTUSIM_PATH read as a missing module. That guard
now fires in the function that needs the variable, so the traceback ends where the
problem is. The temp model moves to /tmp, which deletes a path that silently
depended on how deep the file sat."
```

---

### Task 2: The oracle and the probes, with a measured bound

**Files:**
- Create: `src/regatta/oracle.py` (git mv from `offline/oracle.py`)
- Create: `src/regatta/probes/__init__.py`
- Create: `src/regatta/probes/helm.py` (git mv from `offline/probe_helm.py`)
- Create: `src/regatta/probes/tap.py` (git mv from `scripts/ws_tap.py`)
- Delete: `offline/` (now empty)

**Interfaces:**
- Consumes: `regatta.pilot.Pilot`, and from `regatta.xdyn`: `write_model(wind_dir_deg, wind_speed=None)`, `launch_xdyn(port=12345, solver="rk4", dt=0.005)`, `ws_connect(host, port)`, `init_at(heading, u=0.0)`, `step(sock, state, sheet_rad, helm_rad, dt)`, `yaw_of(st)`, `stop_xdyn()`.
- Produces: `regatta.oracle.run_lap(...) -> (rounded, tacks, traj)` and `regatta.oracle.main() -> None`, the `regatta-oracle` entry point.

- [ ] **Step 1: Move the three files**

```bash
mkdir -p src/regatta/probes
git mv offline/oracle.py src/regatta/oracle.py
git mv offline/probe_helm.py src/regatta/probes/helm.py
git mv scripts/ws_tap.py src/regatta/probes/tap.py
touch src/regatta/probes/__init__.py
git add src/regatta/probes/__init__.py
rmdir offline
```

- [ ] **Step 2: Replace the `sys.path` juggling in `oracle.py` with real imports**

Delete lines 8-16 (the `import os`, `import sys`, both `sys.path.insert` calls and
the two `# noqa: E402` imports) and put in their place:

```python
import math

from regatta import xdyn
from regatta.pilot import Pilot
```

Then replace every bare `ws.` in the file with `xdyn.` — there are six:
`xdyn.write_model`, `xdyn.launch_xdyn`, `xdyn.ws_connect`, `xdyn.init_at`,
`xdyn.step`, `xdyn.yaw_of`, `xdyn.stop_xdyn`.

- [ ] **Step 3: Turn the `__main__` block into a `main()` so the entry point can call it**

Replace the whole `if __name__ == "__main__":` block at the end of `oracle.py` with:

```python
def main():
    """The `regatta-oracle` entry point: one lap, asserted."""
    comm_dt = float(os.environ.get("COMM_DT", 0.005))
    xdyn_dt = float(os.environ.get("XDYN_DT", 0.001))
    reached, tacks, traj = run_lap(dt=xdyn_dt, comm_dt=comm_dt)
    print(
        f"xdyn_dt {xdyn_dt} | comm_dt {comm_dt} | marks reached {reached}/2 "
        f"| tacks {tacks} | dur {traj[-1]['t']:.0f}s"
    )
    assert reached >= 2, f"lap incomplete: only {reached}/2 marks"
    assert tacks >= 1, f"no tack performed (tacks={tacks})"
    print("ORACLE PASS")


if __name__ == "__main__":
    main()
```

`main()` uses `os.environ`, so keep `import os` in the import block:

```python
import math
import os

from regatta import xdyn
from regatta.pilot import Pilot
```

- [ ] **Step 4: Point `probes/helm.py` at the package**

Delete its `sys.path.insert` line and the `import ws  # noqa: E402`, replacing the
import block with:

```python
import math
import os

from regatta import xdyn
```

Then replace each `ws.` with `xdyn.` (four: `write_model`, `launch_xdyn`,
`ws_connect`, `init_at`, `step`, `yaw_of`, `stop_xdyn`).

- [ ] **Step 5: Fix the dead container default in `probes/tap.py`**

Its `--log` default is `/lab/LOTUSim-regatta/_tap.jsonl`, a path that only existed
inside the Docker image. Change the default and the stale docstring line:

```python
    ap.add_argument("--log", default="/tmp/regatta_tap.jsonl")
```

and in the module docstring, replace the line
`Runs INSIDE the lotusim container (stdlib only). Point the gz plugin's`
with:

```
Stdlib only, so it runs anywhere the harness does. Point the gz plugin's
```

- [ ] **Step 6: Measure the offline lap before setting its bound**

The rounding clearance lengthened the lap: 172 s before it, 243 s through gz after.
`run_lap`'s `tmax=220.0` was chosen before that change and may now cut the lap
short. Measure, do not guess:

```bash
. ./env.sh
XDYN_DT=0.001 uv run python -c "
from regatta.oracle import run_lap
r, t, traj = run_lap(tmax=400.0)
print(f'rounded={r} tacks={t} dur={traj[-1][\"t\"]:.0f}s')
"
```

Expected: `rounded=2`, `tacks>=1`, and a duration to read off. This takes ~10 min of
wall time (RTF 0.39 at `--dt 0.001` — that is the price of the fine step the oracle
uses on purpose).

- [ ] **Step 7: Set `tmax` from the measurement**

Change `run_lap`'s signature default to the measured duration rounded up with ~30%
of headroom, and say where the number comes from:

```python
    tmax=<measured × 1.3, rounded to 10>,  # measured: the lap runs <measured>s offline
```

- [ ] **Step 8: Run the oracle through its entry point**

Run: `. ./env.sh && uv run regatta-oracle`
Expected: `marks reached 2/2`, `tacks 3`, then `ORACLE PASS`

- [ ] **Step 9: Run the tests, which must be unaffected**

Run: `uv run pytest -q`
Expected: `8 passed`

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(core): move the oracle and probes into the package

The oracle reached its own dependencies through two sys.path.insert calls, which is
how a repository ends up with a documented command that does not run. It now
imports regatta.pilot and regatta.xdyn like anything else, and ships as the
regatta-oracle entry point.

tmax comes from a measurement rather than the pre-rounding value it inherited: the
clearance that makes the boat sail past each buoy also made the lap longer, and a
bound left at 220 s would have cut it short and reported a failed lap as a pilot
bug.

The tap's --log default pointed at /lab, a path that only existed inside the Docker
image."
```

---

### Task 3: The two edges, the environment, and the installer

Everything that has to keep working from a bare shell.

**Files:**
- Modify: `src/regatta_agents/regatta_agents/helmsman.py:9`
- Modify: `env.sh`
- Modify: `install.sh`
- Modify: `scripts/regatta_stack.sh:83`
- Modify: `README.md` (the two commands that name `offline/`, so nothing documented is broken between here and Task 7)

- [ ] **Step 1: Point the helmsman at the package**

In `src/regatta_agents/regatta_agents/helmsman.py`, line 9 becomes:

```python
from regatta.pilot import Pilot, opt_sheet
```

- [ ] **Step 2: Give the system Python the package, in `env.sh`**

After the `case ":$PATH:"` block that adds `$LOTUSIM_PATH/launch`, insert:

```sh
# The ROS node and the gz smoke gate run on the SYSTEM interpreter -- rclpy and
# gz-transport come from apt, not from any venv -- and they import `regatta`. That
# works with nothing but a path entry because the package has no dependencies of
# its own; `uv` serves the same code to the offline side as an editable install.
case ":${PYTHONPATH:-}:" in
  *":$_lr_root/src:"*) ;;                        # already there
  *) export PYTHONPATH="$_lr_root/src${PYTHONPATH:+:$PYTHONPATH}" ;;
esac
```

Note this must come **before** the `unset _lr_self _lr_root _lr_ext` line at the end
of the file, which is what makes `$_lr_root` available.

- [ ] **Step 3: Bring back the `lotusim` completion, in `env.sh`**

Immediately before that same `unset` line, add:

```sh
# `lotusim` ships completion for its subcommands and flags (and for the xdyn
# binaries). It used to be sourced from the ~/.bashrc block that 021338e removed;
# env.sh is where it belongs. Interactive shells only: the harness sources this
# file on every run and has no use for a compinit.
case "$-" in
  *i*)
    if [ -n "${ZSH_VERSION:-}" ]; then
      # The script speaks bash's completion API. zsh hosts it through bashcompinit,
      # whose `complete` shim calls compdef -- so compinit must have run first, or
      # every registration dies with "compdef: command not found".
      # ponytail: -u skips the insecure-directory prompt rather than stalling a
      # sourced file mid-way; most zshrc have run compinit already anyway.
      command -v compdef > /dev/null 2>&1 || { autoload -U +X compinit && compinit -u; }
      autoload -U +X bashcompinit && bashcompinit
    fi
    [ -f "$LOTUSIM_PATH/launch/bash_completion.sh" ] &&
      . "$LOTUSIM_PATH/launch/bash_completion.sh"
    ;;
esac
```

- [ ] **Step 4: Check both shells still source cleanly, and that completion registers**

```bash
zsh -n env.sh && bash -n env.sh && echo "syntax OK"
zsh -c '. ./env.sh && python3 -c "import regatta.pilot; print(\"zsh: import OK\")"'
bash -c '. ./env.sh && python3 -c "import regatta.pilot; print(\"bash: import OK\")"'
zsh -ic '. ./env.sh && complete -p lotusim' 2>/dev/null
```

Expected: `syntax OK`, both `import OK` lines, and
`complete -F lotusim_script_completion lotusim`.

- [ ] **Step 5: Point the harness at the tap's new home**

In `scripts/regatta_stack.sh`, the tap launch line becomes:

```bash
  python3 -m regatta.probes.tap --log "$REGATTA_ROOT/_tap.jsonl" \
    > /tmp/ws_tap.log 2>&1 & WPID=$!
```

- [ ] **Step 6: Make `install.sh` provide `uv`**

`uv` is not an apt package, so `install_dep.sh` cannot supply it. After the
`ok "overlay built"` line, insert:

```bash
# uv is not an apt package, so install_dep.sh cannot bring it. Say what to do
# rather than dying on "command not found" three lines later.
command -v uv > /dev/null || die "uv is required: curl -LsSf https://astral.sh/uv/install.sh | sh"
uv sync --project "$REGATTA_ROOT"
ok "python environment synced"
```

- [ ] **Step 7: Fix the two commands the README already documents**

`README.md` currently says `cd offline && python3 oracle.py` and names
`offline/probe_helm.py`. Task 7 rewrites this file wholesale, but leaving it wrong
in between would mean shipping a commit whose documented command fails. Replace
them with `uv run regatta-oracle` and `python3 -m regatta.probes.helm`, and the
`WS_LOG=<path> (offline side, in offline/ws.py)` mention with
`src/regatta/xdyn.py`.

- [ ] **Step 8: Rebuild the overlay**

Run: `. ./env.sh && colcon build --symlink-install`
Expected: `Summary: 1 package finished` with no warnings about `regatta_agents`.

- [ ] **Step 9: The full stack, from a bare zsh, nothing sourced by hand**

Run: `zsh -c './scripts/run_regatta.sh 400 smoke'`
Expected, after ~4 min of wall time:

```
windward: rounded, left to port by <1.5-3> m
leeward: rounded, left to port by <1.5-3> m
SMOKE PASS
```

Exit code 0. If it fails with `no pose received`, check `/tmp/helm.log` for an
`ImportError` on `regatta.pilot` — that means `PYTHONPATH` did not reach the node.

- [ ] **Step 10: Confirm nothing survives the run**

```bash
. ./env.sh && timeout 8 gz topic -l 2>/dev/null | grep -c "^/world/lotusim/"
```

Expected: `0`

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor(env): serve the package to both interpreters, and restore completion

The ROS node and the gz gate run on the system interpreter and import regatta, so
env.sh puts src/ on PYTHONPATH -- which is enough only because the package has no
dependencies. install.sh now checks for uv and syncs, since uv cannot come from
install_dep.sh.

Also restores the lotusim completion, lost when install.sh stopped writing to
~/.bashrc and never re-homed. Interactive shells only, and under zsh it needs
compinit before bashcompinit or every registration dies on a missing compdef."
```

---

# Phase 2 — Documentation

Written after the move, because documentation written before it would describe a
layout that no longer exists. Order matters: `reference.md` first, since the other
two point into it.

### Task 4: `docs/reference.md` — the developer's door

**Files:**
- Create: `docs/reference.md`

- [ ] **Step 1: Write the architecture section**

It must carry what cannot be deduced by reading the code. Cover, each with the
consequence rather than just the fact:

- gz orchestrates, renders and keeps the clock, but **its physics is off**
  (`<gravity>0 0 0</gravity>`, and every force comes from elsewhere).
- **xdyn computes all forces**, as an external process on a websocket; the gz
  `physics_interface_plugin` is the **client**, not the server. Consequence: xdyn
  must be up before gz, and the harness enforces that order.
- **xdyn is stateless.** The complete vessel state — position, quaternion, both
  velocity triples — round-trips on every communication step. Consequence: there is
  no "simulation state" to save or restore on the physics side.
- **Three frames.** NED (xdyn: x North, y East, z Down) ↔ ENU (gz: x East, y North,
  z Up) ↔ Unity. Plus the FLU↔FRD body-frame swap on attitude. Consequence: two of
  the three upstream bugs this project found were conversion bugs, invisible at
  identity attitude (`README.md`'s upstream table has the issue numbers).
- **Two step sizes, independent.** Communication step 0.01 s (gz↔xdyn round trip)
  and integration step `--dt 0.005` (rk4), xdyn substepping the former with the
  latter. `0.02` diverges — a numerical fact, not a preference.
- **Three clocks that do not lock.** Simulated time, wall time, and the helmsman's
  30 Hz ROS timer. Consequence: the trajectory is not bit-reproducible between two
  runs of the same commit, so any gate written against a tight margin is one bad run
  from a false failure.
- **The command path**: ROS topic `/<world>/vessel_cmd_array`
  (`lotusim_msgs/msg/VesselCmdArray`, a JSON `cmd_string`), published by the
  helmsman with `TRANSIENT_LOCAL` durability — a volatile publisher is silently
  rejected by `ros_tcp_endpoint`.

- [ ] **Step 2: Write the procedures section**

One runnable block each, with what success looks like: the offline oracle, the
smoke gate, a `hold` run, the web UI (both services plus `WS_BROADCAST_MS`, and the
fact that the backend serves **one spectator per instance** — a second tab receives
nothing), and Unity.

- [ ] **Step 3: Write the platforms section**

Consolidate what is currently scattered over four documents: Ubuntu 24.04 including
WSL2 as the reference platform (native, `install.sh`), macOS through Docker under
Rosetta with the rebuild recipe, and the honest status — the Docker wrapper's
environment variables are **unverified since the split**, task 9 of the previous
plan being the run that settles it. Include the performance table with both
platforms and the conclusion that native is 1.3×, not the 3-4× the port assumed.

- [ ] **Step 4: Write the pitfalls section**

Each with its symptom, because the symptom is what a reader arrives with:

| symptom | cause |
|---|---|
| smoke passes in 17 simulated seconds for a 170 s lap | an orphaned gz still publishing; the pose stream carried two boats |
| a kill command takes down your own shell | `pgrep -f`/`pkill -f` matches the shell whose command line contains the pattern |
| `frame: connection closed` after a clean start | a previous xdyn still holds port 12345, and the client connected to it |
| `no such file or directory: <cwd>/local_setup.sh` | `setup.bash` sourced under zsh: `${BASH_SOURCE}` is empty so the prefix resolves to `$PWD` |
| the boat starts in irons, or the wind is wrong | a second YAML **replaces** the `environment models:` section rather than merging into it |
| `GET /scenarios` answers 500 and the instance list is empty | the web UI backend embeds a literal `~` in its fallback paths |

- [ ] **Step 5: Link out rather than duplicate**

Point at `docs/measurements/2026-07-WSL.md` for every number, and at
`docs/design/` for why each decision was taken. This file explains the system; it
does not re-derive the measurements.

- [ ] **Step 6: Commit**

```bash
git add docs/reference.md
git commit -m "docs(reference): one door for whoever works on the simulator

The architecture was only knowable by reading four documents and the code: that
gz's physics is off, that xdyn is a stateless external server whose client is the
gz plugin, that three frames and three unsynchronised clocks are in play. Each
entry carries its consequence, since a fact without one gets optimised away."
```

---

### Task 5: `CLAUDE.md` — the agent's door

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write the five proofs, verbatim and runnable**

```markdown
## Proof, not opinion

Nothing is done until these pass. Copy them; do not paraphrase them.

| what | command | expected |
|---|---|---|
| unit tests | `uv run pytest -q` | `8 passed` |
| physics oracle | `. ./env.sh && uv run regatta-oracle` | `ORACLE PASS`, 2/2 marks |
| overlay builds | `. ./env.sh && colcon build --symlink-install` | 1 package finished |
| full stack | `zsh -c './scripts/run_regatta.sh 400 smoke'` | `SMOKE PASS`, exit 0 |
| nothing survived | `. ./env.sh && gz topic -l \| grep -c "^/world/lotusim/"` | `0` |

The stack run costs ~4 minutes of wall time and the oracle ~10. Budget for them
rather than skipping them: both have caught silent wrong answers that read as
successes.
```

- [ ] **Step 2: Write the invariants, each with its reason**

A rule without its reason gets "fixed". Copy the five from the spec's Invariants
section: the gate's deliberate duplication of the rounding rule, `--dt 0.005`, the
simulated-seconds budget, no writing to rc files, and killing process trees rather
than wrapper PIDs.

- [ ] **Step 3: Write the traps, in the form "if you are about to..."**

```markdown
## Traps

- **About to `pkill -f` or `pgrep -f` anything?** The pattern matches your own
  shell too, ancestors included. Ask gz instead: `gz topic -l | grep -q "^/world/lotusim/"`.
- **About to conclude a process is dead from `ps` output?** The rtk hook summarises
  it. Re-run through `rtk proxy ps ...` before believing it.
- **About to trust a gate that passed?** Check the simulated duration it reports. A
  lap is ~240 s; a pass in 17 s means two boats were publishing.
- **About to write to `~/.bashrc`?** Don't. `env.sh` exists for this.
- **About to add a dependency to `src/regatta`?** It has none, deliberately — that
  is what lets the ROS node import it from the system Python. See the spec's D1.
```

- [ ] **Step 4: Point at the reference, do not copy it**

One line: architecture, procedures, platforms and the full pitfall table live in
`docs/reference.md`. Two copies diverge.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(agents): give a fresh clone the operational knowledge

Every fact an agent needs -- which commands constitute proof, which pitfalls cost
an hour, which invariants look like bugs and are not -- lived in a personal skill
under ~/.claude/skills, which does not travel with a clone. An agent arriving on
this repository knew none of it."
```

---

### Task 6: `docs/guide.md` — the user's door

The reader knows control theory and knows nothing about LOTUSim. They want to test
a navigation algorithm.

**Files:**
- Create: `docs/guide.md`

- [ ] **Step 1: Write "what this is", in the reader's terms**

A 1 m RC sailboat on a two-buoy windward-leeward course, with real sail
aerodynamics and hull hydrodynamics behind it, so that a navigation algorithm faces
a boat that cannot sail into the wind and must tack. Say what the reference pilot
does, and that replacing it is the point.

- [ ] **Step 2: Write the vocabulary, before any command needs it**

Beat, tack, close-hauled, running, windward/leeward, port/starboard, TWA, in irons,
rounding a mark to port. A sentence each, each tied to something visible in a run.

- [ ] **Step 3: Explain the oracle, since nothing else will**

Why a second path to the same physics exists: `regatta-oracle` drives xdyn directly
over a websocket, with no gz, no ROS and no rendering. It is the fast feedback loop
— a lap in minutes instead of a stack to bring up — and it is the reference the
full stack gets checked against. It is not a shortcut around the production path;
it is a second client of the same co-simulation API.

- [ ] **Step 4: Write install → run → observe**

```bash
./install.sh                              # Ubuntu 24.04 / WSL2, once
uv run regatta-oracle                     # the physics bench: ORACLE PASS
./scripts/run_regatta.sh 400 smoke        # the full stack, headless: SMOKE PASS
./scripts/run_regatta.sh 900 hold         # a run to watch
```

Then how to watch it: the web UI's two services and the URL, with
`WS_BROADCAST_MS=100` because the shipped 2 s default makes a tack invisible.

- [ ] **Step 5: Write "write your own pilot" — the contract**

```markdown
Your pilot is a class with one method. No ROS, no gz, no async, no I/O:

    class MyPilot:
        def update(self, x, y, yaw, r):
            """x, y   -- position in NED metres (x North, y East)
               yaw     -- heading in radians, NED compass (0 = North, clockwise)
               r       -- yaw rate, rad/s
               returns -- (sheet, helm), both radians:
                          sheet 0 = hauled flat, larger = eased out
                          helm  > 0 = ..., clamped to +-35 deg by the harness
            """
            return sheet, helm

Iterate against the oracle, which needs neither ROS nor gz:

    uv run python -c "
    from regatta.oracle import run_lap
    print(run_lap())
    "
```

Verify the helm sign convention against `src/regatta/pilot.py` (`HELM_SIGN`) before
writing it into the guide — state it correctly or not at all.

- [ ] **Step 6: Say what is not there yet, so nobody hunts for it**

No real start/finish line (the leeward mark's perpendicular stands in for it, which
is why tacks recross it during the beat); one competitor; no way yet to select a
pilot class without editing `helmsman.py` — with a pointer to `docs/ROADMAP.md`.

- [ ] **Step 7: Commit**

```bash
git add docs/guide.md
git commit -m "docs(guide): a door for whoever brings their own navigation algorithm

The reader we expect knows control theory and nothing about LOTUSim, and the old
README told them neither what the oracle was nor how to plug a pilot in. This
starts from the course and the vocabulary, then gets to the one method a pilot has
to implement."
```

---

### Task 7: The README signpost, the roadmap, and the archive

**Files:**
- Rewrite: `README.md`
- Rewrite: `docs/ROADMAP.md`
- Move: `docs/HANDOFF-gz-beat.md` → `docs/archive/`
- Move: `docs/plans/2026-07-06-regatta-mvp-plan.md`, `docs/plans/2026-07-25-multiplatform-harness.md` → `docs/archive/plans/`

- [ ] **Step 1: Rewrite `README.md` as a signpost, ~70 lines**

What the project is in three sentences, the architecture diagram (keep the existing
ASCII one — it is good), the three doors with one line each on who should walk
through, the quickstart's four commands, and the repo map. Everything else moves
out: performance figures to `docs/reference.md`, the Docker rebuild recipe to the
platforms section, the upstream fixes table stays (it is a public record).

- [ ] **Step 2: Rewrite `docs/ROADMAP.md`**

It still describes the Mac/Docker world of 2026-07-07. Replace with the current
state and the three axes:

1. **Multi-competitor regatta.** Record the facts established while scoping: the
   plumbing above xdyn is already multi-vessel (`MultiAgentSystem` plugin, array
   topics, a per-vessel `<lotus_param>` carrying its own xdyn URI, `"states": [...]`
   in the protocol), and Unity already ships a Photon session layer
   (`Assets/Scripts/MultiUser/`, `Scenes/Launcher.unity`, player/spectator, offline
   fallback) that synchronises presence rather than physics. Physics stays
   server-side and authoritative — client-side physics would stop two competitors
   from facing identical conditions, which destroys the comparison. First step is a
   measurement: does one xdyn accept N concurrent connections, or is it one process
   per vessel? Then N pilots in the helmsman. Deserves its own design doc.
2. **Display in the web UI and Unity, multi-platform.** The web UI works, with five
   upstream bugs identified (literal `~` in fallback paths, lowercase `src/lotusim`,
   hardcoded `~/.nvm`, stale instances never purged, one spectator per instance) —
   the plan is our own fork merged with upstream, not a priority. Unity: de-risk the
   Linux/WSL editor first, then Windows. Already found and fixed there: a macOS-only
   reference in `Assets/Editor/BuildRegatta.cs` was blocking Play mode entirely on
   Linux (`bc7b63f` in `LOTUSim-Unity-modules`).
3. **Keyboard/gamepad helm in Unity.** The cheapest of the three: a ROS node
   publishing the same `vessel_cmd_array` JSON as the helmsman, so nothing
   downstream changes. Demonstration value.

Then the smaller items: a pilot class selectable by ROS parameter, a real bounded
start/finish line, driving the helmsman off the pose stream instead of a 30 Hz wall
timer (which is what makes the rounding margin vary between runs), and macOS
non-regression (task 9, needs the Mac).

- [ ] **Step 3: Archive what has been executed**

```bash
mkdir -p docs/archive/plans
git mv docs/HANDOFF-gz-beat.md docs/archive/
git mv docs/plans/2026-07-06-regatta-mvp-plan.md docs/archive/plans/
git mv docs/plans/2026-07-25-multiplatform-harness.md docs/archive/plans/
```

Add `docs/archive/README.md` saying in two lines why things are here: executed
plans and closed investigations, kept because they record how decisions were
reached, moved because they no longer describe the current state.

- [ ] **Step 4: Check every internal link still resolves**

```bash
rg -o '\[[^]]+\]\(([^)h][^)]*)\)' -r '$1' --no-filename README.md CLAUDE.md docs/*.md \
  | sort -u | while read -r p; do [ -e "$p" ] || [ -e "docs/$p" ] || echo "BROKEN: $p"; done
```

Expected: no output.

- [ ] **Step 5: Re-run the five proofs, because documentation commits touched paths**

```bash
uv run pytest -q
zsh -c './scripts/run_regatta.sh 400 smoke'
```

Expected: `8 passed`, then `SMOKE PASS`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: make the README a signpost and refresh the roadmap

The README tried to serve every reader and served none; it now points at the three
doors and keeps only what belongs at the entrance. The roadmap described the
Mac/Docker world of July 7 and is replaced by the current three axes, including
what scoping established about multi-competitor: the plumbing above xdyn is already
multi-vessel and Unity already has a Photon session layer, so the open question is
one measurement, not a redesign.

Executed plans and the closed gz-beat investigation move to docs/archive: they
record how decisions were reached, but they stopped describing the present."
```

---

## Self-review

**Spec coverage.** D1 → Task 1 (`pyproject`, `dependencies = []`). D2 → Tasks 1-2
(moves, both renames). D3 → Task 3 (`PYTHONPATH`, `uv sync`, the undeclarable
`package.xml` dependency noted in the pyproject comment). D4 → Tasks 4-7 (four
documents, English). D5 → Task 3 step 3 (completion). D6 → Task 1 step 5
(`_lotusim_path`). Invariants → Task 5 step 2. Verification (five proofs) → Task 3
steps 8-10 and Task 5 step 1, re-run in Task 7 step 5. `tmax` re-measurement → Task
2 steps 6-7. `install.sh` needing `uv` → Task 3 step 6. Out-of-scope items → Task 7
step 2 (roadmap).

**Two spec items with no task, deliberately.** The `[tool.ruff]` line-length
question is a Global Constraint saying *do not*, since the wholesale-format decision
is still open. Unity de-risking is recorded in the roadmap only.

**Type consistency.** `run_lap(...) -> (rounded, tacks, traj)` is used with those
names in Task 2 steps 3, 6 and Task 6 step 5. `Pilot.update(x, y, yaw, r) -> (sheet,
helm)` matches `src/regatta/pilot.py` and the guide's contract. `has_rounded`,
`rounding_target`, `ROUND_OFFSET`, `CLOSE_HAULED`, `desired_heading`, `opt_sheet`,
`wrap` in Task 1 step 3 are exactly the names `tests/test_pilot.py` imports today.
`xdyn.write_model / launch_xdyn / ws_connect / init_at / step / yaw_of / stop_xdyn`
is the same set in Task 2's Interfaces block and steps 2 and 4.

**One thing the plan cannot pin down, and says so.** Task 2 step 7's `tmax` is
written as `<measured × 1.3>` because the measurement in step 6 has not been taken.
That is a genuine unknown handed to the implementer with the method to resolve it,
not a placeholder standing in for a decision.
