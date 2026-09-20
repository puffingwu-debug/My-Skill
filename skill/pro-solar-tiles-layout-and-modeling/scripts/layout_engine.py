"""Whole 70 W Pro tiles on developed roof planes; cuttable full/half blanks."""
import math
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

POWER_W = 70
LATERAL = 1.220
PITCH = .340
WIDTH = 1.240
LENGTH = .390
HALF_WIDTH = .630


def number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} 必须为有限数值')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{name} 超出允许范围')
    return value


def polygon(points, name):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(f'{name} 至少需要三个顶点')
    for p in points:
        if len(p) != 2:
            raise ValueError(f'{name} 顶点必须为 [x,y] 米制坡面展开坐标')
        for c in p:
            number(c, name)
    geom = Polygon(points)
    if not geom.is_valid or geom.area <= 1e-8:
        raise ValueError(f'{name} 存在自交、退化或无效边界')
    return geom


def pieces(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry] if geometry.area > 1e-9 else []
    return [p for g in geometry.geoms for p in pieces(g)] if hasattr(geometry, 'geoms') else []


def rings(geometry):
    return [{'outer': [list(p) for p in g.exterior.coords[:-1]],
             'holes': [[list(p) for p in h.coords[:-1]] for h in g.interiors]}
            for g in pieces(geometry)]


def world(face, point):
    return [face['origin'][i]+point[0]*face['u'][i]+point[1]*face['v'][i] for i in range(3)]


def calculate(project):
    if project.get('units') != 'm':
        raise ValueError('需要 units="m"，屋面边界必须是坡面展开实长，不能使用投影长度')
    for key, expected in [('lateral_pitch_m',LATERAL),('course_pitch_m',PITCH),('power_w',POWER_W)]:
        value = number(project.get(key, expected), key)
        if abs(value-expected)>1e-8:
            raise ValueError(f'当前Pro固定 {key}={expected}，不能混入其他产品参数')
    if not project.get('faces'):
        raise ValueError('缺少屋面 faces')
    assumptions = list(project.get('assumptions', []))
    if not project.get('geometry_source'):
        assumptions.append('未提供尺寸来源，本次为输入几何演示。')
    faces, ids = [], set()
    for raw in project['faces']:
        required = ['id','boundary','origin','tilt_deg','azimuth_deg','pv_regions']
        if any(k not in raw for k in required):
            raise ValueError('坡面缺少边界、原点、坡度、北向或业主指定发电区域')
        fid = str(raw['id'])
        if fid in ids:
            raise ValueError(f'重复坡面编号 {fid}')
        ids.add(fid)
        if raw.get('coordinate_space') != 'developed':
            raise ValueError(f'{fid} 必须声明 coordinate_space="developed" 并使用坡面实长')
        tilt = number(raw['tilt_deg'], '坡度', 0, 90)
        if tilt <= 12:
            raise ValueError(f'{fid} 坡度必须严格大于12°，不得自动改变建筑坡度')
        azimuth = number(raw['azimuth_deg'], '真北方位角', 0, 360) % 360
        if len(raw['origin']) != 3:
            raise ValueError('origin需要三维世界坐标')
        for c in raw['origin']:
            number(c,'origin')
        boundary = polygon(raw['boundary'], f'{fid} 屋面')
        holes = [polygon(h,f'{fid} 孔洞') for h in raw.get('holes',[])]
        exclusions = []
        for o in raw.get('obstacles',[]):
            h = polygon(o['polygon'],f'{fid} 障碍物')
            holes.append(h)
            if 'clearance_m' not in o:
                raise ValueError(f'{fid} 洞口需注明禁布留带clearance_m及其依据')
            exclusions.append(h.buffer(number(o['clearance_m'],'洞口留带',0),join_style=2))
        if any(not boundary.buffer(1e-8).covers(h) for h in holes):
            raise ValueError(f'{fid} 孔洞超出屋面')
        roof = boundary.difference(unary_union(holes))
        if roof.area <= 1e-8:
            raise ValueError(f'{fid} 无有效屋面面积')
        tile_regions=[polygon(q,f'{fid} 铺瓦区域') for q in raw.get('tile_regions',[raw['boundary']])]
        if any(not boundary.buffer(1e-8).covers(q) for q in tile_regions):
            raise ValueError(f'{fid} 铺瓦区域超出屋面')
        tile_surface=unary_union(tile_regions).intersection(roof)
        if tile_surface.area<=1e-8:
            raise ValueError(f'{fid} 无有效铺瓦区域')
        regions = [polygon(r,f'{fid} 发电区') for r in raw['pv_regions']]
        if any(not boundary.buffer(1e-8).covers(r) for r in regions):
            raise ValueError(f'{fid} 发电区域超出屋面')
        allowed = unary_union(regions).intersection(tile_surface).difference(unary_union(exclusions))
        a,t=math.radians(azimuth),math.radians(tilt)
        face = dict(raw,id=fid,name=raw.get('name',fid),tilt_deg=tilt,azimuth_deg=azimuth,
                    u=[-math.cos(a),math.sin(a),0],
                    v=[-math.sin(a)*math.cos(t),-math.cos(a)*math.cos(t),math.sin(t)],
                    normal=[math.sin(a)*math.sin(t),math.cos(a)*math.sin(t),math.cos(t)],
                    holes=[list(map(list,h.exterior.coords[:-1])) for h in holes],
                    roof_parts=rings(roof),tiles=[])
        xmin,ymin,xmax,ymax=tile_surface.bounds
        gx,gy=raw.get('grid_origin',[xmin,ymin])
        number(gx,'起排X');number(gy,'起排Y')
        face['grid_origin']=[gx,gy]
        r0=math.floor((ymin-gy)/PITCH)
        r1=max(r0,math.ceil((ymax-gy-LENGTH-1e-9)/PITCH))
        if (r1-r0+1)*math.ceil((xmax-xmin)/LATERAL+2)>100000:
            raise ValueError('超过十万排布格，请检查图纸单位')
        for row in range(r0,r1+1):
            y=gy+row*PITCH
            shift=-LATERAL/2 if (row-r0)%2 else 0
            start=gx+shift
            c0=math.floor((xmin-start)/LATERAL)
            c1=max(c0,math.ceil((xmax-start-WIDTH-1e-9)/LATERAL))
            for col in range(c0,c1+1):
                x=start+col*LATERAL
                footprint=box(x,y,x+WIDTH,y+LENGTH)
                installed=footprint.intersection(tile_surface)
                if installed.area<1e-8:
                    continue
                pv=allowed.buffer(1e-8).covers(footprint)
                stock='full'
                fx,fy,ex,ey=installed.bounds
                # A clipped grid position fits one half blank only if its entire geometry fits 630 mm.
                if not pv and ex-fx<=HALF_WIDTH+1e-8:
                    stock='half'
                    stock_x=max(x,min(fx,x+WIDTH-HALF_WIDTH))
                    footprint=box(stock_x,y,stock_x+HALF_WIDTH,y+LENGTH)
                width=WIDTH if stock=='full' else HALF_WIDTH
                bx,by,bxx,byy=footprint.bounds
                face['tiles'].append(dict(
                    id=f'{fid}-R{row-r0+1:02d}-C{col-c0+1:02d}',
                    kind='pv' if pv else 'companion',stock_type=stock,
                    row=row-r0,col=col-c0,center=[(bx+bxx)/2,y+LENGTH/2],
                    virtual_center=[x+WIDTH/2,y+LENGTH/2],
                    width_m=width,length_m=LENGTH,thickness_m=.0062,
                    footprint=list(map(list,footprint.exterior.coords[:-1])),
                    parts=rings(installed),power_w=POWER_W if pv else 0,
                    is_trimmed=installed.area<footprint.area-1e-8))
        face['pv_count']=sum(q['kind']=='pv' for q in face['tiles'])
        face['companion_count']=len(face['tiles'])-face['pv_count']
        face['companion_full_count']=sum(q['kind']=='companion' and q['stock_type']=='full' for q in face['tiles'])
        face['companion_half_count']=sum(q['kind']=='companion' and q['stock_type']=='half' for q in face['tiles'])
        face['capacity_kwp']=round(face['pv_count']*POWER_W/1000,6)
        face['area_m2']=roof.area
        face['tile_area_m2']=tile_surface.area
        face['trim_reserved_area_m2']=roof.area-tile_surface.area
        covered=unary_union([Polygon(p['outer'],p['holes']) for q in face['tiles'] for p in q['parts']])
        face['coverage_difference_m2']=tile_surface.symmetric_difference(covered).area
        if face['coverage_difference_m2']>1e-7:
            raise ValueError(f'{fid} 排布未完整覆盖屋面，请核对起排参数')
        faces.append(face)
    edges,edge_ids,coordinates=[],set(),set()
    for raw in project.get('edges',[]):
        eid=str(raw['id']);typ=raw['type']
        if eid in edge_ids or typ not in ['ridge','hip','verge','valley','eave','wall']:
            raise ValueError('收口边编号重复或类型无效')
        edge_ids.add(eid)
        start,end=raw['start'],raw['end']
        if len(start)!=3 or len(end)!=3:
            raise ValueError('收口边起终点须为三维坐标')
        for c in start+end:number(c,'收口坐标')
        length=math.dist(start,end)
        if length<1e-6:raise ValueError('收口边长度为零')
        key=tuple(sorted(tuple(round(c,6) for c in p) for p in [start,end]))
        if key in coordinates:raise ValueError('同一共享收口边不可重复累计')
        coordinates.add(key)
        actual=raw.get('actual_length_m');effective=raw.get('effective_length_m');count=None
        if actual is not None or effective is not None:
            number(actual,'配件实体长度',.001);number(effective,'配件有效长度',.001,actual)
            if not raw.get('source'):raise ValueError('收口配件长度需给出安装书或实物依据')
            count=max(1,math.ceil((length-(actual-effective)-1e-8)/effective))
        edges.append(dict(raw,length_m=length,count=count,actual_length_m=actual,effective_length_m=effective))
    fittings=project.get('fittings',[])
    for f in fittings:
        if not isinstance(f['count'],int) or isinstance(f['count'],bool) or f['count']<0:
            raise ValueError('异型配件数量必须是非负整数')
    pv=sum(f['pv_count'] for f in faces)
    full=sum(f['companion_full_count'] for f in faces)
    half=sum(f['companion_half_count'] for f in faces)
    quantities=[{'name':'Pro发电整瓦 BIAC14B-70','quantity':pv,'unit':'片','basis':'逐片统计完整发电瓦，70 W/片'},
                {'name':'非发电整配瓦（可裁切）','quantity':full,'unit':'片','basis':'1240×390 mm原片占位估算，不优化余料'},
                {'name':'非发电半配瓦（可裁切）','quantity':half,'unit':'片','basis':'630×390 mm原片占位估算，无四分之一配瓦'},
                {'name':'发电瓦抑风扣','quantity':pv*4,'unit':'个','basis':'每片发电整瓦4扣；裁切配瓦固定按安装节点另核'},
                {'name':'发电瓦自攻螺丝','quantity':pv*4,'unit':'枚','basis':'发电瓦4孔各配一钉，不含收口和配瓦固定'}]
    names={'ridge':'正脊收口','hip':'斜脊收口','verge':'山墙边瓦收口','valley':'天沟','eave':'檐口收口','wall':'靠墙泛水'}
    for e in edges:
        quantities.append({'name':names[e['type']],'quantity':e['count'] if e['count'] is not None else round(e['length_m'],3),
                           'unit':'件' if e['count'] is not None else 'm','basis':e['id']+'；'+(e.get('source') or '按安装说明书节点，分段加工长度待确认')})
    quantities += [{'name':f['name'],'quantity':f['count'],'unit':f.get('unit','个'),'basis':f.get('source','图纸节点')} for f in fittings]
    spare=number(project.get('spare_pct',0),'备料比例',0,100)
    for q in quantities:
        if q['unit'] in ('片','个','枚','件'):
            q['spare_quantity']=math.ceil(q['quantity']*spare/100)
            q['purchase_quantity']=q['quantity']+q['spare_quantity']
    assumptions += ['屋面排布使用坡面展开实长；横向1220 mm、沿坡340 mm；上下50 mm及左右20 mm搭接固定。',
                    '厂家坡度条件严格大于12°，无已确认最大坡度，不自动改变建筑坡度。',
                    '发电瓦保持完整，非发电整配瓦/半配瓦允许按斜边及洞口裁切；本版不输出四分之一配瓦。',
                    '容量按实际发电片数×70÷1000 kWp；配瓦和备用瓦均不计入。',
                    '配瓦数量为原片占位估算；细窄片、固定点和裁切余料复用需结合安装节点复核。',
                    '扣件外形沿用已确认模型，孔位/扣件具体尺寸为照片比例示意；收口构造依据安装说明书。']
    if not edges:assumptions.append('收口边尚未输入，配件清单不完整。')
    return dict(project_name=project.get('project_name','Pro光伏瓦屋面排布'),units='m',
                geometry_source=project.get('geometry_source'),lateral_pitch_m=LATERAL,course_pitch_m=PITCH,power_w=POWER_W,
                faces=faces,edges=edges,fittings=fittings,context=project.get('context',{}),quantities=quantities,
                summary=dict(pv_count=pv,companion_count=full+half,companion_full_count=full,companion_half_count=half,
                             capacity_kwp=round(pv*POWER_W/1000,6),j_clip_count=pv*4,roof_area_m2=sum(f['area_m2'] for f in faces),spare_pct=spare),
                assumptions=list(dict.fromkeys(assumptions)))
