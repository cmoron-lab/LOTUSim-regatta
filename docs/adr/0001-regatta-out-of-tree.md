# 0001 — The regatta is an overlay that consumes the core unmodified

Status: accepted, 2026-07-06

## Context

The ecosystem convention put every model in the LOTUSim core. That was not a design
choice: the launcher supported exactly one assets root, so nothing else could work.
A pedagogical regatta needs a world, course furniture and controllers of no interest
to the simulator, and students will later add pilots of their own.

Three costs made the convention worth challenging. Assets that cannot be
redistributed under EPL-2.0 cannot enter the core, so those scenarios could not run
at all. Iterating on a scenario model required a core PR for content the core never
consumes. And with N scenarios the core accumulates assets unrelated to itself.

## Decision

The regatta is a standalone colcon overlay built on top of a core workspace. It
consumes the core; it never modifies it.

The split follows who benefits: `focus_v2` goes to the core — it is a catalogue
model, the first sailing vessel, useful to everyone — while `regatta_buoy`,
`regatta.world` and `src/regatta_agents/` stay here.

## Consequences

It needs a launcher that composes assets roots instead of replacing the core's:
reported as naval-group/LOTUSim#46, fixed by PR#47, carried on `regatta-base` until
it lands upstream.

`focus_v2` has lived only on our fork since 2026-06-27 and still owes an upstream
`new_model` contribution.
