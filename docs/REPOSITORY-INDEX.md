# 可复用 Skill 与模板：内容索引

盘点日期：2026-11-14。来源：默认分支 main，提交 `3f0698c157f779349f7aaf616cac161a38beed44`。

按屋面排布、建议书模板、音频处理分类。4 个 SKILL.md 是不同技能，均保留完整 scripts、references、assets 与 agents 相对结构。

## 分类入口

| 分类 | 入口与内容 |
| --- | --- |
| 三曲瓦排布 / sanqu-roof-layout | [三曲瓦排布 / sanqu-roof-layout](<../3 Cruved Tiles layout and Modeling/README.md>)：40 W/片；三曲瓦参数及额外发电量折减。保留安装 ZIP 与源码。 |
| Pro 平瓦排布 / pro-roof-layout | [Pro 平瓦排布 / pro-roof-layout](<../skill/pro-solar-tiles-layout-and-modeling/SKILL.md>)：70 W/片；88% 系统效率口径与三曲瓦不同，不合并参数。 |
| BIPV 建议书模板 | [BIPV 建议书模板](<../skill/almaden-bipv-proposal-template/SKILL.md>)：从项目 JSON 生成 PPTX；示例图片、视频和文档归属此技能。 |
| 音频处理 / qqmusic-decrypt | [音频处理 / qqmusic-decrypt](<../skill/qqmusic-decrypt/SKILL.md>)：macOS 音频转换技能；保留 GPL 许可及格式限制。 |

## 依赖与保留原则

三曲瓦目录名称虽有拼写问题，但既有 README 与下载地址引用它；本次通过分类索引统一入口，不改路径或技能调用名。未修改 SKILL.md 规则、产品参数、安装包或许可证，未重新执行 Blender 或安装包一致性验证。

本次不改默认分支，不自动合并、不删除仓库、不将活跃源码标记为停用。目录树未被 GitHub 截断；下列清单覆盖盘点提交的 98 个文件，其中 55 个文本文件已读取。其余文件仅依据路径、类型、大小和 Git blob 标识归类，未声称检查二进制内部内容。未发现 .github/workflows、action.yml/action.yaml 或插件清单文件。

## 逐文件清单

这是盘点提交的清单，不包括本次新增索引。归档后的链接指向新位置；原始路径、大小和 blob SHA 可在 [FILES.json](FILES.json) 查询。

| 分类 | 文件 | 字节 | 内容读取 |
| --- | --- | ---: | --- |
| 版本管理与配置 | [3 Cruved Tiles layout and Modeling/.gitignore](<../3 Cruved Tiles layout and Modeling/.gitignore>) | 49 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/README.md](<../3 Cruved Tiles layout and Modeling/README.md>) | 3382 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout.zip](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout.zip>) | 10814048 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/SKILL.md](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/SKILL.md>) | 5395 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/agents/openai.yaml](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/agents/openai.yaml>) | 346 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/241018配瓦(高分子复合材料)报价.pdf](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/241018配瓦(高分子复合材料)报价.pdf>) | 280861 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/Almaden 曲面光伏瓦施工指导书-中文版V2.pdf](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/Almaden 曲面光伏瓦施工指导书-中文版V2.pdf>) | 1694454 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/三曲汉瓦安装说明书(美居屋建材）.pdf](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/三曲汉瓦安装说明书(美居屋建材）.pdf>) | 6183814 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/曲面瓦规格书241206.pdf](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/documents/曲面瓦规格书241206.pdf>) | 1449095 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/logo.png](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/logo.png>) | 1050336 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/ridge-geometry.json](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/ridge-geometry.json>) | 1446789 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/surface-materials.json](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/surface-materials.json>) | 956 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/tile-geometry.json](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/tile-geometry.json>) | 3296864 | 仅元数据 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/windclip.json](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/assets/windclip.json>) | 38336 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/drawing-input.md](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/drawing-input.md>) | 6153 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/energy-method.md](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/energy-method.md>) | 8444 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/example-project.json](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/example-project.json>) | 3705 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/input-schema.md](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/input-schema.md>) | 3968 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/product-rules.md](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/references/product-rules.md>) | 3980 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/deliverables.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/deliverables.py>) | 18805 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/estimate_energy.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/estimate_energy.py>) | 17288 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/inspect_drawing.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/inspect_drawing.py>) | 14626 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/layout_engine.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/layout_engine.py>) | 12261 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/render_blender.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/render_blender.py>) | 27018 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/requirements.txt](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/requirements.txt>) | 42 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/run_project.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/run_project.py>) | 2828 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/setup.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/setup.py>) | 500 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/test_energy.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/test_energy.py>) | 11111 | 已读文本 |
| 屋面排布 / 三曲瓦 | [3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/test_layout.py](<../3 Cruved Tiles layout and Modeling/sanqu-roof-layout/scripts/test_layout.py>) | 5312 | 已读文本 |
| 仓库说明 | [README.md](<../README.md>) | 1141 | 已读文本 |
| 版本管理与配置 | [skill/.gitkeep](<../skill/.gitkeep>) | 1 | 仅元数据 |
| 版本管理与配置 | [skill/almaden-bipv-proposal-template/.gitignore](<../skill/almaden-bipv-proposal-template/.gitignore>) | 33 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/SKILL.md](<../skill/almaden-bipv-proposal-template/SKILL.md>) | 7771 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/agents/openai.yaml](<../skill/almaden-bipv-proposal-template/agents/openai.yaml>) | 422 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/assets/logo_dark.png](<../skill/almaden-bipv-proposal-template/assets/logo_dark.png>) | 225266 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/assets/logo_light.png](<../skill/almaden-bipv-proposal-template/assets/logo_light.png>) | 223049 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/chart_donut.jpg](<../skill/almaden-bipv-proposal-template/examples/images/chart_donut.jpg>) | 23757 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/chart_monthly.jpg](<../skill/almaden-bipv-proposal-template/examples/images/chart_monthly.jpg>) | 54716 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/closing_bg.jpg](<../skill/almaden-bipv-proposal-template/examples/images/closing_bg.jpg>) | 43893 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/cover_bg.jpg](<../skill/almaden-bipv-proposal-template/examples/images/cover_bg.jpg>) | 42227 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/inst_batten.jpg](<../skill/almaden-bipv-proposal-template/examples/images/inst_batten.jpg>) | 267757 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/inst_counterbatten.jpg](<../skill/almaden-bipv-proposal-template/examples/images/inst_counterbatten.jpg>) | 167763 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/inst_flashing.jpg](<../skill/almaden-bipv-proposal-template/examples/images/inst_flashing.jpg>) | 97407 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/inst_gutter.jpg](<../skill/almaden-bipv-proposal-template/examples/images/inst_gutter.jpg>) | 54336 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/inst_pvtile.jpg](<../skill/almaden-bipv-proposal-template/examples/images/inst_pvtile.jpg>) | 246738 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/inst_ridge.jpg](<../skill/almaden-bipv-proposal-template/examples/images/inst_ridge.jpg>) | 116221 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/jclip_detail.jpg](<../skill/almaden-bipv-proposal-template/examples/images/jclip_detail.jpg>) | 105347 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/jclip_lower.jpg](<../skill/almaden-bipv-proposal-template/examples/images/jclip_lower.jpg>) | 52703 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/plan_total.jpg](<../skill/almaden-bipv-proposal-template/examples/images/plan_total.jpg>) | 218635 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/slope_A.jpg](<../skill/almaden-bipv-proposal-template/examples/images/slope_A.jpg>) | 135904 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/slope_B.jpg](<../skill/almaden-bipv-proposal-template/examples/images/slope_B.jpg>) | 137355 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/spec_p1.jpg](<../skill/almaden-bipv-proposal-template/examples/images/spec_p1.jpg>) | 302334 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/video_poster.jpg](<../skill/almaden-bipv-proposal-template/examples/images/video_poster.jpg>) | 51308 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/屋面俯视.jpg](<../skill/almaden-bipv-proposal-template/examples/images/屋面俯视.jpg>) | 62433 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/左侧立面_女儿墙随坡.jpg](<../skill/almaden-bipv-proposal-template/examples/images/左侧立面_女儿墙随坡.jpg>) | 25144 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/整体轴测_图上侧.jpg](<../skill/almaden-bipv-proposal-template/examples/images/整体轴测_图上侧.jpg>) | 60780 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/整体轴测_图下侧.jpg](<../skill/almaden-bipv-proposal-template/examples/images/整体轴测_图下侧.jpg>) | 72012 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/标高与范围核对.jpg](<../skill/almaden-bipv-proposal-template/examples/images/标高与范围核对.jpg>) | 156373 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/images/瓦面与脊瓦近景.jpg](<../skill/almaden-bipv-proposal-template/examples/images/瓦面与脊瓦近景.jpg>) | 120745 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/media/demo.mp4](<../skill/almaden-bipv-proposal-template/examples/media/demo.mp4>) | 103104 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/东江阴变电站.json](<../skill/almaden-bipv-proposal-template/examples/东江阴变电站.json>) | 50626 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/examples/示例输出_东江阴变电站.pptx](<../skill/almaden-bipv-proposal-template/examples/示例输出_东江阴变电站.pptx>) | 2656366 | 仅元数据 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/references/design-system.md](<../skill/almaden-bipv-proposal-template/references/design-system.md>) | 5152 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/references/project-schema.md](<../skill/almaden-bipv-proposal-template/references/project-schema.md>) | 5670 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/references/slide-archetypes.md](<../skill/almaden-bipv-proposal-template/references/slide-archetypes.md>) | 10486 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/scripts/build_proposal.py](<../skill/almaden-bipv-proposal-template/scripts/build_proposal.py>) | 32623 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/scripts/check_deck.py](<../skill/almaden-bipv-proposal-template/scripts/check_deck.py>) | 12149 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/scripts/deck_kit.py](<../skill/almaden-bipv-proposal-template/scripts/deck_kit.py>) | 19526 | 已读文本 |
| 建议书模板 | [skill/almaden-bipv-proposal-template/scripts/requirements.txt](<../skill/almaden-bipv-proposal-template/scripts/requirements.txt>) | 227 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/SKILL.md](<../skill/pro-solar-tiles-layout-and-modeling/SKILL.md>) | 5711 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/agents/openai.yaml](<../skill/pro-solar-tiles-layout-and-modeling/agents/openai.yaml>) | 381 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/assets/approved-wind-clip.blend](<../skill/pro-solar-tiles-layout-and-modeling/assets/approved-wind-clip.blend>) | 126209 | 仅元数据 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/assets/documents/Pro70W规格书.pdf](<../skill/pro-solar-tiles-layout-and-modeling/assets/documents/Pro70W规格书.pdf>) | 1790612 | 仅元数据 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/assets/documents/Pro屋面安装说明书.pdf](<../skill/pro-solar-tiles-layout-and-modeling/assets/documents/Pro屋面安装说明书.pdf>) | 2638122 | 仅元数据 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/assets/logo.png](<../skill/pro-solar-tiles-layout-and-modeling/assets/logo.png>) | 1050336 | 仅元数据 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/assets/pro-geometry-source.json](<../skill/pro-solar-tiles-layout-and-modeling/assets/pro-geometry-source.json>) | 1229 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/references/drawing-input.md](<../skill/pro-solar-tiles-layout-and-modeling/references/drawing-input.md>) | 5083 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/references/energy-method.md](<../skill/pro-solar-tiles-layout-and-modeling/references/energy-method.md>) | 8636 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/references/example-project.json](<../skill/pro-solar-tiles-layout-and-modeling/references/example-project.json>) | 1234 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/references/input-schema.md](<../skill/pro-solar-tiles-layout-and-modeling/references/input-schema.md>) | 3874 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/references/product-rules.md](<../skill/pro-solar-tiles-layout-and-modeling/references/product-rules.md>) | 2863 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/deliverables.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/deliverables.py>) | 22672 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/estimate_energy.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/estimate_energy.py>) | 17929 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/inspect_drawing.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/inspect_drawing.py>) | 14624 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/layout_engine.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/layout_engine.py>) | 13404 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/render_blender.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/render_blender.py>) | 29494 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/requirements.txt](<../skill/pro-solar-tiles-layout-and-modeling/scripts/requirements.txt>) | 42 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/run_project.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/run_project.py>) | 3627 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/setup.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/setup.py>) | 500 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/test_energy.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/test_energy.py>) | 12103 | 已读文本 |
| 屋面排布 / Pro 平瓦 | [skill/pro-solar-tiles-layout-and-modeling/scripts/test_layout.py](<../skill/pro-solar-tiles-layout-and-modeling/scripts/test_layout.py>) | 4813 | 已读文本 |
| 许可 | [skill/qqmusic-decrypt/LICENSE](<../skill/qqmusic-decrypt/LICENSE>) | 34233 | 仅元数据 |
| 音频处理 | [skill/qqmusic-decrypt/SKILL.md](<../skill/qqmusic-decrypt/SKILL.md>) | 3554 | 已读文本 |
| 音频处理 | [skill/qqmusic-decrypt/agents/openai.yaml](<../skill/qqmusic-decrypt/agents/openai.yaml>) | 296 | 已读文本 |
| 音频处理 | [skill/qqmusic-decrypt/references/implementation.md](<../skill/qqmusic-decrypt/references/implementation.md>) | 2518 | 已读文本 |
| 音频处理 | [skill/qqmusic-decrypt/scripts/qmc_crypto.py](<../skill/qqmusic-decrypt/scripts/qmc_crypto.py>) | 3343 | 已读文本 |
| 音频处理 | [skill/qqmusic-decrypt/scripts/qqmusic_decrypt.py](<../skill/qqmusic-decrypt/scripts/qqmusic_decrypt.py>) | 10552 | 已读文本 |
| 音频处理 | [skill/qqmusic-decrypt/scripts/test_qqmusic_decrypt.py](<../skill/qqmusic-decrypt/scripts/test_qqmusic_decrypt.py>) | 7588 | 已读文本 |
