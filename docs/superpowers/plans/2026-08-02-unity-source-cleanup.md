# Unity Source Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the obsolete Unity mirror from `LOTUSim-regatta` and make the sibling Unity 6 repository the only documented source of renderer assets.

**Architecture:** Delete rather than synchronize the divergent copy. Keep runtime code unchanged in `LOTUSim-Unity6-modules`, update only current Regatta documentation, and preserve historical documents and the retired Unity 2023 checkout.

**Tech Stack:** Markdown, Git, pytest

## Global Constraints

- `LOTUSim-Unity6-modules` is the sole source of truth for active Unity assets.
- Do not modify `LOTUSim-Unity6-modules` runtime code.
- Do not modify the retired `LOTUSim-Unity-modules` checkout.
- Do not rewrite documents under `docs/archive/`, `docs/design/`, or `docs/verification/`.
- Preserve the existing local commit history; add one signed cleanup commit.

---

### Task 1: Remove the obsolete mirror and repair current documentation

**Files:**
- Delete: `unity/ActuatorAnimator.cs`
- Delete: `unity/ManualHelm.cs`
- Delete: `unity/NativeFoamWakeController.cs`
- Delete: `unity/RegattaCameraRig.cs`
- Delete: `unity/RegattaHud.cs`
- Delete: `unity/RegattaWakeDecal.mat`
- Delete: `unity/RegattaWakeDecal.mat.meta`
- Delete: `unity/WakeEmitter.cs`
- Delete: `unity/WakeMath/WakeMath.asmdef`
- Delete: `unity/WakeMath/WakeMath.cs`
- Delete: `unity/WakeMath/WakeMathTests.cs`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/unity-scenario.md`

**Interfaces:**
- Consumes: the active scene, scripts, shader, tests, and build recipe documented in `../LOTUSim-Unity6-modules/README.md`.
- Produces: a Regatta repository with no Unity runtime mirror and a current guide pointing to the sibling project.

- [x] **Step 1: Confirm the active and obsolete boundaries**

Run:

```bash
rg -n "Source of truth|unity/|LOTUSim-Unity-modules|Unity 2023|WaterFoamGenerator|WakeEmitter" README.md docs/unity-scenario.md
git -C ../LOTUSim-Unity6-modules status --short
```

Expected: current docs reference the obsolete mirror; the Unity 6 worktree is clean.

- [x] **Step 2: Delete the complete obsolete mirror**

Use `apply_patch` to delete the eleven files listed above. Do not move them to an archive because Git already preserves their history.

- [x] **Step 3: Update the two current documentation entry points**

Change the repository map in `README.md` so it points to the sibling `LOTUSim-Unity6-modules` project. Rewrite `docs/unity-scenario.md` as the current Unity 6000.3.21f1 / HDRP 17 runbook: active scene and prefab, runtime spawn, authoritative script paths, foam-only wake, launch order, editor-focus requirement, EditMode command, and player build command. Update the live rendering milestone in `docs/ROADMAP.md` so it no longer presents Unity 2023 as canonical.

- [x] **Step 4: Verify the cleanup**

Run:

```bash
test ! -e unity
rg -n 'Source of truth is `unity/|canonical .*Unity `2023\.1|WaterFoamGenerator|WakeEmitter' README.md docs/ROADMAP.md docs/unity-scenario.md
uv run pytest -q
git -C ../LOTUSim-Unity6-modules status --short
git diff --check
```

Expected: `unity/` is absent; the stale-reference search and Unity 6 status are empty; the Regatta tests pass; the diff has no whitespace errors.

- [x] **Step 5: Commit the bounded cleanup**

```bash
git add README.md docs/ROADMAP.md docs/unity-scenario.md docs/superpowers/plans/2026-08-02-unity-source-cleanup.md unity
git commit -S -m "refactor(unity): remove the obsolete renderer mirror"
git status --short
```

Expected: the signed commit succeeds and the Regatta worktree is clean.
