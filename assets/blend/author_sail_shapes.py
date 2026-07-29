"""Author deterministic sail shape keys and export the Unity FBX."""

import argparse
import json
import math
import sys

import bpy


SAILS = {
    "Mainsail": {"ripple": 0.018},
    "Jib": {"ripple": 0.015},
}
SHAPES = ("FilledPort", "FilledStarboard", "RipplePort", "RippleStarboard")
DETAIL_OFFSET = 0.0002
CHORD_ROWS = {}


def clamp(value, lower, upper):
    return max(lower, min(value, upper))


def chord_fraction(sail_name, y, height):
    rows = CHORD_ROWS[sail_name]
    _, leech, luff = min(rows, key=lambda row: abs(row[0] - height))
    return 0.0 if math.isclose(leech, luff) else clamp((luff - y) / (luff - leech), 0.0, 1.0)


def shape_key_names(sail):
    return set(sail.data.shape_keys.key_blocks.keys()) if sail.data.shape_keys else set()


def write_inventory(path):
    objects = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        item = {
            "location": [round(value, 9) for value in obj.location],
            "name": obj.name,
            "rotation": [round(value, 9) for value in obj.rotation_euler],
            "scale": [round(value, 9) for value in obj.scale],
            "type": obj.type,
        }
        if obj.type == "MESH":
            item.update(
                faces=len(obj.data.polygons),
                materials=[material.name if material else None for material in obj.data.materials],
                uv_layers=[layer.name for layer in obj.data.uv_layers],
                vertices=len(obj.data.vertices),
            )
        objects.append(item)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(objects, file, indent=2, sort_keys=True)


def author_sail(sail_name, amplitude):
    sail = bpy.data.objects[sail_name]
    original_origin = tuple(sail.location)
    original_materials = tuple(sail.data.materials)
    camber = (
        sail.data.shape_keys.key_blocks.get("FilledStarboard") if sail.data.shape_keys else None
    )
    original_x = (
        tuple(vertex.co.x for vertex in camber.data)
        if camber
        else tuple(vertex.co.x for vertex in sail.data.vertices)
    )
    base_materials = {
        index
        for index, material in enumerate(sail.data.materials)
        if material and material.name == "focus_sail"
    }
    if not base_materials:
        raise AssertionError(f"{sail_name}: focus_sail material missing")
    base_vertices = {
        index
        for polygon in sail.data.polygons
        if polygon.material_index in base_materials
        for index in polygon.vertices
    }
    detail_vertices = {
        index
        for polygon in sail.data.polygons
        if polygon.material_index not in base_materials
        for index in polygon.vertices
    } - base_vertices
    if not detail_vertices:
        raise AssertionError(f"{sail_name}: exclusive detail vertices missing")
    basis_offsets = tuple(
        clamp(value, -DETAIL_OFFSET, DETAIL_OFFSET) if index in detail_vertices else 0.0
        for index, value in enumerate(original_x)
    )
    z_min = min(vertex.co.z for vertex in sail.data.vertices)
    z_max = max(vertex.co.z for vertex in sail.data.vertices)
    if math.isclose(z_min, z_max):
        raise ValueError(f"{sail_name}: sail has no height")

    samples = []
    for vertex in sail.data.vertices:
        height = clamp((vertex.co.z - z_min) / (z_max - z_min), 0.0, 1.0)
        samples.append((height, vertex.co.y))
    CHORD_ROWS[sail_name] = []
    for step in range(101):
        height = step / 100.0
        ys = [y for sample_height, y in samples if abs(sample_height - height) <= 0.03]
        CHORD_ROWS[sail_name].append((height, min(ys), max(ys)))

    while sail.data.shape_keys:
        sail.shape_key_remove(sail.data.shape_keys.key_blocks[-1])
    for vertex, offset in zip(sail.data.vertices, basis_offsets, strict=True):
        vertex.co.x = offset

    basis = sail.shape_key_add(name="Basis", from_mix=False)
    filled_port = sail.shape_key_add(name="FilledPort", from_mix=False)
    filled_starboard = sail.shape_key_add(name="FilledStarboard", from_mix=False)
    ripple_port = sail.shape_key_add(name="RipplePort", from_mix=False)
    ripple_starboard = sail.shape_key_add(name="RippleStarboard", from_mix=False)
    anchors = []

    for index, (co, original) in enumerate(zip(basis.data, original_x, strict=True)):
        height = clamp((co.co.z - z_min) / (z_max - z_min), 0.0, 1.0)
        chord = chord_fraction(sail_name, co.co.y, height)
        envelope = math.sin(math.pi * height) * chord * chord
        ripple = amplitude * envelope * math.sin(3.0 * math.pi * height)
        basis_offset = basis_offsets[index]
        anchored = math.isclose(envelope, 0.0, abs_tol=1e-9)
        if anchored:
            anchors.append(index)
            filled_port.data[index].co.x = basis_offset
            filled_starboard.data[index].co.x = basis_offset
            ripple_port.data[index].co.x = basis_offset
            ripple_starboard.data[index].co.x = basis_offset
        else:
            filled_port.data[index].co.x = -original
            filled_starboard.data[index].co.x = original
            ripple_port.data[index].co.x = basis_offset - ripple
            ripple_starboard.data[index].co.x = basis_offset + ripple

    expected = {"Basis", *SHAPES}
    if shape_key_names(sail) != expected:
        raise AssertionError(f"{sail_name}: unexpected shape keys {shape_key_names(sail)}")
    if tuple(sail.location) != original_origin or tuple(sail.data.materials) != original_materials:
        raise AssertionError(f"{sail_name}: origin or material slots changed")
    if any(
        not math.isclose(key.co.x, basis_offsets[index], abs_tol=1e-9)
        for index, key in enumerate(basis.data)
    ):
        raise AssertionError(f"{sail_name}: Basis offsets changed")
    if not any(
        not math.isclose(basis.data[index].co.x, 0.0, abs_tol=1e-9) for index in detail_vertices
    ):
        raise AssertionError(f"{sail_name}: detail Basis separation is zero")
    if not anchors:
        raise AssertionError(f"{sail_name}: no fixed anchors")
    anchor_set = set(anchors)
    for key in (filled_port, filled_starboard, ripple_port, ripple_starboard):
        if any(
            not math.isclose(key.data[index].co.x, basis.data[index].co.x, abs_tol=1e-9)
            for index in anchors
        ):
            raise AssertionError(f"{sail_name}: shape key moved an anchor")
    if any(
        not math.isclose(port.co.x, -starboard.co.x, abs_tol=1e-9)
        for index, (port, starboard) in enumerate(
            zip(filled_port.data, filled_starboard.data, strict=True)
        )
        if index not in anchor_set
    ):
        raise AssertionError(f"{sail_name}: filled keys are not opposed")
    if not any(abs(key.co.x) > 1e-6 for key in filled_starboard.data):
        raise AssertionError(f"{sail_name}: filled camber is not visible")
    if not any(
        abs(key.co.x - basis.data[index].co.x) > 1e-6
        for index, key in enumerate(ripple_starboard.data)
    ):
        raise AssertionError(f"{sail_name}: ripple is not visible")
    print(sail_name, sorted(shape_key_names(sail)), "detail vertices", len(detail_vertices))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory")
    parser.add_argument("--output-fbx")
    arguments = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])

    if arguments.inventory:
        write_inventory(arguments.inventory)
        if not arguments.output_fbx:
            return
    if not arguments.output_fbx:
        parser.error("--output-fbx is required unless --inventory is used")

    for sail_name, settings in SAILS.items():
        author_sail(sail_name, settings["ripple"])

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    bpy.ops.export_scene.fbx(
        filepath=arguments.output_fbx,
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,
        path_mode="COPY",
        add_leaf_bones=False,
    )


if __name__ == "__main__":
    main()
