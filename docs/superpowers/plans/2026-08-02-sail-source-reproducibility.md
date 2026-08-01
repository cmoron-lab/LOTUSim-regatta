# Sail Source Reproducibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace stale PR #1 with a small, tested PR that preserves the authored Focus V2 sail source and makes its Blender export reproducible and safe.

**Architecture:** Recover only the final Blender source and authoring script from `origin/autoship/sail-visuals`; do not restore the deleted Unity mirror. Harden the generator at its CLI boundary, document a sibling-project export, and run the same headless Blender generation and verification in one focused GitHub Actions job.

**Tech Stack:** Blender 4.5.11, Python 3.12, `uv` 0.11.3, Ruff 0.16.1, pytest 9.1.1, GitHub Actions

## Global Constraints

- Base branch is `feat/multiplatform-harness` at or after `08e2ef5`.
- Do not create any path under `unity/` or modify `docs/unity-scenario.md`.
- Do not modify `LOTUSim-Unity6-modules`; travelling ripple remains separate.
- Normal generation must not write `assets/blend/focus_v2.blend`.
- Inventory and FBX output paths must not resolve to the opened `.blend`.
- Every external texture must resolve before export.
- `--save-source` may save only after a successful FBX export.
- Keep Blender's backup behaviour; do not set `save_version = 0`.
- CI uses the official Blender 4.5.11 Linux archive with SHA-256 `05ed7bd41bf3e61ae4f4a7cdc364c43088bf8b3fed702c2269c018fdf63a2188`.
- Close PR #1 only after the replacement draft PR exists.

---

### Task 1: Recover and harden the authored sail source

**Files:**
- Create: `assets/blend/author_sail_shapes.py`
- Modify: `assets/blend/focus_v2.blend`
- Modify: `assets/blend/README.md`
- Create: `docs/superpowers/plans/2026-08-02-sail-source-reproducibility.md`

**Interfaces:**
- Consumes: final Blender assets at `origin/autoship/sail-visuals` and Blender CLI arguments after `--`.
- Produces: `--output-fbx PATH`, optional `--save-source`, and existing `--verify-fbx PATH` behaviour.

- [x] **Step 1: Recover only the final source asset and generator**

Run:

```bash
git restore --source=origin/autoship/sail-visuals --worktree -- \
  assets/blend/focus_v2.blend \
  assets/blend/author_sail_shapes.py
git status --short
```

Expected: only the binary `.blend`, the new generator, and this plan differ; no
`unity/` path appears.

- [x] **Step 2: Reproduce the unsafe default save before fixing it**

Run with the available Blender 4.5.x preflight binary against a temporary copy:

```bash
sail_red_dir=$(mktemp -d /tmp/lotusim-sail-red.XXXXXX)
cp assets/blend/focus_v2.blend "$sail_red_dir/input.blend"
before_hash=$(shasum -a 256 "$sail_red_dir/input.blend" | awk '{print $1}')
blender --background "$sail_red_dir/input.blend" --python-exit-code 1 \
  --python "$PWD/assets/blend/author_sail_shapes.py" -- \
  --output-fbx "$sail_red_dir/output.fbx"
after_hash=$(shasum -a 256 "$sail_red_dir/input.blend" | awk '{print $1}')
test "$before_hash" = "$after_hash"
```

Expected: the final `test` fails because the historical generator saves the
temporary source unconditionally.

- [x] **Step 3: Add explicit CLI validation and sparse-row failure**

Add the option beside the existing parser arguments:

```python
parser.add_argument(
    "--save-source",
    action="store_true",
    help="Save authored shape keys back to the input .blend after FBX export.",
)
```

After parsing, reject ambiguous source-save invocations:

```python
if arguments.save_source and (arguments.verify_fbx or not arguments.output_fbx):
    parser.error("--save-source requires generation with --output-fbx")
if arguments.save_source and not bpy.data.filepath:
    parser.error("--save-source requires an opened .blend file")
```

Before calling `min(ys)` and `max(ys)` while building `CHORD_ROWS`, add:

```python
if not ys:
    raise AssertionError(
        f"{sail_name}: no chord samples near normalised height {height:.2f}"
    )
```

- [x] **Step 4: Export before any explicit source save**

Replace the unconditional save and unchecked export with:

```python
export_result = bpy.ops.export_scene.fbx(
    filepath=arguments.output_fbx,
    axis_forward="-Z",
    axis_up="Y",
    bake_space_transform=True,
    path_mode="COPY",
    add_leaf_bones=False,
    object_types={"ARMATURE", "EMPTY", "MESH"},
)
if "FINISHED" not in export_result:
    raise AssertionError(f"FBX export failed: {sorted(export_result)}")
if arguments.save_source:
    save_result = bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    if "FINISHED" not in save_result:
        raise AssertionError(f"Source save failed: {sorted(save_result)}")
```

Delete both `bpy.context.preferences.filepaths.save_version = 0` and the save
that currently precedes export.

- [x] **Step 5: Replace the Blender README with the portable contract**

Document Blender 4.5.11, the sibling-path variable, default non-writing
generation, explicit `--save-source`, and fresh FBX verification. The runnable
commands must be:

```bash
UNITY_PROJECT=${UNITY_PROJECT:-../LOTUSim-Unity6-modules}
blender --background assets/blend/focus_v2.blend --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- \
  --output-fbx "$UNITY_PROJECT/Assets/models/focus_v2/mesh/focus_v2.fbx"

blender --background --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- \
  --verify-fbx "$UNITY_PROJECT/Assets/models/focus_v2/mesh/focus_v2.fbx"
```

State that deformation is lateral-only, does not preserve cloth area, and the
current ripple is a static spatial shape rather than a travelling luff wave.

- [x] **Step 6: Verify source safety and the exported FBX locally**

Run:

```bash
sail_green_dir=$(mktemp -d /tmp/lotusim-sail-green.XXXXXX)
cp assets/blend/focus_v2.blend "$sail_green_dir/input.blend"
before_hash=$(shasum -a 256 "$sail_green_dir/input.blend" | awk '{print $1}')
blender --background "$sail_green_dir/input.blend" --python-exit-code 1 \
  --python "$PWD/assets/blend/author_sail_shapes.py" -- \
  --output-fbx "$sail_green_dir/output.fbx"
after_hash=$(shasum -a 256 "$sail_green_dir/input.blend" | awk '{print $1}')
test "$before_hash" = "$after_hash"
blender --background --python-exit-code 1 \
  --python "$PWD/assets/blend/author_sail_shapes.py" -- \
  --verify-fbx "$sail_green_dir/output.fbx"
uv run --with ruff==0.16.1 ruff check \
  assets/blend/author_sail_shapes.py --select E4,E7,E9,F
uv run pytest -q
test ! -e unity
git diff --check
```

Expected: unchanged source hash, successful fresh FBX verification, focused
Ruff pass, `10 passed`, no `unity/`, and no whitespace errors.

- [x] **Step 7: Commit the authored-source boundary**

```bash
git add \
  assets/blend/README.md \
  assets/blend/author_sail_shapes.py \
  assets/blend/focus_v2.blend \
  docs/superpowers/plans/2026-08-02-sail-source-reproducibility.md
git commit -S -m "feat(assets): preserve reproducible sail sources"
```

### Task 2: Add the focused repository CI gate

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `.python-version`, `uv.lock`, `assets/blend/focus_v2.blend`, and the generator CLI from Task 1.
- Produces: one required-capable `verify` job for pushes and pull requests.

- [x] **Step 1: Add the minimal workflow**

Create `.github/workflows/ci.yml` with this complete content:

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - feat/multiplatform-harness

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  verify:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7.0.1
      - uses: actions/setup-python@v7.0.0
        with:
          python-version-file: .python-version
      - uses: astral-sh/setup-uv@v9.0.0
        with:
          version: 0.11.3
          enable-cache: true
      - run: uv sync --locked --dev
      - run: uv run pytest -q
      - run: >-
          uv run --with ruff==0.16.1 ruff check
          assets/blend/author_sail_shapes.py --select E4,E7,E9,F

      - id: blender-cache
        uses: actions/cache@v6.1.0
        with:
          path: ~/.cache/blender/4.5.11
          key: blender-4.5.11-linux-x64-05ed7bd4
      - if: steps.blender-cache.outputs.cache-hit != 'true'
        shell: bash
        run: |
          archive="$RUNNER_TEMP/blender-4.5.11-linux-x64.tar.xz"
          curl -fsSL \
            https://download.blender.org/release/Blender4.5/blender-4.5.11-linux-x64.tar.xz \
            -o "$archive"
          echo "05ed7bd41bf3e61ae4f4a7cdc364c43088bf8b3fed702c2269c018fdf63a2188  $archive" \
            | sha256sum --check
          mkdir -p "$HOME/.cache/blender/4.5.11"
          tar -xJf "$archive" --strip-components=1 \
            -C "$HOME/.cache/blender/4.5.11"
      - run: echo "$HOME/.cache/blender/4.5.11" >> "$GITHUB_PATH"
      - name: Verify deterministic sail export
        shell: bash
        run: |
          blender --background assets/blend/focus_v2.blend --python-exit-code 1 \
            --python assets/blend/author_sail_shapes.py -- \
            --output-fbx "$RUNNER_TEMP/focus_v2.fbx"
          blender --background --python-exit-code 1 \
            --python assets/blend/author_sail_shapes.py -- \
            --verify-fbx "$RUNNER_TEMP/focus_v2.fbx"
          git diff --exit-code -- assets/blend/focus_v2.blend
```

- [x] **Step 2: Exercise every workflow command locally**

Run the Python commands exactly as written. Run the Blender commands with the
local Blender 4.5.x preflight binary and a temporary output, then confirm:

```bash
uv sync --locked --dev
uv run pytest -q
uv run --with ruff==0.16.1 ruff check \
  assets/blend/author_sail_shapes.py --select E4,E7,E9,F
ci_dir=$(mktemp -d /tmp/lotusim-sail-ci.XXXXXX)
ci_fbx="$ci_dir/focus_v2.fbx"
blender --background assets/blend/focus_v2.blend --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- --output-fbx "$ci_fbx"
blender --background --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- \
  --verify-fbx "$ci_fbx"
git diff --exit-code -- assets/blend/focus_v2.blend
git diff --check
```

Expected: all commands exit zero and the source `.blend` stays unchanged.

- [x] **Step 3: Commit the CI gate**

```bash
git add .github/workflows/ci.yml
git commit -S -m "ci: verify sail sources without Unity"
```

### Task 3: Publish the replacement and retire PR #1

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: clean local branch `agent/sail-source-reproducibility` and GitHub repository `cmoron-lab/LOTUSim-regatta`.
- Produces: a draft replacement PR targeting `feat/multiplatform-harness`, green checks, and closed PR #1 linked to its replacement.

- [ ] **Step 1: Run the final local gate**

```bash
uv run pytest -q
uv run --with ruff==0.16.1 ruff check \
  assets/blend/author_sail_shapes.py --select E4,E7,E9,F
test ! -e unity
git diff --check
git status --short
git log --format='%h %G? %s' origin/feat/multiplatform-harness..HEAD
```

Expected: `10 passed`, focused Ruff clean, no `unity/`, clean worktree, and all
new commits report signature status `G`.

- [ ] **Step 2: Push without rewriting any remote branch**

```bash
git push --dry-run -u origin agent/sail-source-reproducibility
git push -u origin agent/sail-source-reproducibility
```

- [ ] **Step 3: Open the replacement draft PR**

Use `gh pr create --draft --base feat/multiplatform-harness` with title
`feat: preserve reproducible sail sources`. The body must state:

```markdown
## What changed

- preserve the final Focus V2 Blender source and deterministic sail exporter
- make source saving explicit and post-export
- reject sparse chord rows with an actionable error
- add portable documentation and a Python/Blender CI gate

## Why

The active sail runtime already lives in LOTUSim-Unity6-modules, but its FBX
source pipeline existed only in stale PR #1. This keeps the source reproducible
without restoring the deleted Unity runtime mirror.

## Verification

- `uv run pytest -q`
- focused Ruff fatal-error gate
- Blender 4.5.11 headless author/export and fresh FBX verification
- default generation leaves `focus_v2.blend` unchanged

Supersedes #1.
```

- [ ] **Step 4: Wait for GitHub verification**

```bash
gh pr checks --watch --interval 10
```

Expected: the `verify` job completes successfully. If it fails, inspect with
`gh run view --log-failed`, fix the root cause, rerun local checks, commit, push,
and watch again.

- [ ] **Step 5: Close the stale PR with the replacement link**

```bash
replacement_number=$(gh pr view --json number --jq .number)
gh pr close 1 --comment "Superseded by #${replacement_number}: the Unity runtime is already canonical in LOTUSim-Unity6-modules, and the replacement keeps only the reproducible Blender source pipeline."
```

Verify both states with `gh pr view` before reporting completion.
