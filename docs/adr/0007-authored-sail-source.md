# 0007 — The authored Blender sail source is kept, its export reproducible

Status: accepted, 2026-08-02

## Context

PR #1 delivered the visible-wind feature across this repository and the retired Unity
2023 project. Its runtime result has since been ported and improved in Unity 6, and
the `unity/` mirror deleted ([0006](0006-unity6-sole-source.md)).

Merging PR #1 would restore dead runtime copies and stale documentation. Closing it
without replacement would lose the authored Blender source behind the FBX Unity 6
uses — and a fresh generation from the base `.blend` fails the exported rudder-pivot
check, so that file is material source data, not disposable build output.

## Decision

Keep `assets/blend/focus_v2.blend` and `assets/blend/author_sail_shapes.py`,
corrected for safe regeneration, with a portable recipe in `assets/blend/README.md`
and a focused CI job that runs the same headless generation and verification.

Normal generation authors the shape keys in memory and exports an FBX without
overwriting the input; `--save-source` saves the authored source only after the
export succeeds. Paths cannot resolve to the opened `.blend`, every external image
must exist, and both export and save statuses must report success. A sparse or
remeshed sail raises an `AssertionError` naming the sail and normalised height
rather than leaking a bare `ValueError` from `min()`.

## Consequences

The lateral-only deformation and the static spatial ripple stay as deliberate
limitations: they preserve neither cloth area nor create a travelling luff wave. The
README records that, so the next reader does not rediscover it as a bug.
