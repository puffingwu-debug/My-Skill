# DWG / DXF 图纸输入与识别边界

使用 `scripts/inspect_drawing.py` 提取候选屋面轮廓、图层、文字与尺寸，辅助确认后再把已确认的坡面边界、单位、洞口和尺寸送入排布。这个脚本不负责无监督识别任意 DWG，也不把所有闭合多段线都当作屋面。

## 本机运行

Python 运行环境：`~/.codex/skills/pro-roof-layout/.venv/bin/python`；依赖 `ezdxf`。SVG 预览由脚本直接生成，无需 Pillow、浏览器、matplotlib 或在线转换服务。

```sh
~/.codex/skills/pro-roof-layout/.venv/bin/python \
  ~/.codex/skills/pro-roof-layout/scripts/inspect_drawing.py \
  '/absolute/path/drawing.dwg' --out '/absolute/path/inspection' --timeout 60
```

DXF 使用相同命令，输入后缀改为 `.dxf` 即直接只读解析，不启动 AutoCAD。

- `--layout 'Model'`：默认读取模型空间，可改为 `summary.json` 中列出的布局名。纸空间的 VIEWPORT 视口不会自动重放模型空间；若纸空间看不到实体，应检查 Model 并根据图框坐标裁切。
- `--layers '图层A,图层B'`：按精确图层名筛选。
- `--bbox XMIN YMIN XMAX YMAX`：只裁切 SVG 视图，JSON 仍保留当前布局/图层筛选下的全部实体。若图中有远离主体的原点符号导致全图被缩小，可依据坐标和图框选择范围后重跑；不要静默删除远端实体。
- `--include-hidden`：SVG 包含关闭/冻结图层。默认预览隐藏这些图层，但 JSON 仍保留。
- `--timeout 60`：仅约束 AutoCAD 转换子进程，最大 120 秒；超时会终止其进程组并保留日志，禁止无限挂起。
- `--core-console '/absolute/path/AcCoreConsole'`：覆盖本机默认路径。

## 输出文件

- `summary.json`：原文件路径、转换方法、原文件 SHA-256 前后校验、布局名、单位标记、实体计数、预览范围、不能预览的实体类型及错误。
- `layers.json`：图层名、颜色、线型、关闭/冻结/锁定状态。
- `texts.json`：原始格式文字 `raw_text`、便于检索的 `plain_text`、插入点、字高和旋转；记录来源 handle 和嵌套块路径。
- `closed-polygons.json`：闭合候选轮廓、坐标与面积。LWPOLYLINE 另保留 `x,y,start_width,end_width,bulge` 原始顶点；圆弧预览折线采用 0.2 图纸单位容差，不据此宣称精密测量。
- `dimensions.json`：尺寸显示覆盖文字、DXF 保存的测量值、ezdxf 变换后几何测量值和原始 DXF 属性。三个数值可能不同，必须并列核查。
- `overview.svg`：便于识别的线图；闭合轮廓蓝色、其余线灰色。文字字体、对齐及曲线仅作近似预览，不替代正式 CAD 出图。
- DWG 输入另生成 `cad-export-*/drawing.dxf`、`export.scr` 与 `core-console.log`，保留完整中间格式和证据。

## 可靠只读导出

本机 AutoCAD 2024 已验证路径：

`/Applications/Autodesk/AutoCAD 2024/AutoCAD 2024.app/Contents/Helpers/AcCoreConsole.app/Contents/MacOS/AcCoreConsole`

必须用 `DXFOUT`，**此版本的 `-DXFOUT` 返回未知命令**。脚本使用：

```lisp
(setvar "FILEDIA" 0)
(setvar "CMDECHO" 1)
(command "_.DXFOUT" "/absolute/fresh/output.dxf" "16")
(princ "\nSANQU_EXPORT_DONE\n")
(command "_.QUIT")
```

控制台参数为 `/i 原DWG /s export.scr /readonly`，工作目录设为独立输出目录。每次输出使用新目录/新文件名，避免覆盖询问。原 DWG 不执行 SAVE、QSAVE 或 SAVEAS，并比较转换前后 SHA-256。控制台会产生字体替代和自定义对象警告；日志是核查依据，不能以返回码 0 等同于所有图元已完整识别。

## 识别与归一化要求

1. 先确认图纸单位。`INSUNITS=0` 表示未指定，不代表毫米；脚本保持图纸原坐标，不自动缩放。即使图上文字出现“mm”，也必须先区分模型空间、块缩放和标注样式比例。
2. 查看图名、坡向、标高、图框和尺寸链，识别具体坡面。闭合候选还包括瓦片、标题栏、详图边框、设备符号等，不能自动全部作为屋面。
3. 嵌套 INSERT 被递归展开到当前布局坐标；块的缩放会影响几何距离，但标注原文字可能仍为真实构件尺寸。用图纸标注、块定义和变换共同确定实际尺寸，不只读两个点之差。
4. 确定已选坡面边界后，记录世界坐标原点、横屋面方向、檐至脊方向、长度单位换算和是否使用斜长。保留原坐标及来源 handle，再另生成排布用局部米制坐标；不要改原图。
5. 需要人工确认/补资料的情况：缺少明确尺寸或单位、多个屋面混排、纸空间依赖 VIEWPORT、外部参照未解析、代理对象或 OLE 包含关键轮廓、曲面或复杂三维屋顶、平面投影与斜长混淆。
6. `ACAD_PROXY_ENTITY`、OLE、HATCH、3D 与其他不支持实体会保留类型计数并列入预览省略，不猜造其几何。ezdxf 展开块可能输出 `DIMASSOC` 复制忽略日志；本脚本不写回 DXF/DWG，因此不把虚拟展开结果当作可直接交付的CAD施工图。

