# Repository layout and three-audience documentation — design

**Date:** 2026-07-26
**Status:** proposed
**Follows:** `docs/design/2026-07-25-multiplatform-design.md` (whose harness plan is
tasks 1-8 done, 9 blocked on the Mac, 10 optional)

## Why

Four defects, three of them reported from a first-contact perspective.

1. **The documented way to run the oracle fails.** `cd offline && python3 oracle.py`
   dies on a traceback whose last frame is `import ws`, so it reads as a missing
   module. It is not: it is the `LOTUSIM_PATH` guard firing at import time. The
   real cause is invisible in the message that gets shown.
2. **No packaging.** `offline/` is a directory of loose scripts — no `pyproject`,
   no `uv`, no lock, no entry point. The launch procedure is a paragraph of prose
   instead of a command.
3. **The README serves nobody.** It never says what the oracle *is* or why it
   exists, and the multi-platform story is scattered over four documents.
4. **Nothing addresses agents.** The repository carries no `CLAUDE.md` or
   `AGENTS.md`. Every operational fact — the pitfalls that cost an hour each, the
   commands that constitute proof — lives in a personal skill under
   `~/.claude/skills/`, which does not travel with a clone.

The audience matters for what follows: not students specifically, but **anyone who
wants to test a sailboat navigation algorithm** — researchers, academics, students.
Someone who knows their control theory and knows nothing about LOTUSim.

## Decisions

### D1 — The frontier is "what needs the system Python"

Measured, not assumed. Imports per file:

| file | needs |
|---|---|
| `pilot.py`, `ws.py`, `oracle.py`, `probe_helm.py`, `ws_tap.py` | **stdlib only** |
| `helmsman.py` | `rclpy`, `lotusim_msgs` — apt / colcon |
| `smoke_rounds_marks.py` | `gz.transport13` — apt |

`rclpy` and `gz-transport` are not on PyPI, so no `uv` lock can name them. But the
five files above need nothing at all: the websocket client is hand-rolled on raw
sockets.

**So the pure core becomes a `uv` project with zero runtime dependencies**, a
strict venv, and tests that run without ROS. The two files that need the system
Python stay outside it, where they already are.

*Rejected:* one venv created with `--system-site-packages` — it would host
everything including the ROS node, at the cost of a venv that no longer describes
what it contains; the reproducibility is lost and nothing is gained, because the
core needs no third-party package to begin with. *Also rejected:* one `uv` project
per unit — two of the three locks could not name their own main dependency.

### D2 — Everything under `src/`

```
src/regatta/            PURE — stdlib only, uv, pytest, runs without ROS
    pilot.py            the brain: Pilot(marks, wind_from).update(x,y,yaw,r) -> (sheet, helm)
    xdyn.py             websocket client to the xdyn co-simulation server (was ws.py)
    oracle.py           the reference physics bench
    probes/helm.py      open-loop response at constant rudder (was probe_helm.py)
    probes/tap.py       websocket tap between the gz plugin and xdyn (was scripts/ws_tap.py)

src/regatta_agents/     ROS EDGE — colcon / ament_python, imports regatta
    helmsman.py         glue: gz pose -> Pilot -> vessel_cmd_array

scripts/                gz EDGE + the harness
    smoke_rounds_marks.py   the gate; imports gz.transport13
    run_regatta.sh, regatta_stack.sh

tests/                  pytest for the core
```

`colcon` ignores `src/regatta`: no `package.xml`, no manifest, not a package it
knows. Python's src-layout is respected.

Two renames, both because the current name misleads:

- **`ws.py` → `xdyn.py`.** "ws" says which protocol, not which service. And it is
  the name that made defect 1 read as a missing module.
- **`pilot.py` leaves the ROS package.** This is the load-bearing move: it is what
  makes a pilot writable, runnable and testable without ROS installed — the whole
  point for the audience in *Why*.

### D3 — How each world sees the core

Two trivial mechanisms rather than one clever one:

- **uv side:** editable install, so `uv run regatta-oracle` works from a bare shell.
- **ROS/gz side:** `env.sh` puts `$REGATTA_ROOT/src` on `PYTHONPATH`. Sufficient
  precisely because the core is stdlib-only — there is no venv to make `rclpy` see.

`regatta_agents/package.xml` cannot declare the dependency: `regatta` is not a ROS
package and `rosdep` has no name for it. It stays undeclared and `env.sh` provides
it — stated here so the omission reads as deliberate rather than forgotten.

`install.sh` must therefore check for `uv` and say what to do when it is absent
(`curl -LsSf https://astral.sh/uv/install.sh | sh`) rather than failing on an
unknown command. It is not an apt package, so it cannot go through `install_dep.sh`.

### D4 — Three audiences behind one signpost

| door | file | reader | the question it answers |
|---|---|---|---|
| the signpost itself | `README.md`, ~70 lines | anyone | "what is this, and which door is mine?" |
| user | `docs/guide.md` | tests a navigation algorithm | "how do I run it, and how do I plug my pilot in?" |
| developer | `docs/reference.md` | works on the simulator | "how does it actually work, and what will bite me?" |
| agent | `CLAUDE.md` | Claude Code and friends | "what do I run to prove something works, and what must I not touch?" |

`docs/guide.md`, in the order the reader needs it: the windward-leeward course and
its vocabulary → what the oracle is and why it exists (a fast physics bench, no ROS
and no gz, that serves as ground truth) → install, run, observe → write your pilot
against `update(x, y, yaw, r) -> (sheet, helm)`, with the oracle as the feedback
loop → glossary (beat, tack, TWA, port/starboard, NED/ENU, RTF, co-simulation).

`docs/reference.md` carries what cannot be deduced from the code:

- **who computes what**: gz orchestrates and renders but its physics is *off*; all
  forces come from xdyn, an external process; the gz plugin is the websocket
  *client*, not the server;
- **xdyn is stateless**: the complete state round-trips every step, nothing is
  remembered between calls;
- **three frames, and the conversions that produced two upstream bugs**: NED (xdyn)
  ↔ ENU (gz) ↔ Unity, plus the FLU↔FRD body-frame swap on attitude;
- **two step sizes**: communication step 0.01 s and integration `--dt 0.005`, and
  the fact that 0.02 diverges — a numerical requirement, not a preference;
- **three clocks that do not lock**: simulated time, wall time, and the helmsman's
  30 Hz timer — which is why the trajectory is not bit-reproducible;
- **the pitfalls and why they exist**: the orphaned gz that makes the gate pass for
  the wrong reason, `pgrep -f` matching its own shell, xdyn still holding port
  12345, `setup.bash` under zsh, and `environment models:` being *replaced* rather
  than merged.

`CLAUDE.md` stays operational and short, and **points into `docs/reference.md`
instead of copying it** — two copies diverge. Frontier with the personal
`lotusim-developer` skill: repository-specific pitfalls come down into `CLAUDE.md`,
because they are repository knowledge rather than personal preference; the skill
keeps what spans the lab's repositories.

**Language: English**, matching every existing document, the code comments and the
commit messages — and the international audience in *Why*.

### D5 — The `lotusim` completion returns, in `env.sh`

It was sourced from the `~/.bashrc` block that `021338e` removed, and never
reinstated. It also completes `xdyn`, `xdyn-for-cs` and `xdyn-for-me`.

```sh
case "$-" in
  *i*)
    if [ -n "${ZSH_VERSION:-}" ]; then
      # The script speaks bash's completion API. zsh hosts it through bashcompinit,
      # whose `complete` shim calls compdef -- so compinit must have run first, or
      # every registration dies with "compdef: command not found".
      command -v compdef > /dev/null 2>&1 || { autoload -U +X compinit && compinit -u; }
      autoload -U +X bashcompinit && bashcompinit
    fi
    . "$LOTUSIM_PATH/launch/bash_completion.sh"
    ;;
esac
```

Interactive shells only: the harness sources `env.sh` on every run and has nothing
to do with a `compinit`. Verified in both shells — `bashcompinit` alone is not
enough, its `complete` shim needs `compdef`.

### D6 — The `LOTUSIM_PATH` guard moves to the point of use

Out of module scope, into the function that launches xdyn, with a message that
names `env.sh`. Defect 1 disappears: the failure explains itself where it happens.

## Invariants

Things a future reader — human or agent — will want to improve, and must not. Each
goes into `CLAUDE.md` with its reason, because a rule without its reason gets
"fixed".

1. **The smoke gate duplicates the rounding rule on purpose.** It re-derives the
   test in ENU rather than importing `regatta.pilot`. Importing it would make the
   gate unable to detect a bug in that very logic — a tautology. The duplication
   buys the oracle's independence.
2. **`--dt 0.005` is not a tuning knob.** 0.02 diverges.
3. **The gate's budget is in simulated seconds**, never wall seconds: a faster
   machine must change how long you wait, never the verdict.
4. **`env.sh` writes nothing to `~/.bashrc` or `~/.zshrc`.** An interactive shell
   belongs to its user.
5. **The harness kills process trees and refuses to start beside another
   publisher.** `lotusim run` spawns gz as a child; killing the wrapper orphans a
   publisher, and two simulations on one topic make the gate believe either boat.

## What changes

| file | change |
|---|---|
| `pyproject.toml`, `uv.lock` | new — the core, zero runtime deps, `regatta-oracle` entry point |
| `src/regatta/**` | new — moved from `offline/` and `src/regatta_agents/`, `ws.py` → `xdyn.py` |
| `tests/` | new — moved from `src/regatta_agents/test/` |
| `offline/` | removed |
| `src/regatta_agents/` | keeps `helmsman.py` only; imports `regatta.pilot` |
| `scripts/ws_tap.py` | moved to `src/regatta/probes/tap.py` |
| `scripts/regatta_stack.sh` | path of the tap |
| `env.sh` | `PYTHONPATH`, plus D5 |
| `install.sh` | checks for `uv`, then `uv sync` |
| `README.md` | rewritten as a signpost |
| `CLAUDE.md`, `docs/guide.md`, `docs/reference.md` | new |
| `docs/ROADMAP.md` | rewritten — it still describes the Mac/Docker world of 2026-07-07 |
| `docs/archive/` | receives `HANDOFF-gz-beat.md` and the two executed plans |

## Verification

Nothing counts until these five pass, in order:

| proof | expected |
|---|---|
| `uv run pytest` | 8 tests green |
| `uv run regatta-oracle` | `ORACLE PASS`, 2/2 marks |
| `colcon build` | clean |
| `./scripts/run_regatta.sh 400 smoke` | `SMOKE PASS` |
| `zsh -c './scripts/run_regatta.sh 400 smoke'` | same, from a bare shell, nothing sourced |

One number must be re-measured rather than guessed: `oracle.py`'s `tmax`. The
rounding clearance lengthened the lap — 172 s before it, 243 s through gz after —
so the offline bound has to come from a measurement of the offline lap.

## Out of scope

Recorded in `docs/ROADMAP.md`, not built here.

- **Selecting the pilot class by ROS parameter**, so a user drops theirs in without
  editing the node. The natural next step for the audience, and a feature, not
  tidying.
- **Multi-competitor architecture.** Established while scoping: the plumbing above
  xdyn is already multi-vessel (a `MultiAgentSystem` plugin, array topics, a
  per-vessel `<lotus_param>` carrying its own xdyn URI, and `"states": [...]` in the
  co-sim protocol), and Unity already ships a Photon-based session layer
  (`Assets/Scripts/MultiUser/`, `Scenes/Launcher.unity`, a player/spectator
  distinction and an offline fallback) which synchronises *presence*, not physics.
  Physics stays server-side and authoritative: client-side physics would mean two
  competitors do not face identical conditions, which destroys the comparison the
  audience came for. Open measurement: does one xdyn accept N concurrent
  connections, or do we run one process per vessel? Deserves its own design doc.
- **A real start/finish line** as a bounded segment between two marks. Today it is
  the infinite perpendicular through the leeward mark, which is why tacks recross
  it during the beat.
- **Custom web UI**, merging our fork's work with upstream.
- **Unity de-risking on Linux.** Started: `Assets/Editor/BuildRegatta.cs` referenced
  `UnityEditor.OSXStandalone` from `Assets/Editor/`, i.e. from
  `Assembly-CSharp-Editor`, where one compile error stops the whole editor and Play
  mode with it — the Regatta scene could not be played at all on Ubuntu. Fixed and
  verified (`bc7b63f` in `LOTUSim-Unity-modules`: cold batchmode import on Ubuntu,
  0 `error CS`).

## Cost

| phase | effort | machine wait |
|---|---|---|
| 1 — layout | ~2-3 h | ~20 min (oracle 8 min, two smokes 10 min, colcon) |
| 2 — documentation | ~3-4 h | — |

Under the 8 h threshold, so inline execution: no `subagent-driven-development`.
Phase 1 first — documentation written before the move would have to be rewritten.
