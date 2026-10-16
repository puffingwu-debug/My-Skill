# 版式库（archetypes）

`build_proposal.py` 的 `ARCHETYPES` 注册了 18 种内容版式。JSON 里每页写
`"type": "<名称>"`。封面、目录、章节页、封底由生成器自动处理，不写在 `slides` 里。

**通用字段**（所有版式）：`title`（必填）、`sub`（副标题，可选）、
`table` / `points` / `images` / `stats` 等见各节。

**表格对象**统一长这样（各版式里叫 `table` / `table_left` / `table_right` / `table_full`）：
```json
{
  "head": ["列1", "列2"],
  "rows": [["a", "b"], ["c", "d"]],
  "weights": [1.2, 3.0],
  "row_h": 0.365, "head_h": 0.36,
  "size": 9.5, "head_size": 9.5,
  "align": ["l", "r"],
  "first_bold": true
}
```
`weights` 为相对列宽（按比例分配到给定宽度）。`head` 省略则不画表头，
`first_bold` 让首列加粗。**行高要与文字量匹配**，否则表格会被自动撑高。

---

## 1. `facts_hero` — 项目概况
左事实表 + 右主视觉图 + 底部 3 个 KPI 卡。
```json
{ "type":"facts_hero",
  "table": {...}, "table_w": 6.35,
  "hero": { "image":"images/hero.jpg", "caption":"..." }, "hero_h": 3.42,
  "stats": [ {"value":"42.64","unit":"kWp","label":"装机容量"}, ... ] }
```
表格行数 ≤ 8；`hero_h` 建议 3.42（下面要放 KPI 卡）。

## 2. `table_points_image` — 条件 + 要点 + 校验图
左表 + 左下要点 + 右图。用于「屋面几何条件」这类"数值 + 校核图"组合。
```json
{ "type":"table_points_image",
  "table": {...}, "table_w": 6.40,
  "points": ["...","..."], "points_y": 4.08, "points_size": 10.5,
  "image": {"image":"...","caption":"..."}, "image_h": 4.72 }
```
`points_y` 省略时按表高自动推算。

## 3. `image_spec_table` — 产品规格
左产品图 + 右规格表 + 表下注。规格表行数多（10–12 行）时用这个。
```json
{ "type":"image_spec_table",
  "image_w": 4.05, "image_h": 4.72,
  "image": {"image":"...","caption":"..."},
  "table": {...}, "note": "口径说明…", "note_y": 4.30 }
```

## 4. `dual_table_panel` — 双表 + 深色说明面板
两张并排表 + 右侧深色面板 + 底部注。适合"电气特性 / 温度特性"这类成对参数。
```json
{ "type":"dual_table_panel",
  "table_left": {...}, "table_right": {...},
  "gap": 0.40, "panel_w": 2.90, "panel_h": 4.34, "panel_size": 10,
  "panel": { "title":"方案取值口径", "items":["...","..."] },
  "note": "..." }
```

## 5. `wide_table_callouts` — 通栏表 + 底部提示框
表列多（5–6 列）时用。底部 2 个提示框放公式、口径、待定项。
```json
{ "type":"wide_table_callouts",
  "table": {...}, "callout_h": 0.86, "callout_size": 9.5,
  "callouts": [ {"title":"公式　","value":"max(1, ceil(...))","body":"..."}, {...} ] }
```

## 6. `image_points_chips` — 节点图 + 要点 + 高亮 + 标签
左图（可为上下两张叠放）+ 右要点 + 橙色高亮框 + 4 个橙色标签。
```json
{ "type":"image_points_chips",
  "image_w": 5.30, "image_h": 4.72,
  "image": {"image":"images/a.jpg","caption":"..."},
  "image2": "images/b.jpg", "image_ratio": 0.65,
  "points": ["..."], "points_size": 10.5, "points_gap": 9,
  "highlight_y": 2.72,
  "highlight": {"title":"自重参考","value":"5,543.2","unit":"kg","note":"= 1,066 × 5.2 kg"},
  "chips_y": 4.00, "chip_size": 9,
  "chips": ["完整瓦不裁切","2 扣／片","沉头螺钉固定","预留定位≠已锁止"] }
```
`image2` 存在时，卡内上下叠放（上为主图，`image_ratio` 为主图高度占比，默认 0.65）——
比把两页 PDF 塞进一张卡清楚。

## 7. `image_stats_table` — 大图 + 统计条 + 表
左大图 + 右侧 2 条统计 + 表。用于「总平面排布 + 分坡片数 + 汇总」。
```json
{ "type":"image_stats_table",
  "image_w": 6.10, "image_h": 4.72, "image": {"image":"..."},
  "stats": [ {"value":"425","unit":"片 · 17.00 kWp","label":"图下坡面 A"}, {...} ],
  "table_y": 2.28, "table": {...} }
```

## 8. `image_param_table` — 展开图 + 参数表 + 要点
左大图（建议 7.70 宽）+ 右参数表 + 表下要点。用于逐坡／逐面展开页。
```json
{ "type":"image_param_table",
  "image_w": 7.70, "image_h": 4.72, "image": {"image":"..."},
  "table": {...}, "points": ["..."], "points_size": 9.5 }
```

## 9. `wide_table_stats` — 宽表 + 侧栏统计
通栏宽表 + 右侧 1–2 个 KPI 卡 + 口径面板。材料清单、成果汇总用。
```json
{ "type":"wide_table_stats",
  "side_w": 3.05, "table": {...},
  "stats": [ {"value":"42.64","unit":"kWp","label":"直流装机容量"}, {...} ],
  "panel": {"title":"清单口径","items":["..."]}, "panel_h": 1.80, "panel_size": 9 }
```

## 10. `steps_panel` — 工序／步骤卡
N 个编号步骤卡（横排）+ 可选底部双栏说明 + 可选表下挂表格。
```json
{ "type":"steps_panel",
  "gap": 0.165, "card_h": 2.62, "accent_upto": 4, "step_size": 8.5,
  "arrows": true,
  "steps": [ {"num":"01","title":"顺水条","desc":"第一行\n第二行"}, ... ],
  "panels": [ {"title":"安装前准备","items":["..."]}, {"title":"电气要求","items":["..."]} ],
  "panel_h": 1.64, "panel_size": 9.5,
  "table_full": {...}, "note": "..." }
```
- 6 步时 `gap` 取 0.165、`card_h` 2.62；5 步时 `gap` 0.16、`card_h` 2.30。
- `desc` 用 `\n` 分行，每行 ≤ 16 个中文字符（窄卡）。
- `accent_upto`：前 N 张卡的顶部色条用橙色，其余用墨黑。
- `arrows: false` 关闭卡片之间的 `›` 连接符（"方法 5 步"这类并列关系建议关闭）。
- `table_full` + `note` 会在步骤卡下方挂一张通栏表（用于"方法 + 汇总表"）。

## 11. `images_points_note` — 双图 + 要点 + 说明框 + 注
左两张图 + 右栏要点 + 说明框 + 底部注。工序详解用。
```json
{ "type":"images_points_note",
  "image1_w": 4.55, "image2_w": 3.05, "image_gap": 0.22, "image_h": 4.72,
  "images": [ {"image":"...","caption":"..."}, {"image":"...","caption":"..."} ],
  "points": ["..."], "points_size": 9.5, "points_gap": 6,
  "box_y": 2.86, "box_h": 1.10, "box_size": 9.5,
  "box": { "title":"与本项目排布的一致性", "body":"…" },
  "note": "...", "note_size": 9 }
```
`box` 也可用 `items: [...]` 代替 `body`（逐条圆点），此时可用 `body_color` 指定圆点文字颜色。
颜色字段可用名称覆盖：`fill` / `border` / `bar` / `title_color` / `body_color`
（如 `"fill":"BG_SOFT"`、`"bar":"ORANGE"`、`"title_color":"INK"`）。

## 12. `images_steps` — 双图 + 堆叠步骤块
左两图 + 右栏若干"标题 + 圆点列表"块。
```json
{ "type":"images_steps",
  "image1_w": 5.55, "image2_w": 3.10, "image_gap": 0.22, "image_h": 4.72,
  "images": [ {...}, {...} ],
  "blocks": [ {"title":"沟瓦","items":["..."]}, ... ] }
```
每块高度 ≈ `0.52 + 条目数 × 0.30`，3 块以内为宜。

## 13. `three_columns_callout` — 三栏卡片 + 注 + 提示条
用于"施工要点 / 安全注意事项"这类并列条目。三栏色条依次为
橙 / 墨黑 / 深橙 / 灰。
```json
{ "type":"three_columns_callout",
  "gap": 0.30, "card_h": 3.42, "item_size": 10, "item_gap": 10,
  "columns": [ {"title":"搬运与存放","items":["..."]}, {...}, {...} ],
  "note": "...", "note_size": 9,
  "callout": {"title":"特别注意 · 屋面清理","body":"…"}, "callout_h": 0.94 }
```

## 14. `image_grid` — 图片网格
成果展示用。默认 3 列，自动按可用高度均分。
```json
{ "type":"image_grid", "cols": 3, "gap": 0.22,
  "images": [ {"image":"...","caption":"..."}, ... ] }
```
6 张（3×2）最稳；单张长宽比 1.1–1.7 最合适。

## 15. `table_stat_panel` — 复验表 + 统计 + 保全说明
用于"独立复验 / 检测结果"。表在前、侧栏统计卡与说明在后。
```json
{ "type":"table_stat_panel",
  "side_w": 3.25, "stat_h": 1.26,
  "table": {...},
  "stats": [ {"value":"27","unit":"项","label":"能源核验项独立通过"} ],
  "panel": {"title":"原建筑与模型保全","items":["..."]}, "panel_h": 3.10, "panel_size": 9 }
```

## 16. `cards_grid` — 两列卡片网格
用于"设计条件 / 待确认事项 / 风险提示"。每条 1–3 行文字。
```json
{ "type":"cards_grid",
  "cols": 2, "card_h": 1.32, "row_gap": 0.22, "body_size": 9.5,
  "cards": [ {"title":"标高解释","color":"ORANGE","body":"…"}, ... ] }
```
`color` 用颜色名；橙色留给"需业主确认"的项，灰色留给"范围外/未深化"的项。

## 17. `charts_stats` — 图表 + KPI 行
左环图（占比）+ 右柱状图（趋势）+ 底部 4 个 KPI 卡。发电量结果页用。
```json
{ "type":"charts_stats",
  "donut": {"image":"images/chart_donut.jpg"},
  "bar": {"image":"images/chart_monthly.jpg","caption":"逐月发电量（kWh）"},
  "donut_w": 3.30, "chart_h": 3.30, "gap": 0.28,
  "stats": [ {"value":"39,883.15","unit":"kWh","label":"年发电量合计"}, ... ] }
```
图表本身用 Pillow 预先画好（不要用 PPT 原生图表，样式无法与本模板统一）；
配色用 `#1A1A1A` 与 `#F45918`，中文字体用系统 CJK 字体。

## 18. `video` — 嵌入视频
视频以 `p14:media` **内嵌**进 PPTX，换机可播。必须配静态封面帧。
```json
{ "type":"video",
  "video": "media/demo.mp4", "poster": "images/video_poster.jpg",
  "video_w": 8.10,
  "points_title": "视频内容", "points_size": 10,
  "points": ["...","..."],
  "box_y": 2.06, "box_h": 1.28,
  "box": {"title":"播放提示","body":"放映模式下单击画面即可播放…"},
  "note": "..." }
```
`video_h` 省略时按 16:9 自动计算。封面帧建议用 ffmpeg 从视频抽取
（`-ss <秒> -frames:v 1`），确保画面清晰、无转场残影。

---

## 组合建议

参考样张（30 页）的典型配比：

| 章节 | 页数 | 版式组合 |
|---|---|---|
| 01 项目概况 | 2 | `facts_hero` → `table_points_image` |
| 02 产品介绍 | 4 | `image_spec_table` → `dual_table_panel` → `wide_table_callouts` → `image_points_chips` |
| 03 屋面排布 | 4 | `image_stats_table` → `image_param_table` ×2 → `wide_table_stats` |
| 04 发电量 | 2 | `steps_panel`(+表格) → `charts_stats` |
| 05 安装介绍 | 5 | `steps_panel` → `images_points_note` → `images_steps` → `images_points_note` → `three_columns_callout` |
| 06 成果与核验 | 4 | `image_grid` → `table_stat_panel` → `cards_grid` → `video` |

加封面 + 目录 + 6 个章节页 + 封底 = 30 页。
项目规模小可只保留 01/02/03/06；纯汇报场合可省掉 05 安装介绍。
