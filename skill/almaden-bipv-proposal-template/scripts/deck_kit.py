"""
deck_kit — 亚玛顿 BIPV 项目建议书视觉系统（design system）

本模块只做一件事：把「亚玛顿 BIPV」系列演示文稿的版式规范固化成一堆可复用函数，
使任何项目都能生成与标准样张完全同源的 PPTX。

设计要点（改版式前请先读 references/design-system.md）：
  · 画布固定 16:9 = 13.3333 × 7.5 in，左右边距 0.62 in。
  · 三级文字：标题 23pt / 小标题 15pt / 正文 10.5pt，正文行距 1.40。
  · 主色 Almaden 橙 #F45918，墨黑 #1A1A1A；橙色只用于强调，不铺大面积。
  · 中文走 a:ea、西文走 a:latin，两处都要显式设置，否则中文会回退成宋体。
  · 所有文本坐标用 Inches，字号用 Pt。

最小用法：
    from deck_kit import *
    prs = new_deck()
    s = page(prs, "01  项目概况", "项目概况与建设内容", 1)
    add_table(s, M, BODY_Y, CW, [1, 2], [["项目", "内容"], ["装机", "42.64 kWp"]])
    prs.save("out.pptx")
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"

# ============================================================ 品牌色板
INK        = RGBColor(0x1A, 0x1A, 0x1A)   # 主文字 / 深底
INK_SOFT   = RGBColor(0x2C, 0x30, 0x34)
ORANGE     = RGBColor(0xF4, 0x59, 0x18)   # Almaden 橙（取自 logo）
ORANGE_DK  = RGBColor(0xC9, 0x42, 0x0C)   # 橙底上的文字色
ORANGE_LT  = RGBColor(0xFD, 0xEC, 0xE3)   # 橙色浅底（提示框）
ORANGE_BD  = RGBColor(0xF6, 0xC9, 0xAE)   # 橙色浅底描边
GRAY       = RGBColor(0x5F, 0x6B, 0x76)   # 正文次要
GRAY_LT    = RGBColor(0x8B, 0x96, 0xA1)   # 页脚 / 图注
LINE       = RGBColor(0xDD, 0xE2, 0xE6)   # 分隔线 / 卡片描边
LINE_DK    = RGBColor(0xC4, 0xCC, 0xD2)
BG_SOFT    = RGBColor(0xF4, 0xF6, 0xF7)   # 浅灰卡片底
BG_CARD    = RGBColor(0xFA, 0xFB, 0xFC)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
DARK_BG    = RGBColor(0x16, 0x16, 0x18)   # 章节页 / 封面底
DARK_CARD  = RGBColor(0x21, 0x22, 0x25)

# ============================================================ 字体
EA    = "微软雅黑"   # 中文（Windows/Office 通用；缺失时 PowerPoint 自动回退）
LATIN = "Arial"      # 西文与数字

# ============================================================ 版面栅格（英寸）
SW, SH = 13.3333, 7.5     # 画布
M      = 0.62             # 左右边距
CW     = SW - 2 * M       # 正文宽度 = 12.0933
HEAD_Y = 0.50             # 页眉起始
BODY_Y = 1.72             # 正文首行
FOOT_Y = 6.98             # 页脚基线
BODY_B = 6.78             # 正文安全下沿（不要越过）


# ============================================================ 基础
def new_deck():
    """空白 16:9 演示文稿（已套用统一画布尺寸）。"""
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    return prs


def blank(prs):
    """新增一张完全空白的幻灯片（不使用占位符）。"""
    return prs.slides.add_slide(prs.slide_layouts[6])


def rect(slide, x, y, w, h, fill=None, line=None, lw=0.75,
         shape=MSO_SHAPE.RECTANGLE, radius=None, shadow=False):
    """矩形／圆角矩形。fill=None 表示无填充，line=None 表示无描边。"""
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            s.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(lw)
    if not shadow:
        s.shadow.inherit = False
    s.text_frame.word_wrap = True
    return s


def _set_ea(run, ea=EA, latin=LATIN):
    """同时写 a:latin / a:ea / a:cs —— 中文排版的关键，缺一个就会出现宋体回退。"""
    rPr = run.font._rPr
    for tag in ("a:ea", "a:cs"):
        for el in rPr.findall(qn(tag)):
            rPr.remove(el)
    for tag, face in (("a:ea", ea), ("a:cs", latin)):
        rPr.append(rPr.makeelement(qn(tag), {"typeface": face}))


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    """无内边距、不自动缩放、可换行的文本框。文本可溢出文本框高度（故 h 只需近似）。"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, first, text, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT,
         space_before=0, space_after=0, line=1.30, italic=False, ea=EA, latin=LATIN):
    """往文本框追加一段。first=True 表示复用已存在的首段（避免留下空行）。"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    p.line_spacing = line
    if text != "":
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
        r.font.color.rgb = color; r.font.name = latin
        _set_ea(r, ea, latin)
    return p


def rich(tf, first, segments, size=14, color=INK, align=PP_ALIGN.LEFT,
         space_before=0, space_after=0, line=1.30, ea=EA, latin=LATIN):
    """一段内混排多种字号/颜色。segments 元素为 (text, bold[, color][, size])。"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before); p.space_after = Pt(space_after)
    p.line_spacing = line
    for seg in segments:
        t, b = seg[0], seg[1]
        c = seg[2] if len(seg) > 2 else color
        s = seg[3] if len(seg) > 3 else size
        r = p.add_run(); r.text = t
        r.font.size = Pt(s); r.font.bold = b
        r.font.color.rgb = c; r.font.name = latin
        _set_ea(r, ea, latin)
    return p


def pic_fit(slide, path, x, y, w, h, halign="center", valign="middle"):
    """等比缩放图片使其完整放进 (x,y,w,h)，不裁切、不变形。"""
    iw, ih = Image.open(path).size
    r = min(w / iw, h / ih)
    dw, dh = iw * r, ih * r
    dx = x + (0 if halign == "left" else (w - dw) if halign == "right" else (w - dw) / 2)
    dy = y + (0 if valign == "top" else (h - dh) if valign == "bottom" else (h - dh) / 2)
    return slide.shapes.add_picture(str(path), Inches(dx), Inches(dy), Inches(dw), Inches(dh))


def pic_cover(slide, path, x, y, w, h):
    """等比缩放并居中裁切填满 (x,y,w,h)，等价于 CSS background-size:cover。"""
    iw, ih = Image.open(path).size
    r = max(w / iw, h / ih)
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(iw * r), Inches(ih * r))
    pic.crop_left = max(0.0, (iw * r - w) / 2 / (iw * r))
    pic.crop_right = max(0.0, (iw * r - w) / 2 / (iw * r))
    pic.crop_top = max(0.0, (ih * r - h) / 2 / (ih * r))
    pic.crop_bottom = max(0.0, (ih * r - h) / 2 / (ih * r))
    pic.left, pic.top = Inches(x), Inches(y)
    pic.width, pic.height = Inches(w), Inches(h)
    return pic


# ============================================================ 页面骨架
def header(slide, kicker, title, sub=None, dark=False):
    """标准页眉：橙色竖条 + 栏目名 + 主标题（+ 副标题或细线）。"""
    tcol = WHITE if dark else INK
    rect(slide, M, HEAD_Y + 0.045, 0.055, 0.36, fill=ORANGE)
    tf = textbox(slide, M + 0.20, HEAD_Y, CW - 2.6, 0.24)
    para(tf, True, kicker, size=10.5, bold=True, color=ORANGE, line=1.0)
    tf2 = textbox(slide, M + 0.20, HEAD_Y + 0.235, CW - 2.2, 0.42)
    para(tf2, True, title, size=23, bold=True, color=tcol, line=1.0)
    if sub:
        tf3 = textbox(slide, M, HEAD_Y + 0.80, CW, 0.26)
        para(tf3, True, sub, size=11.5, color=GRAY_LT if dark else GRAY, line=1.1)
    else:
        rect(slide, M, HEAD_Y + 0.78, CW, 0.012,
             fill=RGBColor(0x33, 0x36, 0x3A) if dark else LINE)


def footer(slide, num, label="亚玛顿 BIPV 项目建议书", dark=False):
    """页脚：细线 + 左标签 + 右页码。num 为 int，显示为两位数。"""
    col = RGBColor(0x6A, 0x72, 0x7A) if dark else GRAY_LT
    rect(slide, M, FOOT_Y - 0.10, CW, 0.010,
         fill=RGBColor(0x39, 0x3C, 0x40) if dark else LINE)
    tf = textbox(slide, M, FOOT_Y + 0.04, CW - 0.9, 0.22)
    para(tf, True, label, size=8.5, color=col, line=1.0)
    tf2 = textbox(slide, SW - M - 0.9, FOOT_Y + 0.02, 0.9, 0.24)
    para(tf2, True, f"{num:02d}", size=11, bold=True, color=ORANGE,
         align=PP_ALIGN.RIGHT, line=1.0)


def page(prs, kicker, title, num, sub=None, dark=False, label="亚玛顿 BIPV 项目建议书"):
    """新建一张「有页眉页脚」的标准内容页，返回 slide。"""
    s = blank(prs)
    if dark:
        rect(s, 0, 0, SW, SH, fill=DARK_BG)
    header(s, kicker, title, sub, dark=dark)
    footer(s, num, label=label, dark=dark)
    return s


def divider(prs, num, title, en, desc, chips=None, num_page=1,
            logo=True, label="亚玛顿 BIPV 项目建议书"):
    """深色章节分隔页：超大编号 + 英文栏目名 + 中文标题 + 要点小卡。"""
    s = blank(prs)
    rect(s, 0, 0, SW, SH, fill=DARK_BG)
    rect(s, 0, 0, 0.14, SH, fill=ORANGE)
    rect(s, 0.14, 0, 0.05, SH, fill=ORANGE_DK)

    tf = textbox(s, M + 0.55, 2.26, 3.0, 1.30)
    para(tf, True, str(num).zfill(2), size=88, bold=True,
         color=RGBColor(0x2E, 0x31, 0x35), line=1.0)
    tf = textbox(s, M + 0.62, 3.30, 8.0, 0.36)
    para(tf, True, en, size=11, bold=True, color=ORANGE, line=1.0)
    tf = textbox(s, M + 0.60, 3.66, 9.4, 0.72)
    para(tf, True, title, size=36, bold=True, color=WHITE, line=1.06)
    tf = textbox(s, M + 0.62, 4.52, 8.4, 0.60)
    para(tf, True, desc, size=12, color=RGBColor(0x9A, 0xA3, 0xAB), line=1.48)

    for i, b in enumerate(chips or []):
        x = M + 0.62 + i * 3.35
        rect(s, x, 5.52, 3.05, 0.60, fill=DARK_CARD, line=RGBColor(0x33, 0x36, 0x3A))
        rect(s, x, 5.52, 0.035, 0.60, fill=ORANGE)
        tf = textbox(s, x + 0.20, 5.52, 2.78, 0.60, anchor=MSO_ANCHOR.MIDDLE)
        para(tf, True, b, size=10.5, color=RGBColor(0xC5, 0xCC, 0xD2), line=1.28)

    if logo:
        pic_fit(s, ASSETS / "logo_light.png", SW - M - 1.85, 0.62, 1.85, 0.38, halign="right")
    footer(s, num_page, label=label, dark=True)
    return s


# ============================================================ 通用组件
def stat_card(slide, x, y, w, h, value, unit, label, accent=ORANGE, dark=False):
    """KPI 数字卡：顶部色条 + 大数字 + 单位 + 说明。"""
    bg = DARK_CARD if dark else BG_CARD
    ln = RGBColor(0x33, 0x36, 0x3A) if dark else LINE
    rect(slide, x, y, w, h, fill=bg, line=ln, lw=0.75)
    rect(slide, x, y, w, 0.045, fill=accent)
    tf = textbox(slide, x + 0.20, y + 0.26, w - 0.4, 0.50)
    rich(tf, True, [(str(value), True, WHITE if dark else INK, 27),
                    ("  " + str(unit), True, accent, 12)], line=1.0)
    tf2 = textbox(slide, x + 0.20, y + h - 0.46, w - 0.4, 0.30)
    para(tf2, True, label, size=10, color=GRAY_LT if dark else GRAY, line=1.05)


def bullets(slide, x, y, w, items, size=12, gap=7, color=GRAY,
            bullet_color=ORANGE, line=1.42, dot=True):
    """
    橙色圆点列表。文本框高度只作占位，文本可向下自然溢出——
    调用方需自行保证下方留白（用 check_deck.py 复核）。
    items 元素为 str 或 (str, bold)。
    """
    tf = textbox(slide, x, y, w, 0.4)
    first = True
    for it in items:
        t, b = it if isinstance(it, tuple) else (it, False)
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        p.space_before = Pt(0 if first else gap)
        first = False
        p.line_spacing = line
        r0 = p.add_run(); r0.text = "·  " if dot else ""
        r0.font.size = Pt(size); r0.font.bold = True
        r0.font.color.rgb = bullet_color; r0.font.name = LATIN
        _set_ea(r0)
        r = p.add_run(); r.text = t
        r.font.size = Pt(size); r.font.bold = b
        r.font.color.rgb = INK if b else color; r.font.name = LATIN
        _set_ea(r)
    return tf


def img_card(slide, path, x, y, w, h, caption=None, pad=0.10, bg=WHITE,
             border=LINE, caption_h=0.30):
    """带细边框的图片卡；caption 会在卡底居中显示图注。"""
    rect(slide, x, y, w, h, fill=bg, line=border, lw=0.75)
    ih = h - 2 * pad - (caption_h if caption else 0)
    pic_fit(slide, path, x + pad, y + pad, w - 2 * pad, ih)
    if caption:
        tf = textbox(slide, x + pad, y + h - caption_h - 0.04, w - 2 * pad, 0.26)
        para(tf, True, caption, size=9.5, color=GRAY, align=PP_ALIGN.CENTER, line=1.05)


def img_card_pair(slide, path_top, path_bottom, x, y, w, h, caption=None,
                  pad=0.10, ratio=0.65, gap=0.07, bg=WHITE, border=LINE,
                  caption_h=0.30):
    """
    单张卡内上下叠放两张图（主图 + 辅图）。
    用于「一张节点大样 + 一张局部特写」这类需要同框对比的场景；
    比把两页 PDF 直接塞进一张卡更清晰。ratio 为主图占可用高度的比例。
    """
    rect(slide, x, y, w, h, fill=bg, line=border, lw=0.75)
    inner_h = h - 2 * pad - (caption_h if caption else 0)
    h1 = (inner_h - gap) * ratio
    h2 = inner_h - gap - h1
    iw = w - 2 * pad
    pic_fit(slide, path_top, x + pad, y + pad, iw, h1)
    pic_fit(slide, path_bottom, x + pad, y + pad + h1 + gap, iw, h2)
    if caption:
        tf = textbox(slide, x + pad, y + h - caption_h - 0.04, iw, 0.26)
        para(tf, True, caption, size=9.5, color=GRAY, align=PP_ALIGN.CENTER, line=1.05)


def _cell_border(cell, edges=("L", "R", "T", "B"), color=LINE, w=Pt(0.75)):
    """给单元格画四边线。python-pptx 无此 API，需按 CT_TableCellProperties 的顺序插 XML。"""
    tcPr = cell._tc.get_or_add_tcPr()
    tagmap = {"L": "a:lnL", "R": "a:lnR", "T": "a:lnT", "B": "a:lnB"}
    for e in edges:
        for el in tcPr.findall(qn(tagmap[e])):
            tcPr.remove(el)
    for e in ("L", "R", "T", "B"):
        if e not in edges:
            continue
        ln = etree.SubElement(tcPr, qn(tagmap[e]))
        ln.set("w", str(int(w))); ln.set("cap", "flat")
        ln.set("cmpd", "sng"); ln.set("algn", "ctr")
        fill = etree.SubElement(ln, qn("a:solidFill"))
        clr = etree.SubElement(fill, qn("a:srgbClr"))
        clr.set("val", "%02X%02X%02X" % (color[0], color[1], color[2]))
    # 必须按 schema 顺序重排，否则 LibreOffice 会整篇拒绝解析
    order = ["a:lnL", "a:lnR", "a:lnT", "a:lnB", "a:lnTlToBr", "a:lnBlToTr",
             "a:cell3D", "a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
             "a:pattFill", "a:grpFill", "a:headers", "a:extLst"]
    kids = list(tcPr)
    kids.sort(key=lambda c: order.index(etree.QName(c).text)
              if etree.QName(c).text in order else 99)
    for c in kids:
        tcPr.append(c)


def add_table(slide, x, y, w, col_w, rows, header_rows=1, row_h=0.34,
              head_h=0.40, size=10.5, head_size=10.5, align=None,
              head_fill=INK, zebra=BG_SOFT, first_bold=False, head_color=WHITE):
    """
    斑马纹表格。col_w 为相对宽度（按比例分配到 w）。
    align 为每列 'l'/'c'/'r' 的列表。
    注意：表格高度由 row_h/head_h 决定，内容过多时 PowerPoint 会自动撑高，
    因此表格下方的元素要留足余量。
    """
    nrow, ncol = len(rows), len(rows[0])
    tot = sum(col_w)
    widths = [w * c / tot for c in col_w]
    heights = [head_h] * header_rows + [row_h] * (nrow - header_rows)
    gf = slide.shapes.add_table(nrow, ncol, Inches(x), Inches(y), Inches(w),
                                Inches(sum(heights)))
    tbl = gf.table
    tbl.first_row = False; tbl.horz_banding = False
    for i, cw in enumerate(widths):
        tbl.columns[i].width = Inches(cw)
    for i, hh in enumerate(heights):
        tbl.rows[i].height = Inches(hh)

    for ri, row in enumerate(rows):
        is_head = ri < header_rows
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.margin_left = Inches(0.09); cell.margin_right = Inches(0.07)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if is_head else (
                WHITE if (ri - header_rows) % 2 == 0 else zebra)
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]; p.line_spacing = 1.12
            if align and ci < len(align):
                p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER,
                               "r": PP_ALIGN.RIGHT}[align[ci]]
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(head_size if is_head else size)
            r.font.bold = bool(is_head or (first_bold and ci == 0))
            r.font.color.rgb = head_color if is_head else INK
            r.font.name = LATIN
            _set_ea(r)
            _cell_border(cell, ("L", "R", "T", "B"),
                         color=head_fill if is_head else LINE, w=Pt(0.75))
    return tbl


def chip(slide, x, y, w, h, text, fill=ORANGE_LT, color=ORANGE_DK, size=9.5, bold=True):
    """橙色圆角小标签。"""
    rect(slide, x, y, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.35)
    tf = textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, True, text, size=size, bold=bold, color=color,
         align=PP_ALIGN.CENTER, line=1.0)


def note(slide, x, y, w, text, size=9.5, color=GRAY, prefix="注：", bar=LINE_DK):
    """左侧竖线的灰色小注。"""
    rect(slide, x, y, 0.035, 0.30, fill=bar)
    tf = textbox(slide, x + 0.14, y - 0.02, w - 0.14, 0.34)
    p = tf.paragraphs[0]; p.line_spacing = 1.25
    r0 = p.add_run(); r0.text = prefix
    r0.font.size = Pt(size); r0.font.bold = True; r0.font.color.rgb = ORANGE
    r0.font.name = LATIN; _set_ea(r0)
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.color.rgb = color
    r.font.name = LATIN; _set_ea(r)
    return tf


def callout(slide, x, y, w, h, title, body, fill=BG_SOFT, border=LINE,
            bar=ORANGE, title_color=INK, body_color=GRAY, size=9.5):
    """带左侧色条的小结／提示框（「与本项目的一致性」「清单口径」等）。"""
    rect(slide, x, y, w, h, fill=fill, line=border, lw=0.75)
    rect(slide, x, y, 0.04, h, fill=bar)
    tf = textbox(slide, x + 0.24, y + 0.14, w - 0.48, 0.28)
    para(tf, True, title, size=10.5, bold=True, color=title_color, line=1.0)
    if body:
        tf2 = textbox(slide, x + 0.24, y + 0.48, w - 0.48, h - 0.60)
        para(tf2, True, body, size=size, color=body_color, line=1.36)
    return tf


def kicker_row(slide, x, y, w, text, size=10.5, color=ORANGE, bold=True):
    """橙色小栏目名。"""
    tf = textbox(slide, x, y, w, 0.24)
    para(tf, True, text, size=size, bold=bold, color=color, line=1.0)
    return tf
