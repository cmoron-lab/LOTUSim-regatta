# Roadmap

State as of 2026-07-07: **full-stack milestone reached** — the reference helmsman
sails the complete windward-leeward lap through gz+xdyn at RTF ≈ 1.0 on the dev
Mac, rendered in Unity (animated sail/rudder, camera rig). Everything is pushed:
this repo (`cmoron-lab/LOTUSim-regatta`), the Unity scenario
(`cmoron-lab/LOTUSim-Unity-modules` branch `feature/regatta-scenario`), and three
upstream fixes (naval-group/LOTUSim PRs #28, #33, #35 — all open).

## Next workstreams (ordered)

### 1. Demo pace — the lap is correct but slow to watch
- Wind 3 → 4-5 m/s in `focus_v2.yaml` (~2× boat speed; heel/trim change →
  re-validate via the oiled gate: `COMM_DT/XDYN_DT` oracle → smoke).
- Comm step 0.01 → 0.02 (already oracle-validated) → RTF ~1.25.
- Gate xdyn `--dt 0.01` with the oracle (0.005 proven, 0.02 diverges); if PASS,
  RTF ~2 combined.

### 2. Rendering / gameplay
- **Waves**: xdyn wave environment in the yaml. Prerequisite: upstream PR #35
  (absolute co-sim time) merged or carried locally — with the old protocol the
  wave clock is frozen. Re-validate the beat on waves.
- Wake: stern particle system modulated by speed (~30 lines, sells motion).
- Wind indicator: static 3D arrow + label (wind is constant from N).
- Keyboard teleop: tiny ROS node publishing the same `vessel_cmd_array` JSON —
  viable on the Mac now that RTF ≈ 1.
- Rudder stock pivot: current axis is a bbox heuristic (blade leading edge);
  refine the origin in `assets/blend/focus_v2.blend` if the visual bothers.

### 3. Native arm64 (kills Rosetta — RTF 3-4×)
Rebuild xdyn (source: LOTUSim-Xdyn) and the LOTUSim image for arm64
(ROS Jazzy + gz Harmonic exist arm64). Measured baseline: one rk4 substep
≈ 3.1 ms emulated; expect ~1 ms native. Enables fast-forward runs and a
comfortable keyboard demo.

## Standing notes
- `lotusim:focus-v2` carries two git-invisible docker-commit layers (rebuilt
  physics plugin + ros_tcp_endpoint) — rebuild recipe in README. Backup tag:
  `focus-v2-pre-quatfix`. When upstream merges the PRs, rebase
  `LOTUSim@regatta-base` (duplicate cherry-picks drop automatically) and rebake
  the image from clean upstream.
- `LOTUSim@regatta-base` = upstream `new_main` + focus_v2 model + patched xdyn
  binaries (pending naval-group/LOTUSim-Xdyn#2) + composable `--assets-path`
  (pending naval-group/LOTUSim#47). Each temporary layer disappears when its
  upstream PR lands; the branch should melt back into upstream.
- Root blends (`~/src/lotusim-lab/*.blend`) are working copies; versioned
  sources live in `assets/blend/` (make the texture path relative on first open).
- Watch: naval-group/LOTUSim #28, #33, #35.
