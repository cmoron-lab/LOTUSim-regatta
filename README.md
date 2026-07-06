# LOTUSim-regatta

A dedicated, out-of-tree LOTUSim project for a pedagogical **windward-leeward
regatta**: a Focus V2 sailboat sails a full W/L lap around two buoys under xdyn
co-simulation, rendered in Unity. It consumes the LOTUSim core unchanged; the
race pilots, world, buoy, and Unity integration live here.

The control brain (`src/regatta_agents/regatta_agents/pilot.py`) is validated
fast against xdyn by the offline websocket oracle (`offline/oracle.py`), then run
unchanged inside the ROS2 helmsman node (`helmsman.py`) against Gazebo.

## Run (headless co-simulation, Docker)

```bash
scripts/run_regatta.sh 120        # xdyn-for-cs + gz(regatta.world) + helmsman
```

## Design

- Spec: `docs/design/2026-07-06-regatta-mvp-design.md`
- Plan: `docs/plans/2026-07-06-regatta-mvp-plan.md`

License: EPL-2.0.
