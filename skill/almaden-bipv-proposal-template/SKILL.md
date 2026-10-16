---
name: 亚玛顿BIPV项目建议书模板
description: 按亚玛顿（Almaden）BIPV 标准视觉规范生成中文项目建议书／方案说明书 PPTX——橙色品牌体系、深色章节页、16:9 栅格、表格与图片卡版式库、嵌入产品视频。当用户要为新 BIPV／光伏瓦／光伏屋面项目出建议书、方案说明书、投标方案、汇报 PPT，或要求沿用「东江阴那套 PPT 的风格」时使用。
---

# 亚玛顿 BIPV 项目建议书模板

把一份项目 JSON 渲染成品牌统一的中文 BIPV 项目建议书 `.pptx`。
版式、配色、字号、栅格全部固化在本技能的 `scripts/` 里，**不要临时改样式**——
新项目只提供数据，不重画版式。

产出：一个可编辑 PPTX（真实文本与表格，非图片拼贴），页数由 JSON 内容决定；
可选附带 PDF 预览。

## 快速开始

```sh
# 1) 取运行环境（含 python-pptx / Pillow）
#    用 load_workspace_dependencies 返回的 python 路径，不要另装包

# 2) 复制示例 JSON 改数据（图片路径相对于该 JSON 所在目录）
cp <skill>/examples/东江阴变电站.json ./项目.json

# 3) 生成
<python> <skill>/scripts/build_proposal.py --project ./项目.json --output ./成果/建议书.pptx

# 4) 体检（必须做，见下文「交付前必查」）
<python> <skill>/scripts/check_deck.py ./成果/建议书.pptx \
    --expect-slides <页数> --contains "<关键数字>" --json ./成果/体检.json
```

`<skill>` 为本 SKILL.md 所在目录。

## 工作流程

1. **先定数据，再排版。** 从项目资料里把这几组数字确认清楚，缺的宁可留空也不要猜：
   装机容量（kWp）、发电瓦片数、年发电量（kWh）、分坡参数、材料清单、站址与朝向。
   容量口径必须是 **完整发电瓦片数 × 单片功率 ÷ 1000**，不含配瓦与备料。

2. **整理图片。** 与 `sanqu-roof-layout` 等排布技能衔接时，把成果图（总平面、分坡展开、
   轴测、俯视、近景、立面）转成 JPG/PNG 放进项目目录；PDF 页面需先渲染成图片。
   SVG 建议用无头 Chrome 渲染成 ≥2 倍图，不要截屏。

3. **写项目 JSON。** 结构见 [references/project-schema.md](references/project-schema.md)，
   字段含义与默认值都在那里。最省事的做法是复制
   [examples/东江阴变电站.json](examples/东江阴变电站.json) 后逐节替换。

4. **选版式。** 每种版式（archetype）对应一类内容，取舍看
   [references/slide-archetypes.md](references/slide-archetypes.md)。
   章节页由 `sections[].divider` 自动插入，页码自动编号。

5. **生成并体检。** 必须跑 `check_deck.py`，直到「结论：通过」。

6. **交付。** 用 `present` 交付 PPTX；若同时给了 PDF 预览，注明 PDF 是旁路渲染、
   以 PPTX 为准。

## 交付前必查

`check_deck.py` 会检查结构（ZIP/XML 完整性、媒体与关系、视频是否真内嵌）、
版式（用真实字体度量估算文字高度，找溢出页面底部、压到下方表格卡片、超出卡片底边）、
内容（必需文案是否命中、是否残留 `TBD`/`{{ }}` 等占位符）。**这三类问题它都能在
不渲染的情况下发现**，所以即使没有渲染器也要跑。

指标要求：
- 版式问题 = 0、占位符 = 0、外链 = 0（视频必须内嵌，`TargetMode="External"` 为 0）
- `--contains` 至少覆盖：装机容量、发电瓦片数、年发电量 三个关键数字

若需要人眼复核或交付 PDF，用部署里提供的 LibreOffice Kit 渲染
（`node <cli> render --input x.pptx --output-dir preview --dpi 144`；
`convert --input x.pptx --output x.pdf`）。渲染只是旁证，不能替代上面的检查；
渲染器不可用时按「结构＋版式＋内容」三项检查收口，并在交付说明里写明未做视觉复核。

## 品牌硬约束（改版式前必读）

- **画布** 固定 16:9 = 13.3333 × 7.5 in；左右边距 0.62 in，正文不越过 6.88 in。
- **主色** Almaden 橙 `#F45918`；墨黑 `#1A1A1A`；正文灰 `#5F6B76`。
  橙色只作强调（色条、编号、关键数字、圆点），**不要大面积铺橙**。
  深色底仅用于封面、章节页、封底。
- **字体** 中文 `微软雅黑`、西文 `Arial`。中文必须写进 `a:ea`，
  只设 `a:latin` 会导致中文回退成宋体（`deck_kit._set_ea` 已处理）。
- **Logo** 只从 `assets/` 取：浅色页用 `logo_dark.png`，深色页用 `logo_light.png`。
  保持原始比例与留白，不要拉伸、换色、加描边。
- **页眉** 橙色竖条 + 栏目名 + 主标题（+ 副标题或细分隔线）；**页脚** 细线 + 左标签 + 右页码。
  封面不编号，其余按出现顺序从 01 连续编号。
- 一页只讲一件事；标题尽量给出范围限定（例：「装机容量与材料清单(不含下面钢结构部分以及挂瓦条顺水条)」）。

规范细节与容差见 [references/design-system.md](references/design-system.md)。

## 内容纪律

BIPV 建议书最容易出的问题是把"没算的东西"写成"已经算好了"。沿用以下口径：

- 未确认型号／未深化节点：只列**延米**或标「待定」，不编造片数。
- 功能瓦数量按**原片保守占位**，不声称已优化余料复用，不出裁切加工表。
- 发电量必须标注：气象来源与年份、系统损耗、折减系数是否已应用及**应用次数**、
  未模拟的因素（时变遮挡、局部失配等）。同一折减系数不得重复相乘。
- 与图上方向有关的结论要写明「地理北向是否已核定」。
- 存在两种标高／范围解释时，把采用的那一种写成明确假设，并把另一种列为待确认。

## 扩展

新增版式：在 `scripts/build_proposal.py` 里加一个 `a_xxx(prs, c, sp, kicker)` 函数，
注册进 `ARCHETYPES`，按 `page()` / `deck_kit` 的既有组件拼装，然后
①跑 `check_deck.py` 确认零版式问题；②在
[references/slide-archetypes.md](references/slide-archetypes.md) 补一节；
③用 `examples/东江阴变电站.json` 回归一遍，确认旧页面未受影响。

只调样式：改 `scripts/deck_kit.py` 顶部的调色板与栅格常量，不要在 `build_proposal.py`
里写死颜色或坐标。

## 文件

```
SKILL.md                      本文件
assets/logo_dark.png          浅色底 Logo（透明背景）
assets/logo_light.png         深色底 Logo（白字，透明背景）
scripts/deck_kit.py           视觉系统：调色板、栅格、页眉页脚、表格、卡片、图表框
scripts/build_proposal.py     生成器：JSON → PPTX，含版式库 ARCHETYPES
scripts/check_deck.py         体检：结构 + 版式 + 内容（不需渲染器）
references/design-system.md   配色、字号、间距、容差、常见错误
references/slide-archetypes.md 17 种版式的用途、必填字段与几何
references/project-schema.md  JSON 字段逐项说明
examples/东江阴变电站.json      完整可运行示例（30 页）
examples/images/              示例图片
examples/media/demo.mp4       示例短视频（演示视频版式用）
```

## 自检

改完本技能后跑一遍回归（应全部通过）：

```sh
<python> <skill>/scripts/build_proposal.py \
    --project <skill>/examples/东江阴变电站.json --output /tmp/regress.pptx
<python> <skill>/scripts/check_deck.py /tmp/regress.pptx --expect-slides 30 \
    --contains "42.64" --contains "39,883.15" --contains "BHAC40R-40"
```

期望：画布 16:9、30 页、版式问题 0、占位符 0、外链 0、视频内嵌于第 29 页。
`examples/示例输出_东江阴变电站.pptx` 是同一份 JSON 的生成结果，可用来对照版式。
