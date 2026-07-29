"""Author deterministic sail shape keys and export the Unity FBX."""

import argparse
import json
import math
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


SAILS = {
    "Mainsail": {"ripple": 0.018},
    "Jib": {"ripple": 0.015},
}
SHAPES = ("FilledPort", "FilledStarboard", "RipplePort", "RippleStarboard")
RUDDER_PIVOT = Vector((0.0, -0.425, 0.0))
CHORD_ROWS = {}


def clamp(value, lower, upper):
    return max(lower, min(value, upper))


def chord_fraction(sail_name, y, height):
    rows = CHORD_ROWS[sail_name]
    _, leech, luff = min(rows, key=lambda row: abs(row[0] - height))
    return 0.0 if math.isclose(leech, luff) else clamp((luff - y) / (luff - leech), 0.0, 1.0)


def shape_key_names(sail):
    return set(sail.data.shape_keys.key_blocks.keys()) if sail.data.shape_keys else set()


def sail_vertex_groups(sail):
    base_materials = {
        index
        for index, material in enumerate(sail.data.materials)
        if material and material.name == "focus_sail"
    }
    if not base_materials:
        raise AssertionError(f"{sail.name}: focus_sail material missing")
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
        raise AssertionError(f"{sail.name}: exclusive detail vertices missing")
    return base_materials, base_vertices, detail_vertices


def marking_surface(sail, source_x, base_materials, detail_vertices):
    sail.data.calc_loop_triangles()
    triangles = [
        tuple(triangle.vertices)
        for triangle in sail.data.loop_triangles
        if sail.data.polygons[triangle.polygon_index].material_index in base_materials
    ]
    tree = BVHTree.FromPolygons(
        [
            Vector((source_x[index], vertex.co.y, vertex.co.z))
            for index, vertex in enumerate(sail.data.vertices)
        ],
        triangles,
        all_triangles=True,
    )
    if tree is None:
        raise AssertionError(f"{sail.name}: cannot build sail surface")

    surface_x = list(source_x)
    directions = (Vector((1.0, 0.0, 0.0)), Vector((-1.0, 0.0, 0.0)))
    for index in detail_vertices:
        vertex = sail.data.vertices[index]
        point = Vector((source_x[index], vertex.co.y, vertex.co.z))
        hits = []
        for direction in directions:
            location, _, triangle, distance = tree.ray_cast(point, direction)
            if location is not None:
                hits.append((distance, triangle, location.x))
        if hits:
            surface_x[index] = min(hits)[2]
            continue
        location, _, _, _ = tree.find_nearest(point)
        if location is None:
            raise AssertionError(f"{sail.name}: cannot project detail vertex {index}")
        surface_x[index] = location.x
    return tuple(surface_x)


def verify_authored_sail(sail):
    expected = {"Basis", *SHAPES}
    if shape_key_names(sail) != expected:
        raise AssertionError(f"{sail.name}: unexpected shape keys {shape_key_names(sail)}")
    base_materials, base_vertices, detail_vertices = sail_vertex_groups(sail)
    keys = sail.data.shape_keys.key_blocks
    basis = keys["Basis"]
    filled_port = keys["FilledPort"]
    filled_starboard = keys["FilledStarboard"]
    starboard_x = tuple(vertex.co.x for vertex in filled_starboard.data)
    starboard_surface = marking_surface(sail, starboard_x, base_materials, detail_vertices)
    reconstructed_relief = tuple(
        starboard_x[index] - starboard_surface[index] if index in detail_vertices else 0.0
        for index in range(len(sail.data.vertices))
    )
    relief_values = [basis.data[index].co.x for index in detail_vertices]
    relief_span = max(relief_values) - min(relief_values)
    tolerance = max(1e-7, relief_span * 5e-5)
    relief_errors = [
        (abs(basis.data[index].co.x - relief), index)
        for index, relief in enumerate(reconstructed_relief)
    ]
    maximum_error, maximum_index = max(relief_errors)
    if maximum_error > tolerance:
        raise AssertionError(
            f"{sail.name}: marking relief was not preserved "
            f"(vertex {maximum_index}, error {maximum_error:.9f})"
        )
    if relief_span <= 1e-5:
        raise AssertionError(f"{sail.name}: marking relief distribution was flattened")
    if any(not math.isclose(basis.data[index].co.x, 0.0, abs_tol=1e-9) for index in base_vertices):
        raise AssertionError(f"{sail.name}: cloth Basis is not fixed")
    if any(
        not math.isclose(
            filled_port.data[index].co.x - basis.data[index].co.x,
            -(filled_starboard.data[index].co.x - basis.data[index].co.x),
            abs_tol=tolerance,
        )
        for index in range(len(sail.data.vertices))
    ):
        raise AssertionError(f"{sail.name}: camber is not opposed around marking relief")
    print(
        sail.name,
        sorted(shape_key_names(sail)),
        "detail vertices",
        len(detail_vertices),
        "relief span",
        round(relief_span, 9),
    )


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
    base_materials, _, detail_vertices = sail_vertex_groups(sail)
    surface_x = marking_surface(sail, original_x, base_materials, detail_vertices)
    basis_offsets = tuple(
        original_x[index] - surface_x[index] if index in detail_vertices else 0.0
        for index in range(len(sail.data.vertices))
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

    for index, co in enumerate(basis.data):
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
            filled_port.data[index].co.x = -surface_x[index] + basis_offset
            filled_starboard.data[index].co.x = surface_x[index] + basis_offset
            ripple_port.data[index].co.x = basis_offset - ripple
            ripple_starboard.data[index].co.x = basis_offset + ripple

    if tuple(sail.location) != original_origin or tuple(sail.data.materials) != original_materials:
        raise AssertionError(f"{sail_name}: origin or material slots changed")
    if any(
        not math.isclose(key.co.x, basis_offsets[index], abs_tol=1e-9)
        for index, key in enumerate(basis.data)
    ):
        raise AssertionError(f"{sail_name}: Basis offsets changed")
    if any(
        not math.isclose(surface_x[index] + basis_offsets[index], original_x[index], abs_tol=1e-9)
        for index in detail_vertices
    ):
        raise AssertionError(f"{sail_name}: marking relief reconstruction changed")
    if not anchors:
        raise AssertionError(f"{sail_name}: no fixed anchors")
    for key in (filled_port, filled_starboard, ripple_port, ripple_starboard):
        if any(
            not math.isclose(key.data[index].co.x, basis.data[index].co.x, abs_tol=1e-9)
            for index in anchors
        ):
            raise AssertionError(f"{sail_name}: shape key moved an anchor")
    if not any(abs(key.co.x) > 1e-6 for key in filled_starboard.data):
        raise AssertionError(f"{sail_name}: filled camber is not visible")
    if not any(
        abs(key.co.x - basis.data[index].co.x) > 1e-6
        for index, key in enumerate(ripple_starboard.data)
    ):
        raise AssertionError(f"{sail_name}: ripple is not visible")
    verify_authored_sail(sail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory")
    parser.add_argument("--output-fbx")
    parser.add_argument("--verify-fbx")
    arguments = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])

    if arguments.verify_fbx:
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.ops.import_scene.fbx(filepath=arguments.verify_fbx)
        runtime_objects = sorted(
            obj.name for obj in bpy.context.scene.objects if obj.type in {"CAMERA", "LIGHT"}
        )
        if runtime_objects:
            raise AssertionError(f"FBX contains runtime cameras/lights: {runtime_objects}")
        rudder = bpy.data.objects["Rudder"]
        if not all(
            math.isclose(value, expected, abs_tol=1e-6)
            for value, expected in zip(rudder.location, RUDDER_PIVOT)
        ):
            raise AssertionError(f"Rudder pivot moved: {tuple(rudder.location)}")
        for sail_name in SAILS:
            verify_authored_sail(bpy.data.objects[sail_name])
        return
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
        object_types={"ARMATURE", "EMPTY", "MESH"},
    )


if __name__ == "__main__":
    main()
