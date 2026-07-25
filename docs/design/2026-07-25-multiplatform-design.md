# Multi-platform regatta — design

**Date:** 2026-07-25
**Status:** approved, implementation pending

## Why

Ubuntu 24.04 is LOTUSim's reference platform: it is what `lotusim install` targets and
what most users run. This project was built on macOS / Apple Silicon, where ROS and gz
cannot run natively, so everything went through Docker with `--platform linux/amd64`
under Rosetta — and that accident got encoded as if it were the norm. Hard-coded host
paths, an image nobody can rebuild from a recipe, an `amd64` platform flag, and timing
constants calibrated on emulation.

The goal is to invert that: **Ubuntu first-class and native, macOS supported through
Docker as the special case it is.** WSL2 with Ubuntu 24.04 is literally the reference
platform, so the same work serves both the development machine and the student
deliverable.

A second driver: this repository should be a showcase of LOTUSim and of good practice.
That raises the bar from "make it run elsewhere" to "make it the example someone copies".

## Scope and sequencing

Two steps, in order:

1. **Portable harness**, validated on WSL.
2. **Student deliverable** — a third party clones and runs the regatta from the README.

The harness code is written **on WSL**, where every change is immediately testable, not
here on the Mac where the native path cannot be exercised. This document and the WSL
runbook are what gets produced beforehand. Work that *is* testable here has been done
here — the launcher fix below ships with a passing test suite.

## Decision 1 — where code lives

Scenario assets stay with the scenario:

| Element | Home | Why |
|---|---|---|
| `focus_v2` model | LOTUSim core | catalogue model, the first sailing vessel; useful to everyone |
| `regatta_buoy` model | regatta repo | course furniture, of no interest to the core |
| `regatta.world` | regatta repo | idem |
| `src/regatta_agents/` | regatta repo | controllers belong to the scenario |

The ecosystem convention ("models go in the core") was not a design choice — it was
imposed by the launcher, which supported exactly one assets root. Three costs made it
worth challenging rather than obeying:

- **Licensing.** Assets that cannot be redistributed under EPL-2.0 (manufacturer CAD,
  third-party meshes) cannot enter the core, so those scenarios could not run at all.
- **Release coupling.** Iterating on a scenario-specific model required a core PR and
  review cycle, for content the core never consumes.
- **Scale.** With N scenarios the core accumulates assets unrelated to the simulator.

Reported as [naval-group/LOTUSim#46][i46] and fixed by [PR#47][pr47]: `--assets-path`
now adds roots to the core one instead of replacing it, accepts a colon-separated list
and stays repeatable. Carried in `regatta-base` until it lands upstream.

**Follow-up:** `focus_v2` has lived only on our fork since 2026-06-27 and was never
proposed upstream. Since it belongs in the core, it should be submitted as a
`new_model` contribution.

## Decision 2 — installation

Follow the pattern `LOTUSim-generic-scenario` already established in
`install_core_and_generic_scenario.sh`: a core workspace, and the scenario built as a
**colcon overlay** on top of it — not built into the core workspace.

```
$HOME/lotusim_ws/       core, from LOTUSim@regatta-base, via `lotusim install`
<regatta repo>/         overlay workspace: it already holds src/regatta_agents,
                        so `colcon build --symlink-install` runs at its root
<regatta repo>/assets/  worlds + buoy, never copied, passed via --assets-path
```

The regatta repo is itself the overlay workspace — it has the `src/` layout colcon
expects, so no separate workspace directory is created.

It ships an `install.sh` that detects the Ubuntu release (24.04 → Jazzy), clones and
builds the core, builds the overlay in place, and writes the environment exports to
`~/.bashrc` as `install_core_and_generic_scenario.sh` does.

Launching then needs no workaround:

```bash
lotusim --assets-path <regatta repo>/assets run regatta.world
```

### The `regatta-base` branch

`LOTUSim@regatta-base` = upstream `new_main` + three named layers:

| Layer | Retired by |
|---|---|
| `focus_v2` model and demo world | a `new_model` PR upstream |
| patched xdyn binaries (heading-independent foil force) | [naval-group/LOTUSim-Xdyn#2][x2] |
| composable `--assets-path` | [naval-group/LOTUSim#47][pr47] |

It replaces `integration/post36` and `feature/focus-v2-model`, which were cut before the
`#44` revert and mixed a snapshot, assets and tuning. Every temporary layer disappears
when its upstream PR lands; the branch is meant to melt back into upstream.

The patched xdyn binaries are built from our own `LOTUSim-Xdyn` fork, not vendored from
nowhere. That the core ships xdyn as a binary blob at all is a separate upstream
concern, tracked in [naval-group/LOTUSim#10][i10].

## Decision 3 — harness shape

The harness currently re-implements by hand what `launch/lotusim` already does: sourcing
ROS and the workspace, setting `GZ_SIM_SYSTEM_PLUGIN_PATH` and `GZ_SIM_RESOURCE_PATH`.
That duplication is the source of the platform coupling. With `--assets-path` composable,
it can simply go.

Split in two, and that is the whole abstraction:

```
scripts/regatta_stack.sh   the sequence. Assumes it runs INSIDE a LOTUSim
                           environment. Knows nothing about the platform.
scripts/run_regatta.sh     entry point. Linux: exec directly.
                           macOS (or RUNNER=docker): docker run … regatta_stack.sh
```

The core orchestrates three processes — `xdyn-for-cs`, the helmsman, then
`lotusim --assets-path "$REGATTA_ROOT/assets" run regatta.world` — plus the ROS-TCP
endpoint when Unity renders. Paths stop being hard-coded: `REGATTA_ROOT` derives from the
script's own location, core assets come from `$LOTUSIM_PATH`. The `/lab` mount and
`--platform` survive only inside the macOS wrapper.

### Kept, and why

**The startup order stays.** It is not purely a Rosetta relic. Starting the helmsman
before gz has two justifications and only one is emulation-specific: (a) pre-creating a
DDS participant, which matters under Rosetta; (b) publishing `vessel_cmd_array`
continuously so xdyn has sheet and helm at the first physics step — without it xdyn
errors `Unable to find signal` and the plugin crashes parsing the reply. (b) holds on
every platform.

### Removed

- **`FASTDDS_BUILTIN_TRANSPORTS=UDPv4`** — a Rosetta shared-memory workaround, and
  already in the image's `ENV`. The explicit export is redundant; natively it should not
  be set at all.
- **`_patched_lib/`** — a hatch that overwrote the image's plugin with a locally built
  `.so`, to avoid re-committing the image on every iteration. Natively one rebuilds the
  workspace; the hatch has no purpose.

### Scenario conditions

The harness currently rewrites the core's `focus_v2.yaml` at every run with a Python
regex heredoc, to set the wind and the initial state. xdyn accepts **several** YAML files
(`-y [ --yml ] arg  Name(s) of the YAML file(s)`), so this can partly become
configuration instead of patching:

| Patched value | Location in the YAML | Separable into a second file? |
|---|---|---|
| wind direction | `environment models:` — top level | yes |
| initial heading `psi` | nested in `bodies[0].initial position` | no |
| initial speed `u` | nested in `bodies[0].initial velocity` | no |

**Wind moves to a scenario conditions YAML** in the regatta repo; the core keeps its demo
breeze; xdyn is given both files.

**The initial state stays patched until measured.** The hypothesis to test is that it is
irrelevant on the gz path: in co-simulation xdyn is stateless, the full pose round-trips
over the websocket every step, and `regatta.world` places the boat. If that holds, the
patch only ever served the offline oracle — which has no gz to hand it a state — and it
disappears from the gz path entirely. This is a hypothesis, not a decision.

## Decision 4 — verification

### A bug this exposed

`scripts/smoke_rounds_marks.py` gates on **wall-clock** time:

```python
t0 = time.time()
while time.time() - t0 < timeout and state["idx"] < len(MARKS):
```

That only means what the documentation claims because Rosetta happens to give RTF ≈ 1.0
("wall-clock durations in the scripts above ARE the sim duration"). Native x86-64 is
expected at RTF 3-4, where the same 900 s budget becomes 2700-3600 simulated seconds. The
gate will not produce false failures — it will quietly lose its discriminating power,
since a regression that slows the boat gets three times more simulated time to pass
anyway.

**Required fix: gate on simulated time**, read from the gz pose stream, not on
`time.time()`. RTF then decides only how long one waits, never the verdict.

The offline oracle is already sound: it drives xdyn in explicit steps (`dt`, `comm_dt`)
and asserts `reached >= 2` and `tacks >= 1`, with no wall clock anywhere.

### The ladder, cheapest first

1. **Offline oracle** — physics only, no gz, no ROS, deterministic. First move on a new
   machine: if it passes, the physics is sound and any later failure is plumbing.
2. **Plumbing pre-flight** — does `lotusim --assets-path <regatta>/assets run
   regatta.world` resolve the world and the buoy? Seconds, and it catches a path mistake
   before a quarter-hour run.
3. **Smoke** — the behavioural gate: does the boat round both marks? Outcome-based, so it
   survives a harness refactor without being rewritten.
4. **Unity** — visual, manual, not automatable.

### Definition of done

The smoke gate returns the same verdict on both platforms. On macOS that is a
non-regression run, once, at the end of the work (~900 s wall under Rosetta — not per
commit). On WSL it is the exit criterion.

### What cannot be verified yet

The entire native path, until the WSL machine exists. Stated plainly rather than dressed
up: the harness is written there, under test. What was testable here has been tested here
— the launcher fix ships with `launch/tests/test_assets_path.sh`, 9 passing checks
including a gz A/B that fails when a root is removed.

## Non-goals

- **Converting `lotusim:focus-v2` into a Dockerfile.** Worth doing eventually, but not a
  prerequisite: the image is already `amd64`, so it transplants to an x86-64 host as-is
  via a registry push or `docker save`.
- **Rewriting `docs/plans/`, `docs/design/` and `docs/archive/`.** Those are dated
  records of what was true when written; updating them would falsify the account. Only
  `README.md` and `ROADMAP.md` track the current state.
- **An isolation flag for `--assets-path`.** Nobody asked to exclude the core root, and
  an extra search entry is harmless.

## Open questions, to settle empirically on WSL

1. Does xdyn **merge or reject** two `environment models:` sections across YAML files?
   Decides whether the wind really can move out of the core model.
2. Does the gz path actually need the patched initial state, or does `regatta.world`
   already govern it? Compare the state at the first step with and without.
3. ROS-TCP-Connector polls with `Task.Delay(10 ms)` and Unity connects over TCP. Measure
   the real latency on Windows — where timer resolution may round that up — before
   changing anything. `SleepTimeSeconds` is an inspector field if it proves to matter.

[i46]: https://github.com/naval-group/LOTUSim/issues/46
[pr47]: https://github.com/naval-group/LOTUSim/pull/47
[x2]: https://github.com/naval-group/LOTUSim-Xdyn/pull/2
[i10]: https://github.com/naval-group/LOTUSim/issues/10
