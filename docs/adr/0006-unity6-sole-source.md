# 0006 — `LOTUSim-Unity6-modules` is the only source of Unity runtime code

Status: accepted, 2026-08-02

## Context

`LOTUSim-regatta/unity/` duplicated scripts that are deployed and maintained in
`LOTUSim-Unity6-modules/Assets/Scripts/Regatta/`. The copies had diverged: the
scenario repository still described the retired Unity 2023 wake while the active
Unity 6 project had moved to the foam-only HDRP implementation ([0004](0004-hdrp-native-water-foam.md)).

Two copies mean an ambiguous source of truth, and make a future edit likely to land
in dead code.

## Decision

`LOTUSim-Unity6-modules` is the sole source of truth for Unity runtime code, shaders,
scenes, prefabs and EditMode tests. The regatta mirror is deleted rather than
synchronised.

## Consequences

No runtime code had to move: the active Unity 6 assets already existed and were
already referenced by the Regatta scene and the `focus_v2` prefab. The retired
`LOTUSim-Unity-modules` checkout is untouched.
