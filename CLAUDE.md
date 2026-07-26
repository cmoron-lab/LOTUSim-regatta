# Working on LOTUSim-regatta

A windward-leeward regatta for a 1 m RC sailboat on LOTUSim: gz orchestrates and
renders, an external **xdyn** process computes all the physics over a websocket, and
a ROS node steers. Full architecture in `docs/reference.md` — this file is the
operational subset, and it points there rather than copying it. Two copies diverge.

## Proof, not opinion

Nothing here is done until these pass. Copy them; do not paraphrase them.

| what | command | expected |
|---|---|---|
| unit tests | `uv run pytest -q` | `8 passed` |
| physics oracle | `. ./env.sh && uv run regatta-oracle` | `ORACLE PASS`, 2/2 marks |
| overlay builds | `. ./env.sh && colcon build --symlink-install` | `1 package finished` |
| the full stack | `zsh -c './scripts/run_regatta.sh 400 smoke'` | `SMOKE PASS`, exit 0 |
| nothing survived | `. ./env.sh && gz topic -l \| grep -c "^/world/lotusim/"` | `0` |

The stack run costs ~4 minutes of wall time and the oracle ~10. **Budget for them
rather than skipping them.** Both have caught silent wrong answers that read as
successes — a gate that passed in 17 simulated seconds for a 240 s lap, and a run
that talked to the previous run's physics server.

The last row matters as much as the others: an orphan left publishing will make the
*next* run lie.

## Invariants

Each of these looks like something to improve. Each has a reason, stated so that it
does not get "fixed".

1. **The smoke gate re-derives the rounding rule instead of importing
   `regatta.pilot`.** Deliberate. If the gate imported the pilot's own logic it
   could never detect a bug in that logic — it would be a tautology. The duplication
   buys the oracle's independence. Do not DRY it.
2. **`--dt 0.005` is not a tuning knob.** `0.02` diverges into NaN and gz aborts.
   `rkck` is forbidden outright — it needs a monotonic clock the co-simulation does
   not provide.
3. **The gate's budget is in simulated seconds, never wall seconds.** RTF is a
   property of the machine; it must change how long you wait, never the verdict.
4. **`env.sh` writes nothing to `~/.bashrc` or `~/.zshrc`.** An interactive shell
   belongs to its user, and half of them run zsh where the ROS `setup.bash` files
   break outright.
5. **The harness kills process trees, not wrapper PIDs, and refuses to start beside
   another publisher.** `lotusim run` spawns gz as a child; killing the wrapper
   orphans a publisher that then corrupts the next run.
6. **`src/regatta` has zero runtime dependencies.** That is what lets the ROS node
   and the gz gate import it from the *system* interpreter through `PYTHONPATH`,
   with no venv for `rclpy` to see. Adding one breaks both edges.

## Traps

Phrased as "if you are about to…", because that is when they are cheap.

- **About to `pkill -f` or `pgrep -f` anything?** The pattern matches your own shell
  and its ancestors too — this has killed a session mid-task. Ask gz instead:
  `gz topic -l | grep -q "^/world/lotusim/"`.
- **About to conclude from `ps` or `grep` output that a process is dead?** The `rtk`
  hook summarises it. Re-run through `rtk proxy ps ...` before believing it. A
  warning above an output invalidates that output.
- **About to trust a gate that passed?** Read the simulated duration it reports. A
  lap is ≈ 243 s. A pass in 17 s means two boats were publishing.
- **About to add a dependency to `src/regatta`?** See invariant 6.
- **About to edit an import before the code that uses it?** The repository's format
  hook strips imports it sees as unused, and it fires between your two edits. Change
  the call sites first, or check the import survived.
- **About to write a shell one-liner with nested quotes?** Put it in a file. A
  quoting slip in a `python -c` cost a 10-minute measurement here.
- **About to run something long?** `uv run regatta-oracle` is ~10 min, the smoke
  gate ~4. Start them in the background and do something else.

## Layout

```
src/regatta/            PURE python, stdlib only, no ROS -- uv project, pytest
    pilot.py            the brain: Pilot(marks, wind_from).update(x,y,yaw,r) -> (sheet, helm)
    xdyn.py             websocket client to the xdyn co-simulation server
    oracle.py           the reference physics bench (`regatta-oracle`)
    probes/             helm.py (open-loop response), tap.py (websocket tap)
src/regatta_agents/     ROS edge: helmsman.py, colcon/ament_python
scripts/                gz edge (smoke_rounds_marks.py) + the harness
tests/                  pytest for the pure core
```

The frontier is **what needs the system's ROS/gz Python**. `rclpy` and
`gz-transport` come from apt and are not on PyPI; everything else needs nothing at
all. Reasoning in `docs/design/2026-07-26-layout-and-docs-design.md`.

## Conventions

- Python through **`uv`**, never `pip`. The dev interpreter is pinned to 3.12 in
  `.python-version` because that is what ROS Jazzy runs — testing on 3.13 would test
  a Python that never executes the production path.
- The ROS package stays `ament_python` (`package.xml` + `setup.py`); colcon needs
  that shape. It cannot declare its dependency on `regatta` — that is not a ROS
  package and `rosdep` has no name for it — so `env.sh` provides it. The omission is
  deliberate.
- Commits: Conventional Commits, and the subject says **why**; the diff already says
  what.
- Comments explain the non-obvious, especially where the obvious reading is wrong.
  Most of the comments in this repository exist because someone lost an hour.

## Documentation

| file | reader |
|---|---|
| `README.md` | anyone — a signpost, nothing more |
| `docs/guide.md` | someone bringing their own navigation algorithm |
| `docs/reference.md` | someone working on the simulator |
| this file | agents |
| `docs/measurements/` | every number, with how it was measured |
| `docs/design/` | why each decision was taken |
