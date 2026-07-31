# macOS / Apple Silicon — the renderer cliff is a thermal regime, not a mode

Machine: MacBook Air M2 (fanless), 8 cores, 16 GB, macOS 26.5, display desktop
2940×1912 (scaled "looks like 1470×956" — the *effective* native surface, larger
than the panel's 2560×1664). Docker Desktop VM 7.7 GB, container path under
Rosetta. Unity 2023.1.20f1 / HDRP 15.0.7, player built from
`LOTUSim-Unity-modules@perf/render-options` (adds the `RenderBudget` runtime
knobs: frame cap / render scale / fx toggle, K/L/O).

Method: `UNITY=1 ./scripts/run_regatta.sh <dur> hold`, RTF sampled from
`gz topic -e -t /world/lotusim/stats` (`real_time_factor`, ~8 Hz) over 60–90 s
per cell — an *instantaneous* RTF, unlike yesterday's wall-per-lap figure, so
regime changes inside a session become visible instead of averaging away.

## What was measured

| # | condition (all fx on, cap 60, scale 100 unless noted) | machine state | RTF p50 |
|---|---|---|---|
| M0 | windowed-maximized 2940×1912 | cold-ish (2 min of rendering) | **0.64** |
| M1 | fullscreen native 2940×1846 | +10 min sustained rendering | **0.17** |
| M2–M5 | fullscreen, fx/cap/scale keystrokes | hot | 0.16–0.17 |
| M6 | exit-fullscreen attempt | hot | 0.17 |
| CT | windowed-max, app category patched `games`→`simulation` | hot, fresh stack | **0.16** |
| M0R | M0 replica, fresh stack | **after 8 min full cool-down** | **0.57** |
| E1 | fullscreen, **scale 50 % + cap 30** (via PlayerPrefs) | ⚠ started hot | 0.13 |
| E2 | same, sustained | t+10 min | 0.165 |

Caveat on M2–M6: the AppleScript keystroke/AX path is **dead once the player is
fullscreen** — the toggles never registered, so those rows are five replicas of
M1, not fx/cap data points. (The K/L/O keys themselves work: verified windowed,
`Metal RecreateSurface 2940×1912 → 2206×1434` on an L press.)

## The finding

**Same window, same pixels, same build: RTF 0.57–0.64 on a cool machine,
0.16 after ~10 minutes of sustained near-native HDRP rendering — and 0.16 stays
regardless of every software knob** (fullscreen or windowed, fx on/off, cap,
LSApplicationCategoryType). The fanless M2 Air drops into a package
power/thermal regime under sustained GPU load, and the first casualty is the
latency-bound gz↔xdyn round-trip chain in the Rosetta VM (100 blocking
round-trips per simulated second — scheduling latency is fatal there long
before raw throughput is).

A 1-second single-core CPU benchmark reads **identical hot and cold** (0.95 s)
— burst clocks survive; it is the *sustained mixed CPU+GPU+VM envelope* that
collapses. `pmset -g therm` reports nothing on Apple Silicon; the regime is
invisible to the usual probes and must be measured through the workload.

## What this rewrites from 2026-07-30

Yesterday's table ("windowed 1280×720 → 0.84, native fullscreen → 0.13")
attributed the cliff to resolution/fullscreen. The rows carried a **thermal
history confound**: each successive condition ran on an increasingly heat-soaked
machine. The unexplained item — "why a 0.9-core player takes 87 % of the clock
is not established" — resolves the same way: it was never the player's CPU
share; the package throttles and the VM's round-trips absorb the damage.
Resolution still matters (it sets how fast the envelope is consumed, and the
renderer tax at near-native is real: 0.93 headless → ~0.6 cold), but the
0.13/0.17 floor is the thermal regime, not the render mode.

## Consequences

1. **The demo levers change meaning**: cap 30 / scale 50 % are not instant-RTF
   knobs (in the hot regime they do nothing) — they are *thermal budget* knobs.
   The endurance rows E1/E2 were meant to test that but **started on a hot
   machine** (protocol slip: no cool-down after M0R), so all they establish is
   that once hot, backing the renderer off does not recover the sim within
   10 min — only full idle (8 min) did. The real question — *does
   scale 50 % + cap 30 started cold keep the machine out of the hot regime for
   a whole demo?* — is open, and is the first cell to run on a cold machine.
2. **Session protocol**: any RTF comparison across conditions must either
   bookend with a reference cell (cold/cold) or randomize condition order.
   Thermal history is a first-class variable on fanless hardware.
3. **Multi-consumer architecture** (ROADMAP §racing): unchanged and reinforced
   — no backpressure path exists renderer→sim (verified in code: fire-and-forget
   DDS + unbounded queues at every hop), so a renderer on a *different machine*
   cannot hurt the sim. On a shared fanless machine it always eventually will.
4. **Native arm64 xdyn** (ROADMAP workstream): reinforced — less Rosetta CPU =
   less heat = wider envelope, on top of the latency win.

## Measurement-protocol traps (this session)

- **Quiescence**: a subagent's filesystem sweep (`bfs` over `/`) during a
  sample cost ~1 core and invalidated the first cell. No background agents, no
  Spotlight/XProtect churn (they re-scan renamed .app bundles), during windows.
- **French locale**: `awk` under `LC_NUMERIC=fr_FR` parses `"0.95"` as `0` —
  every parser in the loop needs `LC_ALL=C`.
- **Fullscreen kills the AppleScript control path**: keystroke/AX calls
  silently no-op on a fullscreen player. Drive conditions via PlayerPrefs
  (`defaults write com.Unity-Technologies.… "Screenmanager …"` and
  `regatta.renderBudget.*`) + relaunch, which also makes every cell's state
  explicit and logged (`Metal RecreateSurface` lines in Player.log).
- The player writes its log to `~/Library/Logs/NavalGroup/lotusim_scenario/` —
  `RecreateSurface` lines are the ground truth for the actual surface size.

## Open questions, in priority order

1. Cold-start endurance with scale 50 % + cap 30: does it avoid the hot regime
   entirely? (The go/no-go for "demo at native fullscreen on this Mac".)
2. Do the `RenderBudget` PlayerPrefs presets actually apply in the player?
   (K/L/O verified windowed; the `defaults write` preset path is unverified —
   E1's surface line stayed 2940×1846.)
3. fx on/off cost on a cold machine (never actually measured — the foam may be
   nearly free, as M1≈M2 hinted before those rows were invalidated).
4. HDRP 14 / Unity 2022.3 comparison at iso-pixels on a cold machine
   (worktree `LOTUSim-Unity-modules-ref0714` is ready) — is any of the
   regression attributable to the 2023.1/HDRP 15 cutover at all?
5. ~~No IMGUI (OnGUI) renders in the macOS player~~ — **resolved same day**: the
   Unity 6.3 player (LOTUSim-Unity6-modules) renders every HUD line correctly;
   the blackout is specific to the 2023.1 player. No fix needed on the 2023.1
   side — it is being retired.
