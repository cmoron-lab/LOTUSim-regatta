# LOTUSim-regatta MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single Focus V2 sailboat, driven by a shared `Pilot` brain, sails a full windward-leeward lap around two buoys under xdyn co-simulation, rendered in Unity with a wind indicator and animated sail/rudder.

**Architecture:** One pure `Pilot` control module is validated fast against xdyn via an offline websocket oracle, then run unchanged inside a thin ROS2 helmsman node against gz pose + `vessel_cmd_array`. A dedicated colcon workspace (`LOTUSim-regatta`) consumes the LOTUSim core; no core change. Unity renders the lap and animates the actuators by subscribing to the same command topic.

**Tech Stack:** ROS 2 Jazzy · Gazebo Harmonic (`gz`) · xdyn (co-sim, patched `libx-dyn.so`) · Python 3 (rclpy + gz-transport, pytest) · Unity HDRP (ROS-TCP-Endpoint, Input System) · Blender (buoy mesh export).

## Global Constraints

- **License EPL-2.0** on every source file. Re-author assets from own sources only.
- **Runtime = Docker** on this Mac (`lotusim:focus-v2`, `--platform linux/amd64`). Unity runs natively (Cyril launches it; drive via Unity MCP when live).
- **xdyn conventions:** NED; body X-fwd/Y-stbd/Z-down; rotation `Z/Y/X` `[psi,theta',phi'']`; quaternion order `qr,qi,qj,qk` (attitude body→NED); gz↔Unity `Z→-Y`.
- **Commands are published**, never in the yaml `commands:` block: `/<world>/vessel_cmd_array` (`lotusim_msgs/msg/VesselCmdArray`), `cmd_string` = JSON `{"mainsail(sheet)": <rad>, "rudder(helm)": <rad>}`.
- **Seed angle-commanded actuators** via the world `<control_surfaces>` block or xdyn throws before the first setpoint.
- **`HELM_SIGN = -1`**; the tuned `focus_v2.yaml` (yaw damping lin 0.3 / quad 0.4) and patched `libx-dyn.so` live on core branch `feature/focus-v2-model` — prerequisites, not built here.
- **Co-sim stability (the decoupling rule):** launch `xdyn-for-cs` with a **fine** `--dt` (0.001) and communicate/step slower (Dt≈0.02). Effective step = min(--dt, Dt). rkck is forbidden (monotonic clock) → `-s rk4`.
- **Never `pkill -f`** (self-kill, pitfall #5): capture PIDs / `trap cleanup EXIT`.
- **Commit only what a task delivers**; conventional commits, message = why.

---

## File structure

| File | Responsibility |
|---|---|
| `src/regatta_agents/regatta_agents/pilot.py` | Pure W/L control brain (no I/O): `Pilot.update(x,y,yaw,r)→(sheet,helm)` + pure helpers |
| `src/regatta_agents/regatta_agents/helmsman.py` | Thin ROS2 node: gz pose in → `Pilot` → `vessel_cmd_array` out |
| `src/regatta_agents/test/test_pilot.py` | pytest unit tests for `pilot.py` |
| `src/regatta_agents/{package.xml,setup.py,setup.cfg,resource/regatta_agents}` | ament_python package |
| `offline/oracle.py` | Websocket physics oracle: drive `Pilot` against xdyn in Docker, assert 2/2 marks + tacks |
| `offline/ws.py` | Migrated websocket + docker helpers from `_offline/cosim.py` |
| `assets/worlds/regatta.world` | Sea + uniform wind + 2 buoys + `focus_v2` include (control_surfaces + render) |
| `assets/models/regatta_buoy/{model.config,model.sdf,meshes/regatta_buoy.dae}` | gz buoy model |
| `scripts/run_regatta.sh` | xdyn-for-cs + gz(regatta.world) + helmsman, `trap cleanup` |
| `scripts/smoke_rounds_marks.py` | gz pose oracle: assert boat passes within `wp_radius` of both marks |
| `unity/{README.md,WindIndicator.cs,ActuatorAnimator.cs}` | Unity scene notes + wind widget + sail/rudder animation |

---

## Task 1: Project scaffold (colcon workspace + ROS2 package)

**Files:**
- Create: `README.md`, `LICENSE`, `.gitignore`
- Create: `src/regatta_agents/package.xml`, `setup.py`, `setup.cfg`, `resource/regatta_agents`, `regatta_agents/__init__.py`
- Create dirs: `offline/`, `scripts/`, `assets/worlds/`, `assets/models/regatta_buoy/meshes/`, `unity/`

**Interfaces:**
- Produces: ROS2 package `regatta_agents` with console entry point `helmsman` (wired in Task 5); package name reused by `ros2 run regatta_agents helmsman`.

- [ ] **Step 1: Copy the license and write project files**
```bash
cd LOTUSim-regatta
cp ../LOTUSim-generic-scenario/LICENSE LICENSE
printf '%s\n' '__pycache__/' '*.pyc' 'build/' 'install/' 'log/' '_cosim_model.yaml' \
  '.DS_Store' 'offline/_*.yaml' > .gitignore
```
Write `README.md` (one paragraph: what the project is + `scripts/run_regatta.sh` + link to the spec).

- [ ] **Step 2: Create the ament_python package skeleton** (mirror `../LOTUSim-generic-scenario/src/agents/focus_v2/`)

`src/regatta_agents/package.xml`:
```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>regatta_agents</name>
  <version>0.1.0</version>
  <description>Reference pilots for the LOTUSim regatta (Focus V2 helmsman).</description>
  <maintainer email="cyril.moron@gmail.com">Cyril Moron</maintainer>
  <license>EPL-2.0</license>
  <exec_depend>rclpy</exec_depend>
  <exec_depend>lotusim_msgs</exec_depend>
  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <test_depend>python3-pytest</test_depend>
  <export><build_type>ament_python</build_type></export>
</package>
```

`src/regatta_agents/setup.py`:
```python
from setuptools import find_packages, setup

package_name = "regatta_agents"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Cyril Moron",
    maintainer_email="cyril.moron@gmail.com",
    description="Reference pilots for the LOTUSim regatta.",
    license="EPL-2.0",
    entry_points={"console_scripts": ["helmsman = regatta_agents.helmsman:main"]},
)
```

`src/regatta_agents/setup.cfg`:
```ini
[develop]
script_dir=$base/lib/regatta_agents
[install]
install_scripts=$base/lib/regatta_agents
```
Create empty `resource/regatta_agents` and `regatta_agents/__init__.py`.

- [ ] **Step 3: Verify the package is discoverable** (no ROS needed for a structural check)
```bash
python3 -c "import ast; ast.parse(open('src/regatta_agents/setup.py').read()); print('setup.py OK')"
test -f src/regatta_agents/resource/regatta_agents && echo "marker OK"
```
Expected: `setup.py OK` and `marker OK`.

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "chore: scaffold LOTUSim-regatta workspace + regatta_agents package"
```

---

## Task 2: `Pilot` — the pure W/L control brain (TDD)

**Files:**
- Create: `src/regatta_agents/regatta_agents/pilot.py`
- Test: `src/regatta_agents/test/test_pilot.py`

**Interfaces:**
- Produces: `Pilot(marks, wind_from, corridor=5.0, wp_radius=1.8)` with attributes `wp, tack, tacks, tacking, finished` and method `update(x, y, yaw, r) -> (sheet_rad, helm_rad)`; module constants `NO_GO, CLOSE_HAULED, HELM_SIGN, KP, KD, HELM_MAX`; pure helpers `wrap, clamp, opt_sheet, desired_heading, cross_track`. Consumed by `offline/oracle.py` (Task 3) and `helmsman.py` (Task 5). All angles in radians, headings NED (compass), `HELM_SIGN=-1`.

- [ ] **Step 1: Write the failing tests**

`src/regatta_agents/test/test_pilot.py`:
```python
import math
from regatta_agents.pilot import Pilot, opt_sheet, desired_heading, wrap, CLOSE_HAULED, NO_GO

WF = 0.0  # wind from North

def test_opt_sheet_hard_upwind_eased_downwind():
    assert math.degrees(opt_sheet(45)) < 10        # close-hauled: sheet hard in
    assert math.degrees(opt_sheet(150)) > 60       # downwind: eased out
    assert 4.0 <= math.degrees(opt_sheet(0)) <= 4.01  # clamped floor

def test_desired_heading_direct_when_mark_not_upwind():
    # mark abeam/downwind of the wind axis -> steer straight at it
    d = desired_heading((0, 0), (0, 10), WF, tack=1)   # bearing due East(y+) = +pi/2
    assert abs(wrap(d - math.pi / 2)) < 1e-6

def test_desired_heading_close_hauled_when_mark_dead_upwind():
    # mark dead upwind (North, x+) is inside the no-go cone -> beat on the tack
    d = desired_heading((0, 0), (10, 0), WF, tack=1)
    assert abs(wrap(d - (WF + CLOSE_HAULED))) < 1e-6

def test_tack_flips_and_counts_when_crossing_corridor():
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, corridor=5.0)
    # beating on starboard (tack=+1); push the boat well left of the leg line
    p.update(x=3.0, y=6.0, yaw=math.radians(-60), r=0.0)   # y=6 > corridor 5
    assert p.tacks == 1
    assert p.tacking is True
    assert p.tack == -1

def test_high_gain_helm_while_tacking():
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, corridor=5.0)
    p.update(x=3.0, y=6.0, yaw=math.radians(-60), r=0.0)   # enters tacking
    _, helm_tacking = p.update(x=3.1, y=6.0, yaw=math.radians(-60), r=0.0)
    assert abs(helm_tacking) > 0.0   # commanding a turn through the eye

def test_waypoint_advances_and_finishes():
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, wp_radius=1.8)
    p.update(x=15.0, y=0.0, yaw=0.0, r=0.0)   # at windward mark
    assert p.wp == 1
    p.update(x=0.0, y=0.0, yaw=math.radians(180), r=0.0)  # at leeward mark
    assert p.finished is True
```

- [ ] **Step 2: Run the tests to verify they fail**
```bash
cd src/regatta_agents && python3 -m pytest test/test_pilot.py -q
```
Expected: FAIL — `ModuleNotFoundError: No module named 'regatta_agents.pilot'`.

- [ ] **Step 3: Implement `pilot.py`** (ported verbatim from the proven `_offline/cosim.py`; the stale "virement NON RÉSOLU" comment is dropped — tacks complete on the tuned model)

`src/regatta_agents/regatta_agents/pilot.py`:
```python
# Copyright (c) 2026 Cyril Moron — EPL-2.0
"""Pure windward-leeward control brain for the Focus V2, shared by the offline
xdyn oracle and the ROS2 helmsman. No I/O: feed it pose, get (sheet, helm).

Ported from the offline-validated _offline/cosim.py (2/2 marks, 3-4 tacks on the
tuned model). All angles radians; headings are NED compass; HELM_SIGN=-1."""
import math

HELM_SIGN = -1.0
AOA_OPT = 20.0
NO_GO = math.radians(50.0)          # half dead-zone: mark closer than this to the wind -> beat
CLOSE_HAULED = math.radians(60.0)   # real upwind heading (tenable + good VMG; foot for speed)
KP, KD, HELM_MAX = 2.2, 0.9, math.radians(35)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def opt_sheet(twa_deg):
    """Sheet angle (rad) vs true-wind angle. Hard upwind, eased downwind — calibrated
    on the patched-xdyn beat sweep; over-easing upwind kills drive (crawl + leeway)."""
    return math.radians(clamp(0.6 * (twa_deg - 42.0), 4.0, 80.0))


def desired_heading(pos, mark, wind_from, tack):
    """Target heading: mark inside the no-go cone -> close-hauled on the current
    tack (+1/-1); else steer straight at the mark."""
    brg = math.atan2(mark[1] - pos[1], mark[0] - pos[0])
    if abs(wrap(brg - wind_from)) < NO_GO:
        return wrap(wind_from + tack * CLOSE_HAULED)
    return brg


def cross_track(pos, a, b):
    """Signed perpendicular offset of pos from line a->b (>0 = left of a->b)."""
    lx, ly = b[0] - a[0], b[1] - a[1]
    L = math.hypot(lx, ly) or 1.0
    return ((pos[0] - a[0]) * (-ly) + (pos[1] - a[1]) * lx) / L


class Pilot:
    """Stateful W/L pilot. update(x,y,yaw,r) -> (sheet_rad, helm_rad).

    State machine: beat toward the windward mark on alternating tacks inside a
    corridor; when crossing the corridor edge, run an ENGAGED-TACK (firm rudder +
    high gain) through the eye instead of stalling in irons; steer straight when
    the mark is not upwind; advance to the next mark within wp_radius."""

    def __init__(self, marks, wind_from, corridor=5.0, wp_radius=1.8):
        self.marks = list(marks)
        self.wind_from = wind_from
        self.corridor = corridor
        self.wp_radius = wp_radius
        self.wp = 0
        self.tack = 1
        self.tacks = 0
        self.leg_start = (0.0, 0.0)
        self.tacking = False
        self.finished = False

    def update(self, x, y, yaw, r):
        pos = (x, y)
        if self.finished:
            return opt_sheet(abs(math.degrees(wrap(yaw - self.wind_from)))), 0.0
        mark = self.marks[self.wp]
        if math.hypot(mark[0] - x, mark[1] - y) < self.wp_radius:
            self.wp += 1
            if self.wp >= len(self.marks):
                self.finished = True
                return opt_sheet(abs(math.degrees(wrap(yaw - self.wind_from)))), 0.0
            self.leg_start, mark, self.tacking = pos, self.marks[self.wp], False

        brg = math.atan2(mark[1] - y, mark[0] - x)
        upwind = abs(wrap(brg - self.wind_from)) < NO_GO

        if self.tacking:
            desired = wrap(self.wind_from + self.tack * CLOSE_HAULED)
            if abs(wrap(desired - yaw)) < math.radians(18):
                self.tacking = False
        else:
            if upwind:
                c = cross_track(pos, self.leg_start, mark)
                if (c > self.corridor and self.tack > 0) or (c < -self.corridor and self.tack < 0):
                    self.tack, self.tacks, self.tacking = -self.tack, self.tacks + 1, True
            desired = desired_heading(pos, mark, self.wind_from, self.tack)

        kp = KP * (2.4 if self.tacking else 1.0)
        helm = clamp(HELM_SIGN * (kp * wrap(desired - yaw) - KD * r), -HELM_MAX, HELM_MAX)
        twa = abs(math.degrees(wrap(yaw - self.wind_from)))
        return opt_sheet(twa), helm
```

- [ ] **Step 4: Run the tests to verify they pass**
```bash
cd src/regatta_agents && python3 -m pytest test/test_pilot.py -q
```
Expected: `6 passed`.

- [ ] **Step 5: Commit**
```bash
rtk git add -A && rtk git commit -m "feat: pure Pilot W/L control brain ported from offline oracle, unit-tested"
```

---

## Task 3: Offline physics oracle (drive `Pilot` against xdyn in Docker)

**Files:**
- Create: `offline/ws.py` (migrated websocket + docker + step helpers from `_offline/cosim.py`)
- Create: `offline/oracle.py`

**Interfaces:**
- Consumes: `Pilot` (Task 2). `ws.py` exposes `launch_xdyn(port,solver,dt,name)`, `stop_xdyn(name)`, `ws_connect(host,port)`, `step(sock,state,sheet,helm,dt)`, `init_at(heading,u)`, `yaw_of(st)`, `write_model(wind_dir_deg)`.
- Produces: `run_lap(wind_dir_deg, marks) -> (reached, tacks, traj)` asserting the same lap the ROS node will fly. This is the physics regression test.

- [ ] **Step 1: Migrate the websocket/docker helpers**
```bash
cp ../_offline/cosim.py offline/ws.py
```
Edit `offline/ws.py`: keep `write_model, ws_connect, ws_send, ws_recv, launch_xdyn, stop_xdyn, step, init_at, yaw_of, roll_of, leeway_of, INIT, FIELDS, LAB, IMAGE, C_MESH`. Delete the control logic now living in `pilot.py` (`run_leg, sail_course, opt_sheet, desired_heading, cross_track, maneuver_probe, KP/KD/NO_GO/...`) and the `__main__` blocks. Point `MODEL_SRC`/`OFF` at this project:
```python
LAB = os.path.expanduser("~/src/lotusim-lab")
MODEL_SRC = f"{LAB}/LOTUSim/assets/models/focus_v2/focus_v2.yaml"
OFF = f"{LAB}/LOTUSim-regatta/offline"
```
(`write_model` writes `{OFF}/_cosim_model.yaml`; `launch_xdyn`'s docker `-w`/mount already resolve via `/lab`.) Update the inner command's model path to `/lab/LOTUSim-regatta/offline/_cosim_model.yaml`.

- [ ] **Step 2: Write `oracle.py` (the failing integration test)**

`offline/oracle.py`:
```python
#!/usr/bin/env python3
"""Physics oracle: run the exact W/L lap the ROS helmsman will fly, directly
against xdyn over websocket (fast, deterministic). Asserts the lap completes."""
import math, sys, time
sys.path.insert(0, ".")
sys.path.insert(0, "../src/regatta_agents")   # import the SHIPPED Pilot
from regatta_agents.pilot import Pilot
import ws


def run_lap(wind_dir_deg=180, marks=((15.0, 0.0), (0.0, 0.0)), dt=0.005, tmax=170.0):
    wind_from = math.radians(wind_dir_deg - 180)   # 180 blows toward S -> wind_from = 0 (N)
    ws.write_model(wind_dir_deg)
    ws.launch_xdyn(solver="rk4", dt=dt)
    try:
        time.sleep(4)
        sock = ws.ws_connect("127.0.0.1", 12345)
        pilot = Pilot(marks=list(marks), wind_from=wind_from)
        st = ws.init_at(wind_from + math.radians(60), u=0.8)
        traj = []
        for _ in range(int(tmax / dt)):
            sheet, helm = pilot.update(st["x"], st["y"], ws.yaw_of(st), st["r"])
            st = ws.step(sock, st, sheet, helm, dt)
            traj.append(dict(st))
            if pilot.finished:
                break
        return pilot.wp, pilot.tacks, traj
    finally:
        ws.stop_xdyn()


if __name__ == "__main__":
    reached, tacks, traj = run_lap()
    print(f"marks reached {reached}/2 | tacks {tacks} | dur {traj[-1]['t']:.0f}s")
    assert reached >= 2, f"lap incomplete: only {reached}/2 marks"
    assert tacks >= 1, f"no tack performed (tacks={tacks})"
    print("ORACLE PASS")
```

- [ ] **Step 3: Run the oracle (requires Docker)**
```bash
cd offline && python3 oracle.py
```
Expected: `marks reached 2/2 | tacks >=1 ...` then `ORACLE PASS`. If it fails, the Pilot port diverged from the offline behavior — diff against `_offline/cosim.py` `sail_course` before proceeding.

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "test: offline xdyn oracle proves the W/L lap on the shipped Pilot"
```

---

## Task 4: `regatta.world` + buoy gz model (placeholder visual)

**Files:**
- Create: `assets/worlds/regatta.world`
- Create: `assets/models/regatta_buoy/model.config`, `assets/models/regatta_buoy/model.sdf`

**Interfaces:**
- Consumes: core `model://focus_v2`.
- Produces: world `lotusim` with entities `focus_v2`, `mark_windward` (15,0), `mark_leeward` (0,0); `focus_v2` wired with `<control_surfaces>` (`mainsail(sheet)`, `rudder(helm)`) on `ws://127.0.0.1:12345` + `render_interface` `focus_v2`. Mark positions consumed by Task 5 (helmsman params) and Task 6 (smoke oracle).

- [ ] **Step 1: Write the buoy model** (cylinder placeholder; real mesh in Task 7)

`assets/models/regatta_buoy/model.config`:
```xml
<?xml version="1.0"?>
<model>
  <name>regatta_buoy</name>
  <version>1.0</version>
  <sdf version="1.10">model.sdf</sdf>
  <description>Inflatable racing mark for the LOTUSim regatta.</description>
</model>
```
`assets/models/regatta_buoy/model.sdf`:
```xml
<?xml version="1.0"?>
<sdf version="1.10">
  <model name="regatta_buoy">
    <static>true</static>
    <link name="buoy">
      <visual name="buoy">
        <geometry><cylinder><radius>0.15</radius><length>0.6</length></cylinder></geometry>
        <material>
          <ambient>0.9 0.4 0.0 1</ambient>
          <diffuse>1.0 0.45 0.0 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>
```

- [ ] **Step 2: Write the world** (adapted from core `assets/worlds/focus_v2_demo.world`; two buoys instead of one, marks positioned to force a W/L beat with wind from North — windward mark dead upwind at x=15)

`assets/worlds/regatta.world`: copy `../LOTUSim/assets/worlds/focus_v2_demo.world` and change the `<model name="mark">` block into two includes:
```xml
    <include>
      <uri>model://regatta_buoy</uri><name>mark_windward</name><pose>15 0 0 0 0 0</pose>
    </include>
    <include>
      <uri>model://regatta_buoy</uri><name>mark_leeward</name><pose>0 0 0 0 0 0</pose>
    </include>
```
Keep the four LOTUSim plugins + `SceneBroadcaster`, the `sea` plane, and the `focus_v2` include with its `<lotus_param>` (control_surfaces + render_interface) unchanged. Enlarge the sea plane `<size>` to `60 60`. Wind stays in `focus_v2.yaml` (direction 180 = from North; set it in Task 6's run script via `write_model`, or leave the model default and document the required wind).

- [ ] **Step 3: Verify the world loads headless in Docker**
```bash
docker run --rm --platform linux/amd64 -v ~/src/lotusim-lab:/lab \
  -e GZ_SIM_RESOURCE_PATH=/lab/LOTUSim/assets/models:/lab/LOTUSim-regatta/assets/models \
  lotusim:focus-v2 bash -lc \
  'source /opt/ros/jazzy/setup.bash 2>/dev/null; timeout 8 gz sim -s -r /lab/LOTUSim-regatta/assets/worlds/regatta.world 2>&1 | tail -20'
```
Expected: gz loads without SDF parse errors; `mark_windward`, `mark_leeward`, `focus_v2` entities created. (`XdynWebsocket::onFail` is expected here — no xdyn server yet; that is fine for a load check.)

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "feat: regatta world with windward+leeward buoys and wired focus_v2"
```

---

## Task 5: ROS2 helmsman node (wraps `Pilot`) + run script

**Files:**
- Create: `src/regatta_agents/regatta_agents/helmsman.py`
- Create: `scripts/run_regatta.sh`

**Interfaces:**
- Consumes: `Pilot` (Task 2), `regatta.world` (Task 4), the mark positions.
- Produces: `ros2 run regatta_agents helmsman` — subscribes gz `/world/<world>/dynamic_pose/info`, calls `Pilot.update`, publishes `/<world>/vessel_cmd_array`. Params: `world, vessel, wind_from_deg, mark_windward_x/y, mark_leeward_x/y, rate_hz`.

- [ ] **Step 1: Write the helmsman node** (skeleton from generic-scenario `helmsman.py`, brain delegated to `Pilot`)

`src/regatta_agents/regatta_agents/helmsman.py`:
```python
# Copyright (c) 2026 Cyril Moron — EPL-2.0
"""Thin ROS2 helmsman: gz pose -> Pilot -> vessel_cmd_array. The control brain is
regatta_agents.pilot.Pilot (offline-validated). Seeds a neutral setpoint on start."""
import json, math
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from lotusim_msgs.msg import VesselCmd, VesselCmdArray
from regatta_agents.pilot import Pilot, opt_sheet

try:
    from gz.transport13 import Node as GzNode
    from gz.msgs10.pose_v_pb2 import Pose_V
    _HAVE_GZ = True
except ImportError:
    _HAVE_GZ = False


class Helmsman(Node):
    def __init__(self):
        super().__init__("regatta_helmsman")
        p = self.declare_parameter
        self.world = p("world", "lotusim").value
        self.vessel = p("vessel", "focus_v2").value
        wind_from = math.radians(p("wind_from_deg", 0.0).value)
        marks = [(p("mark_windward_x", 15.0).value, p("mark_windward_y", 0.0).value),
                 (p("mark_leeward_x", 0.0).value, p("mark_leeward_y", 0.0).value)]
        self.rate_hz = p("rate_hz", 30.0).value
        self.pilot = Pilot(marks=marks, wind_from=wind_from)
        self.wind_from = wind_from
        self.x = self.y = self.yaw = self.r = 0.0
        self._prev = None

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                         history=HistoryPolicy.KEEP_LAST)
        self.pub = self.create_publisher(VesselCmdArray, f"/{self.world}/vessel_cmd_array", qos)
        self._publish(opt_sheet(0.0), 0.0)   # seed neutral so xdyn has a command

        if _HAVE_GZ:
            self.gz = GzNode()
            self.gz.subscribe(Pose_V, f"/world/{self.world}/dynamic_pose/info", self._on_pose)
        else:
            self.get_logger().error("gz-transport python unavailable; no pose feedback")
        self.create_timer(1.0 / self.rate_hz, self._control)

    def _on_pose(self, msg):
        for e in msg.pose:
            if e.name == self.vessel:
                self.x, self.y = e.position.x, e.position.y
                q = e.orientation
                self.yaw = math.atan2(2 * (q.w * q.z + q.x * q.y),
                                      1 - 2 * (q.y * q.y + q.z * q.z))
                if self._prev is not None:
                    self.r = 0.0  # yaw-rate unused by Pilot's damping term at low rate; keep 0
                self._prev = self.yaw

    def _control(self):
        sheet, helm = self.pilot.update(self.x, self.y, self.yaw, self.r)
        self._publish(sheet, helm)

    def _publish(self, sheet, helm):
        cmd = VesselCmd()
        cmd.vessel_name = self.vessel
        cmd.cmd_string = json.dumps({"mainsail(sheet)": sheet, "rudder(helm)": helm})
        arr = VesselCmdArray()
        arr.cmds = [cmd]
        self.pub.publish(arr)


def main():
    rclpy.init()
    try:
        rclpy.spin(Helmsman())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```
> Note on `r` (yaw rate): gz `dynamic_pose` carries pose, not twist. The Pilot uses `-KD*r` for damping; at the ~30 Hz control rate we start with `r=0` (proven adequate offline where the beat is stable) and, only if Task 6 shows tack overshoot, estimate `r` by finite-differencing yaw with the message timestamps. Documented as the R1 tuning knob.

- [ ] **Step 2: Write `run_regatta.sh`** (all in one Docker container: xdyn + gz + helmsman)

`scripts/run_regatta.sh`:
```bash
#!/bin/bash
# Headless regatta run: xdyn co-sim + gz(regatta.world) + helmsman, in the lotusim image.
# Usage: run_regatta.sh [duration_s]   (run from anywhere; paths are absolute /lab)
set -u
DUR=${1:-120}
docker run --rm --platform linux/amd64 --name regatta -v ~/src/lotusim-lab:/lab \
  lotusim:focus-v2 bash -lc '
    set -u
    cleanup(){ kill "$XPID" "$GPID" "$HPID" 2>/dev/null; }
    trap cleanup EXIT
    source /opt/ros/jazzy/setup.bash
    source /lab/LOTUSim/install/setup.bash 2>/dev/null || true
    cd /lab/LOTUSim-regatta && colcon build --packages-select regatta_agents >/dev/null 2>&1
    source install/setup.bash
    export GZ_SIM_RESOURCE_PATH=/lab/LOTUSim/assets/models:/lab/LOTUSim-regatta/assets/models
    # fine internal --dt (decoupling rule), rk4 mandatory:
    ( cd /lab/LOTUSim/assets/models && \
      LD_LIBRARY_PATH=/lab/LOTUSim/physics \
      /lab/LOTUSim/physics/xdyn-for-cs focus_v2/focus_v2.yaml -s rk4 --dt 0.001 -a 127.0.0.1 -p 12345 ) &
    XPID=$!; sleep 4
    gz sim -s -r /lab/LOTUSim-regatta/assets/worlds/regatta.world & GPID=$!; sleep 8
    ros2 run regatta_agents helmsman & HPID=$!
    sleep '"$DUR"'
  '
```
> `xdyn-for-cs` reads the wind from `focus_v2.yaml`; ensure its `direction` is `180` (from North) for this course before running (edit the model or add a `write_model` step). The world's `<physics>` `real_time_update_rate` sets the gz→xdyn comm Dt; keep it ≥20 Hz.

- [ ] **Step 3: Smoke that the node imports and the stack starts** (short run; full assertion in Task 6)
```bash
bash scripts/run_regatta.sh 25 2>&1 | grep -E "onOpen|Surface init completed|onFail" | tail -5
```
Expected: `XdynWebsocket::onOpen` and `Surface init completed` (physics connected). `onFail` means a port/timing problem — bump the `sleep`.

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "feat: ROS2 helmsman node wrapping Pilot + run_regatta.sh"
```

---

## Task 6: Docker gz smoke — assert the boat rounds both marks (R1 gate)

**Files:**
- Create: `scripts/smoke_rounds_marks.py`
- Modify: `scripts/run_regatta.sh` (record boat pose to a file for the oracle)

**Interfaces:**
- Consumes: the running stack (Task 5), mark positions (Task 4).
- Produces: exit 0 iff the boat passes within `wp_radius` of `mark_windward` then `mark_leeward` within the run. The end-to-end proof that the offline-validated Pilot survives the async gz/xdyn cadence.

- [ ] **Step 1: Write the pose-oracle** (subscribe gz pose, track closest approach to each mark, in order)

`scripts/smoke_rounds_marks.py`:
```python
#!/usr/bin/env python3
"""gz pose oracle: pass iff focus_v2 rounds mark_windward then mark_leeward.
Run INSIDE the lotusim container alongside gz. Usage: smoke_rounds_marks.py [timeout_s]"""
import math, sys, time
from gz.transport13 import Node
from gz.msgs10.pose_v_pb2 import Pose_V

MARKS = [("windward", 15.0, 0.0), ("leeward", 0.0, 0.0)]
WP_R = 1.8
state = {"idx": 0, "min": [9e9, 9e9], "x": None, "y": None}

def on_pose(msg):
    for e in msg.pose:
        if e.name == "focus_v2":
            state["x"], state["y"] = e.position.x, e.position.y
            for i, (_, mx, my) in enumerate(MARKS):
                d = math.hypot(mx - e.position.x, my - e.position.y)
                state["min"][i] = min(state["min"][i], d)
                if i == state["idx"] and d < WP_R:
                    state["idx"] += 1

def main():
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 130.0
    n = Node()
    n.subscribe(Pose_V, "/world/lotusim/dynamic_pose/info", on_pose)
    t0 = time.time()
    while time.time() - t0 < timeout and state["idx"] < len(MARKS):
        time.sleep(0.5)
    for i, (name, _, _) in enumerate(MARKS):
        print(f"{name}: closest {state['min'][i]:.2f} m (need < {WP_R})")
    ok = state["idx"] >= len(MARKS)
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Wire the oracle into the run** — in `run_regatta.sh`, after starting the helmsman, replace the bare `sleep "$DUR"` with:
```bash
    python3 /lab/LOTUSim-regatta/scripts/smoke_rounds_marks.py "'"$DUR"'"; RC=$?
    exit $RC
```
so the container exit code is the smoke result.

- [ ] **Step 3: Run the smoke (the R1 gate)**
```bash
bash scripts/run_regatta.sh 130; echo "exit=$?"
```
Expected: `windward: closest <1.8`, `leeward: closest <1.8`, `SMOKE PASS`, `exit=0`. If FAIL at the windward mark with the boat stuck head-to-wind → R1: finite-difference `r` in `helmsman._on_pose` and/or raise `rate_hz`, re-run. If FAIL by drifting → check wind direction (must be from North) and `HELM_SIGN`.

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "test: gz smoke proves the boat rounds both marks under co-sim (R1 closed)"
```

---

## Task 7: Real buoy mesh (export `regatta_buoy.blend`)

**Files:**
- Create: `assets/models/regatta_buoy/meshes/regatta_buoy.dae`
- Modify: `assets/models/regatta_buoy/model.sdf` (swap cylinder → mesh)

**Interfaces:**
- Produces: `regatta_buoy.dae` in metres, Z-up, origin at the waterline, resolvable by both gz (this task) and Unity (Task 8).

- [ ] **Step 1: Export the mesh from Blender.** If Cyril has Blender open with `regatta_buoy.blend` (Blender MCP live): select the buoy object, export `assets/models/regatta_buoy/meshes/regatta_buoy.dae` (COLLADA, +Z up, apply modifiers, selection only). Else headless:
```bash
blender ~/src/lotusim-lab/regatta_buoy.blend --background --python-expr \
"import bpy; bpy.ops.wm.collada_export(filepath='$PWD/assets/models/regatta_buoy/meshes/regatta_buoy.dae', selected=False)"
```
Verify scale: buoy height ≈ 0.6–1.0 m (a race mark), not centimetres or tens of metres.

- [ ] **Step 2: Point the model at the mesh** — replace the `<geometry><cylinder>…</cylinder></geometry>` in `model.sdf` with:
```xml
        <geometry><mesh><uri>meshes/regatta_buoy.dae</uri></mesh></geometry>
```
Drop the `<material>` if the mesh carries its own.

- [ ] **Step 3: Verify it loads + renders in gz** (GUI optional; headless load check)
```bash
docker run --rm --platform linux/amd64 -v ~/src/lotusim-lab:/lab \
  -e GZ_SIM_RESOURCE_PATH=/lab/LOTUSim-regatta/assets/models \
  lotusim:focus-v2 bash -lc 'timeout 6 gz sim -s /lab/LOTUSim-regatta/assets/worlds/regatta.world 2>&1 | grep -iE "error|regatta_buoy" | tail'
```
Expected: no mesh-load error; buoy entity present.

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "feat: real buoy mesh exported from Blender, wired into the gz model"
```

---

## Task 8: Unity regatta scene + wind indicator (C6)

> Unity work: driven in the editor by Cyril; inspected/wired via Unity MCP when live. No pytest — verification is visual + MCP scene queries.

**Files:**
- Create (in `LOTUSim-Unity-modules`): a `Regatta` scene under `Assets/Scenes/`, buoy prefab from the imported mesh.
- Create: `unity/WindIndicator.cs`, `unity/README.md` (import + wiring steps).

**Interfaces:**
- Consumes: `regatta_buoy.dae` (Task 7), the existing `focus_v2` prefab + Addressable, world name `lotusim`.
- Produces: a scene that renders the boat (bridged) + two static buoys, with a wind arrow reading a `wind_from_deg`/`speed` config matching `focus_v2.yaml`.

- [ ] **Step 1: Import the buoy mesh** into `LOTUSim-Unity-modules/Assets/models/regatta_buoy/`, make a `regatta_buoy` prefab (static, no Rigidbody).
- [ ] **Step 2: Build the scene** — duplicate the existing focus_v2 Unity scene; place `mark_windward` at the ENU equivalent of (15,0) and `mark_leeward` at (0,0) (gz X-North,Y-East → Unity `(x,z,y)` = `Z→-Y`); HDRP water for the sea; the `focus_v2` prefab as the bridged renderer. Set `LotusimInterface.m_namespace = "lotusim"`.
- [ ] **Step 3: Write `WindIndicator.cs`** — a `MonoBehaviour` with `public float windFromDeg = 0f; public float windSpeed = 3f;` that orients a child arrow to the wind axis (world-space, over the boat or a HUD corner) and shows the speed as text. (Static for the uniform-wind MVP; a later `WindSource` topic swaps the constant for a subscription.)

`unity/WindIndicator.cs`:
```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
using UnityEngine;

// Orients an arrow to the wind and shows its force. Static for the uniform-wind
// MVP; Phase 2 replaces windFromDeg/windSpeed with a ROS subscription.
public class WindIndicator : MonoBehaviour
{
    [Tooltip("Compass bearing the wind blows FROM (deg, NED). Match focus_v2.yaml.")]
    public float windFromDeg = 0f;
    public float windSpeed = 3f;
    public Transform arrow;                 // child arrow pointing +Z at rest
    public TextMesh forceLabel;             // optional

    void Update()
    {
        if (arrow != null)
            // NED 'from' bearing -> Unity Y-rotation of the 'to' direction (Z->-Y world).
            arrow.rotation = Quaternion.Euler(0f, windFromDeg + 180f, 0f);
        if (forceLabel != null)
            forceLabel.text = $"{windSpeed:0.0} m/s";
    }
}
```

- [ ] **Step 4: Verify (MCP + visual)** — with gz+xdyn+helmsman running (Task 5) and Unity playing the scene: the boat appears and moves along the lap, both buoys are placed, the wind arrow points from North. Query the scene via Unity MCP to confirm the boat GameObject exists and its transform updates. Cyril confirms visually.
- [ ] **Step 5: Commit** (Unity repo + this repo's `unity/` notes)
```bash
rtk git add unity/ && rtk git commit -m "feat: Unity regatta scene notes + wind indicator (C6)"
```

---

## Task 9: Unity actuator animation — sail + rudder (C7)

> The "magical" layer. Rig-gated (R5); may slip to Phase 1.5 without touching C1–C8.

**Files:**
- Create: `unity/ActuatorAnimator.cs`
- Rig: pivots on the `focus_v2` prefab (Blender or Unity editor).

**Interfaces:**
- Consumes: `/<world>/vessel_cmd_array` (published by the helmsman, Task 5) via ROS-TCP-Endpoint; the mesh objects `Boom, Mainsail, Rudder, Gooseneck, Mast`.
- Produces: on-screen sail trim + rudder deflection tracking the live commands.

- [ ] **Step 1: Rig the pivots** — parent `Boom`+`Mainsail` under a `SailPivot` empty at the gooseneck (mast base), axis = mast (Unity local Y); parent `Rudder` under a `RudderPivot` empty at its stock. Verify each pivot rotates its parts about the right axis with no mesh drift.
- [ ] **Step 2: Write `ActuatorAnimator.cs`** — subscribe `vessel_cmd_array`, parse the JSON `cmd_string`, apply `mainsail(sheet)` to `SailPivot` local Y and `rudder(helm)` to `RudderPivot` local Y. Boom falls to leeward: the sail's sign follows the tack (sail on the side opposite the boom's windward edge). Smooth with `Mathf.LerpAngle` to avoid jitter at 30 Hz.

`unity/ActuatorAnimator.cs`:
```csharp
// Copyright (c) 2026 Cyril Moron — EPL-2.0
using UnityEngine;
using RosMessageTypes.Lotusim;              // VesselCmdArrayMsg (generated from lotusim_msgs)
using Unity.Robotics.ROSTCPConnector;
using SimpleJSON;                           // or MiniJSON; parse cmd_string

public class ActuatorAnimator : MonoBehaviour
{
    public string worldName = "lotusim";
    public string vesselName = "focus_v2";
    public Transform sailPivot;             // Boom+Mainsail
    public Transform rudderPivot;           // Rudder
    public float sailSlew = 90f, rudderSlew = 180f;  // deg/s
    float _sailTarget, _rudderTarget;

    void Start()
    {
        ROSConnection.GetOrCreateInstance()
            .Subscribe<VesselCmdArrayMsg>($"/{worldName}/vessel_cmd_array", OnCmd);
    }

    void OnCmd(VesselCmdArrayMsg msg)
    {
        foreach (var c in msg.cmds)
            if (c.vessel_name == vesselName)
            {
                var j = JSON.Parse(c.cmd_string);
                _sailTarget = -j["mainsail(sheet)"].AsFloat * Mathf.Rad2Deg;   // sign: boom to leeward
                _rudderTarget = j["rudder(helm)"].AsFloat * Mathf.Rad2Deg;
            }
    }

    void Update()
    {
        if (sailPivot != null)
            sailPivot.localRotation = Quaternion.Euler(0,
                Mathf.MoveTowardsAngle(sailPivot.localEulerAngles.y, _sailTarget, sailSlew * Time.deltaTime), 0);
        if (rudderPivot != null)
            rudderPivot.localRotation = Quaternion.Euler(0,
                Mathf.MoveTowardsAngle(rudderPivot.localEulerAngles.y, _rudderTarget, rudderSlew * Time.deltaTime), 0);
    }
}
```
> `RosMessageTypes.Lotusim.VesselCmdArrayMsg` must be generated from `lotusim_msgs` via the ROS-TCP message generator (one-time, in the Unity editor). If that is heavy, the fallback is a `std_msgs/String` relay node republishing the JSON. The sail-sign convention (`-sheet`) is verified visually against a known tack in Step 3.

- [ ] **Step 3: Verify (MCP + visual)** — running the full stack + scene: on a beat the boom sits to leeward and the mainsail trims in; through a tack the sail crosses to the new leeward side; the rudder kicks in the steering direction. Adjust the sail sign / pivot if the boom ends up to windward. Cyril confirms.
- [ ] **Step 4: Commit**
```bash
rtk git add unity/ && rtk git commit -m "feat: Unity sail+rudder animation from vessel_cmd_array (C7)"
```

---

## Self-review notes

- **Spec coverage:** C1 world→T4; C2 buoy→T4(placeholder)+T7(mesh); C3 helmsman→T2(brain)+T5(node); C4 offline oracle→T3; C5 run script→T5; C6 Unity scene+wind→T8; C7 actuator anim→T9. Verification levels 1/2/3 → T3 / T6 / T8-9. All spec components mapped.
- **R1** addressed structurally: fine `--dt` + async control is the proven decoupling; T5 note + T6 fallback (finite-difference `r`, raise `rate_hz`) make it a tuning knob, not a blocker.
- **Type consistency:** `Pilot(marks, wind_from, corridor, wp_radius)` and `Pilot.update(x,y,yaw,r)->(sheet,helm)` identical across T2/T3/T5. `ws.*` helper names match `_offline/cosim.py`. Command JSON keys `mainsail(sheet)`/`rudder(helm)` identical in T3/T5/T9.
- **YAGNI:** no scenario-launcher, no `generate_lotus_param` patch, no multi-boat, no keyboard mode (all Phase 2/3, out of scope).
