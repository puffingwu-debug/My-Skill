#!/usr/bin/env python3
"""
build_proposal.py — 亚玛顿 BIPV 项目建议书生成器

把一份项目 JSON 渲染成与标准样张同源的 PPTX。

用法：
    python build_proposal.py --project 项目.json --output 成果/建议书.pptx
    python build_proposal.py --project 项目.json --output out.pptx --skeleton   # 生成空模板骨架

JSON 结构见 references/project-schema.md；完整示例见 examples/东江阴变电站.json。
所有图片路径按「相对于 JSON 文件所在目录」解析。

设计约束（勿轻易改动，除非同步更新 references/design-system.md）：
    · 章节内页码由本脚本统一编号，封面不编号。
    · 版式函数全部来自 deck_kit，本文件只负责「把数据摆到正确的位置」。
    · 每种版式都经过高度核算；新增版式后必须跑 check_deck.py。
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from deck_kit import *          # noqa: F401,F403
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


# ============================================================ 工具
#: JSON 里可用颜色名（字符串）代替 RGBColor，便于手写 spec
COLORS = {
    "INK": INK, "INK_SOFT": INK_SOFT, "ORANGE": ORANGE, "ORANGE_DK": ORANGE_DK,
    "ORANGE_LT": ORANGE_LT, "ORANGE_BD": ORANGE_BD, "GRAY": GRAY, "GRAY_LT": GRAY_LT,
    "LINE": LINE, "LINE_DK": LINE_DK, "BG_SOFT": BG_SOFT, "BG_CARD": BG_CARD,
    "WHITE": WHITE, "DARK_BG": DARK_BG, "DARK_CARD": DARK_CARD,
}


def col(v, default=None):
    """把 'ORANGE' 这类颜色名解析成 RGBColor；已是 RGBColor 则原样返回。"""
    if v is None:
        return default
    if isinstance(v, RGBColor):
        return v
    key = str(v).strip().upper()
    if key not in COLORS:
        raise ValueError(f'未知颜色名 "{v}"，可用：{sorted(COLORS)}')
    return COLORS[key]


class Ctx:
    """一次生成过程的上下文：页码、图片根目录、样张文案。"""

    def __init__(self, spec, base):
        self.spec = spec
        self.base = pathlib.Path(base)
        self.meta = spec.get("meta", {})
        self.page = 0
        self.label = self.meta.get("footer_label") or \
            f'{self.meta.get("project_name", "")} · BIPV 项目建议书'

    def img(self, rel):
        if not rel:
            return None
        p = self.base / rel
        if not p.exists():
            raise FileNotFoundError(f"图片不存在：{rel}（解析为 {p}）")
        return str(p)

    def num(self):
        self.page += 1
        return self.page

    def t(self, key, default=""):
        return self.meta.get(key, default)


def _rows(tbl):
    """把 {"head":[...], "rows":[[...]]} 归一成 (二维列表, 表头行数)。

    注意：head 的「长度」是列数，表头行数恒为 1（有 head 时）——不要写成 len(head)。
    """
    head = tbl.get("head") or []
    body = tbl.get("rows") or []
    data = ([list(head)] if head else []) + [list(r) for r in body]
    return data, (1 if head else 0)


def _tbl(slide, x, y, w, spec):
    if not spec:
        return
    data, hrows = _rows(spec)
    if not data:
        return
    add_table(
        slide, x, y, w,
        spec.get("weights") or [1] * len(data[0]),
        data,
        header_rows=hrows,
        row_h=spec.get("row_h", 0.34),
        head_h=spec.get("head_h", 0.40),
        size=spec.get("size", 10.5),
        head_size=spec.get("head_size", spec.get("size", 10.5)),
        align=spec.get("align"),
        first_bold=spec.get("first_bold", False),
    )


# ============================================================ 封面 / 目录 / 结尾
def s_cover(prs, c):
    m = c.meta
    s = blank(prs)
    if m.get("cover_bg"):
        pic_cover(s, c.img(m["cover_bg"]), 0, 0, SW, SH)
    else:
        rect(s, 0, 0, SW, SH, fill=DARK_BG)

    pic_fit(s, ASSETS / "logo_light.png", M, 0.62, 2.20, 0.46, halign="left")
    rect(s, M, 1.38, 0.70, 0.030, fill=ORANGE)

    tf = textbox(s, M, 1.78, 8.6, 0.30)
    para(tf, True, m.get("eyebrow", "SOLUTION PROPOSAL  ·  方案说明书"),
         size=11.5, bold=True, color=ORANGE, line=1.0)

    lines = m.get("title_lines") or [m.get("project_name", "")]
    tf = textbox(s, M, 2.24, 9.6, 0.6 * len(lines) + 0.7)
    for i, ln in enumerate(lines):
        para(tf, i == 0, ln, size=42, bold=True, color=WHITE, line=1.16)

    tf = textbox(s, M, 4.28, 8.4, 0.62)
    para(tf, True, m.get("subtitle", ""), size=13,
         color=RGBColor(0xB8, 0xC0, 0xC8), line=1.45)

    stats = c.spec.get("cover_stats") or []
    bx, bw, gap = M, 2.42, 0.28
    for i, st in enumerate(stats[:4]):
        x = bx + i * (bw + gap)
        rect(s, x, 5.34, bw, 0.028,
             fill=ORANGE if i == 0 else RGBColor(0x4A, 0x4E, 0x52))
        tf = textbox(s, x, 5.56, bw, 0.42)
        rich(tf, True, [(str(st.get("value", "")), True, WHITE, 25),
                        ("  " + str(st.get("unit", "")), True, ORANGE, 11)], line=1.0)
        tf = textbox(s, x, 6.06, bw, 0.26)
        para(tf, True, st.get("label", ""), size=9.5,
             color=RGBColor(0x93, 0x9C, 0xA4), line=1.0)

    stamp = "   |   ".join([v for v in [m.get("date", ""),
                                        f'成果版本 {m["version"]}' if m.get("version") else ""] if v])
    tf = textbox(s, SW - M - 3.4, 6.42, 3.4, 0.26)
    para(tf, True, stamp, size=9.5, color=RGBColor(0x74, 0x7C, 0x84),
         align=PP_ALIGN.RIGHT, line=1.0)


def s_agenda(prs, c):
    ag = c.spec.get("agenda") or {}
    items = ag.get("items") or []
    s = page(prs, ag.get("kicker", "CONTENTS"), ag.get("title", "目录"),
             c.num(), sub=ag.get("sub"), label=c.label)
    cw, ch, gx, gy = 3.90, 2.28, 0.32, 0.26
    for i, it in enumerate(items[:6]):
        r_, cc = divmod(i, 3)
        x = M + cc * (cw + gx); y = BODY_Y + 0.06 + r_ * (ch + gy)
        rect(s, x, y, cw, ch, fill=BG_CARD, line=LINE, lw=0.75)
        rect(s, x, y, 0.042, ch, fill=ORANGE)
        tf = textbox(s, x + 0.30, y + 0.24, 2.0, 0.52)
        para(tf, True, str(it.get("num", i + 1)).zfill(2), size=30, bold=True,
             color=ORANGE, line=1.0)
        tf = textbox(s, x + 0.30, y + 0.92, cw - 0.6, 0.34)
        para(tf, True, it.get("title", ""), size=15, bold=True, color=INK, line=1.0)
        tf = textbox(s, x + 0.30, y + 1.34, cw - 0.58, 0.78)
        para(tf, True, it.get("desc", ""), size=10.5, color=GRAY, line=1.42)


def s_closing(prs, c):
    cl = c.spec.get("closing") or {}
    m = c.meta
    s = blank(prs)
    if m.get("closing_bg"):
        pic_cover(s, c.img(m["closing_bg"]), 0, 0, SW, SH)
        rect(s, 0, 0, SW, 2.10, fill=DARK_BG)
        rect(s, 0, 5.10, SW, SH - 5.10, fill=DARK_BG)
    else:
        rect(s, 0, 0, SW, SH, fill=DARK_BG)

    pic_fit(s, ASSETS / "logo_light.png", M, 0.72, 2.05, 0.43, halign="left")
    rect(s, M, 1.44, 0.62, 0.028, fill=ORANGE)
    tf = textbox(s, M, 3.18, 10.0, 0.86)
    para(tf, True, cl.get("headline", "让建筑的每一寸表皮都可以发电"),
         size=32, bold=True, color=WHITE, line=1.06)
    tf = textbox(s, M, 4.18, 10.0, 0.32)
    para(tf, True, cl.get("subline") or m.get("subtitle", ""), size=13,
         color=RGBColor(0xA8, 0xB0, 0xB8), line=1.0)
    tf = textbox(s, M, 5.60, 8.0, 0.30)
    para(tf, True, cl.get("stamp") or
         "Almaden  |  BIPV 项目建议书", size=11, color=RGBColor(0x7E, 0x86, 0x8E), line=1.0)
    if cl.get("note"):
        tf = textbox(s, M, 6.10, 9.0, 0.28)
        para(tf, True, cl["note"], size=9, color=RGBColor(0x5E, 0x66, 0x6E), line=1.0)


# ============================================================ 版式库

def _im(sp, key="image"):
    """取图片对象；缺 image 字段返回 None（版式据此自动让出图位）。"""
    o = sp.get(key) or {}
    return o if o.get("image") else None

def a_facts_hero(prs, c, sp, kicker):
    """左表 + 右大图 + 底部 KPI 条。用于「项目概况」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    hero = _im(sp, "hero")
    stats = sp.get("stats") or []
    tw = sp.get("table_w", 6.35) if hero else CW
    _tbl(s, M, BODY_Y + 0.02, tw, sp.get("table"))
    if hero:
        hx = M + tw + 0.34; hw = CW - tw - 0.34
        hh = sp.get("hero_h", 3.42)
        img_card(s, c.img(hero["image"]), hx, BODY_Y + 0.02, hw, hh,
                 caption=hero.get("caption"))
        sy, sw = BODY_Y + hh + 0.20, hw
    else:
        hx, sy, sw = M, 5.34, CW
    if stats:
        kw = (sw - (len(stats) - 1) * 0.20) / len(stats)
        for i, st in enumerate(stats):
            stat_card(s, hx + i * (kw + 0.20), sy, kw, 1.24,
                      st.get("value", ""), st.get("unit", ""), st.get("label", ""))


def a_table_points_image(prs, c, sp, kicker):
    """左表 + 左下要点 + 右图。用于「屋面条件 / 数据 + 校验图」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    im = _im(sp)
    tw = sp.get("table_w", 6.40) if im else CW
    _tbl(s, M, BODY_Y + 0.02, tw, sp.get("table"))
    ty = sp.get("points_y")
    if ty is None:
        tbl = sp.get("table") or {}
        nrow = len(tbl.get("rows") or []) + (1 if tbl.get("head") else 0)
        ty = BODY_Y + 0.02 + tbl.get("head_h", 0.40) + \
            (nrow - 1) * tbl.get("row_h", 0.34) + 0.12
    if sp.get("points"):
        bullets(s, M, ty, tw, sp["points"], size=sp.get("points_size", 10.5), gap=6)
    if im:
        img_card(s, c.img(im["image"]), M + tw + 0.32, BODY_Y + 0.02,
                 CW - tw - 0.32, sp.get("image_h", 4.72), caption=im.get("caption"))


def a_image_spec_table(prs, c, sp, kicker):
    """左图 + 右规格表 + 底部注。用于「产品介绍」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    im = _im(sp)
    iw = sp.get("image_w", 4.05) if im else 0.0
    if im:
        img_card(s, c.img(im["image"]), M, BODY_Y + 0.02, iw, sp.get("image_h", 4.72),
                 caption=im.get("caption"))
    x = M + (iw + 0.30 if im else 0.0); w = CW - (iw + 0.30 if im else 0.0)
    _tbl(s, x, BODY_Y + 0.02, w, sp.get("table"))
    if sp.get("note"):
        ty = sp.get("note_y")
        if ty is None:
            tbl = sp.get("table") or {}
            nrow = len(tbl.get("rows") or []) + (1 if tbl.get("head") else 0)
            ty = BODY_Y + 0.02 + tbl.get("head_h", 0.40) + \
                (nrow - 1) * tbl.get("row_h", 0.34) + 0.20
        note(s, x, ty, w, sp["note"], size=sp.get("note_size", 9))


def a_dual_table_panel(prs, c, sp, kicker):
    """两张并排表 + 右侧深色说明面板 + 底部注。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    gap = sp.get("gap", 0.40)
    pw = sp.get("panel_w", 2.90)
    tw = (CW - 2 * gap - pw) / 2
    _tbl(s, M, BODY_Y + 0.02, tw, sp.get("table_left"))
    _tbl(s, M + tw + gap, BODY_Y + 0.02, tw, sp.get("table_right"))
    p = sp.get("panel") or {}
    px = M + 2 * (tw + gap); ph = sp.get("panel_h", 4.34)
    rect(s, px, BODY_Y + 0.02, pw, ph, fill=INK)
    rect(s, px, BODY_Y + 0.02, pw, 0.045, fill=ORANGE)
    tf = textbox(s, px + 0.32, BODY_Y + 0.42, pw - 0.64, 0.30)
    para(tf, True, p.get("title", ""), size=13, bold=True, color=WHITE, line=1.0)
    bullets(s, px + 0.32, BODY_Y + 0.94, pw - 0.64, p.get("items", []),
            size=sp.get("panel_size", 10), gap=8,
            color=RGBColor(0xB9, 0xC1, 0xC8))
    if sp.get("note"):
        note(s, M, BODY_Y + ph + 0.22, CW, sp["note"], size=sp.get("note_size", 9))


def a_wide_table_callouts(prs, c, sp, kicker):
    """通栏表 + 底部两个提示框。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    _tbl(s, M, BODY_Y + 0.02, CW, sp.get("table"))
    cos = sp.get("callouts") or []
    if not cos:
        return
    tbl = sp.get("table") or {}
    nrow = len(tbl.get("rows") or []) + (1 if tbl.get("head") else 0)
    by = BODY_Y + 0.02 + tbl.get("head_h", 0.40) + (nrow - 1) * tbl.get("row_h", 0.34) + 0.20
    ch = sp.get("callout_h", 0.86)
    n = len(cos)
    cwid = (CW - (n - 1) * 0.32) / n
    for i, co in enumerate(cos):
        x = M + i * (cwid + 0.32)
        rect(s, x, by, cwid, ch, fill=BG_SOFT, line=LINE, lw=0.75)
        rect(s, x, by, 0.04, ch, fill=ORANGE)
        tf = textbox(s, x + 0.24, by + 0.14, cwid - 0.48, 0.30)
        rich(tf, True, [(co.get("title", ""), True, INK, 10.5),
                        ("　" + co.get("value", ""), False, GRAY, 10)], line=1.15)
        if co.get("body"):
            tf = textbox(s, x + 0.24, by + 0.48, cwid - 0.48, ch - 0.58)
            para(tf, True, co["body"], size=sp.get("callout_size", 9.5),
                 color=GRAY_LT, line=1.25)


def a_image_points_chips(prs, c, sp, kicker):
    """左图 + 右要点 + 高亮框 + 底部标签行。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    im = _im(sp)
    iw = sp.get("image_w", 5.30) if im else 0.0
    ih = sp.get("image_h", 4.72)
    if im and sp.get("image2"):
        img_card_pair(s, c.img(im["image"]), c.img(sp["image2"]), M, BODY_Y + 0.02,
                      iw, ih, caption=im.get("caption"),
                      ratio=sp.get("image_ratio", 0.65))
    elif im:
        img_card(s, c.img(im["image"]), M, BODY_Y + 0.02, iw, ih,
                 caption=im.get("caption"))
    x = M + (iw + 0.32 if im else 0.0); w = CW - (iw + 0.32 if im else 0.0)
    bullets(s, x, BODY_Y + 0.10, w, sp.get("points", []),
            size=sp.get("points_size", 10.5), gap=sp.get("points_gap", 9))
    hl = sp.get("highlight") or {}
    if hl:
        hy = BODY_Y + sp.get("highlight_y", 2.72)
        rect(s, x, hy, w, 0.98, fill=ORANGE_LT, line=ORANGE_BD, lw=0.75)
        tf = textbox(s, x + 0.26, hy + 0.15, w - 0.52, 0.30)
        para(tf, True, hl.get("title", ""), size=11, bold=True, color=ORANGE_DK, line=1.0)
        tf = textbox(s, x + 0.26, hy + 0.50, w - 0.52, 0.34)
        rich(tf, True, [(str(hl.get("value", "")), True, INK, 19),
                        ("  " + str(hl.get("unit", "")), True, ORANGE_DK, 11),
                        ("　" + hl.get("note", ""), False, GRAY, 9.5)], line=1.0)
    chips = sp.get("chips") or []
    if chips:
        cy = BODY_Y + sp.get("chips_y", 4.00)
        cwid = (w - (len(chips) - 1) * 0.16) / len(chips)
        for i, ck in enumerate(chips):
            chip(s, x + i * (cwid + 0.16), cy, cwid, 0.46, ck,
                 size=sp.get("chip_size", 9))


def a_image_stats_table(prs, c, sp, kicker):
    """左大图 + 右两张统计卡 + 右侧表格。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    im = _im(sp)
    iw = sp.get("image_w", 6.10) if im else 0.0
    if im:
        img_card(s, c.img(im["image"]), M, BODY_Y + 0.02, iw, sp.get("image_h", 4.72))
    x = M + (iw + 0.32 if im else 0.0); w = CW - (iw + 0.32 if im else 0.0)
    for i, st in enumerate((sp.get("stats") or [])[:2]):
        y = BODY_Y + 0.06 + i * 1.06
        col = INK if i == 0 else ORANGE
        rect(s, x, y, w, 0.94, fill=BG_SOFT, line=LINE, lw=0.75)
        rect(s, x, y, 0.045, 0.94, fill=col)
        tf = textbox(s, x + 0.26, y + 0.14, w - 0.5, 0.36)
        rich(tf, True, [(str(st.get("value", "")), True, col, 20),
                        ("  " + str(st.get("unit", "")), True, GRAY, 10)], line=1.0)
        tf = textbox(s, x + 0.26, y + 0.56, w - 0.5, 0.26)
        para(tf, True, st.get("label", ""), size=10, color=GRAY, line=1.0)
    if sp.get("table"):
        _tbl(s, x, BODY_Y + sp.get("table_y", 2.28), w, sp["table"])


def a_image_param_table(prs, c, sp, kicker):
    """左大图 + 右参数表 + 表下要点。用于「分坡展开」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    im = _im(sp)
    iw = sp.get("image_w", 7.70) if im else 0.0
    if im:
        img_card(s, c.img(im["image"]), M, BODY_Y + 0.02, iw, sp.get("image_h", 4.72))
    x = M + (iw + 0.32 if im else 0.0); w = CW - (iw + 0.32 if im else 0.0)
    _tbl(s, x, BODY_Y + 0.02, w, sp.get("table"))
    if sp.get("points"):
        tbl = sp.get("table") or {}
        nrow = len(tbl.get("rows") or []) + (1 if tbl.get("head") else 0)
        py = BODY_Y + 0.02 + tbl.get("head_h", 0.36) + \
            (nrow - 1) * tbl.get("row_h", 0.365) + 0.24
        bullets(s, x, py, w, sp["points"], size=sp.get("points_size", 9.5), gap=5)


def a_wide_table_stats(prs, c, sp, kicker):
    """通栏宽表 + 右侧统计卡与口径面板。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    sw_ = sp.get("side_w", 3.05)
    _tbl(s, M, BODY_Y + 0.02, CW - sw_ - 0.25, sp.get("table"))
    x = SW - M - sw_; y = BODY_Y + 0.02
    for st in (sp.get("stats") or []):
        stat_card(s, x, y, sw_, 1.30, st.get("value", ""), st.get("unit", ""),
                  st.get("label", ""))
        y += 1.46
    p = sp.get("panel") or {}
    if p:
        ph = min(6.78 - y, sp.get("panel_h", 1.80))
        if ph > 0.6:
            callout(s, x, y, sw_, ph, p.get("title", ""),
                    "\n".join("·  " + i for i in p.get("items", [])),
                    size=sp.get("panel_size", 9), body_color=GRAY)


def a_steps_panel(prs, c, sp, kicker):
    """N 个编号步骤卡 + 底部双栏说明。用于「工序总览」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    steps = sp.get("steps") or []
    n = max(1, len(steps))
    gx = sp.get("gap", 0.165)
    cw = (CW - (n - 1) * gx) / n
    ch = sp.get("card_h", 2.62)
    for i, st in enumerate(steps):
        x = M + i * (cw + gx)
        rect(s, x, BODY_Y + 0.10, cw, ch, fill=WHITE, line=LINE, lw=0.75)
        rect(s, x, BODY_Y + 0.10, cw, 0.045,
             fill=ORANGE if i < sp.get("accent_upto", n) else INK)
        tf = textbox(s, x + 0.20, BODY_Y + 0.34, cw - 0.4, 0.34)
        para(tf, True, str(st.get("num", i + 1)).zfill(2), size=18, bold=True,
             color=ORANGE, line=1.0)
        tf = textbox(s, x + 0.20, BODY_Y + 0.78, cw - 0.4, 0.30)
        para(tf, True, st.get("title", ""), size=11.5, bold=True, color=INK, line=1.0)
        tf = textbox(s, x + 0.20, BODY_Y + 1.14, cw - 0.38, ch - 1.20)
        for j, ln in enumerate(str(st.get("desc", "")).split("\n")):
            para(tf, j == 0, ln, size=sp.get("step_size", 8.5), color=GRAY,
                 line=1.35, space_before=0 if j == 0 else 3)
        if i < n - 1 and sp.get("arrows", True):
            tf = textbox(s, x + cw - 0.02, BODY_Y + 1.20, gx + 0.04, 0.30,
                         anchor=MSO_ANCHOR.MIDDLE)
            para(tf, True, "›", size=14, bold=True, color=LINE_DK,
                 align=PP_ALIGN.CENTER, line=1.0)
    panels = sp.get("panels") or []
    if panels:
        py = BODY_Y + ch + 0.48
        ph = min(6.78 - py, sp.get("panel_h", 1.64))
        if ph > 0.7:
            rect(s, M, py, CW, ph, fill=BG_SOFT, line=LINE, lw=0.75)
            half = CW / 2
            for i, p in enumerate(panels[:2]):
                x = M + i * half
                tf = textbox(s, x + 0.34, py + 0.20, half - 0.6, 0.30)
                para(tf, True, p.get("title", ""), size=12, bold=True, color=INK, line=1.0)
                bullets(s, x + 0.34, py + 0.62, half - 0.6, p.get("items", []),
                        size=sp.get("panel_size", 9.5), gap=5)
    if sp.get("table_full"):
        tbl = sp["table_full"]
        ty = BODY_Y + ch + 0.44
        _tbl(s, M, ty, CW, tbl)
        if sp.get("note"):
            nrow = len(tbl.get("rows") or []) + (1 if tbl.get("head") else 0)
            ny = ty + tbl.get("head_h", 0.36) + (nrow - 1) * tbl.get("row_h", 0.34) + 0.22
            note(s, M, min(ny, 6.52), CW, sp["note"], size=sp.get("note_size", 9))


def a_images_points_note(prs, c, sp, kicker):
    """两张图 + 右栏要点 + 说明框 + 底部注。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    gap = sp.get("image_gap", 0.22)
    ims = [i for i in (sp.get("images") or []) if i.get("image")]
    if ims:
        iw1 = sp.get("image1_w", 4.55)
        iw2 = sp.get("image2_w", 3.05)
        img_card(s, c.img(ims[0]["image"]), M, BODY_Y + 0.02, iw1,
                 sp.get("image_h", 4.72), caption=ims[0].get("caption"))
        if len(ims) > 1:
            img_card(s, c.img(ims[1]["image"]), M + iw1 + gap, BODY_Y + 0.02, iw2,
                     sp.get("image_h", 4.72), caption=ims[1].get("caption"))
        used = iw1 + gap + (iw2 + gap if len(ims) > 1 else gap)
    else:
        used = 0.0
    x = M + used; w = CW - used
    bullets(s, x, BODY_Y + 0.10, w, sp.get("points", []),
            size=sp.get("points_size", 9.5), gap=sp.get("points_gap", 6))
    if sp.get("box"):
        by = BODY_Y + sp.get("box_y", 2.86)
        bh = sp.get("box_h", 1.10)
        bx_ = sp["box"]
        callout(s, x, by, w, bh, bx_.get("title", ""), bx_.get("body", ""),
                fill=col(bx_.get("fill"), ORANGE_LT),
                border=col(bx_.get("border"), ORANGE_BD),
                bar=col(bx_.get("bar"), ORANGE),
                title_color=col(bx_.get("title_color"), ORANGE_DK),
                size=sp.get("box_size", 9.5))
        if bx_.get("items"):
            bullets(s, x + 0.24, by + 0.52, w - 0.48, bx_["items"],
                    size=sp.get("box_size", 9.5), gap=5,
                    color=col(bx_.get("body_color"), GRAY))
        if sp.get("note"):
            note(s, x, by + bh + 0.24, w, sp["note"], size=sp.get("note_size", 9))
    elif sp.get("note"):
        note(s, x, BODY_Y + sp.get("note_y", 4.30), w, sp["note"],
             size=sp.get("note_size", 9))


def a_images_steps(prs, c, sp, kicker):
    """两图 + 右栏堆叠的步骤说明块。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    gap = sp.get("image_gap", 0.22)
    ims = [i for i in (sp.get("images") or []) if i.get("image")]
    if ims:
        iw1 = sp.get("image1_w", 5.55)
        iw2 = sp.get("image2_w", 3.10)
        img_card(s, c.img(ims[0]["image"]), M, BODY_Y + 0.02, iw1,
                 sp.get("image_h", 4.72), caption=ims[0].get("caption"))
        if len(ims) > 1:
            img_card(s, c.img(ims[1]["image"]), M + iw1 + gap, BODY_Y + 0.02, iw2,
                     sp.get("image_h", 4.72), caption=ims[1].get("caption"))
        used = iw1 + gap + (iw2 + gap if len(ims) > 1 else gap)
    else:
        used = 0.0
    x = M + used; w = CW - used
    y = BODY_Y + 0.06
    for blk in (sp.get("blocks") or []):
        items = blk.get("items", [])
        h = 0.52 + len(items) * 0.30
        rect(s, x, y, w, h, fill=BG_SOFT, line=LINE, lw=0.75)
        rect(s, x, y, 0.04, h, fill=ORANGE)
        tf = textbox(s, x + 0.22, y + 0.12, w - 0.42, 0.26)
        para(tf, True, blk.get("title", ""), size=11, bold=True, color=INK, line=1.0)
        bullets(s, x + 0.22, y + 0.44, w - 0.44, items, size=8.5, gap=3, line=1.28)
        y += h + 0.16


def a_three_columns_callout(prs, c, sp, kicker):
    """三栏卡片 + 底部注 + 橙色提示条。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    cols = sp.get("columns") or []
    n = max(1, len(cols))
    gap = sp.get("gap", 0.30)
    cw = (CW - (n - 1) * gap) / n
    ch = sp.get("card_h", 3.42)
    for i, col in enumerate(cols):
        x = M + i * (cw + gap)
        rect(s, x, BODY_Y + 0.06, cw, ch, fill=WHITE, line=LINE, lw=0.75)
        rect(s, x, BODY_Y + 0.06, cw, 0.045,
             fill=[ORANGE, INK, ORANGE_DK, GRAY][i % 4])
        tf = textbox(s, x + 0.26, BODY_Y + 0.30, cw - 0.5, 0.32)
        para(tf, True, col.get("title", ""), size=13.5, bold=True, color=INK, line=1.0)
        bullets(s, x + 0.26, BODY_Y + 0.84, cw - 0.52, col.get("items", []),
                size=sp.get("item_size", 10), gap=sp.get("item_gap", 10), line=1.40)
    if sp.get("note"):
        note(s, M, BODY_Y + ch + 0.26, CW, sp["note"], size=sp.get("note_size", 9))
    co = sp.get("callout")
    if co:
        cy = BODY_Y + ch + (0.70 if sp.get("note") else 0.26)
        chh = min(6.78 - cy, sp.get("callout_h", 0.94))
        if chh > 0.5:
            rect(s, M, cy, CW, chh, fill=ORANGE_LT, line=ORANGE_BD, lw=0.75)
            rect(s, M, cy, 0.05, chh, fill=ORANGE)
            tf = textbox(s, M + 0.30, cy + 0.14, CW - 0.60, 0.28)
            para(tf, True, co.get("title", ""), size=11, bold=True,
                 color=ORANGE_DK, line=1.0)
            tf = textbox(s, M + 0.30, cy + 0.46, CW - 0.60, chh - 0.56)
            para(tf, True, co.get("body", ""), size=9.5, color=GRAY, line=1.35)


def a_image_grid(prs, c, sp, kicker):
    """图片网格（默认 3 列 × N 行）。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    items = [i for i in (sp.get("images") or []) if i.get("image")]
    if not items:
        raise ValueError('image_grid 需要至少一张图（images[].image）')
    cols = sp.get("cols", 3)
    gap = sp.get("gap", 0.22)
    avail = 6.78 - (BODY_Y + 0.02)
    rows = max(1, (len(items) + cols - 1) // cols)
    cwid = (CW - (cols - 1) * gap) / cols
    chgt = (avail - (rows - 1) * gap) / rows
    for i, it in enumerate(items):
        r_, cc = divmod(i, cols)
        img_card(s, c.img(it["image"]), M + cc * (cwid + gap),
                 BODY_Y + 0.02 + r_ * (chgt + gap), cwid, chgt,
                 caption=it.get("caption"))


def a_table_stat_panel(prs, c, sp, kicker):
    """表格 + 右侧统计卡 + 口径面板。用于「核验结果」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    sw_ = sp.get("side_w", 3.25)
    _tbl(s, M, BODY_Y + 0.02, CW - sw_ - 0.30, sp.get("table"))
    x = SW - M - sw_; y = BODY_Y + 0.02
    for st in (sp.get("stats") or []):
        stat_card(s, x, y, sw_, sp.get("stat_h", 1.26), st.get("value", ""),
                  st.get("unit", ""), st.get("label", ""))
        y += sp.get("stat_h", 1.26) + 0.16
    p = sp.get("panel") or {}
    if p:
        ph = min(6.78 - y, sp.get("panel_h", 3.10))
        if ph > 0.8:
            rect(s, x, y, sw_, ph, fill=BG_SOFT, line=LINE, lw=0.75)
            rect(s, x, y, 0.04, ph, fill=ORANGE)
            tf = textbox(s, x + 0.24, y + 0.18, sw_ - 0.48, 0.28)
            para(tf, True, p.get("title", ""), size=11, bold=True, color=INK, line=1.0)
            bullets(s, x + 0.24, y + 0.56, sw_ - 0.48, p.get("items", []),
                    size=sp.get("panel_size", 9), gap=6)


def a_cards_grid(prs, c, sp, kicker):
    """两列卡片网格。用于「设计条件 / 待确认事项」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    cards = sp.get("cards") or []
    cols = sp.get("cols", 2)
    gap = sp.get("gap", 0.30)
    cwid = (CW - (cols - 1) * gap) / cols
    chgt = sp.get("card_h", 1.32)
    rgap = sp.get("row_gap", 0.22)
    for i, cd in enumerate(cards):
        r_, cc = divmod(i, cols)
        x = M + cc * (cwid + gap); y = BODY_Y + 0.06 + r_ * (chgt + rgap)
        rect(s, x, y, cwid, chgt, fill=WHITE, line=LINE, lw=0.75)
        rect(s, x, y, 0.045, chgt, fill=col(cd.get("color"), ORANGE))
        tf = textbox(s, x + 0.28, y + 0.20, cwid - 0.54, 0.28)
        para(tf, True, cd.get("title", ""), size=12, bold=True, color=INK, line=1.0)
        tf = textbox(s, x + 0.28, y + 0.56, cwid - 0.54, chgt - 0.68)
        para(tf, True, cd.get("body", ""), size=sp.get("body_size", 9.5),
             color=GRAY, line=1.40)


def a_charts_stats(prs, c, sp, kicker):
    """左环图 + 右柱状图 + 底部 KPI 行。用于「年发电量与逐月分布」。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    dw = sp.get("donut_w", 3.30)
    dh = sp.get("chart_h", 3.30)
    img_card(s, c.img((sp.get("donut") or {})["image"]), M, BODY_Y + 0.02, dw, dh)
    x = M + dw + (sp.get("gap", 0.28))
    bar = sp.get("bar") or {}
    img_card(s, c.img(bar["image"]), x, BODY_Y + 0.02, CW - dw - sp.get("gap", 0.28), dh,
             caption=bar.get("caption"))
    stats = sp.get("stats") or []
    if stats:
        by = BODY_Y + dh + 0.22
        cwid = (CW - (len(stats) - 1) * 0.22) / len(stats)
        for i, st in enumerate(stats):
            stat_card(s, M + i * (cwid + 0.22), by, cwid, sp.get("stat_h", 1.22),
                      st.get("value", ""), st.get("unit", ""), st.get("label", ""))


def a_video(prs, c, sp, kicker):
    """嵌入视频页。视频为真实嵌入（p14:media），换机播放无需外链。"""
    s = page(prs, kicker, sp["title"], c.num(), sub=sp.get("sub"), label=c.label)
    if not sp.get("video"):
        raise ValueError('video 版式必须提供 "video" 字段（相对 JSON 的 mp4 路径）')
    vw = sp.get("video_w", 8.10)
    vh = sp.get("video_h", vw * 9 / 16)
    vx, vy = M, BODY_Y + 0.04
    rect(s, vx - 0.055, vy - 0.055, vw + 0.11, vh + 0.11, fill=INK)
    path = c.img(sp["video"])
    poster = c.img(sp.get("poster")) if sp.get("poster") else None
    if poster:
        s.shapes.add_movie(path, Inches(vx), Inches(vy), Inches(vw), Inches(vh),
                           poster_frame_image=poster, mime_type="video/mp4")
    else:
        s.shapes.add_movie(path, Inches(vx), Inches(vy), Inches(vw), Inches(vh),
                           mime_type="video/mp4")

    x = vx + vw + 0.45; w = CW - vw - 0.45
    if sp.get("points_title"):
        tf = textbox(s, x, vy + 0.02, w, 0.30)
        para(tf, True, sp["points_title"], size=12.5, bold=True, color=INK, line=1.0)
    bullets(s, x, vy + 0.46, w, sp.get("points", []),
            size=sp.get("points_size", 10), gap=7)
    if sp.get("box"):
        by = vy + sp.get("box_y", 2.06)
        callout(s, x, by, w, sp.get("box_h", 1.28),
                sp["box"].get("title", ""), sp["box"].get("body", ""), size=9.5)
        if sp.get("note"):
            note(s, x, by + sp.get("box_h", 1.28) + 0.22, w, sp["note"], size=9)


# 版式注册表：JSON 的 "type" 字段即此处的键
ARCHETYPES = {
    "facts_hero": a_facts_hero,
    "table_points_image": a_table_points_image,
    "image_spec_table": a_image_spec_table,
    "dual_table_panel": a_dual_table_panel,
    "wide_table_callouts": a_wide_table_callouts,
    "image_points_chips": a_image_points_chips,
    "image_stats_table": a_image_stats_table,
    "image_param_table": a_image_param_table,
    "wide_table_stats": a_wide_table_stats,
    "steps_panel": a_steps_panel,
    "images_points_note": a_images_points_note,
    "images_steps": a_images_steps,
    "three_columns_callout": a_three_columns_callout,
    "image_grid": a_image_grid,
    "charts_stats": a_charts_stats,
    "table_stat_panel": a_table_stat_panel,
    "cards_grid": a_cards_grid,
    "video": a_video,
}


# ============================================================ 主流程
def build(spec, out_path, base=None):
    base = base or pathlib.Path(".")
    c = Ctx(spec, base)
    prs = new_deck()
    s_cover(prs, c)
    if spec.get("agenda"):
        s_agenda(prs, c)
    for sec in spec.get("sections", []):
        if sec.get("divider", True):
            c.num()
            divider(prs, sec.get("num", ""), sec.get("title", ""), sec.get("en", ""),
                    sec.get("desc", ""), sec.get("chips"), num_page=c.page, label=c.label)
        kicker = sec.get("kicker") or \
            f'{sec.get("num", "")}  {sec.get("title", "")}'.strip()
        for sp in sec.get("slides", []):
            fn = ARCHETYPES.get(sp.get("type"))
            if fn is None:
                raise ValueError(
                    f'未知版式 type="{sp.get("type")}"。可用：{sorted(ARCHETYPES)}')
            fn(prs, c, sp, kicker)
    s_closing(prs, c)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out, len(prs.slides._sldIdLst)


def main():
    ap = argparse.ArgumentParser(description="亚玛顿 BIPV 项目建议书生成器")
    ap.add_argument("--project", required=True, help="项目 JSON 路径")
    ap.add_argument("--output", required=True, help="输出 .pptx 路径")
    a = ap.parse_args()
    pj = pathlib.Path(a.project).resolve()
    spec = json.loads(pj.read_text(encoding="utf-8"))
    out, n = build(spec, a.output, base=pj.parent)
    print(f"已生成：{out}")
    print(f"幻灯片：{n} 页")
    print(f"体积：{out.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
