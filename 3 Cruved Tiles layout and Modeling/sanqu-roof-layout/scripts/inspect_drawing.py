#!/usr/bin/env python3
"""Read DXF, or read-only export DWG with AutoCAD Core Console, then inspect.

Geometry is reported in drawing coordinates. This tool does not choose roof
boundaries, infer units, repair drawings, or reconstruct a roof automatically.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile

import ezdxf
from ezdxf import path as dxfpath

CORE = Path('/Applications/Autodesk/AutoCAD 2024/AutoCAD 2024.app/Contents/Helpers/AcCoreConsole.app/Contents/MacOS/AcCoreConsole')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def export_dwg(source, output, core, timeout):
    """Keep native files untouched and use a fresh export name to avoid prompts."""
    if not core.is_file():
        raise RuntimeError(f'AutoCAD Core Console not found: {core}')
    run = Path(tempfile.mkdtemp(prefix='cad-export-', dir=output))
    destination = run / 'drawing.dxf'
    lisp_name = str(destination).replace('\\', '\\\\').replace('"', '\\"')
    script = run / 'export.scr'
    script.write_text(
        '(setvar "FILEDIA" 0)\n(setvar "CMDECHO" 1)\n'
        f'(command "_.DXFOUT" "{lisp_name}" "16")\n'
        '(princ "\\nSANQU_EXPORT_DONE\\n")\n(command "_.QUIT")\n', encoding='utf-8')
    before = digest(source)
    process = subprocess.Popen(
        [str(core), '/i', str(source), '/s', str(script), '/readonly'],
        cwd=run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True)
    timed_out = False
    try:
        log, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        log, _ = process.communicate()
    log_path = run / 'core-console.log'
    log_path.write_bytes(log)
    after = digest(source)
    if before != after:
        raise RuntimeError('Source SHA-256 changed during conversion; stop and inspect the source.')
    if timed_out:
        raise RuntimeError(f'Core Console exceeded {timeout}s; process group stopped. Log: {log_path}')
    if process.returncode or not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f'DWG export failed (exit {process.returncode}). Log: {log_path}')
    return destination, {
        'method': 'AutoCAD Core Console /readonly; FILEDIA=0; DXFOUT; precision=16',
        'source_sha256_before': before, 'source_sha256_after': after,
        'source_unchanged': before == after, 'exit_code': process.returncode,
        'log': str(log_path), 'dxf_path': str(destination),
        'dxf_bytes': destination.stat().st_size}


def serial(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    try:
        return [serial(v) for v in value]
    except TypeError:
        return str(value)


def point(value):
    return [float(v) for v in value]


def polygon_area(points):
    return abs(sum(p[0]*points[(i+1) % len(points)][1] - points[(i+1) % len(points)][0]*p[1]
                   for i, p in enumerate(points))) / 2


def inspect(document, chosen, layer_filter):
    texts, polygons, dimensions, paths = [], [], [], []
    counts, omissions = Counter(), Counter()
    warnings = []

    def visit(entity, source_handle=None, chain=(), inherited='0', depth=0):
        kind = entity.dxftype()
        layer = entity.dxf.get('layer', '0')
        if layer == '0':
            layer = inherited
        provenance = {'handle': entity.dxf.get('handle'),
                      'source_handle': source_handle or entity.dxf.get('handle'),
                      'layer': layer, 'block_path': list(chain), 'type': kind}
        if kind == 'INSERT':
            if depth >= 32:
                omissions['INSERT depth limit'] += 1
                return
            try:
                inserts = entity.multi_insert() if entity.mcount > 1 else [entity]
                for insert in inserts:
                    for attribute in insert.attribs:
                        visit(attribute, provenance['source_handle'], chain + (entity.dxf.name,), layer, depth+1)
                    for child in insert.virtual_entities():
                        visit(child, provenance['source_handle'], chain + (entity.dxf.name,), layer, depth+1)
            except Exception as error:
                warnings.append(f"INSERT {provenance['source_handle']}: {error}")
            return
        if layer_filter and layer not in layer_filter:
            return
        counts[kind] += 1
        if kind in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'):
            raw = entity.text if kind == 'MTEXT' else entity.dxf.get('text', '')
            try:
                plain = entity.plain_text()
            except AttributeError:
                plain = raw
            insert = point(entity.dxf.get('insert', (0, 0, 0)))
            height = float(entity.dxf.get('char_height' if kind == 'MTEXT' else 'height', 1))
            texts.append({**provenance, 'raw_text': raw, 'plain_text': plain, 'insert': insert,
                          'height': height, 'rotation': entity.dxf.get('rotation', 0)})
            return
        if kind == 'DIMENSION':
            try:
                measurement = serial(entity.get_measurement())
            except Exception as error:
                measurement = None
                warnings.append(f"DIMENSION {provenance['source_handle']} measurement: {error}")
            dimensions.append({**provenance,
                'text_override': entity.dxf.get('text', '<>'),
                'actual_measurement_stored': entity.dxf.get('actual_measurement'),
                'geometry_measurement_ezdxf': measurement,
                'raw_dxf_attributes': serial(entity.dxfattribs())})
            # Its display block can contain overridden dimension text; preserve it separately.
            try:
                for child in entity.virtual_entities():
                    visit(child, provenance['source_handle'], chain + ('DIMENSION_DISPLAY',), layer, depth+1)
            except Exception as error:
                warnings.append(f"DIMENSION {provenance['source_handle']} display: {error}")
            return
        if kind in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'):
            try:
                curve = dxfpath.make_path(entity)
                vertices = [point(p) for p in curve.flattening(distance=.2, segments=8)]
                if len(vertices) < 2:
                    return
                closed = bool(curve.is_closed)
                record = {**provenance, 'vertices': vertices, 'closed': closed}
                paths.append(record)
                if closed:
                    polygons.append({**record, 'area_drawing_units_squared': polygon_area(vertices),
                                     'raw_polyline_vertices': serial(list(entity.get_points('xyseb'))) if kind == 'LWPOLYLINE' else None,
                                     'raw_polyline_format': 'x,y,start_width,end_width,bulge' if kind == 'LWPOLYLINE' else None,
                                     'representation': 'flattened outline; arcs use 0.2 drawing-unit tolerance'})
            except Exception as error:
                warnings.append(f"{kind} {provenance['source_handle']}: {error}")
            return
        # OLE, proxy objects, hatches and 3D entities are counted, not invented as roof outlines.
        omissions[kind] += 1

    for entity in chosen:
        visit(entity)
    return texts, polygons, dimensions, paths, counts, omissions, warnings


def write_svg(path, paths, texts, crop, layer_states, include_hidden):
    def visible(item):
        state = layer_states.get(item['layer'], {})
        return include_hidden or not (state.get('off') or state.get('frozen'))
    paths = [p for p in paths if visible(p)]
    texts = [t for t in texts if visible(t)]
    vertices = [v for p in paths for v in p['vertices']]
    if crop:
        xmin, ymin, xmax, ymax = crop
    elif vertices:
        xmin, ymin = [min(v[i] for v in vertices) for i in (0, 1)]
        xmax, ymax = [max(v[i] for v in vertices) for i in (0, 1)]
    elif texts:
        xmin, ymin = [min(t['insert'][i] for t in texts) for i in (0, 1)]
        xmax, ymax = [max(t['insert'][i] for t in texts) for i in (0, 1)]
    else:
        xmin, ymin, xmax, ymax = 0, 0, 1, 1
    width, height = max(xmax-xmin, 1e-6), max(ymax-ymin, 1e-6)
    factor = min(1560/width, 1160/height)
    sx, sy = width*factor+40, height*factor+40
    def xy(v):
        return ((v[0]-xmin)*factor+20, (ymax-v[1])*factor+20)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{sx:.1f}" height="{sy:.1f}" viewBox="0 0 {sx:.4f} {sy:.4f}">',
             '<rect width="100%" height="100%" fill="#fff"/>',
             f'<defs><clipPath id="drawing"><rect x="20" y="20" width="{width*factor:.4f}" height="{height*factor:.4f}"/></clipPath></defs>',
             '<g clip-path="url(#drawing)">']
    for record in paths:
        coords = ' '.join(f'{x:.4f},{y:.4f}' for x,y in map(xy,record['vertices']))
        kind = 'polygon' if record['closed'] else 'polyline'
        color = '#246887' if record['closed'] else '#505961'
        parts.append(f'<{kind} points="{coords}" fill="none" stroke="{color}" stroke-width=".65"><title>{html.escape(record["layer"])}</title></{kind}>')
    for text in texts:
        x, y = xy(text['insert'])
        if not (-50 < x < sx+50 and -50 < y < sy+50):
            continue
        # Heights/rotations are approximate; raw and formatted text remain exact in JSON.
        size = max(.25, text['height']*factor)
        rotation = -float(text['rotation'])
        lines = str(text['plain_text']).splitlines() or ['']
        spans = ''.join(f'<tspan x="{x:.4f}" dy="{0 if i==0 else 1.15}em">{html.escape(line)}</tspan>' for i,line in enumerate(lines))
        parts.append(f'<text x="{x:.4f}" y="{y:.4f}" transform="rotate({rotation:.5f} {x:.4f} {y:.4f})" font-family="Arial,PingFang SC,sans-serif" font-size="{size:.5f}" fill="#253b46">{spans}</text>')
    parts.extend(['</g>', '</svg>'])
    path.write_text('\n'.join(parts), encoding='utf-8')
    return [xmin,ymin,xmax,ymax]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('drawing', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--layout', default='Model')
    parser.add_argument('--layers', help='Comma-separated exact DXF layer names')
    parser.add_argument('--bbox', nargs=4, type=float, metavar=('XMIN','YMIN','XMAX','YMAX'), help='SVG crop in drawing coordinates; JSON remains complete')
    parser.add_argument('--include-hidden', action='store_true', help='Include off/frozen layers in SVG; JSON always includes them')
    parser.add_argument('--core-console', type=Path, default=CORE)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    source = args.drawing.expanduser().resolve()
    output = args.out.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in ('.dwg','.dxf'):
        parser.error('Input must be an existing .dwg or .dxf file.')
    if not 1 <= args.timeout <= 120:
        parser.error('--timeout must be between 1 and 120 seconds.')
    if args.bbox and (args.bbox[0] >= args.bbox[2] or args.bbox[1] >= args.bbox[3]):
        parser.error('--bbox requires XMIN<XMAX and YMIN<YMAX.')
    output.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == '.dwg':
        dxf, conversion = export_dwg(source, output, args.core_console.expanduser().resolve(), args.timeout)
    else:
        dxf, conversion = source, {'method':'direct DXF read', 'source_sha256':digest(source)}
    document = ezdxf.readfile(dxf)
    if args.layout not in document.layout_names():
        parser.error(f'Unknown layout {args.layout!r}; available: {document.layout_names()}')
    chosen = document.layouts.get(args.layout)
    layer_filter = set(args.layers.split(',')) if args.layers else None
    texts, polygons, dimensions, paths, counts, omissions, warnings = inspect(document, chosen, layer_filter)
    layers = [{'name':l.dxf.name, 'color':l.dxf.color, 'linetype':l.dxf.linetype,
               'off':l.is_off(), 'frozen':l.is_frozen(), 'locked':l.is_locked()} for l in document.layers]
    bounds = write_svg(output/'overview.svg', paths, texts, args.bbox,
                       {l['name']:l for l in layers}, args.include_hidden)
    summary = {'source':str(source), 'conversion':conversion, 'dxf_version':document.dxfversion,
        'units':{'INSUNITS':document.units, 'note':'0 means unspecified; do not assume millimetres. All coordinates remain in drawing units.'},
        'available_layouts':document.layout_names(), 'selected_layout':args.layout,
        'top_level_entity_counts':dict(Counter(e.dxftype() for e in chosen)),
        'expanded_entity_counts':dict(counts), 'layer_count':len(layers), 'text_count':len(texts),
        'closed_outline_count':len(polygons), 'dimension_count':len(dimensions),
        'preview_bounds':bounds, 'preview_omissions':dict(omissions), 'warnings':warnings,
        'limits':['Closed outlines are candidates, not identified roof planes.',
                  'Block inserts are expanded; proxy/OLE/hatch/3D content is counted but not reconstructed.',
                  'SVG is an identification aid, not a faithful CAD plot. Text font/alignment and curves are approximate.',
                  'Dimension stored measurement, calculated measurement and text override may disagree; all are retained.',
                  'No source drawing is edited or saved. DWG exports use read-only mode and verify SHA-256.']}
    for name, data in [('summary',summary),('layers',layers),('texts',texts),('closed-polygons',polygons),('dimensions',dimensions)]:
        (output/f'{name}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'summary':str(output/'summary.json'),'preview':str(output/'overview.svg'),
                      'layers':len(layers),'texts':len(texts),'closed_outlines':len(polygons),
                      'dimensions':len(dimensions),'units_INSUNITS':document.units,
                      'source_unchanged':conversion.get('source_unchanged',True)},ensure_ascii=False))


if __name__ == '__main__':
    main()
