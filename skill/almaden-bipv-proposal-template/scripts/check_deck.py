#!/usr/bin/env python3
"""
check_deck.py — 生成后的自动体检（不依赖渲染器，可在无图形环境运行）

检查三类问题：
  A. 结构：ZIP / XML 完整性、媒体与关系是否齐全、视频是否真的嵌入（而非外链）
  B. 版式：用真实字体度量估算每段文字的实际高度，找出
       · 溢出幻灯片底部页脚区
       · 压到下方图形（表格、卡片）
       · 超出所属卡片底边
  C. 内容：必填文案是否存在、是否残留占位符（TBD / XXX / 待填 / {{ }}）

用法：
    python check_deck.py 建议书.pptx
    python check_deck.py 建议书.pptx --contains "42.64" --contains "年发电量" --json report.json
出口码：0 = 无问题；1 = 有问题（便于串到流水线里）。
"""

import argparse
import json
import pathlib
import re
import sys
import zipfile

from pptx import Presentation
from pptx.util import Emu
from PIL import ImageFont

EMU = 914400
SLIDE_W_IN, SLIDE_H_IN = 13.3333, 7.5
FOOT_LIMIT = int(6.88 * EMU)          # 正文不得越过此线
FOOTER_SKIP = int(6.9 * EMU)          # 页脚自身文本的起始位置

# 用于估算中文宽度的系统字体（任一 CJK 字体均可，中文均为全角等宽）
FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]
PLACEHOLDERS = re.compile(r"\{\{|\}\}|TBD|XXX+|待补充|待填写|Lorem ipsum|TODO", re.I)

_fc = {}


def _font(sz, bold):
    key = (round(sz), bold)
    if key not in _fc:
        f = None
        for path in FONT_CANDIDATES:
            try:
                f = ImageFont.truetype(path, max(1, round(sz * 4)),
                                       index=1 if bold else 0)
                break
            except Exception:
                continue
        _fc[key] = f or ImageFont.load_default()
    return _fc[key]


def _char_w(ch, sz, bold):
    """CJK / 全角字符按 1 em 计；西文用真实字体度量。"""
    if ord(ch) > 0x2E80:
        return sz
    f = _font(sz, bold)
    try:
        return f.getlength(ch) / 4.0
    except Exception:
        return sz * 0.52


def _lines(text, width_pt, sz, bold):
    if not text:
        return 1
    n, cur = 1, 0.0
    for ch in text:
        w = _char_w(ch, sz, bold)
        if cur + w > width_pt + 0.01:
            n += 1; cur = w
        else:
            cur += w
    return n


def _text_height(tf, box_w_emu):
    """估算文本框渲染后的实际高度（EMU）。"""
    bw = (box_w_emu - tf.margin_left - tf.margin_right) / EMU * 72
    total = 0.0
    for p in tf.paragraphs:
        if not p.runs:
            continue
        sz = max([(r.font.size.pt if r.font.size else 18) for r in p.runs])
        bold = any(r.font.bold for r in p.runs)
        txt = "".join(r.text for r in p.runs)
        ls = p.line_spacing if isinstance(p.line_spacing, (int, float)) else 1.2
        total += _lines(txt, bw, sz, bold) * sz * ls
        total += (p.space_before.pt if p.space_before else 0)
        total += (p.space_after.pt if p.space_after else 0)
    return int(total / 72 * EMU)


def check_structure(path, report):
    z = zipfile.ZipFile(path)
    bad = z.testzip()
    report["zip_ok"] = bad is None
    if bad:
        report["errors"].append(f"ZIP 损坏：{bad}")
    names = z.namelist()
    media = [n for n in names if n.startswith("ppt/media/")]
    vids = [n for n in media if n.endswith((".mp4", ".m4v", ".mov"))]
    report["media_parts"] = len(media)
    report["media_types"] = sorted({n.rsplit(".", 1)[-1].lower() for n in media})
    report["videos"] = [{"part": v, "mb": round(z.getinfo(v).file_size / 1e6, 2)}
                        for v in vids]

    # 视频必须内嵌：slide rels 里出现 External 才算外链
    external = []
    for n in names:
        if n.endswith(".rels"):
            x = z.read(n).decode("utf-8", "ignore")
            for m in re.finditer(r'Target="([^"]+)"[^>]*TargetMode="External"', x):
                external.append({"rels": n, "target": m.group(1)[:120]})
    report["external_links"] = external

    slides = [n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)]
    report["slide_parts"] = len(slides)
    ct = z.read("[Content_Types].xml").decode("utf-8", "ignore")
    if vids and "mp4" not in ct:
        report["errors"].append("存在 mp4 媒体，但 [Content_Types].xml 未声明 mp4")
    return z


def check_layout(prs, report):
    issues = []
    for si, sl in enumerate(prs.slides, 1):
        solids, texts = [], []
        shapes = list(sl.shapes)
        has_media = any(sh.shape_type is not None and "MEDIA" in str(sh.shape_type)
                        for sh in shapes)
        for pos, sh in enumerate(shapes):
            try:
                l, t, w, h = sh.left, sh.top, sh.width, sh.height
            except Exception:
                continue
            if None in (l, t, w, h):
                continue
            # 越界检测（允许整页背景）
            if l < -Emu(10000) or t < -Emu(10000) or \
               l + w > int(SLIDE_W_IN * EMU) + Emu(20000) or \
               t + h > int(SLIDE_H_IN * EMU) + Emu(20000):
                full_bleed = (l <= 0 and t <= 0 and w >= int(SLIDE_W_IN * EMU) - Emu(5000)
                              and h >= int(SLIDE_H_IN * EMU) - Emu(5000))
                if not full_bleed:
                    issues.append({"slide": si, "kind": "OUT-OF-SLIDE",
                                   "detail": f"({l/EMU:.2f},{t/EMU:.2f}) "
                                             f"{w/EMU:.2f}x{h/EMU:.2f}",
                                   "text": ""})
            if sh.has_text_frame and sh.text_frame.text.strip():
                eh = _text_height(sh.text_frame, w)
                texts.append((l, t, w, eh, pos,
                              sh.text_frame.text[:38].replace("\n", "/")))
            else:
                full_bleed = (l <= 0 and t <= 0 and w >= int(SLIDE_W_IN * EMU) - Emu(5000)
                              and h >= int(SLIDE_H_IN * EMU) - Emu(5000))
                if not full_bleed:
                    solids.append((l, t, w, h, pos, str(sh.shape_type)[:14]))

        for (l, t, w, eh, pos, tx) in texts:
            if t > FOOTER_SKIP:
                continue
            bottom = t + eh
            if bottom > FOOT_LIMIT + Emu(15000):
                issues.append({"slide": si, "kind": "PAST-FOOTER",
                               "detail": f"文字到 {bottom/EMU:.2f}in（上限 6.88in）",
                               "text": tx})
            for (l2, t2, w2, h2, pos2, stype) in solids:
                if pos2 < pos and t2 + h2 < t:
                    continue
                vov = min(bottom, t2 + h2) - max(t, t2)
                if vov <= Emu(15000):
                    continue
                if l + w <= l2 + Emu(8000) or l >= l2 + w2 - Emu(8000):
                    continue
                if t < t2:
                    issues.append({"slide": si, "kind": "SPILL-INTO",
                                   "detail": f"压到 {stype} +{vov/EMU:.2f}in "
                                             f"@y={t2/EMU:.2f}", "text": tx})
                elif t < t2 + h2 < bottom:
                    issues.append({"slide": si, "kind": "OVERFLOW-CARD",
                                   "detail": f"超出卡片 {(bottom-(t2+h2))/EMU:.2f}in "
                                             f"@y={(t2+h2)/EMU:.2f}", "text": tx})
        if has_media:
            report["video_slides"].append(si)
    report["layout_issues"] = issues


def check_content(prs, report, required):
    texts, placeholders = [], []
    for si, sl in enumerate(prs.slides, 1):
        for sh in sl.shapes:
            if sh.has_text_frame:
                t = sh.text_frame.text
                if t.strip():
                    texts.append((si, t))
                    if PLACEHOLDERS.search(t):
                        placeholders.append({"slide": si, "text": t[:60]})
            if sh.has_table:
                for r in sh.table.rows:
                    for c in r.cells:
                        if c.text.strip():
                            texts.append((si, c.text))
                            if PLACEHOLDERS.search(c.text):
                                placeholders.append({"slide": si, "text": c.text[:60]})
    blob = "\n".join(t for _, t in texts)
    report["char_count"] = len(blob)
    report["placeholders"] = placeholders
    report["missing_required"] = [s for s in required if s not in blob]
    report["slide_count"] = len(prs.slides._sldIdLst)


def main():
    ap = argparse.ArgumentParser(description="PPTX 结构与版式体检")
    ap.add_argument("pptx")
    ap.add_argument("--contains", action="append", default=[],
                    help="必须出现的文案，可重复")
    ap.add_argument("--json", help="把结果写入 JSON")
    ap.add_argument("--expect-slides", type=int, help="期望页数")
    a = ap.parse_args()

    path = pathlib.Path(a.pptx)
    if not path.is_file():
        print(f"找不到文件：{path}", file=sys.stderr)
        return 2
    report = {"file": str(path), "errors": [], "warnings": [],
              "video_slides": [], "external_links": []}
    check_structure(path, report)
    prs = Presentation(str(path))
    report["slide_size_in"] = [round(prs.slide_width / EMU, 4),
                               round(prs.slide_height / EMU, 4)]
    check_layout(prs, report)
    check_content(prs, report, a.contains)

    w_ok = abs(report["slide_size_in"][0] - SLIDE_W_IN) < 0.01 and \
        abs(report["slide_size_in"][1] - SLIDE_H_IN) < 0.01
    report["size_ok"] = w_ok
    if not w_ok:
        report["errors"].append(f'画布不是 16:9 标准尺寸：{report["slide_size_in"]}')
    if a.expect_slides and report["slide_count"] != a.expect_slides:
        report["errors"].append(
            f'页数不符：期望 {a.expect_slides}，实际 {report["slide_count"]}')
    if report["missing_required"]:
        report["errors"].append(f'缺少必需文案：{report["missing_required"]}')
    if report["placeholders"]:
        report["errors"].append(f'残留占位符 {len(report["placeholders"])} 处')
    if report["layout_issues"]:
        report["errors"].append(f'版式问题 {len(report["layout_issues"])} 处')

    print(f'文件      : {path.name}  ({path.stat().st_size/1e6:.2f} MB)')
    print(f'画布      : {report["slide_size_in"][0]} x {report["slide_size_in"][1]} in'
          f'  {"OK" if w_ok else "✗ 非 16:9"}')
    print(f'页数      : {report["slide_count"]}')
    print(f'媒体      : {report["media_parts"]} 个 {report["media_types"]}')
    if report["videos"]:
        for v in report["videos"]:
            print(f'  视频    : {v["part"]}  {v["mb"]} MB  内嵌于第 '
                  f'{report["video_slides"]} 页')
    print(f'ZIP 完整性: {"OK" if report["zip_ok"] else "✗ 损坏"}')
    print(f'外链      : {len(report["external_links"])} 个'
          f'{"（视频为内嵌，换机可播）" if not report["external_links"] else ""}')
    print(f'版式问题  : {len(report["layout_issues"])}')
    for i in report["layout_issues"][:15]:
        print(f'  p{i["slide"]:02d} {i["kind"]:15s} {i["detail"]:34s} | {i["text"]}')
    print(f'占位符残留: {len(report["placeholders"])}')
    for p in report["placeholders"][:8]:
        print(f'  p{p["slide"]:02d} | {p["text"]}')
    if a.contains:
        print(f'必需文案  : {"全部命中" if not report["missing_required"] else "缺 " + str(report["missing_required"])}')

    if a.json:
        pathlib.Path(a.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f'报告已写入: {a.json}')
    print("\n结论：" + ("通过" if not report["errors"] else "需修正 → " +
                       "; ".join(report["errors"])))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
