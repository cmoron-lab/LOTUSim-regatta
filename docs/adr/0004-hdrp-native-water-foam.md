# 0004 — The wake is HDRP native water foam

Status: accepted, 2026-07-29. Supersedes the particle, trail and decal wakes.

## Context

Three implementations failed the visual acceptance test in turn. Particles look like
sparse cards and can leave the rendered water. A `TrailRenderer` follows one
centreline instead of forming a divergent wake. HDRP 14 decals give none of HDRP's
local foam accumulation and did not stay convincing on a rough rendered sea.

HDRP's local `WaterFoamGenerator`, intended among other uses for boat trails, starts
in HDRP 15 and therefore requires Unity 2023.1. The Windows project was on Unity
2022.3.62f2 / HDRP 14.0.12.

## Decision

Run a disposable spike on Unity 2023.1.20f1 / HDRP 15.0.7 — the smallest editor and
render-pipeline upgrade containing the native foam generator — in a Windows project
isolated from the source one, to answer a single question: can accumulated local foam
produce a dense, wave-integrated, divergent wake at the scenario's ~0.5 m/s.

It could. The spike was cut over to production and evolved from two static stern arms
to four periodically driven dynamic foam generators per boat, bow and stern
injection, plus a `BowWave` `WaterDeformer`. `WakeEmitter` is disabled.

## Consequences

Evidence: EditMode 41/41, a successful Windows build with 9 warnings, an accepted
mono-boat visual test, and a player build validating compilation of `Launcher` and
`defenseScenario`.

Not done, and still owed: multi-boat qualification, and visual non-regression of
`defenseScenario`.
