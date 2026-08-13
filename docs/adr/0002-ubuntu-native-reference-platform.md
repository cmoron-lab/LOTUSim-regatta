# 0002 — Ubuntu 24.04 native is the reference platform, containers elsewhere

Status: accepted, 2026-07-25

## Context

This project was built on macOS / Apple Silicon, where ROS and gz cannot run
natively, so everything went through Docker with `--platform linux/amd64` under
Rosetta — and that accident got encoded as if it were the norm: hard-coded host
paths, an image nobody could rebuild from a recipe, a platform flag, and timing
constants calibrated on emulation.

Ubuntu 24.04 is what `lotusim install` targets and what most users run. WSL2 with
Ubuntu 24.04 is literally that platform, so one effort serves both the development
machine and the deliverable.

## Decision

Ubuntu 24.04 x86-64 is the reference platform and runs the stack natively. Every
other platform runs the same stack in a container.

The harness splits accordingly: `regatta_stack.sh` is platform-agnostic and assumes
it already runs inside a LOTUSim environment; `run_regatta.sh` decides whether that
environment is local or containerised, routing on the same rule `install.sh` gates
on rather than on "is this Linux".

Installation follows the pattern `LOTUSim-generic-scenario` established: a core
workspace, and the scenario built as a colcon overlay on top of it. The repository
is itself that overlay workspace — it already has the `src/` layout colcon expects.

## Consequences

macOS and arm64 stay supported, emulated, and never primary. A platform that cannot
build natively fails in the preflight with advice that works there, instead of
failing with advice that cannot.
