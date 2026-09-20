"""Deterministic whole-PV / cuttable companion layout in each roof plane (metres)."""
import math
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

POWER_W = 40
PITCH = .405
FUNCTIONS = {
    'ridge': ('正脊瓦', .750, .713),
    'hip': ('斜脊瓦', .750, .700),
    'verge': ('封檐瓦', .620, .600),
    'valley': ('排水沟瓦', .840, .800),
}


def number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} 必须为有限数值')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{name} 超出允许范围')
    return value


def polygon(points, name):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(f'{name} 需要至少三个顶点')
    for p in points:
        if len(p) != 2:
            raise ValueError(f'{name} 顶点必须是 [x,y]，单位米')
        for n in p:
            number(n, name)
    shape = Polygon(points)
    if not shape.is_valid or shape.area <= 1e-8:
        raise ValueError(f'{name} 存在自交、退化或无效边界；请核对图纸')
    return shape


def pieces(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry] if geometry.area > 1e-8 else []
    return [p for g in geometry.geoms for p in pieces(g)] if hasattr(geometry, 'geoms') else []


def rings(geometry):
    return [{'outer': [list(p) for p in g.exterior.coords[:-1]],
             'holes': [[list(p) for p in h.coords[:-1]] for h in g.interiors]}
            for g in pieces(geometry)]


def world(face, point):
    return [face['origin'][i] + point[0]*face['u'][i] + point[1]*face['v'][i] for i in range(3)]


def calculate(project):
    if project.get('units') != 'm':
        raise ValueError('请先把图纸转为米，输入 units="m"；不要默认把毫米当米')
    source_faces = project.get('faces', [])
    if not source_faces:
        raise ValueError('缺少屋面 faces')
    lateral = number(project.get('lateral_pitch_m', .713), '横向有效模数', .1, .723)
    if abs(lateral-.713) > 1e-9:
        raise ValueError('现款发电瓦、主配瓦及正脊沿脊的有效模数已统一确认为 0.713 m；旧700 mm不可直接套用')
    if abs(project.get('course_pitch_m', PITCH)-PITCH) > 1e-9:
        raise ValueError('本产品沿坡排距为已确认的 0.405 m；其他排距需要更新产品规则')
    if project.get('power_w', POWER_W) != POWER_W:
        raise ValueError('本技能现款统一 40 W，不能沿用旧图 45 W')
    assumptions = list(project.get('assumptions', []))
    if not project.get('geometry_source'):
        assumptions.append('输入未提供图纸/尺寸来源，本次只作输入几何的演示排布。')
    faces = []
    ids = set()
    for raw in source_faces:
        missing = [k for k in ('id','boundary','origin','tilt_deg','azimuth_deg','pv_regions') if k not in raw]
        if missing:
            raise ValueError(f'坡面缺少关键输入：{", ".join(missing)}；请核对图纸或业主要求')
        fid = str(raw['id'])
        if fid in ids:
            raise ValueError(f'屋面编号重复: {fid}')
        ids.add(fid)
        boundary = polygon(raw['boundary'], f'{fid} 屋面')
        holes = [polygon(h, f'{fid} 孔洞') for h in raw.get('holes', [])]
        obstacles = raw.get('obstacles', [])
        exclusions = []
        for o in obstacles:
            if 'clearance_m' not in o:
                raise ValueError(f'{fid} 洞口 {o.get("id", "")} 缺少禁布预留带 clearance_m；示例150 mm不可静默套用')
            h = polygon(o['polygon'], f'{fid} 障碍物')
            if not boundary.covers(h):
                raise ValueError(f'{fid} 障碍物超出屋面，请核对坐标')
            holes.append(h)
            exclusions.append(h.buffer(number(o['clearance_m'], '洞口留带', 0), join_style=2))
        for h in holes:
            if not boundary.covers(h):
                raise ValueError(f'{fid} 孔洞超出屋面')
        roof = boundary.difference(unary_union(holes))
        if roof.area <= 1e-8:
            raise ValueError(f'{fid} 没有有效屋面面积')
        if 'pv_regions' not in raw:
            raise ValueError(f'{fid} 缺少业主指定发电区域 pv_regions；不发电坡面填 []')
        regions = [polygon(q, f'{fid} 发电区域') for q in raw['pv_regions']]
        if any(not boundary.buffer(1e-7).covers(q) for q in regions):
            raise ValueError(f'{fid} 指定发电区域超出屋面')
        pv_region = unary_union(regions).intersection(roof).difference(unary_union(exclusions))
        tilt = number(raw['tilt_deg'], f'{fid} 坡度', 0, 85)
        azimuth = number(raw['azimuth_deg'], f'{fid} 方位角', 0, 360) % 360
        if len(raw['origin']) != 3:
            raise ValueError(f'{fid} origin 需要三维坐标')
        for v in raw['origin']:
            number(v, f'{fid} origin')
        a, t = math.radians(azimuth), math.radians(tilt)
        face = dict(raw, id=fid, name=raw.get('name', fid), tilt_deg=tilt, azimuth_deg=azimuth,
                    u=[-math.cos(a), math.sin(a), 0],
                    v=[-math.sin(a)*math.cos(t), -math.cos(a)*math.cos(t), math.sin(t)],
                    normal=[math.sin(a)*math.sin(t), math.cos(a)*math.sin(t), math.cos(t)],
                    holes=[list(map(list, h.exterior.coords[:-1])) for h in holes],
                    roof_parts=rings(roof), tiles=[])
        xmin, ymin, xmax, ymax = boundary.bounds
        gx, gy = raw.get('grid_origin', [xmin, ymin])
        number(gx, '排布起点X'); number(gy, '排布起点Y')
        face['grid_origin'] = [gx, gy]
        col0 = math.floor((xmin-gx)/lateral)
        row0 = math.floor((ymin-gy)/PITCH)
        ncols = math.ceil((xmax-gx)/lateral)-col0
        nrows = math.ceil((ymax-gy)/PITCH)-row0
        if nrows*ncols > 100000:
            raise ValueError(f'{fid} 超过十万个网格；请检查图纸单位或拆分建筑')
        min_fragment = number(raw.get('min_companion_area_m2', .0001), '配瓦最小几何面积', 0, .1)
        for row in range(row0, row0+nrows):
            for col in range(col0, col0+ncols):
                x, y = gx+col*lateral, gy+row*PITCH
                # Only effective cells intersecting the roof generate a billable stock tile.
                if box(x, y, x+lateral, y+PITCH).intersection(roof).area <= 1e-8:
                    continue
                pv_box = box(x, y, x+.723, y+.5)
                is_pv = pv_region.buffer(1e-8).covers(pv_box)
                width = .723 if is_pv else .724
                footprint = box(x, y, x+width, y+.5)
                geom = footprint if is_pv else footprint.intersection(roof)
                if geom.area < min_fragment:
                    continue
                face['tiles'].append({
                    'id': f'{fid}-R{row-row0+1:02d}-C{col-col0+1:02d}',
                    'kind': 'pv' if is_pv else 'companion', 'row': row-row0, 'col': col-col0,
                    'center': [x+width/2, y+.25], 'width_m': width, 'length_m': .5,
                    'footprint': list(map(list, footprint.exterior.coords[:-1])), 'parts': rings(geom),
                })
        face['pv_count'] = sum(t['kind'] == 'pv' for t in face['tiles'])
        face['companion_count'] = len(face['tiles'])-face['pv_count']
        face['capacity_kwp'] = face['pv_count']*POWER_W/1000
        face['area_m2'] = roof.area
        faces.append(face)
    edges, edge_ids = [], set()
    coordinates = set()
    for raw in project.get('edges', []):
        eid, typ = str(raw['id']), raw['type']
        if eid in edge_ids:
            raise ValueError(f'共享收口边重复编号 {eid}；同一条正脊只能统计一次')
        edge_ids.add(eid)
        if typ not in FUNCTIONS and typ != 'eave':
            raise ValueError(f'未知功能瓦类型 {typ}；异型节点需按个补充 fittings')
        start, end = raw['start'], raw['end']
        if len(start) != 3 or len(end) != 3:
            raise ValueError(f'{eid} 起终点须为三维坐标')
        for c in start+end: number(c, f'{eid} 坐标')
        length = math.dist(start, end)
        if length < 1e-6:
            raise ValueError(f'{eid} 边长为零')
        key = tuple(sorted(tuple(round(c, 6) for c in p) for p in [start, end]))
        if key in coordinates:
            raise ValueError(f'{eid} 与已输入收口边重合；请合并共享边')
        coordinates.add(key)
        if typ == 'eave':
            count, actual, effective = None, None, None
            assumptions.append(f'{eid} 檐口收口 {length:.2f} m：未提供现款功能件有效尺寸，仅列长度，数量待定。')
        else:
            _, actual, effective = FUNCTIONS[typ]
            count = max(1, math.ceil((length-(actual-effective)-1e-8)/effective))
        edges.append(dict(raw, length_m=length, count=count, effective_length_m=effective, actual_length_m=actual))
    if not edges:
        assumptions.append('未标注收口边，功能瓦清单尚不完整；正脊、斜脊、檐边、天沟需从图纸补齐。')
    fittings = project.get('fittings', [])
    for f in fittings:
        if not isinstance(f['count'], int) or isinstance(f['count'], bool) or f['count'] < 0:
            raise ValueError('异型配件数量必须为非负整数')
    pv = sum(f['pv_count'] for f in faces)
    companion = sum(f['companion_count'] for f in faces)
    quantities = [{'name': '三曲发电瓦 BHAC40R-40', 'quantity': pv, 'unit': '片', 'basis': '完整发电瓦逐片计数，40 W/片'},
                  {'name': '主配瓦（可裁切）', 'quantity': companion, 'unit': '片', 'basis': '占位所需原片估算；不优化余料复用，不含另加备料'},
                  {'name': 'J形抑风扣', 'quantity': pv*2, 'unit': '个', 'basis': '两波谷各一个，朝坡下扣住上瓦下边缘'}]
    for typ, (name, _, _) in FUNCTIONS.items():
        selected = [e for e in edges if e['type'] == typ]
        if selected:
            quantities.append({'name': name, 'quantity': sum(e['count'] for e in selected), 'unit': '片',
                               'basis': '各连续边按实长和有效搭接长度分别向上取整'})
    for e in edges:
        if e['type'] == 'eave': quantities.append({'name': '檐口收口（型号待定）', 'quantity': round(e['length_m'], 3), 'unit': 'm', 'basis': e['id']+'；未计入瓦片数量'})
    quantities += [{'name': f['name'], 'quantity': f['count'], 'unit': f.get('unit', '个'), 'basis': f.get('source', '图纸节点数量')} for f in fittings]
    spare = number(project.get('spare_pct', 0), '备料比例', 0, 100)
    for q in quantities:
        if q['unit'] in ('片', '个'):
            q['spare_quantity'] = math.ceil(q['quantity']*spare/100)
            q['purchase_quantity'] = q['quantity']+q['spare_quantity']
    assumptions += ['装机容量=完整发电瓦数量×40÷1000 kWp；配瓦不计发电。',
                    '两侧、坡顶及洞口配瓦按边界显示裁切；清单只估算各功能原片数量，不输出裁切加工表。',
                    '2026-09-13用户确认：发电瓦/主配瓦横向及正脊沿脊有效模数统一713 mm，覆盖旧报价700 mm；沿坡405 mm。斜脊沿线700 mm、封檐瓦600 mm、沟瓦800 mm保留报价口径。',
                    '三维搭接和部分收口截面用于方案表现，不能替代厂家节点尺寸与现场安装复核。']
    return {'project_name': project.get('project_name', '三曲瓦屋面排布'), 'units': 'm',
            'geometry_source': project.get('geometry_source'), 'lateral_pitch_m': lateral, 'course_pitch_m': PITCH,
            'faces': faces, 'edges': edges, 'fittings': fittings, 'quantities': quantities,
            'summary': {'pv_count': pv, 'companion_count': companion, 'capacity_kwp': pv*POWER_W/1000,
                        'j_clip_count': pv*2, 'roof_area_m2': sum(f['area_m2'] for f in faces), 'spare_pct': spare},
            'assumptions': list(dict.fromkeys(assumptions))}
