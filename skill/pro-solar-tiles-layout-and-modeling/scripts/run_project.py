#!/usr/bin/env python3
"""Run layout -> quantities/drawings -> energy -> optional Blender -> HTML."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from layout_engine import calculate
from deliverables import drawings, report


def verify_render(output, layout):
    required = ['屋面模型.blend','屋面模型.glb','屋面效果图.png','屋面俯视图.png','Blender核验.json']
    if not all((output/name).is_file() and (output/name).stat().st_size for name in required):
        return False
    audit = json.loads((output/'Blender核验.json').read_text(encoding='utf-8'))
    counts, summary = audit.get('counts', {}), layout['summary']
    return (audit.get('saved_file_reopen') == 'passed' and audit.get('finite_geometry') is True
            and audit.get('glb_exported') is True
            and counts.get('pv_count') == summary['pv_count']
            and counts.get('companion_count') == summary['companion_count']
            and counts.get('pv_wind_clip_count') == summary['pv_count'] * 4
            and abs(audit.get('capacity_kwp', -1) - summary['capacity_kwp']) < 1e-9)


def main():
    parser = argparse.ArgumentParser(description='Pro光伏瓦屋面排布成果生成')
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--render', action='store_true', help='生成Blender模型与两张PNG')
    parser.add_argument('--blender', default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = Path(args.project).resolve()
    project = json.loads(source.read_text(encoding='utf-8'))
    layout = calculate(project)
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('输出目录非空；为保留已有成果，请使用一个新版本目录')
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('project.json',project),('layout.json',layout)]:
        (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2), encoding='utf-8')
    drawings(layout, output)
    from estimate_energy import estimate
    energy = estimate(project, layout, output)
    (output/'energy.json').write_text(json.dumps(energy,ensure_ascii=False,indent=2), encoding='utf-8')
    render_ok = False
    if args.render:
        blender = args.blender or shutil.which('blender') or '/Applications/Blender.app/Contents/MacOS/Blender'
        with (output/'model-build.log').open('w',encoding='utf-8') as log:
            result = subprocess.run([blender,'--background','--factory-startup','--python-exit-code','1','--python',str(root/'scripts/render_blender.py'),'--',
                                     '--layout',str(output/'layout.json'),'--output',str(output),'--assets',str(root/'assets')],
                                    stdout=log,stderr=subprocess.STDOUT)
        render_ok = result.returncode == 0 and verify_render(output, layout)
    report(project, layout, energy, output, root/'assets')
    manifest = {'layout_summary':layout['summary'],'energy_status':energy.get('status'),
                'model_and_renders_generated':render_ok,'files':[p.name for p in sorted(output.iterdir())]}
    (output/'成果核验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    if args.render and not render_ok:
        raise RuntimeError(f'模型/渲染未完整生成，请检查 {output}/model-build.log；已保留排布图及报告')


if __name__ == '__main__': main()
