# User guide — bring your own navigation algorithm

For someone who knows control and knows nothing about LOTUSim or about sailing.
By the end you will have run the simulation and replaced the reference pilot with
your own.

If you work **on** the simulator rather than with it, `reference.md` is your door.

## What this is

A **1 m radio-controlled sailboat** (a Joysway Focus V2) racing a two-buoy course.
The physics is not a kinematic toy: an aerodynamic sail polar, a hydrodynamic keel
and rudder, buoyancy from a hull mesh, and a wind field. The consequences are the
interesting part for a control problem:

- **the boat cannot sail straight into the wind**, so a mark placed upwind cannot be
  reached directly — it has to be zig-zagged towards;
- **turning through the wind costs speed**, so an algorithm that turns too often
  loses to one that turns rarely;
- **the boat drifts sideways** (leeway), so its heading and its track differ.

A reference pilot ships with the project and sails the course. **Replacing it is the
point of the exercise.**

## The course, and the words for it

```
              ▲ wind FROM the north
              │
        ╭─────┴─────╮
        │  ◉  windward mark  (15 m north)
        │  │
        │  │   the boat must BEAT up to it:
        │  │   zig-zag, because it lies dead upwind
        │  │
        │  ◉  leeward mark  (the origin)
        ╰───────────╯
```

The boat starts near the leeward mark, works up to the windward mark, rounds it,
runs back down, rounds the leeward mark, and starts another lap.

| word | meaning |
|---|---|
| **windward** | the side the wind comes from. The windward mark is upwind. |
| **leeward** | the downwind side. |
| **beating** | zig-zagging upwind because you cannot go straight there. |
| **tack** (noun) | which side the wind is on: port tack or starboard tack. |
| **tack** (verb) | turning the bow **through** the wind to change tack. Costs speed. |
| **close-hauled** | sailing as close to the wind as the boat can — about 60° here. |
| **in irons** | stuck pointing at the wind with no drive. What a bad tack ends in. |
| **running** | sailing downwind, wind from behind. |
| **TWA** | true wind angle: the angle between where you point and where the wind comes from. |
| **port / starboard** | left / right, looking forward. |
| **rounding a mark** | passing it and turning around it, on the required side. Here: leaving every mark **to port**, the racing convention. |
| **sheet** | the rope that sets how far out the sail is. Hauled in for upwind, eased out for downwind. |
| **helm** | the rudder. |

## The oracle, and why it exists

The project has **two ways to run the same physics**:

- the **full stack** — gz orchestrating, xdyn computing forces, ROS carrying
  commands, and a renderer. This is what you demonstrate.
- the **oracle** — a single Python process talking directly to the physics server
  over a websocket. No gz, no ROS, no rendering.

The oracle is the fast feedback loop. It is one command, it needs nothing running,
and it answers "does this pilot complete a lap" without bringing a stack up. It is
also the reference the full stack gets checked against: when the two disagree, the
difference is in the layers the full stack adds, so you know where to look.

It is **not a shortcut around the real system** — it speaks the identical
co-simulation protocol the gz plugin speaks. It is a second client of the same API.

**Iterate on the oracle. Demonstrate on the stack.**

## Install, run, watch

Ubuntu 24.04 (including WSL2), x86-64. Once:

```bash
./install.sh
```

It writes **nothing** to your `~/.bashrc` or `~/.zshrc`. The environment lives in
`env.sh`, which works in bash and zsh:

```bash
. ./env.sh
```

Then, in increasing order of ceremony:

```bash
uv run regatta-oracle                   # the physics bench      (~10 min, ORACLE PASS)
./scripts/run_regatta.sh 400 smoke      # the full stack, headless (~4 min, SMOKE PASS)
./scripts/run_regatta.sh 900 hold       # a run to watch          (~5 laps)
```

The argument is a budget in **simulated** seconds, not wall seconds — a faster
machine changes how long you wait, never the result.

To watch it on a map, bring up the LOTUSim web UI and open `http://localhost:5173`.
The exact procedure, and the upstream defects you will meet, are in
`reference.md` under *Procedures → The web UI*.

## Write your own pilot

Your pilot is a class with one method. **No ROS, no gz, no async, no I/O** — it is
called with the boat's state and returns two numbers:

```python
class MyPilot:
    def __init__(self, marks, wind_from):
        self.marks = marks          # [(x, y), ...] in NED metres, in the order to round
        self.wind_from = wind_from  # radians, NED compass: 0 = wind from the north

    def update(self, x, y, yaw, r):
        """x, y  -- position, NED metres: x North, y East
           yaw   -- heading, radians, NED compass: 0 = North, increasing clockwise
           r     -- yaw rate, rad/s

           returns (sheet, helm), both radians:
             sheet -- 0 hauled flat amidships, larger eased out
             helm  -- NEGATIVE turns to starboard (right), positive to port,
                      clamped to +-35 deg by the harness
        """
        return sheet, helm
```

That is the whole contract. The reference implementation is
`src/regatta/pilot.py`, ~130 lines, and it is worth reading once: it is a state
machine that beats inside a corridor, commits to a tack rather than stalling in
irons, and steers at a point beside each mark so it rounds rather than clips.

### The feedback loop

Point the oracle at your class:

```python
# my_run.py
import math
from regatta import xdyn
from my_pilot import MyPilot

wind_from = 0.0                                   # from the north
marks = [(15.0, 0.0), (0.0, 0.0)]                 # windward, then leeward

xdyn.write_model(180)                             # 180 = blows toward the south
xdyn.launch_xdyn(solver="rk4", dt=0.001)
try:
    sock = xdyn.ws_connect("127.0.0.1", 12345)
    pilot = MyPilot(marks, wind_from)
    st = xdyn.init_at(wind_from + math.radians(60), u=0.8)
    for _ in range(int(250 / 0.005)):
        sheet, helm = pilot.update(st["x"], st["y"], xdyn.yaw_of(st), st["r"])
        st = xdyn.step(sock, st, sheet, helm, 0.005)
finally:
    xdyn.stop_xdyn()
```

```bash
. ./env.sh && uv run python my_run.py
```

Compare against the reference: it completes the lap in **189 simulated seconds with
3 tacks**. Fewer tacks or a shorter lap is a better pilot.

### Two numbers you will want

- **`--dt 0.005` is the integration step, and it is not adjustable.** `0.02`
  diverges. If your run produces NaN, this is not where to look.
- **A full lap is ~189 simulated seconds** offline, ~243 through the full stack —
  the difference is that the oracle starts with way on rather than from rest.

### Running yours on the full stack

`src/regatta_agents/regatta_agents/helmsman.py` constructs the pilot. Today you
change the import there; making the class selectable by ROS parameter is on the
roadmap.

## What is not there yet

So you do not hunt for it:

- **No real start/finish line.** A racing line is a segment between two marks; here
  the leeward mark's perpendicular stands in for it, and it is infinite — which is
  why the boat crosses it several times while beating.
- **One competitor.** The plumbing underneath is already multi-vessel, but nothing
  above it is wired up yet.
- **The boat cannot be stopped.** The sail model has no stall, so no trim brings her
  to rest; the reference pilot starts a new lap at the finish instead. See
  `reference.md`.
- **No pilot selection without editing the node**, as above.

`ROADMAP.md` has the current state of each of these.

## Glossary of the simulation side

| term | meaning |
|---|---|
| **co-simulation** | two simulators advancing together, exchanging state each step. Here gz and xdyn. |
| **xdyn** | the physics server. Computes forces; remembers nothing between calls. |
| **gz** (Gazebo) | orchestrates the scene, the clock and the rendering. Its own physics is **off**. |
| **NED** | x North, y East, z Down — the physics frame. |
| **ENU** | x East, y North, z Up — the Gazebo frame. |
| **RTF** | real-time factor: simulated seconds per wall second. ≈ 1.0 for the full stack here. |
| **communication step** | one gz↔xdyn round trip, 0.01 s. |
| **integration step** | xdyn's internal step, `--dt 0.005`. |
| **the smoke gate** | the automated check that the boat rounds both marks in order. |
