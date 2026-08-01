# Unity Regatta scenario

The active renderer is the sibling project
[`LOTUSim-Unity6-modules`](https://github.com/cmoron-lab/LOTUSim-Unity6-modules),
on `main`:

- Unity `6000.3.21f1`;
- HDRP `17.3.0`;
- scene `Assets/Scenes/Regatta/Regatta.unity`.

This repository owns the scenario and simulation stack. The Unity 6 project is
the sole source of truth for renderer scripts, shaders, scenes, prefabs, and
EditMode tests.

## Runtime boundary

Unity renders poses and commands received through ROS-TCP; it does not compute
the boat physics. Keep the scene's `LotusimInterface` namespace set to `lotusim`,
matching the `<world name="lotusim">` in `regatta.world`.

Do not place the boat or marks by hand. The bridge spawns them from renderer
commands, and `renderer_type_name = focus_v2` resolves the Addressable prefab at
`Assets/models/focus_v2/focus_v2.prefab`. A hand-placed copy becomes an inert
duplicate beside the simulated object.

The active scenario scripts live under `Assets/Scripts/Regatta/` in the Unity 6
project:

- `ActuatorAnimator` animates the mainsail and rudder from vessel commands;
- `ManualHelm` publishes an optional manual override;
- `RegattaCameraRig` provides chase, orbit, onboard, and free cameras;
- `RegattaHud` and `RenderBudget` provide the runtime display controls;
- `NativeFoamWakeController` is the only wake implementation.

The wake uses one subtle bow stamp and one stronger stern stamp through
`Assets/Shaders/WakeFoamStamp.shader`. It writes foam into HDRP's persistent
world-space buffer and deliberately adds no analytical wave deformation.

## Run in the editor

From this repository:

```bash
UNITY=1 ./scripts/run_regatta.sh 900 hold
```

The script starts the ROS-TCP endpoint and waits for Unity. Open the Regatta
scene in the sibling project and press Play when the terminal prints
`[*] waiting for Unity ...`.

Keep the Unity editor focused during Play: an unfocused editor throttles this
project and can stop the scene from advancing. Use `hold`, not `smoke`, for an
interactive session; `smoke` is a pass/fail gate with a hard timeout.

Useful controls:

- `C`: cycle camera modes;
- `M`: toggle manual helm;
- arrow keys: rudder and sheet in manual mode;
- `B`: rebind physical helm and sheet axes;
- `K`, `L`, `O`: change render-budget presets.

## EditMode verification

With the editor closed:

```bash
cd ../LOTUSim-Unity6-modules
/Applications/Unity/Hub/Editor/6000.3.21f1/Unity.app/Contents/MacOS/Unity \
  -batchmode -nographics -projectPath "$PWD" \
  -runTests -testPlatform EditMode \
  -testResults /tmp/lotusim-unity6-editmode.xml \
  -logFile /tmp/lotusim-unity6-editmode.log
```

Do not combine `-runTests` with `-quit`: the Test Runner exits Unity itself.
Check that the generated XML reports `result="Passed"`; the process exit code
alone is not sufficient proof.

## Standalone player

The same project builds a native player and refreshes its Addressables catalog:

```bash
cd ../LOTUSim-Unity6-modules
/Applications/Unity/Hub/Editor/6000.3.21f1/Unity.app/Contents/MacOS/Unity \
  -batchmode -quit -projectPath "$PWD" \
  -executeMethod BuildRegatta.Build \
  -logFile /tmp/lotusim-unity6-build.log
```

On macOS the output is `Builds/Regatta.app`. Start the simulation stack first,
then open the player instead of entering Play mode.

## Troubleshooting

- A QoS durability mismatch can reject traffic without a visible Unity error;
  inspect `/tmp/endpoint.log` in the `regatta` container.
- Serialized Inspector values override script defaults after a field has been
  touched; inspect the prefab when a source default appears ineffective.
- If the Game view looks frozen or black, check the selected Display tab before
  debugging the renderer.
- Disable Gizmos when judging the production image; debug markers are not part
  of the rendered scenario.
