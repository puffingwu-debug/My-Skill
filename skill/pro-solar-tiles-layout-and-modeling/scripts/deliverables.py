"""Create traceable vector drawings, quantities and a portable Chinese report."""
import base64
import csv
import html
import json
import math
from pathlib import Path
import ezdxf
from layout_engine import world

ESC = html.escape


def svg_drawing(layout, face=None):
    faces = [face] if face else layout['faces']
    def xy(f, p):
        q = p if face else world(f, p)
        return q[0], -q[1]
    coords = [xy(f, p) for f in faces for p in f['boundary']]
    x0, x1 = min(p[0] for p in coords), max(p[0] for p in coords)
    y0, y1 = min(p[1] for p in coords), max(p[1] for p in coords)
    w, h = x1-x0, y1-y0
    scale = 950/max(w, h, .1)
    margin = 100
    def pts(f, ps):
        return ' '.join(f'{margin+(xy(f,p)[0]-x0)*scale:.3f},{margin+(xy(f,p)[1]-y0)*scale:.3f}' for p in ps)
    width, height = w*scale+2*margin, h*scale+2*margin
    content = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" role="img" aria-label="屋面排布图">',
               '<rect width="100%" height="100%" fill="#ffffff"/>',
               '<style>text{font-family:"PingFang SC","Microsoft YaHei",sans-serif;fill:#263238} .tile{stroke:#fff;stroke-width:.65}</style>',
               f'<text x="30" y="35" font-size="22" font-weight="600">{ESC(face["name"] if face else "屋面总平面排布 · 真北朝上")}</text>',
               '<text x="30" y="61" font-size="13">灰黑：70 W 发电瓦　浅灰：整配瓦　浅橙：半配瓦　蓝灰：障碍物　单位 m</text>']
    for i, f in enumerate(faces):
        boundary_pts = pts(f, f['boundary'])
        content.append(f'<polygon points="{boundary_pts}" fill="#e6e8e8" stroke="#737b80" stroke-width="2"/>')
        # Rendering whole footprints from eave upward preserves visible overlapping rows.
        for t in sorted(f['tiles'], key=lambda q: (q['row'], q['col'])):
            color = '#303638' if t['kind'] == 'pv' else '#e4bb93' if t.get('stock_type') == 'half' else '#a5aaac'
            for part in t['parts']:
                loops = [part['outer']]+part['holes']
                d = ' '.join('M' + ' L'.join(pts(f, [p]) for p in loop)+' Z' for loop in loops)
                content.append(f'<path class="tile" d="{d}" fill="{color}" fill-rule="evenodd"><title>{ESC(t["id"])} · {"70 W 整发电瓦" if t["kind"] == "pv" else "可裁切半配瓦" if t.get("stock_type") == "half" else "可裁切整配瓦"}</title></path>')
        for hole in f.get('holes', []):
            content.append(f'<polygon points="{pts(f,hole)}" fill="#fff" stroke="#54676b" stroke-width="1"/>')
        for o in f.get('obstacles', []):
            content.append(f'<polygon points="{pts(f,o["polygon"])}" fill="#678591" stroke="#303638" stroke-width="5"/>')
        content.append(f'<polygon points="{boundary_pts}" fill="none" stroke="#333b40" stroke-width="1.8"/>')
        if face:
            for a, b in zip(f['boundary'], f['boundary'][1:] + f['boundary'][:1]):
                length = math.dist(a, b)
                mx, my = xy(f, ((a[0]+b[0])/2, (a[1]+b[1])/2))
                tx, ty = margin+(mx-x0)*scale, margin+(my-y0)*scale
                content.append(f'<text x="{tx:.2f}" y="{ty-10:.2f}" text-anchor="middle" font-size="13" stroke="white" stroke-width="4" paint-order="stroke">{length:.3f} m</text>')
        cx = sum(p[0] for p in f['boundary'])/len(f['boundary'])
        cy = sum(p[1] for p in f['boundary'])/len(f['boundary'])
        px, py = xy(f, (cx, cy))
        px, py = margin+(px-x0)*scale, margin+(py-y0)*scale
        label = f'{f["id"]} · {f["pv_count"]}片 · {f["capacity_kwp"]:.2f} kWp'
        content.append(f'<rect x="{px-106:.1f}" y="{py-15:.1f}" width="212" height="30" rx="6" fill="white" fill-opacity=".9"/>')
        content.append(f'<text x="{px:.1f}" y="{py+5:.1f}" text-anchor="middle" font-size="14">{ESC(label)}</text>')
    if not face:
        for edge in layout.get('edges', []):
            a,b = edge['start'],edge['end']
            ax,ay = margin+(a[0]-x0)*scale, margin+(-a[1]-y0)*scale
            bx,by = margin+(b[0]-x0)*scale, margin+(-b[1]-y0)*scale
            label = edge['id'] + (f' / {edge["count"]}片' if edge.get('count') is not None else ' / 待定')
            content.append(f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" stroke="#4d5b63" stroke-width="2" stroke-dasharray="8 4"><title>{ESC(label)}</title></line>')
    caption = f'有效模数1220 × 340 mm · 20 mm侧搭接 | {"坡面展开实长" if face else "水平投影，非斜长"} | {w:.3f} × {h:.3f} m'
    content += [f'<text x="30" y="{height-24:.1f}" font-size="14">{caption}</text>', '</svg>']
    return '\n'.join(content)


def write_dxf(layout, target, face=None):
    doc = ezdxf.new('R2013')
    doc.units = 6  # metres
    doc.header['$MEASUREMENT'] = 1
    msp = doc.modelspace()
    for name, color in [('ROOF', 7), ('PV', 5), ('COMPANION_FULL', 8), ('COMPANION_HALF', 30), ('OPENING', 4), ('TEXT', 7), ('EDGE', 2)]:
        doc.layers.new(name, dxfattribs={'color': color})
    for f in [face] if face else layout['faces']:
        transform = (lambda p:p) if face else (lambda p:world(f,p)[:2])
        msp.add_lwpolyline([transform(p) for p in f['boundary']], close=True, dxfattribs={'layer':'ROOF'})
        for t in f['tiles']:
            for part in t['parts']:
                for ring in [part['outer']]+part['holes']:
                    msp.add_lwpolyline([transform(p) for p in ring], close=True, dxfattribs={'layer': 'PV' if t['kind']=='pv' else 'COMPANION_HALF' if t.get('stock_type')=='half' else 'COMPANION_FULL'})
        for hole in f.get('holes', []):
            msp.add_lwpolyline([transform(p) for p in hole], close=True, dxfattribs={'layer':'OPENING'})
        p = transform(f['boundary'][0])
        msp.add_text(f'{f["id"]}: {f["pv_count"]} PV / {f["capacity_kwp"]:.2f} kWp', dxfattribs={'height':.16,'layer':'TEXT','insert':(p[0],p[1]-.3)})
    if not face:
        for e in layout.get('edges', []):
            msp.add_line(e['start'][:2], e['end'][:2], dxfattribs={'layer':'EDGE'})
    msp.add_text('PRO 70W | REAL SLOPE LENGTHS' if face else 'PRO 70W | HORIZONTAL PROJECTION', dxfattribs={'height':.16,'layer':'TEXT','insert':(0,-.7)})
    if face:
        for a,b in zip(face['boundary'],face['boundary'][1:]+face['boundary'][:1]):
            msp.add_text(f'{math.dist(a,b):.3f} m', dxfattribs={'height':.10,'layer':'TEXT','insert':((a[0]+b[0])/2,(a[1]+b[1])/2+.06)})
    doc.saveas(target)


def _validate_counts(layout):
    total = 0
    for f in layout['faces']:
        count = sum(t['kind'] == 'pv' for t in f['tiles'])
        if count != f['pv_count'] or not math.isclose(count * .07, f['capacity_kwp'], abs_tol=1e-8):
            raise ValueError(f"{f['id']}: 排布瓦片与70 W容量统计不一致")
        companions = [t for t in f['tiles'] if t['kind'] == 'companion']
        if len(companions) != f['companion_count']:
            raise ValueError(f"{f['id']}: 配瓦图形与统计不一致")
        for stock in ('full', 'half'):
            key = 'companion_' + stock + '_count'
            if key in f and f[key] != sum(t.get('stock_type') == stock for t in companions):
                raise ValueError(f"{f['id']}: 整/半配瓦统计不一致")
        total += count
    if sum(f['companion_count'] for f in layout['faces']) != layout['summary']['companion_count']:
        raise ValueError('项目配瓦总数与逐坡统计不一致')
    if total != layout['summary']['pv_count'] or not math.isclose(total * .07, layout['summary']['capacity_kwp'], abs_tol=1e-8):
        raise ValueError('项目装机容量必须等于完整发电瓦片数 × 0.07 kWp')


def drawings(layout, output):
    _validate_counts(layout)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output/'屋面总平面排布.svg').write_text(svg_drawing(layout), encoding='utf-8')
    write_dxf(layout, output/'屋面总平面排布.dxf')
    for i, f in enumerate(layout['faces'], 1):
        (output/f'坡面{i:02d}展开排布.svg').write_text(svg_drawing(layout, f), encoding='utf-8')
        write_dxf(layout, output/f'坡面{i:02d}展开排布.dxf', f)
    with (output/'功能瓦数量表.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['项目','方案数量','单位','另加备料','含备料采购数量','依据'])
        for q in layout['quantities']:
            writer.writerow([q['name'], q['quantity'], q['unit'], q.get('spare_quantity',''), q.get('purchase_quantity',''), q['basis']])
    with (output/'分坡容量表.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['坡面','朝向(真北0°顺时针)','坡度°','真实屋面面积m²','完整70W发电瓦片','非发电整配瓦原片','非发电半配瓦原片','容量kWp'])
        for f in layout['faces']:
            writer.writerow([f['name'],f['azimuth_deg'],f['tilt_deg'],round(f['area_m2'],3),f['pv_count'],f.get('companion_full_count',sum(t['kind']=='companion' and t.get('stock_type')=='full' for t in f['tiles'])),f.get('companion_half_count',sum(t['kind']=='companion' and t.get('stock_type')=='half' for t in f['tiles'])),f['capacity_kwp']])


def report(project, layout, energy, output, assets):
    _validate_counts(layout)
    output, assets = Path(output), Path(assets)
    def image_file(path, alt):
        if not path.exists(): return ''
        data = base64.b64encode(path.read_bytes()).decode()
        return f'<img alt="{ESC(alt)}" src="data:image/png;base64,{data}">'
    svg = svg_drawing(layout)
    rows = ''.join(f'<tr><td>{ESC(q["name"])}</td><td>{q["quantity"]} {q["unit"]}</td><td>{q.get("purchase_quantity","—")}</td><td>{ESC(q["basis"])}</td></tr>' for q in layout['quantities'])
    roof_rows = ''.join(f'<tr><td>{ESC(f["name"])}</td><td>{f["tilt_deg"]:.2f}° / {f["azimuth_deg"]:g}°</td><td>{f["pv_count"]}</td><td>{f["capacity_kwp"]:.2f}</td></tr>' for f in layout['faces'])
    basis = list(layout['assumptions'])
    if (output/'Blender核验.json').exists():
        basis += json.loads((output/'Blender核验.json').read_text()).get('assumptions',[])
    assumptions = ''.join(f'<li>{ESC(str(a))}</li>' for a in dict.fromkeys(basis))
    links = [('屋面总平面排布.dxf','CAD 总平面'),('屋面总平面排布.svg','矢量总平面'),('功能瓦数量表.csv','功能瓦数量表'),('分坡容量表.csv','分坡容量表'),('屋面模型.blend','Blender 模型'),('屋面效果图.png','效果图 PNG'),('屋面俯视图.png','俯视图 PNG'),('project.json','项目输入'),('layout.json','排布数据'),('energy.json','发电量依据')]
    links += [(f'坡面{i:02d}展开排布.{ext}', f'坡面{i:02d} {label}展开图') for i in range(1,len(layout['faces'])+1) for ext,label in [('dxf','CAD '),('svg','矢量')]]
    links += [('屋面模型.glb','通用 GLB 模型'),('建筑示意图.png','建筑整体示意图')]
    links_html = ''.join(f'<a href="{ESC(filename)}" download>{ESC(label)} ↗</a>' for filename,label in links if (output/filename).exists())
    data = json.dumps(energy, ensure_ascii=False).replace('<', '\\u003c')
    title = ESC(layout['project_name'])
    summary = layout['summary']
    content = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>[hidden]{display:none!important}*{box-sizing:border-box}body{margin:0;color:#263238;background:#f4f6f7;font-family:Inter,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.6}header{height:90px;background:white;padding:14px 4vw;display:flex;align-items:center;gap:24px;border-bottom:1px solid #dfe5e8}.brand{width:215px;height:65px;overflow:hidden}.brand img{width:100%;height:100%;object-fit:contain;object-position:center}.tag{padding:5px 12px;background:#fff0e5;color:#c85319;border-radius:5px;font-size:16px}main{max-width:1480px;margin:auto;padding:32px 4vw}h1{font-size:30px;letter-spacing:-.5px;margin:8px 0}h2{font-size:22px;margin:0 0 14px}.eyebrow{font-size:12px;letter-spacing:2px;color:#ba4b19}.muted{color:#6f7c83}nav{display:flex;gap:8px;margin:25px 0;flex-wrap:wrap}button{padding:12px 20px;border:1px solid #dce2e5;border-radius:8px;background:#fff;color:#344047;cursor:pointer;font-size:15px}button.active{background:#fff0e5;color:#bd4d19;border-color:#ffdbc1}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:#fff;border:1px solid #dfe5e8;border-radius:12px;padding:22px}.value{font-size:32px;font-weight:600;line-height:1.3}small{font-size:13px;color:#748088}.panel{display:none}.panel.active{display:block}.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(290px,1fr);gap:22px}.drawing{padding:0;overflow:hidden}.drawing svg{width:100%;height:auto;display:block}.render img{width:100%;display:block;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:13px 10px;border-bottom:1px solid #e5e9eb;vertical-align:top}th{font-size:12px;color:#737e83;background:#f5f7f8}ul{padding-left:20px}li{margin:9px 0}.downloads{display:flex;gap:10px;flex-wrap:wrap}.downloads a{padding:9px 14px;border:1px solid #d8e0e3;border-radius:7px;color:#344c58;text-decoration:none;background:white}.note{border-left:3px solid #ed9661;padding:12px 18px;background:#fff8f2;margin:18px 0}.scroll{overflow-x:auto}footer{font-size:12px;color:#7e898f;padding:24px 0}.energy-value{font-size:36px;font-weight:600}#energy-details{white-space:pre-wrap;font-size:13px;color:#55656f}#chart{display:flex;align-items:end;height:220px;gap:8px;padding-top:20px;margin-bottom:32px}.bar{background:#658392;flex:1;position:relative;min-height:2px;border-radius:4px 4px 0 0}.bar span{position:absolute;bottom:-25px;left:0;right:0;text-align:center;font-size:12px}details{margin-top:18px}@media(max-width:800px){header{height:80px}.brand{width:175px}.stats{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}main{padding:24px 16px}.value{font-size:27px}h1{font-size:24px}.card{padding:16px}.drawing{padding:0}}@media print{nav,.downloads{display:none}.panel{display:block!important;break-inside:avoid;margin:25px 0}main{padding:10px}.stats{grid-template-columns:repeat(4,1fr)}body{background:white}.grid{display:block}.card{margin-bottom:12px}}</style>
<header><div class="brand">__LOGO__</div><span class="tag">Pro 光伏瓦</span><span class="muted">屋面排布方案</span></header>
<main><div class="eyebrow">ROOF LAYOUT · BIAC14B-70</div><h1>__TITLE__</h1><p class="muted">__SOURCE__</p>
<div class="stats"><div class="card"><small>装机容量</small><div class="value">__KW__ <small>kWp</small></div></div><div class="card"><small>完整发电瓦</small><div class="value">__PV__ <small>片</small></div></div><div class="card"><small>非发电配瓦原片估算</small><div class="value">__COMP__ <small>片</small></div><small>整配 __COMP_FULL__ · 半配 __COMP_HALF__</small></div><div class="card"><small>排布有效模数</small><div class="value">1220 × 340 <small>mm</small></div></div></div>
<nav><button class="active" data-tab="plan">屋面排布</button><button data-tab="render">3D 效果</button><button data-tab="quantities">工程清单</button><button data-tab="energy">发电量估算</button><button data-tab="basis">依据与下载</button></nav>
<section class="panel active" id="plan"><div class="grid"><div class="card drawing">__SVG__</div><div class="card"><h2>分坡排布</h2><table><tr><th>坡面</th><th>坡度 / 朝向</th><th>发电瓦</th><th>kWp</th></tr>__FACES__</table><p class="muted">方位角以真北为0°，顺时针计。总平面显示水平投影；各坡面CAD展开图保留沿坡实长。</p><div class="note">__PV__ × 70 W ÷ 1000 = <strong>__KW__ kWp</strong><br>发电瓦不可裁切；整配瓦与半配瓦可裁切且不计入发电容量。</div></div></div></section>
<section class="panel" id="render"><div class="card render"><h2>屋面效果图</h2>__RENDER__<p class="muted">根据同一份排布数据生成，瓦片数量与容量表一致。屋面节点按方案级结构表现。</p><details><summary>查看俯视效果图</summary>__TOP__</details></div></section>
<section class="panel" id="quantities"><div class="card"><h2>功能瓦与配件数量</h2><div class="scroll"><table><tr><th>产品 / 功能</th><th>方案数量</th><th>含备料数量</th><th>计算依据</th></tr>__ROWS__</table></div><p class="muted">备料比例 __SPARE__%；与装机片数分开统计。配瓦按排布所需原片统计，未将裁切余料跨片复用；灰色/浅橙边缘为裁切配瓦示意，图纸不是加工下料图。</p></div></section>
<section class="panel" id="energy"><div class="card"><h2>预测发电量 · 方案级</h2><div class="energy-value" id="annual">待计算</div><p id="energy-method" class="muted"></p><div id="chart"></div>__ENERGY_TABLE__<div id="energy-details">__ENERGY_TEXT__</div><details><summary>查看完整计算依据</summary><pre id="energy-json" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details></div></section>
<section class="panel" id="basis"><div class="card"><h2>项目条件与数据依据</h2><ul>__ASSUMPTIONS__</ul><h2>下载成果</h2><div class="downloads">__LINKS__</div></div></section>
<footer>Pro 光伏瓦屋面排布 · 70 W/片 · 不包含并网条件设计及储能配置</footer></main>
<script>const energy=__ENERGY__;document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-tab],.panel').forEach(e=>e.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active')}));document.getElementById('energy-json').textContent=JSON.stringify(energy,null,2);
const totals=energy.totals||{},annual=totals.annual_kwh??energy.annual_kwh;document.getElementById('annual').textContent=typeof annual==='number'?annual.toLocaleString('zh-CN',{maximumFractionDigits:2})+' kWh / 年':'暂无可用的全年估算';document.getElementById('energy-method').textContent=({complete:'计算完成',partial:'部分坡面未完成',failed:'计算未完成',no_pv:'无发电瓦',not_requested:'未设估算条件'}[energy.status]||'未计算')+' · '+({pvgis:'基于PVGIS气象数据的方案估算',specific_yield:'基于基准年比发电量和88%系统效率的方案估算',none:'暂不计算'}[energy.method]||'');const monthly=totals.monthly_kwh||energy.monthly_kwh;if(Array.isArray(monthly)&&monthly.length===12){let nums=monthly.map(x=>typeof x==='number'?x:(x.energy_kwh??x.kwh??0)),max=Math.max(...nums,1);nums.forEach((v,i)=>{const b=document.createElement('div');b.className='bar';b.style.height=(v/max*190)+'px';b.title=(i+1)+'月：'+Math.round(v)+' kWh';const s=document.createElement('span');s.textContent=(i+1)+'月';b.append(s);document.getElementById('chart').append(b)})}else document.getElementById('chart').hidden=true;
</script></html>'''
    energy_notes = []
    if project.get('location'):
        loc = project['location']
        energy_notes.append(f"地点：{loc.get('label','')}（{loc.get('latitude','')}，{loc.get('longitude','')}）")
    settings = energy.get('assumptions', {})
    if isinstance(settings, dict):
        if settings.get('system_loss_applied'):
            energy_notes.append(f"系统效率：{settings['system_efficiency']:.0%}；未扣系统综合损耗的基准发电量 × {settings['system_efficiency']:g}，仅折算一次。")
        energy_notes.append(f"额外遮挡损耗：{settings.get('additional_shading_loss_pct',0):g}%；未代替现场遮挡调查。")
    if energy.get('method') == 'specific_yield':
        energy_notes.append(f"未扣系统损耗的年比发电量：{project.get('energy',{}).get('annual_specific_yield_kwh_kwp','—')} kWh/kWp；依据：{project.get('energy',{}).get('source','未提供')}")
    for f in energy.get('faces', []):
        if f.get('baseline_annual_kwh') is not None and f.get('annual_kwh') is not None:
            energy_notes.append(f"{f.get('name',f['id'])}：基准年发电量 {f['baseline_annual_kwh']:.2f} kWh，按0.88及已列额外遮挡折算后 {f['annual_kwh']:.2f} kWh。")
        meta = f.get('radiation_metadata', {})
        if meta:
            energy_notes.append(f"{f.get('name', f['id'])}气象依据：{meta.get('radiation_db','')}，{meta.get('year_min','')}–{meta.get('year_max','')}。")
    energy_notes += [str(n) for n in energy.get('limitations', [])]
    energy_notes += [e['message'] for e in energy.get('errors', [])]
    energy_text = '<ul>'+''.join('<li>'+ESC(str(n))+'</li>' for n in energy_notes)+'</ul>'
    energy_text += '<p>'+ ' · '.join(f'<a href="{ESC(url)}" target="_blank">PVGIS官方依据{index+1}</a>' for index,url in enumerate(energy.get('sources',[])))+'</p>'
    energy_table = ''
    totals = energy.get('totals') or {}
    if totals.get('monthly_kwh'):
        energy_table = '<table><tr><th>月份</th><th>预测发电量 kWh</th></tr>' + ''.join(f'<tr><td>{m["month"]}月</td><td>{m["energy_kwh"]:.2f}</td></tr>' for m in totals['monthly_kwh']) + '</table>'
        with (output/'月度发电量.csv').open('w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['月份','预测发电量kWh','方法'])
            writer.writerows([[m['month'],m['energy_kwh'],energy['method']] for m in totals['monthly_kwh']])
        links_html += '<a href="月度发电量.csv" download>月度发电量表 ↗</a>'
    replacements = {'TITLE':title,'SOURCE':ESC(str(layout.get('geometry_source') or '输入尺寸来源待确认')),
                    'LOGO':image_file(assets/'logo.png','Almaden'), 'KW':f'{summary["capacity_kwp"]:.2f}',
                    'PV':str(summary['pv_count']), 'COMP':str(summary['companion_count']), 'COMP_FULL':str(summary.get('companion_full_count','—')), 'COMP_HALF':str(summary.get('companion_half_count','—')), 'SPARE':str(summary['spare_pct']),
                    'SVG':svg, 'FACES':roof_rows, 'ROWS':rows, 'ASSUMPTIONS':assumptions, 'LINKS':links_html,
                    'RENDER':image_file(output/'屋面效果图.png','屋面效果图') or '<p>此轮尚未生成渲染图。</p>',
                    'TOP':image_file(output/'屋面俯视图.png','屋面俯视图'), 'ENERGY':data, 'ENERGY_TEXT':energy_text, 'ENERGY_TABLE':energy_table}
    for key, value in replacements.items(): content = content.replace('__'+key+'__', value)
    (output/'屋面排布报告.html').write_text(content, encoding='utf-8')
