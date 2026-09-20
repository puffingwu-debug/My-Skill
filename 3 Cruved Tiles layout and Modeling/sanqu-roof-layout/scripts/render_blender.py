#!/usr/bin/env python3
"""Build an editable multi-plane PV-tile roof from the skill's layout.json.

Blender -b --factory-startup --python render_blender.py -- \
  --layout layout.json --output result-directory --assets assets-directory
"""

import argparse
import bisect
from collections import Counter
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon


BASE_Z = .12
ROW_RISE = .007
WIDTH, LENGTH, COMPANION_WIDTH = .723, .5, .724
EPS = 1e-9


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def area(poly):
    return sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(poly, poly[1:]+poly[:1])) / 2


def loop(poly, ccw=True):
    result = [tuple(p[:2]) for p in poly]
    if result and result[0] == result[-1]:
        result.pop()
    assert len(result) >= 3 and abs(area(result)) > EPS, "Degenerate footprint polygon."
    return result if (area(result) > 0) == ccw else result[::-1]


def triangulate(part):
    loops = [loop(part["outer"])] + [loop(p, False) for p in part.get("holes", [])]
    vectors = [[Vector((x, y, 0)) for x, y in p] for p in loops]
    flat = [v for p in loops for v in p]
    result = []
    for tri in tessellate_polygon(vectors):
        # Blender 5.2 returns indices; older supported builds return vectors.
        poly = [flat[v] if isinstance(v, int) else (v.x, v.y) for v in tri]
        result.append(poly if area(poly) > 0 else poly[::-1])
    expected = abs(area(loops[0])) - sum(abs(area(p)) for p in loops[1:])
    actual = sum(abs(area(p)) for p in result)
    assert abs(actual-expected) < max(1e-7, expected*1e-6), "Polygon/hole triangulation area mismatch."
    return loops, result


def clip_x(poly, bound, keep_greater):
    out = []
    for a, b in zip(poly, poly[1:]+poly[:1]):
        da, db = a[0]-bound, b[0]-bound
        inside = da >= -EPS if keep_greater else da <= EPS
        if inside:
            out.append(a)
        if da*db < 0:
            t = da/(da-db)
            out.append((bound, a[1]+t*(b[1]-a[1])))
    clean = []
    for p in out:
        if not clean or math.dist(p, clean[-1]) > EPS:
            clean.append(p)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) < EPS:
        clean.pop()
    return clean


def make_mesh(name, vertices, faces, material, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    return mesh


def material(name, values):
    result = bpy.data.materials.new(name)
    value = values["color"]
    rgb = [int(value[i:i+2], 16)/255 for i in (1, 3, 5)]
    rgb = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in rgb]
    result.diffuse_color = (*rgb, 1)
    result.use_nodes = True
    result.node_tree.nodes.clear()
    shader = result.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    output = result.node_tree.nodes.new("ShaderNodeOutputMaterial")
    result.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    shader.inputs["Base Color"].default_value = (*rgb, 1)
    shader.inputs["Roughness"].default_value = values.get("roughness", .88)
    shader.inputs["Metallic"].default_value = values.get("metalness", .02)
    result["sRGB"] = value
    return result


def object_mesh(name, mesh, collection, parent=None, matrix=None):
    result = bpy.data.objects.new(name, mesh)
    collection.objects.link(result)
    if parent:
        result.parent = parent
    if matrix is not None:
        result.matrix_world = matrix
    return result


def collection(name, parent=None):
    result = bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(result)
    return result


def companion_profile(source):
    transform = source["suggested_transform"]
    glass = next(m for m in source["meshes"] if m["material"]["name"] == "Matte curved front glass")
    heights = {}
    for i in range(0, len(glass["positions"]), 3):
        x = (glass["positions"][i]-transform["origin_m"][0])*transform["scale"][0]*COMPANION_WIDTH/WIDTH
        z = (glass["positions"][i+2]-transform["origin_m"][2])*transform["scale"][2]
        heights[x] = max(heights.get(x, -math.inf), z)
    points = sorted(heights.items())
    return [(-COMPANION_WIDTH/2, points[0][1])] + points + [(COMPANION_WIDTH/2, points[-1][1])]


def profiled_solid(name, parts, profile, center, base_z, tilt, material):
    """Intersect footprint triangles with each linear segment of the real wave.

    Top/bottom faces share vertices. Only the actual polygon and hole outlines
    receive side walls, so internal wave-band boundaries do not add walls.
    """
    vertices, faces, lookup = [], [], {}
    cx, cy = center
    knots = [cx+x for x, _ in profile]
    cosine, slope = math.cos(tilt), math.tan(tilt)

    def height(x, y, bottom=False):
        i = max(0, min(len(profile)-2, bisect.bisect_right(knots, x)-1))
        x0, z0 = profile[i]
        x1, z1 = profile[i+1]
        t = max(0, min(1, (x-cx-x0)/(x1-x0)))
        return base_z + (y-cy)*slope + (z0+t*(z1-z0)-(.004 if bottom else 0))/cosine

    def vertex(x, y, bottom=False):
        p = (x, y, height(x, y, bottom))
        key = tuple(round(v, 9) for v in p)
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(p)
        return lookup[key]

    for part in parts:
        loops, triangles = triangulate(part)
        for triangle in triangles:
            minimum, maximum = min(p[0] for p in triangle), max(p[0] for p in triangle)
            breaks = [minimum] + [x for x in knots if minimum+EPS < x < maximum-EPS] + [maximum]
            for left, right in zip(breaks, breaks[1:]):
                poly = clip_x(clip_x(triangle, left, True), right, False)
                if len(poly) < 3 or abs(area(poly)) < 1e-14:
                    continue
                top = [vertex(x, y) for x, y in poly]
                bottom = [vertex(x, y, True) for x, y in poly]
                for j in range(1, len(poly)-1):
                    faces.extend(((top[0], top[j], top[j+1]), (bottom[0], bottom[j+1], bottom[j])))
        for outline in loops:
            for a, b in zip(outline, outline[1:]+outline[:1]):
                values = [0., 1.]
                if abs(b[0]-a[0]) > EPS:
                    values += [(x-a[0])/(b[0]-a[0]) for x in knots if EPS < (x-a[0])/(b[0]-a[0]) < 1-EPS]
                points = [(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])) for t in sorted(values)]
                for p, q in zip(points, points[1:]):
                    faces.append((vertex(*p, True), vertex(*q, True), vertex(*q), vertex(*p)))
    assert vertices, "Companion footprint has no area."
    return make_mesh(name, vertices, faces, material, True)


def plane_solid(name, outer, holes, z0, z1, material):
    loops, triangles = triangulate({"outer": outer, "holes": holes})
    vertices, faces, lookup = [], [], {}
    def index(p, z):
        key = (p[0], p[1], z)
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(key)
        return lookup[key]
    for triangle in triangles:
        faces.append(tuple(index(p, z1) for p in triangle))
        faces.append(tuple(index(p, z0) for p in reversed(triangle)))
    for outline in loops:
        for a, b in zip(outline, outline[1:]+outline[:1]):
            faces.append((index(a, z0), index(b, z0), index(b, z1), index(a, z1)))
    return make_mesh(name, vertices, faces, material)


def beam_mesh(name, length, cross, material):
    cross = loop(cross)
    vertices = [(x, y, z) for x in (0, length) for y, z in cross]
    n = len(cross)
    faces = [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    faces.extend((tuple(reversed(range(n))), tuple(range(n, 2*n))))
    return make_mesh(name, vertices, faces, material)


def basis_matrix(u, v, normal, origin):
    basis = Matrix((u, v, normal)).transposed()
    assert all(abs(Vector(a).length-1) < 1e-5 for a in (u, v, normal)), "Roof basis vectors must have unit length."
    assert abs(abs(basis.determinant())-1) < 1e-5, "Roof basis vectors must be orthogonal."
    result = basis.to_4x4()
    result.translation = Vector(origin)
    return result


def inside(point, poly):
    x, y = point
    hit = False
    for a, b in zip(poly, poly[1:]+poly[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
    return hit


def edge_frame(start, end, preferred_up=Vector((0, 0, 1))):
    x = (end-start).normalized()
    z = preferred_up - x*preferred_up.dot(x)
    if z.length < 1e-7:
        z = Vector((0, 1, 0))-x*x.y
    z.normalize()
    y = z.cross(x).normalized()
    return x, y, z


def cut_ridge(source, length, material, nominal=.75):
    mesh = make_mesh("脊瓦段", [((source["positions"][i]+.375)*nominal/.75, source["positions"][i+1], source["positions"][i+2])
                                   for i in range(0, len(source["positions"]), 3)],
                     [source["indices"][i:i+3] for i in range(0, len(source["indices"]), 3)], material, True)
    if length < nominal-1e-7:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        result = bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces), dist=1e-8,
                                       plane_co=(length, 0, 0), plane_no=(1, 0, 0), clear_outer=True)
        edges = [e for e in result["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_boundary]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges)
        bm.normal_update()
        bm.to_mesh(mesh)
        bm.free()
    return mesh


def render(args, data):
    assert abs(data.get("course_pitch_m", .405)-.405) < 1e-7, "This confirmed J-clip assembly requires the 405 mm course pitch."
    args.output.mkdir(parents=True, exist_ok=True)
    tile_source = json.loads((args.assets/"tile-geometry.json").read_text())
    ridge_source = json.loads((args.assets/"ridge-geometry.json").read_text())
    clip_source = json.loads((args.assets/"windclip.json").read_text())
    surfaces = json.loads((args.assets/"surface-materials.json").read_text())
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    materials = {key: material(key, value) for key, value in surfaces.items()}
    deck_material = material("基层展示灰", {"color": "#474e52"})
    flashing_material = material("功能附件黑灰_示意", {"color": "#34383a"})
    glass_material = material("天窗蓝灰玻璃_示意", {"color": "#537b8d", "roughness": .18, "metalness": .18})
    ground_material = material("展示背景", {"color": "#e5e8ea"})
    root = collection(data.get("project_name", "三曲瓦屋面"))
    face_collections = {}
    transform = tile_source["suggested_transform"]
    pv_meshes = []
    for source in tile_source["meshes"]:
        name = source["material"]["name"]
        vertices = [tuple((source["positions"][i+k]-transform["origin_m"][k])*transform["scale"][k] for k in range(3))
                    for i in range(0, len(source["positions"]), 3)]
        mesh = make_mesh("原瓦_"+name, vertices, [source["indices"][i:i+3] for i in range(0, len(source["indices"]), 3)], materials[name], True)
        pv_meshes.append(mesh)
    clip_meshes = []
    for source in clip_source["meshes"]:
        ma = material(source["name"], {"color": source["color"], "roughness": .45, "metalness": .60})
        clip_meshes.append(make_mesh(source["name"], [source["positions"][i:i+3] for i in range(0, len(source["positions"]), 3)],
                                    [source["indices"][i:i+3] for i in range(0, len(source["indices"]), 3)], ma))
    profile = companion_profile(tile_source)
    tile_tilt = clip_source["jProfile"]["tile_tilt_rad"]
    counts = Counter()
    frames = []
    render_objects = []
    for face in data["faces"]:
        co = collection(face.get("name", face["id"]), root)
        face_collections[face["id"]] = co
        matrix = basis_matrix(face["u"], face["v"], face["normal"], face["origin"])
        frames.append((face, matrix))
        deck_mesh = plane_solid("屋面基层", face["boundary"], face.get("holes", []), .075, .095, deck_material)
        y0 = min(p[1] for p in face["boundary"])
        for vertex in deck_mesh.vertices:
            vertex.co.z += (vertex.co.y-y0)*ROW_RISE/.405
        deck = object_mesh(face["id"]+"_基层_展示", deck_mesh, co, matrix=matrix)
        render_objects.append(deck)
        for tile in face["tiles"]:
            identifier = face["id"]+"_"+tile["id"]
            z = BASE_Z + tile["row"]*ROW_RISE
            if tile["kind"] == "pv":
                parent = bpy.data.objects.new(identifier, None)
                co.objects.link(parent)
                parent.matrix_world = matrix @ Matrix.Translation((*tile["center"], z)) @ Matrix.Rotation(tile_tilt, 4, "X")
                parent.empty_display_size = .025
                parent["kind"] = "pv"
                parent["tile_id"] = tile["id"]
                for mesh in pv_meshes:
                    render_objects.append(object_mesh(identifier+"_"+mesh.name, mesh, co, parent))
                for j, anchor in enumerate(clip_source["anchors"]):
                    clip = bpy.data.objects.new(identifier+f"_J扣{j+1}", None)
                    co.objects.link(clip)
                    clip.parent = parent
                    clip.location = anchor
                    clip.empty_display_size = .012
                    clip["kind"] = "j_clip"
                    clip["说明"] = "J钩朝坡下，扣住上瓦下边缘；尺寸为教学节点"
                    for mesh in clip_meshes:
                        render_objects.append(object_mesh(clip.name+"_"+mesh.name, mesh, co, clip))
                    counts["j_clip_count"] += 1
                counts["pv_count"] += 1
            else:
                assert tile["kind"] == "companion"
                parts = tile.get("parts") or [{"outer": tile["footprint"], "holes": []}]
                mesh = profiled_solid(identifier, parts, profile, tile["center"], z, tile_tilt, materials["accessory"])
                obj = object_mesh(identifier, mesh, co, matrix=matrix)
                obj["kind"] = "companion"
                obj["裁切边界"] = json.dumps(parts, ensure_ascii=False)
                render_objects.append(obj)
                counts["companion_count"] += 1
        for obstacle in face.get("obstacles", []):
            if obstacle.get("type") != "skylight":
                continue
            polygon = loop(obstacle["polygon"])
            center = Vector((sum(p[0] for p in polygon)/len(polygon), sum(p[1] for p in polygon)/len(polygon)))
            nearest = min(face["tiles"], key=lambda t: math.dist(t["center"], center)) if face["tiles"] else {"row": 0}
            z = BASE_Z+nearest["row"]*ROW_RISE+.041
            glass = object_mesh(obstacle["id"]+"_玻璃_示意", plane_solid("天窗玻璃", polygon, [], z+.045, z+.057, glass_material), co, matrix=matrix)
            render_objects.append(glass)
            for j, (a, b) in enumerate(zip(polygon, polygon[1:]+polygon[:1])):
                d = Vector((b[0]-a[0], b[1]-a[1], 0))
                x, y, normal = edge_frame(Vector((0, 0, 0)), d)
                for label, width, bottom, top in (("黑灰窗框", .065, .026, .076), ("黑灰泛水", .16, .0, .006)):
                    mesh = beam_mesh(label, d.length, [(-width/2, bottom), (width/2, bottom), (width/2, top), (-width/2, top)], flashing_material)
                    pose = matrix @ basis_matrix(x, y, normal, (a[0], a[1], z))
                    obj = object_mesh(obstacle["id"]+f"_{label}{j+1}_示意", mesh, co, matrix=pose)
                    obj["说明"] = "天窗边框与泛水为展示构造，不是产品加工图"
                    render_objects.append(obj)
            counts["skylight_count"] += 1
    edges_co = collection("屋脊与功能边缘附件", root)
    ridge_meshes = {.75: cut_ridge(ridge_source, .75, materials["accessory"])}
    for edge in data.get("edges", []):
        start, end = Vector(edge["start"]), Vector(edge["end"])
        length = (end-start).length
        if length < EPS:
            continue
        mid = (start+end)/2
        adjacent = [(f, m) for f, m in frames if abs(Vector(f["normal"]).dot(mid-Vector(f["origin"]))) < .03]
        preferred_up = Vector((0, 0, 1)) if edge["type"] in ("ridge", "hip") or not adjacent else Vector(adjacent[0][0]["normal"])
        x, y, z = edge_frame(start, end, preferred_up)
        length_only = edge["type"] == "eave" and not all(edge.get(k) for k in ("count", "effective_length_m", "actual_length_m"))
        effective = length if length_only else edge.get("effective_length_m") or (.7 if edge["type"] in ("ridge", "hip") else .6)
        nominal = length if length_only else edge.get("actual_length_m") or (.75 if edge["type"] in ("ridge", "hip") else .62)
        assert nominal >= effective > 0, "Accessory actual length must cover its effective pitch."
        count = 1 if length_only else edge.get("count") or math.ceil(length/effective)
        for i in range(count):
            offset = i*effective
            if offset >= length-EPS:
                break
            point = start+x*offset
            sample = point+x*min(effective/2, (length-offset)/2)
            levels = []
            for face, matrix in adjacent:
                local = matrix.inverted() @ sample
                nearest = min(face["tiles"], key=lambda t: math.dist(t["center"], local.xy)) if face["tiles"] else {"row": 0}
                target = BASE_Z+nearest["row"]*ROW_RISE+.041+.004
                normal = Vector(face["normal"])
                if edge["type"] in ("ridge", "hip"):
                    # Place the skirt above the complete wave peak envelope.
                    side = next((sign for sign in (-1, 1) if inside((matrix.inverted() @ (sample+y*sign*.15)).xy, face["boundary"])), None)
                    across = normal.dot(y)*side*.19 if side else abs(normal.dot(y))*.19
                    if normal.dot(z) > .1:
                        levels.append((target-across)/normal.dot(z))
                else:
                    levels.append(target)
            lift = max(levels, default=BASE_Z+.041)
            if edge["type"] in ("ridge", "hip"):
                piece_length = min(nominal, length-offset)
                if nominal not in ridge_meshes:
                    ridge_meshes[nominal] = cut_ridge(ridge_source, nominal, materials["accessory"], nominal)
                mesh = ridge_meshes[nominal] if piece_length >= nominal-EPS else cut_ridge(ridge_source, piece_length, materials["accessory"], nominal)
            else:
                piece_length = min(nominal, length-offset)
                if edge["type"] == "verge":
                    cross = [(0, 0), (.17, 0), (.17, -.004), (.004, -.004), (.004, -.10), (0, -.10)]
                    if adjacent:
                        face, matrix = adjacent[0]
                        inward = 1 if inside((matrix.inverted() @ (sample+y*.06)).xy, face["boundary"]) else -1
                        cross = [(width*inward, height) for width, height in cross]
                elif edge["type"] == "valley":
                    cross = [(-.135, .012), (0, 0), (.135, .012), (.135, .008), (0, -.004), (-.135, .008)]
                else:
                    cross = [(-.045, 0), (.045, 0), (.045, -.025), (-.045, -.025)]
                mesh = beam_mesh(edge["type"], piece_length, cross, flashing_material)
            obj = object_mesh(edge["id"]+f"_{i+1:03d}", mesh, edges_co, matrix=basis_matrix(x, y, z, point+z*lift))
            obj["kind"] = edge["type"]
            obj["边缘编号"] = edge["id"]
            obj["说明"] = ("未知产品模数的整段檐口示意条，仅表示延米，不计配件片数" if length_only else
                         "真实正脊瓦外形，局部搭接及承托高度为教学示意" if edge["type"] == "ridge" else
                         "斜脊以正脊外形作示意，段长采用输入配件尺寸，需产品节点复核" if edge["type"] == "hip" else
                         "功能附件示意，需项目节点详图确认")
            render_objects.append(obj)
            if not length_only:
                counts[edge["type"]+"_pieces"] += 1
    bpy.context.view_layer.update()
    for key in ("pv_count", "companion_count", "j_clip_count"):
        assert counts[key] == data["summary"][key], f"Count mismatch: {key}: {counts[key]} vs {data['summary'][key]}"
    assert counts["j_clip_count"] == 2*counts["pv_count"]
    assert abs(counts["pv_count"]*.04-data["summary"]["capacity_kwp"]) < 1e-7
    points = [obj.matrix_world @ Vector(v) for obj in render_objects for v in obj.bound_box]
    assert points and all(math.isfinite(v) for p in points for v in p)
    minimum = Vector(tuple(min(p[k] for p in points) for k in range(3)))
    maximum = Vector(tuple(max(p[k] for p in points) for k in range(3)))
    center = (minimum+maximum)/2
    extent = max((maximum-minimum).length, 1)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1100
    scene.render.resolution_percentage = 100
    scene.world.use_nodes = True
    background = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    background.inputs["Color"].default_value = (.8, .84, .9, 1)
    background.inputs["Strength"].default_value = .25
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    bpy.ops.mesh.primitive_plane_add(size=extent*20, location=(center.x, center.y, minimum.z-.07))
    bpy.context.object.name = "摄影背景_非建筑构件"
    bpy.context.object.data.materials.append(ground_material)
    for name, delta, power, size in (("柔光主灯", (-.3, -.5, 1), 8*extent*extent, extent*.8),
                                    ("柔光补灯", (.6, .2, .7), 5*extent*extent, extent*.7)):
        bpy.ops.object.light_add(type="AREA", location=center+Vector(delta)*extent)
        light = bpy.context.object
        light.name = name
        light.data.energy, light.data.shape, light.data.size = power, "DISK", size
        light.rotation_euler = (center-light.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "屋面摄影相机"
    camera.data.type = "ORTHO"
    camera.data.clip_end = extent*20
    scene.camera = camera
    def camera_view(direction):
        camera.location = center+direction.normalized()*extent*2
        camera.rotation_euler = (center-camera.location).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        inverse = camera.matrix_world.inverted()
        framed = [inverse @ p for p in points]
        width = max(p.x for p in framed)-min(p.x for p in framed)
        height = max(p.y for p in framed)-min(p.y for p in framed)
        offset = Vector(((max(p.x for p in framed)+min(p.x for p in framed))/2,
                         (max(p.y for p in framed)+min(p.y for p in framed))/2, 0))
        camera.location += camera.matrix_world.to_3x3() @ offset
        camera.data.ortho_scale = max(width, height*scene.render.resolution_x/scene.render.resolution_y)*1.14
    first = data["faces"][0]
    camera_view(Vector(first["u"])*.75-Vector(first["v"])*.8+Vector(first["normal"])*1.15)
    assumptions = list(data.get("assumptions", [])) + [
        "原始三曲瓦可见电池片与焊带网格均保留；按723×500×41mm进行统一包络变换。",
        "7mm逐排抬升、16.5mm搭接净高及单瓦微倾用于演示J扣扣接，不是厂家节点加工尺寸。",
        "配瓦取原瓦玻璃外曲线制作4mm教学壳，按多边形及孔洞裁切。",
        "脊瓦采用750×380×195mm双筋开口壳并沿实际边线分段；承托高度与泛水、封边、天窗均为教学示意。",
        "斜脊暂以正脊外形按输入段长示意；其他功能附件使用简化截面，各段实际长度与有效步距读取边缘数据。",
    ]
    report = {"project_name": data.get("project_name"), "counts": dict(counts), "world_bounds_m": [list(minimum), list(maximum)],
              "source_layout": str(args.layout), "source_assets": str(args.assets), "assumptions": assumptions,
              "pv_material_groups": len(pv_meshes), "cells_and_ribbons_preserved": True, "finite_transforms": True}
    text = bpy.data.texts.new("请先阅读_建模与限制")
    text.write(json.dumps(report, ensure_ascii=False, indent=2))
    logo = args.assets/"logo.png"
    if logo.exists():
        bpy.data.images.load(str(logo)).pack()
    scene["项目名称"] = data.get("project_name", "三曲瓦屋面")
    scene["排布核验"] = json.dumps(dict(counts), ensure_ascii=False)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.color_type = "MATERIAL"
                area.spaces.active.region_3d.view_distance = extent
                area.spaces.active.region_3d.view_location = center
    bpy.context.preferences.filepaths.save_version = 0
    blend = args.output/"屋面模型.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scene.render.filepath = str(args.output/"屋面效果图.png")
    bpy.ops.render.render(write_still=True)
    camera_view(Vector((0, 0, 1)))
    scene.render.filepath = str(args.output/"屋面俯视图.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    restored = json.loads(bpy.context.scene["排布核验"])
    assert restored == dict(counts)
    actual_pv = [o for o in bpy.data.objects if o.get("kind") == "pv"]
    actual_j = [o for o in bpy.data.objects if o.get("kind") == "j_clip"]
    assert len(actual_pv) == counts["pv_count"] and len(actual_j) == counts["j_clip_count"]
    assert all(sum(c.parent == p for c in actual_j) == 2 for p in actual_pv)
    assert all(math.isfinite(v) for o in bpy.data.objects for row in o.matrix_world for v in row)
    report["saved_file_reopen"] = "passed"
    (args.output/"Blender核验.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BLENDER_LAYOUT_VERIFIED:"+json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    options = arguments()
    render(options, json.loads(options.layout.read_text()))
