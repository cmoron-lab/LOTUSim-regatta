# Unity source cleanup

**Status:** approved on 2026-08-02

## Context

`LOTUSim-regatta/unity/` duplicates scripts that are deployed and maintained in
`LOTUSim-Unity6-modules/Assets/Scripts/Regatta/`. The copies have diverged: the
scenario repository still describes the retired Unity 2023 wake, while the active
Unity 6 project uses the foam-only HDRP implementation.

Keeping both copies creates an ambiguous source of truth and makes a future edit
likely to target dead code.

## Decision

`LOTUSim-Unity6-modules` is the sole source of truth for Unity runtime code,
shaders, scenes, prefabs, and EditMode tests.

The cleanup will:

- delete the complete `LOTUSim-regatta/unity/` mirror;
- update the repository map and current Unity scenario guide;
- leave historical design, archive, and verification documents unchanged;
- leave the retired `LOTUSim-Unity-modules` checkout untouched.

No runtime code needs to be moved or rewritten: the active Unity 6 assets already
exist and are referenced by the Regatta scene and `focus_v2` prefab.

## Verification

- no live documentation identifies `LOTUSim-regatta/unity/` as source code;
- the Regatta Python test suite still passes;
- the Unity 6 worktree remains unchanged and clean;
- the final diff contains only deletions and current-documentation updates.
