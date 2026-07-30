# Archive

Executed plans and closed investigations. They are kept because they record **how**
a decision was reached — the measurements, the dead ends, the reasoning — and moved
here because they stopped describing the present.

Read them as history, not as instructions. Where they contradict `../reference.md`
or `../guide.md`, those are right and these are old.

| what | why it is here |
|---|---|
| `plans/2026-07-06-regatta-mvp-plan.md` | executed: the MVP lap works |
| `plans/2026-07-25-multiplatform-harness.md` | executed in full. Task 9 (macOS non-regression) was run 2026-07-30: `SMOKE PASS`, and it took two fixes — see `../reference.md` §Platforms |
| `plans/2026-07-26-layout-and-docs.md` | executed: the `uv` package and the three doors (`guide.md`, `reference.md`, `CLAUDE.md`) |
| `plans/2026-07-28-unity-wake-trail.md` | **rejected**, then superseded. The particle trail did not read as water motion; kept for the reasoning |
| `plans/2026-07-28-unity-water-decal-wake.md` | superseded by the native foam spike below, which was accepted instead |
| `plans/2026-07-29-unity-native-water-foam-spike.md` | executed and **accepted** — this is the wake that ships. Evidence in `../verification/2026-07-29-unity-native-water-foam-spike.md` |
| `HANDOFF-gz-beat.md` | the investigation into the boat not holding a beat. Resolved — root cause was the missing FLU↔FRD body-frame swap, fixed upstream in naval-group/LOTUSim#33 |
| `PR-cosim-quaternion-brief.md` | briefing for the quaternion fix, merged upstream |
| `focus_v2_notes.md`, `focus_v2_fable_brief*.md` | the sail/hull model tuning passes that produced `focus_v2.yaml` |
| `xdyn-foil-heading-bug.md` | closed investigation |
