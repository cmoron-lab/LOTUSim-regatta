# Sail source reproducibility replacement

**Status:** approved on 2026-08-02

## Context

PR #1 originally delivered the complete visible-wind feature across the Regatta
scenario repository and the retired Unity 2023 project. Its runtime result has
since been ported and improved in `LOTUSim-Unity6-modules`, while the Regatta
base branch has deleted its obsolete `unity/` mirror.

Merging PR #1 now would restore dead runtime copies and stale Unity 2023
documentation. Closing it without replacement would lose the authored Blender
source and deterministic exporter behind the FBX currently used by Unity 6.
A fresh generation from the current base `.blend` also fails the exported
rudder-pivot check, so the final authored `.blend` from PR #1 remains material
source data rather than disposable build output.

## Decision

Replace PR #1 with a small PR based on the current
`feat/multiplatform-harness` branch. It will contain only:

- the final `assets/blend/focus_v2.blend` source from PR #1;
- `assets/blend/author_sail_shapes.py`, corrected for safe regeneration;
- a portable recipe in `assets/blend/README.md`;
- this design record and a focused GitHub Actions workflow.

It will not restore `unity/`, modify `docs/unity-scenario.md`, change the Unity 6
runtime, or attempt the travelling-ripple improvement. PR #1 will be closed as
superseded only after the replacement PR exists, with a link between them.

## Generator behaviour

Normal generation authors the sail shape keys in memory and exports an FBX, but
does not overwrite the input `.blend`. Passing `--save-source` explicitly saves
the authored source only after the FBX export succeeds. The script keeps
Blender's normal backup behaviour instead of setting `save_version = 0`.

Every sampled chord row must contain vertices. A sparse or remeshed sail raises
an `AssertionError` naming the sail and normalised height instead of leaking a
bare `ValueError` from `min()` or `max()`.

The existing filled-camber geometry is retained: direct measurement places its
maximum near 50% chord on both sails. The current lateral-only deformation and
static spatial ripple remain deliberate limitations; the README records that
they do not preserve cloth area or create a travelling luff wave.

## Portable recipe

The documented export uses a configurable sibling path rather than a personal
Windows path:

```bash
UNITY_PROJECT=${UNITY_PROJECT:-../LOTUSim-Unity6-modules}
blender --background assets/blend/focus_v2.blend --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- \
  --output-fbx "$UNITY_PROJECT/Assets/models/focus_v2/mesh/focus_v2.fbx"
```

Source persistence requires adding `--save-source` deliberately.

## Continuous integration

One Ubuntu 24.04 workflow runs without ROS, Gazebo, or Unity:

1. Python 3.12 and the locked `uv` development environment;
2. `uv run pytest -q`;
3. pinned Ruff checks limited to fatal Python errors and the Blender generator,
   because the repository currently has unrelated whole-tree lint debt;
4. cached official Blender 4.5.11;
5. headless generation to runner temporary storage;
6. fresh empty-scene import through `--verify-fbx`;
7. `--python-exit-code 1` so Blender propagates script failures;
8. `git diff --exit-code -- assets/blend/focus_v2.blend` to prove the default
   generation path did not overwrite its source.

The workflow is a verification gate only. It does not publish artifacts or
require GitHub secrets.

## Acceptance

- the replacement branch contains no `unity/` path;
- generation and fresh FBX verification pass with Blender 4.5.11;
- generation without `--save-source` leaves the committed `.blend` byte-for-byte
  unchanged;
- `--save-source` is documented as the only source-writing path;
- Python tests and the focused Ruff gate pass locally and in GitHub Actions;
- the replacement PR targets `feat/multiplatform-harness` and PR #1 links to it
  when closed.
