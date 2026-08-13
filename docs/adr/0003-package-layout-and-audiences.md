# 0003 — One uv package, three documents, invariants in `CLAUDE.md`

Status: accepted, 2026-07-26

## Context

Four defects, three of them found on first contact. The documented way to run the
oracle died on a traceback ending in `import ws`, which reads as a missing module
and is in fact the `LOTUSIM_PATH` guard firing at import time. `offline/` was a
directory of loose scripts — no `pyproject`, no lock, no entry point. The README
never said what the oracle was or why it existed. And nothing addressed agents: every
operational fact lived in a personal skill that does not travel with a clone.

The audience is anyone wanting to test a sailboat navigation algorithm — someone who
knows control theory and knows nothing about LOTUSim.

## Decision

The frontier is what needs the system Python: everything else moves under `src/` as
a `uv`-managed package that runs without ROS. Three documents serve three audiences
behind one signpost, and `CLAUDE.md` carries the invariants — each with its reason,
because a rule without its reason gets "fixed".

## Consequences

Five invariants a future reader will want to improve and must not:

1. The smoke gate re-derives the rounding rule in ENU instead of importing
   `regatta.pilot`. Importing it would make the gate unable to detect a bug in that
   very logic. The duplication buys its independence.
2. `--dt 0.005` is not a tuning knob. 0.02 diverges.
3. The gate's budget is in simulated seconds, never wall seconds: a faster machine
   changes how long you wait, never the verdict.
4. `env.sh` writes nothing to `~/.bashrc` or `~/.zshrc`.
5. The harness kills process trees and refuses to start beside another publisher.
   `lotusim run` spawns gz as a child, so killing the wrapper orphans a publisher,
   and two simulations on one topic make the gate believe either boat.
