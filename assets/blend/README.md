# Blender sources

`regatta_buoy.blend` and `focus_v2.blend` are the authored sources for the
scenario models. `focus_v2.baseline.blend` is a historical reference, not an
export input.

## Focus V2 sail export

Use Blender 4.5.11 LTS. From the repository root, generate the Unity 6 FBX with
a configurable sibling-project path:

```bash
UNITY_PROJECT=${UNITY_PROJECT:-../LOTUSim-Unity6-modules}
blender --background assets/blend/focus_v2.blend --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- \
  --output-fbx "$UNITY_PROJECT/Assets/models/focus_v2/mesh/focus_v2.fbx"
```

Generation authors the sail shapes in memory and does **not** overwrite
`focus_v2.blend`. To persist the generated shape keys deliberately, add
`--save-source`; the save happens only after a successful FBX export and keeps
Blender's normal backup behaviour.

Verify the exported FBX from a fresh empty Blender scene:

```bash
blender --background --python-exit-code 1 \
  --python assets/blend/author_sail_shapes.py -- \
  --verify-fbx "$UNITY_PROJECT/Assets/models/focus_v2/mesh/focus_v2.fbx"
```

The verifier checks both sails' exact shape-key set, marking relief, runtime
camera/light exclusion, and rudder pivot.

## Deliberate visual limits

Sail deformation changes only the lateral coordinate. It is deterministic and
preserves the required pivots and markings, but it does not shorten the
projected chord as camber increases, so cloth area is not conserved.

The filled shapes retain the authored camber, whose maximum is near mid-chord.
The ripple shapes are a static spatial profile animated in amplitude by Unity;
a travelling luff wave belongs to the Unity 6 runtime work, not this exporter.
