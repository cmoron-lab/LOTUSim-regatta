# Blender sources

`regatta_buoy.blend` and `focus_v2.blend` are the authored sources exported to
the FBX/OBJ meshes used by gz (`assets/models/regatta_buoy/`) and Unity
(`LOTUSim-Unity-modules`). Export recipe (headless, `blender --background
--python`): `axis_forward='-Z'`, `axis_up='Y'`, `bake_space_transform=True`,
`path_mode='COPY'`.

`focus_v2.blend` is a working copy; the model may later migrate to the
LOTUSim upstream core alongside the `focus_v2` xdyn model.

`focus_v2_wood_mahogany.png` is a texture referenced by `focus_v2.blend`; open
focus_v2.blend then File > External Data > Make Paths Relative — the texture
path is currently absolute. `focus_v2.baseline.blend` is a historical reference
copy.
