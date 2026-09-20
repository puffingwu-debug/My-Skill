#!/usr/bin/env python3
"""Render an editable Almaden Pro roof from a measured, unfolded layout.

Blender -b --factory-startup --python render_blender.py -- \
  --layout layout.json --output result-directory --assets assets-directory

Coordinates in each face are metres along orthonormal u/v axes. v points
upslope. Geometry retains the input roof plane and uses only the confirmed
Pro installation specimen's small local lap inclination, never row-rise.
"""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

WIDTH, LENGTH, THICKNESS = 1.240, .390, .0062
X_PITCH, Y_PITCH = 1.220, .340
PAD, SEAL_HEIGHT, BASE_Z = .001, .0025, .058
SX = -(THICKNESS+PAD)/X_PITCH
SY = -(THICKNESS+SEAL_HEIGHT+(THICKNESS+PAD)/2+.00015)/Y_PITCH
EPS = 1e-8


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--layout', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True)
    return p.parse_args(sys.argv[sys.argv.index('--')+1:])


def area(poly):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2


def loop(poly, ccw=True):
    points = []
    for point in poly:
        point = tuple(point[:2])
        if not points or math.dist(point,points[-1])>EPS:
            points.append(point)
    if math.dist(points[0],points[-1])<=EPS:
        points.pop()
    assert len(points) >= 3 and abs(area(points)) > EPS, 'Degenerate polygon'
    return points if (area(points)>0)==ccw else points[::-1]


def triangulate(part):
    loops = [loop(part['outer'])] + [loop(p,False) for p in part.get('holes',[])]
    # Recenter before Blender float32 triangulation: a millimetre-wide seal
    # can otherwise lose useful precision on a roof tens of metres wide.
    ox,oy = loops[0][0]
    vectors = [[Vector((x-ox,y-oy,0)) for x,y in outline] for outline in loops]
    flat = [v for outline in vectors for v in outline]
    original = [p for outline in loops for p in outline]
    lookup = {tuple(v):p for v,p in zip(flat,original)}
    triangles = []
    for tri in tessellate_polygon(vectors):
        poly = [original[p] if isinstance(p,int) else lookup[tuple(p)] for p in tri]
        triangles.append(poly if area(poly)>0 else poly[::-1])
    expected = abs(area(loops[0]))-sum(abs(area(p)) for p in loops[1:])
    actual = sum(abs(area(p)) for p in triangles)
    assert abs(actual-expected) < max(1e-7,expected*1e-6), 'Polygon triangulation area mismatch'
    return loops,triangles


def inside(point, poly):
    x,y = point
    hit = False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
    return hit


def within(point, parts):
    return any(inside(point,p['outer']) and not any(inside(point,h) for h in p.get('holes',[])) for p in parts)


def material(name,color,roughness=.75,metallic=.02):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color,1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metallic
    m.diffuse_color = (*color,1)
    return m


def mesh(name,vertices,faces,ma):
    m = bpy.data.meshes.new(name)
    m.from_pydata(vertices,[],faces)
    m.materials.append(ma)
    m.update()
    return m


def collection(name,parent=None):
    co = bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(co)
    return co


def obj(name,data,co,parent=None,matrix=None):
    o = bpy.data.objects.new(name,data)
    co.objects.link(o)
    if parent:
        o.parent = parent
    if matrix is not None:
        o.matrix_world = matrix
    return o


def basis(u,v,n,origin):
    m = Matrix((u,v,n)).transposed()
    assert all(abs(Vector(a).length-1)<1e-5 for a in (u,v,n)), 'Non-unit roof basis'
    assert abs(m.determinant()-1)<1e-5, 'Roof basis must be orthogonal and right-handed'
    result = m.to_4x4()
    result.translation = Vector(origin)
    return result


def solid(name,parts,low,high,ma):
    vertices,faces,lookup,boundary_edges = [],[],{},{}
    def ix(p,top):
        z = high(*p) if top else low(*p)
        key = (round(p[0],10),round(p[1],10),round(z,10))
        if key not in lookup:
            lookup[key] = len(vertices)
            vertices.append(key)
        return lookup[key]
    for part in parts:
        outlines,triangles = triangulate(part)
        for tri in triangles:
            faces.extend((tuple(ix(p,True) for p in tri),tuple(ix(p,False) for p in tri[::-1])))
        for outline in outlines:
            for a,b in zip(outline,outline[1:]+outline[:1]):
                key = tuple(sorted((tuple(round(v,9) for v in a),tuple(round(v,9) for v in b))))
                if key in boundary_edges:
                    del boundary_edges[key]
                else:
                    boundary_edges[key] = (a,b)
    for a,b in boundary_edges.values():
        faces.append((ix(a,False),ix(b,False),ix(b,True),ix(a,True)))
    return mesh(name,vertices,faces,ma)


def rect(x0,y0,x1,y1):
    return [{'outer':[(x0,y0),(x1,y0),(x1,y1),(x0,y1)],'holes':[]}]


def cut_holes(m,positions,radius,co):
    o = obj('temporary_panel',m.copy() if m.users else m,co)
    for x,y,z in positions:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=radius,depth=.050,location=(x,y,z))
        cutter = bpy.context.object
        bpy.context.view_layer.objects.active = o
        mod = o.modifiers.new('Factory mounting bore','BOOLEAN')
        mod.operation,mod.solver,mod.object = 'DIFFERENCE','EXACT',cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    result = o.data
    bpy.data.objects.remove(o,do_unlink=True)
    return result


def section_mesh(name,cross,length,ma):
    cross = loop(cross)
    n = len(cross)
    vertices = [(x,y,z) for x in (0,length) for y,z in cross]
    faces = [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    faces += [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    return mesh(name,vertices,faces,ma)


def cylinder(name,radius,length,ma,n=16):
    vertices = [(radius*math.cos(i*math.tau/n),radius*math.sin(i*math.tau/n),z) for z in (0,length) for i in range(n)]
    faces = [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,vertices,faces,ma)


def clipped_x(poly,bound,greater):
    result = []
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da,db = a[0]-bound,b[0]-bound
        if da>=-EPS if greater else da<=EPS:
            result.append(a)
        if da*db<0:
            t = da/(da-db)
            result.append((bound,a[1]+t*(b[1]-a[1])))
    return result


def pad_parts(parts,x0,x1):
    result = []
    for part in parts:
        _,triangles = triangulate(part)
        for tri in triangles:
            poly = clipped_x(clipped_x(tri,x0,True),x1,False)
            if len(poly)>=3 and abs(area(poly))>EPS:
                result.append({'outer':poly})
    return result


def horizontal_intervals(parts,y):
    xs = []
    for part in parts:
        for outline in [part['outer']]+part.get('holes',[]):
            for a,b in zip(outline,outline[1:]+outline[:1]):
                if (a[1]<=y<b[1]) or (b[1]<=y<a[1]):
                    xs.append(a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]))
    xs = sorted(set(xs))
    return [(a,b) for a,b in zip(xs,xs[1:]) if b-a>.001 and within(((a+b)/2,y),parts)]


def seal_mesh(name,a,b,y,top,anchors,lifts,ma):
    xs = [a,b]
    for hx,hy in anchors:
        xs += [max(a,min(b,hx+q)) for q in (-.009,-.008,.008,.009)]
    xs = sorted(set(xs))
    vertices = []
    n = 13
    for x in xs:
        compression = 1
        for (hx,hy),lift in zip(anchors,lifts):
            if abs(x-hx)<=.008001:
                compression = min(compression,max(.05,min(1,(lift+.00010)/SEAL_HEIGHT)))
        for i in range(n):
            yy = y+.0025*math.cos(math.pi*i/(n-1))
            vertices.append((x,yy,top(x,yy)+SEAL_HEIGHT*math.sin(math.pi*i/(n-1))*compression))
    faces = [tuple(range(n-1,-1,-1)),tuple(range((len(xs)-1)*n,len(xs)*n))]
    for j in range(len(xs)-1):
        faces += [(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for k in range(n)]
    return mesh(name,vertices,faces,ma)


def render(args,data):
    args.output.mkdir(parents=True,exist_ok=True)
    assert abs(data.get('course_pitch_m',Y_PITCH)-Y_PITCH)<EPS, 'Pro row pitch must be 340 mm'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    ma = {
        'pv':material('Pro AG glass · masked cells · 70 W',(.035,.045,.057),.73,.12),
        'companion':material('Pro non-generating cuttable companion',(.045,.050,.056),.76,.08),
        'rubber':material('EPDM · 5×2.5 mm half-round / 20 mm right pad',(.014,.017,.019),.87),
        'metal':material('Black folded flashings · indicative section',(.027,.034,.043),.44,.25),
        'steel':material('Screw / support steel',(.32,.36,.39),.45,.65),
        'deck':material('Roof substrate · display section',(.33,.36,.39),.9),
        'original_roof':material('Existing north roof · context only',(.19,.195,.19),.92),
        'wall':material('Building context · drawing-based envelope',(.72,.71,.67),.9),
        'window':material('Glazing context',(.15,.24,.29),.25,.10),
        'ground':material('Studio background',(.84,.87,.88),.95),
    }
    root = collection(data.get('project_name','Almaden Pro 屋面排布'))
    helper = collection('Construction helpers',root)
    approved_file = args.assets/'approved-wind-clip.blend'
    with bpy.data.libraries.load(str(approved_file),link=False) as (src,dst):
        dst.meshes = [n for n in src.meshes if n.startswith('Wind_clip_continuous_flat_strip_U_return')]
    assert len(dst.meshes)==1, 'Approved continuous folded clip mesh is missing'
    clip_source = dst.meshes[0]
    pv_holes = [(x,.185,SX*x+SY*.185+THICKNESS/2) for x in (-.580,-.035,.035,.580)]
    pv_mesh = solid('Pro_1240x390x6p2_4_bores',rect(-.620,-.195,.620,.195),lambda x,y:SX*x+SY*y,lambda x,y:SX*x+SY*y+THICKNESS,ma['pv'])
    pv_mesh = cut_holes(pv_mesh,pv_holes,.0029,helper)
    shaft = cylinder('Self-tapping screw 3.8×40 · indicative',.0019,.040,ma['steel'])
    head = cylinder('Screw head',.0045,.003,ma['metal'])
    render_objects,frames = [],[]
    counts = Counter()
    all_parents = []
    clip_cache = {}
    def add(name,m,co,parent=None,matrix=None,kind=None):
        o = obj(name,m,co,parent,matrix)
        if kind:
            o['kind'] = kind
        render_objects.append(o)
        return o

    for face in data['faces']:
        co = collection(face.get('name',face['id']),root)
        matrix = basis(face['u'],face['v'],face['normal'],face['origin'])
        assert math.degrees(math.acos(max(-1,min(1,face['normal'][2]))))>12, 'Pro requires roof slope >12 degrees'
        frames.append((face,matrix))
        roof_parts = face.get('roof_parts') or [{'outer':face['boundary'],'holes':face.get('holes',[])}]
        add(face['id']+'_屋面基层',solid('Roof substrate',roof_parts,lambda x,y:-.030,lambda x,y:0,ma['deck']),co,matrix=matrix,kind='roof_deck')
        all_tiles = face['tiles']
        for tile in all_tiles:
            assert tile['kind'] in ('pv','companion'), 'Unknown tile kind'
            assert tile.get('stock_type','full') in ('full','half'), 'Quarter companions are not supported'
            cx,cy = tile['center']
            virtual = tile.get('virtual_center',tile['center'])
            if isinstance(virtual,(int,float)):
                virtual = [virtual,cy]
            vx = virtual[0]
            width = tile.get('width_m',WIDTH if tile.get('stock_type','full')=='full' else .630)
            length = tile.get('length_m',LENGTH)
            assert abs(length-LENGTH)<EPS, 'Pro stock tile length must be 390 mm'
            identifier = face['id']+'_'+tile['id']
            parent = obj(identifier,None,co,matrix=matrix)
            parent.empty_display_size = .025
            parent['kind'],parent['tile_id'] = tile['kind'],tile['id']
            parent['stock_type'] = tile.get('stock_type','full')
            parent['row'],parent['col'] = tile['row'],tile['col']
            parent['power_w'] = 70 if tile['kind']=='pv' else 0
            parent['cuttable'] = tile['kind']=='companion'
            parent['manufacturer_dimensions_mm'] = [1240,390,6.2] if tile['kind']=='pv' else [1240 if width>.7 else 630,390,6.2]
            all_parents.append(parent)
            parts = tile.get('parts') or [{'outer':tile['footprint'],'holes':[]}]
            def bottom(x,y):
                return BASE_Z+SX*(x-vx)+SY*(y-cy)
            def top(x,y):
                return bottom(x,y)+THICKNESS
            if tile['kind']=='pv':
                assert abs(width-WIDTH)<EPS, 'Generating Pro tiles cannot be cut or half-width'
                panel = add(identifier+'_防眩光整瓦_70W',pv_mesh,co,parent,kind='pv_laminate')
                panel.location = (cx,cy,BASE_Z+SX*(cx-vx))
                anchors = [(cx+x,cy+.185) for x in (-.580,-.035,.035,.580)]
                counts['pv_count'] += 1
            else:
                panel = add(identifier+'_可裁切非发电配瓦',solid(identifier,parts,bottom,top,ma['companion']),co,parent,kind='companion_laminate')
                panel['cut_parts'] = json.dumps(parts,ensure_ascii=False)
                nominal_xs = (cx-width/2+.04,cx-.035,cx+.035,cx+width/2-.04) if width>.7 else (cx-width*.32,cx+width*.32)
                anchors = [(x,cy+.185) for x in nominal_xs if within((x,cy+.185),parts)]
                if anchors:
                    panel.data = cut_holes(panel.data,[(x,y,top(x,y)-THICKNESS/2) for x,y in anchors],.0029,helper)
                counts['companion_count'] += 1
            lifts = []
            for k,(hx,hy) in enumerate(anchors):
                lip_y = hy-.029
                upper = []
                for other in all_tiles:
                    if other['row'] != tile['row']+1:
                        continue
                    op = other.get('parts') or [{'outer':other['footprint'],'holes':[]}]
                    if within((hx,lip_y),op):
                        ocx,ocy = other['center']
                        ov = other.get('virtual_center',[ocx,ocy])
                        ox = ov if isinstance(ov,(int,float)) else ov[0]
                        upper.append(BASE_Z+SX*(hx-ox)+SY*(lip_y-ocy)+THICKNESS)
                lift = max(.001,max(upper,default=top(hx,lip_y)) - top(hx,lip_y)-.00925+.00065)
                lifts.append(lift)
                key = round(lift,7)
                if key not in clip_cache:
                    m = clip_source.copy()
                    m.name = 'Approved Pro U-return clip · installed flex '+str(key)
                    for vertex in m.vertices:
                        qx,qy,qz = vertex.co
                        dx,dy = qy,-(qx+.011)
                        t = max(0,min(1,(qx+.011)/.012))
                        vertex.co = (dx,dy,SX*dx+SY*dy+.00015+qz+lift*t*t*(3-2*t))
                    m.update()
                    clip_cache[key] = m
                clip = add(identifier+f'_抑风扣{k+1}',clip_cache[key],co,parent,kind='wind_clip')
                clip.location = (hx,hy,top(hx,hy))
                clip['hook_direction'] = 'downslope; closed nose to eave'
                clip['dimension_status'] = 'User-approved shape; photo-proportion dimensions; indicative installed flex'
                counts['wind_clip_count'] += 1
                if tile['kind']=='pv':
                    counts['pv_wind_clip_count'] += 1
                s = add(identifier+f'_自攻螺丝{k+1}',shaft,co,parent,kind='screw')
                s.location = (hx,hy,top(hx,hy)+.00165-.040)
                h = add(identifier+f'_螺丝头{k+1}',head,co,parent)
                h.location = (hx,hy,top(hx,hy)+.00165)
                counts['screw_count'] += 1
            for j,y in enumerate((cy+.195-.024,cy+.195-.043)):
                for k,(a,b) in enumerate(horizontal_intervals(parts,y)):
                    a,b = max(a,cx-width/2+.001),min(b,cx+width/2-.020)
                    if b-a>.002:
                        add(identifier+f'_上沿半圆胶条{j+1}_{k+1}',seal_mesh(identifier,a,b,y,top,anchors,lifts,ma['rubber']),co,parent,kind='top_seal')
                if tile['kind']=='pv':
                    counts['pv_top_seal_count'] += 1
            pads = pad_parts(parts,cx+width/2-.020,cx+width/2)
            if pads:
                add(identifier+'_右侧20mm防水垫',solid(identifier,pads,top,lambda x,y:top(x,y)+PAD,ma['rubber']),co,parent,kind='right_pad')
                if tile['kind']=='pv':
                    counts['pv_right_pad_count'] += 1
            if tile['kind']=='pv':
                junction = add(identifier+'_背面接线盒',solid(identifier,rect(cx-.0275,cy-.0315,cx+.0275,cy+.0115),lambda x,y:bottom(x,y)-.015,lambda x,y:bottom(x,y)-.0003,ma['rubber']),co,parent,kind='junction_box')
                junction['electrical_design'] = 'Factory box geometry only; no project string design inferred'

        for obstacle in face.get('obstacles',[]):
            if obstacle.get('type') not in ('skylight','chimney'):
                continue
            polygon = obstacle['polygon']
            height = obstacle.get('height_m',.12 if obstacle['type']=='skylight' else .75)
            p = [{'outer':polygon,'holes':[]}]
            item = add(obstacle.get('id','obstacle')+'_示意',solid('Roof obstruction',p,lambda x,y:.020,lambda x,y:height,ma['window'] if obstacle['type']=='skylight' else ma['wall']),co,matrix=matrix,kind=obstacle['type'])
            item['dimension_status'] = 'Geometry from input footprint; height may be indicative'

    context = data.get('context',{})
    context_co = collection('图纸建筑环境 · 非发电区',root)
    for item in context.get('objects',[]):
        if item.get('type') != 'box':
            continue
        x,y,z = item['center']
        w,d,h = item['size']
        add(item.get('label','建筑框体'),solid('Context box',rect(x-w/2,y-d/2,x+w/2,y+d/2),lambda x,y:z-h/2,lambda x,y:z+h/2,ma['wall']),context_co,kind='building_context')
    for f in context.get('roof_faces',[]):
        m = basis(f['u'],f['v'],f['normal'],f['origin'])
        p = f.get('roof_parts') or [{'outer':f['boundary'],'holes':f.get('holes',[])}]
        add(f.get('name','非发电屋面'),solid('Context roof',p,lambda x,y:-.035,lambda x,y:.058,ma['original_roof']),context_co,matrix=m,kind='roof_context')
    for panel in context.get('wall_panels',[]):
        vertices = panel['vertices']
        m = mesh(panel.get('id','高低跨竖立面'),vertices,[tuple(range(len(vertices)))],ma['wall'])
        add(panel.get('label',panel.get('id','高低跨竖立面')),m,context_co,kind='wall_context')

    edge_co = collection('安装说明书收口 · 未提供截面尺寸处示意',root)
    for edge in data.get('edges',[]):
        start,end = Vector(edge['start']),Vector(edge['end'])
        delta = end-start
        if delta.length < .012:
            continue
        x = delta.normalized()
        midpoint = (start+end)/2
        nearest = sorted(frames,key=lambda fm:abs(Vector(fm[0]['normal']).dot(midpoint-Vector(fm[0]['origin']))))
        adjacent = [(f,m) for f,m in nearest if abs(Vector(f['normal']).dot(midpoint-Vector(f['origin'])))<.040]
        if edge.get('face_id') and edge['type'] not in ('ridge','hip'):
            adjacent = [(f,m) for f,m in adjacent if f['id']==edge['face_id']]
        if edge['type'] in ('ridge','hip'):
            up = Vector((0,0,1))
        else:
            up = Vector(adjacent[0][0]['normal']) if adjacent else Vector((0,0,1))
        z = (up-x*up.dot(x)).normalized()
        y = z.cross(x).normalized()
        lengths = delta.length-.006
        point = start+x*.003
        kind = edge['type']
        if kind in ('ridge','hip'):
            # Folded hollow cap follows the two roof inclinations; it is not
            # a copied curved tile. Raise the skirts above the tile envelope.
            w = .18
            lift = .082
            for f,m in adjacent:
                n = Vector(f['normal'])
                if n.dot(z)>.1:
                    lift = max(lift,.075+(.078-abs(n.dot(y))*w)/n.dot(z))
            cross = [(-w,-.075),(0,0),(w,-.075),(w,-.078),(0,-.003),(-w,-.078)]
        elif kind in ('verge','wall'):
            inward = 1
            if adjacent:
                f,m = adjacent[0]
                inward = 1 if inside((m.inverted()@(midpoint+y*.04)).xy,f['boundary']) else -1
            lift = .081
            if kind=='wall':
                cross = [(0,.200),(.003*inward,.200),(.003*inward,.003),(.100*inward,.003),(.100*inward,0),(0,0)]
            else:
                cross = [(0,0),(.100*inward,0),(.100*inward,-.002),(.002*inward,-.002),(.002*inward,-.110),(0,-.110)]
        elif kind=='valley':
            lift = .024
            cross = [(-.135,.018),(0,0),(.135,.018),(.135,.015),(0,-.003),(-.135,.015)]
        elif kind=='eave':
            inward = 1
            if adjacent:
                f,m = adjacent[0]
                inward = 1 if inside((m.inverted()@(midpoint+y*.04)).xy,f['boundary']) else -1
            lift = .032
            cross = [(.015*inward,0),(-.040*inward,0),(-.040*inward,-.055),(-.020*inward,-.060),(-.020*inward,-.063),(-.043*inward,-.058),(-.043*inward,.003),(.015*inward,.003)]
        else:
            continue
        o = add(edge['id']+'_连续收口示意',section_mesh(kind,cross,lengths,ma['metal']),edge_co,matrix=basis(x,y,z,point+z*lift),kind=kind)
        o['说明'] = 'Pro 安装说明书收口类别；连续折板示意，不是加工截面，按延米统计'
        o['source_edge_length_m'] = delta.length
        counts[kind+'_continuous_edges'] += 1

    assert counts['pv_wind_clip_count']==4*counts['pv_count']
    assert counts['pv_top_seal_count']==2*counts['pv_count']
    assert counts['pv_right_pad_count']==counts['pv_count']
    expected = data.get('summary',{})
    for key in ('pv_count','companion_count'):
        if key in expected:
            assert counts[key]==expected[key], f'Layout/render count mismatch: {key}'
    if 'capacity_kwp' in expected:
        assert abs(counts['pv_count']*.07-expected['capacity_kwp'])<1e-6
    bpy.context.view_layer.update()
    points = [o.matrix_world@Vector(v) for o in render_objects for v in o.bound_box]
    assert points and all(math.isfinite(v) for p in points for v in p)
    lo = Vector(tuple(min(p[k] for p in points) for k in range(3)))
    hi = Vector(tuple(max(p[k] for p in points) for k in range(3)))
    center,extent = (lo+hi)/2,max((hi-lo).length,1)
    scene.world = bpy.data.worlds.new('Neutral white studio')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value,bg.inputs['Strength'].default_value = (.8,.84,.9,1),.55
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage = 1800,1200,100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = .5
    bpy.ops.mesh.primitive_plane_add(size=extent*20,location=(center.x,center.y,lo.z-.04))
    ground = bpy.context.object
    ground.name = '摄影背景 · 非建筑构件'
    ground.data.materials.append(ma['ground'])
    for label,offset,power,size in [('主柔光',(-.3,-.5,1),18,.8),('补光',(.6,.3,.7),10,.7)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(offset)*extent)
        light = bpy.context.object
        light.name = label
        light.data.energy,light.data.shape,light.data.size = power*extent**2,'DISK',size*extent
        light.rotation_euler = (center-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type,camera.data.clip_end = 'ORTHO',extent*20
    scene.camera = camera
    roof_points = [o.matrix_world@Vector(v) for o in render_objects if o.get('kind')!='building_context' for v in o.bound_box]
    roof_lo = Vector(tuple(min(p[k] for p in roof_points) for k in range(3)))
    roof_hi = Vector(tuple(max(p[k] for p in roof_points) for k in range(3)))
    roof_center = (roof_lo+roof_hi)/2
    def camera_view(direction,full=False):
        target = center if full else roof_center
        camera.location = target+direction.normalized()*extent*2
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update()
        framed = [camera.matrix_world.inverted()@p for p in (points if full else roof_points)]
        xmin,xmax = min(p.x for p in framed),max(p.x for p in framed)
        ymin,ymax = min(p.y for p in framed),max(p.y for p in framed)
        camera.location += camera.matrix_world.to_3x3()@Vector(((xmin+xmax)/2,(ymin+ymax)/2,0))
        camera.data.ortho_scale = max(xmax-xmin,(ymax-ymin)*scene.render.resolution_x/scene.render.resolution_y)*1.14
    f = data['faces'][0]
    camera_view(Vector(f['u'])*.70-Vector(f['v'])*.80+Vector(f['normal'])*1.30)
    report = {
        'project_name':data.get('project_name'),'counts':dict(counts),'capacity_kwp':round(counts['pv_count']*.07,6),
        'input_layout':str(args.layout),'world_bounds_m':[list(lo),list(hi)],'roof_bases_preserved':True,
        'approved_clip_asset':approved_file.name,'finite_geometry':True,
        'assumptions':list(data.get('assumptions',[]))+[
            'Pro 70 W；1240×390×6.2 mm；横向1220 mm、坡面逐排340 mm；只有整/半非发电配瓦可裁切。',
            '屋面采用输入的真实展开 u/v 坐标与朝向坡度；单瓦搭接微倾沿用已确认安装样段，不累积逐排抬高屋面。',
            '四孔位置、抑风扣尺寸、右垫1 mm厚度按已确认照片比例示意；不是加工图。',
            '抑风扣连续折回形体取自用户批准的 Blender 资产。平条微弯与双胶条局部压缩仅示意连接关系。',
            '收口采用安装书中的檐口、山墙、正/斜脊与天沟类别，折板截面与承托未获实尺寸处为示意。',
            '背面接线盒表示产品组成，不表示已经完成项目组串、线缆、逆变器、电气或水密及风荷载设计。',
        ],
    }
    note = bpy.data.texts.new('请先阅读 · Pro 建模依据及限制')
    note.write(json.dumps(report,ensure_ascii=False,indent=2))
    scene['排布核验'] = json.dumps(dict(counts),ensure_ascii=False)
    scene['项目名称'] = data.get('project_name','Almaden Pro 屋面排布')
    logo = args.assets/'logo.png'
    if logo.exists():
        bpy.data.images.load(str(logo)).pack()
    for screen in bpy.data.screens:
        for ar in screen.areas:
            if ar.type=='VIEW_3D':
                ar.spaces.active.shading.color_type = 'MATERIAL'
                ar.spaces.active.region_3d.view_distance = extent
                ar.spaces.active.region_3d.view_location = center
                ar.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
    bpy.context.preferences.filepaths.save_version = 0
    blend_file = args.output/'屋面模型.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_file))
    bpy.ops.object.select_all(action='DESELECT')
    for o in list(root.all_objects):
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(args.output/'屋面模型.glb'),export_format='GLB',use_selection=True,export_extras=True,export_cameras=False,export_lights=False)
    scene.render.filepath = str(args.output/'屋面效果图.png')
    bpy.ops.render.render(write_still=True)
    camera_view(Vector((0,0,1)))
    scene.render.filepath = str(args.output/'屋面俯视图.png')
    bpy.ops.render.render(write_still=True)
    camera_view(Vector(f['u'])*.70-Vector(f['v'])*.80+Vector(f['normal'])*1.30,full=True)
    scene.render.filepath = str(args.output/'建筑示意图.png')
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend_file))
    assert json.loads(bpy.context.scene['排布核验'])==dict(counts)
    pv = [o for o in bpy.data.objects if o.get('kind')=='pv']
    assert len(pv)==counts['pv_count']
    assert all(sum(c.get('kind')=='wind_clip' for c in p.children)==4 for p in pv)
    assert all(sum(c.get('kind')=='top_seal' for c in p.children)==2 for p in pv)
    assert all(sum(c.get('kind')=='right_pad' for c in p.children)==1 for p in pv)
    assert all(math.isfinite(v) for o in bpy.data.objects for row in o.matrix_world for v in row)
    report['saved_file_reopen'] = 'passed'
    report['glb_exported'] = (args.output/'屋面模型.glb').stat().st_size>0
    (args.output/'Blender核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('BLENDER_PRO_VERIFIED:'+json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    options = arguments()
    render(options,json.loads(options.layout.read_text()))
